"""
AWS S3-based video service for video file management and optimization.

This service handles video file uploads, downloads, streaming, thumbnail generation,
and metadata management using AWS S3 for storage and RDS for metadata persistence.
"""

import os
import logging
import asyncio
import threading
import time
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.s3.transfer import TransferConfig
from PIL import Image
import cv2
from sqlalchemy import text

from ..models.video import (
    VideoMetadata, VideoStatus, VideoFormat, VideoResolution,
    ThumbnailMetadata, VideoQualityMetrics, VideoProcessingMetrics
)
from ..models.job import Job, JobStatus
from ..database.connection import RDSConnectionManager
from ..database.pydantic_models import FileMetadataDB
from src.config.aws_config import AWSConfig

logger = logging.getLogger(__name__)


class ProgressCallback:
    """Progress callback for video upload operations with job status updates."""
    
    def __init__(self, 
                 file_path: str, 
                 job_id: str, 
                 scene_number: int,
                 progress_callback: Optional[Callable[[float], None]] = None):
        self.file_path = file_path
        self.job_id = job_id
        self.scene_number = scene_number
        self.progress_callback = progress_callback
        self._size = float(os.path.getsize(file_path))
        self._seen_so_far = 0
        self._lock = threading.Lock()
        
        logger.info(f"Initialized progress tracking for {file_path} (size: {self._size} bytes)")
    
    def __call__(self, bytes_amount: int):
        """Called by boto3 during upload progress."""
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            
            # Call external progress callback if provided
            if self.progress_callback:
                try:
                    self.progress_callback(percentage)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
            
            # Log progress at intervals
            if int(percentage) % 10 == 0 and percentage > 0:
                logger.info(
                    f"Video upload progress - Job: {self.job_id}, "
                    f"Scene: {self.scene_number}, Progress: {percentage:.1f}%"
                )


class AWSVideoService:
    """
    AWS S3-based video service for video file management and optimization.
    
    Handles video uploads with progress tracking, streaming URL generation,
    thumbnail creation, and comprehensive metadata management.
    """
    
    def __init__(self, aws_config: AWSConfig, db_manager: RDSConnectionManager):
        self.config = aws_config
        self.db_manager = db_manager
        
        # Create AWS session for thread safety
        self.session = boto3.Session(
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        self.s3_client = self.session.client('s3')
        
        # Configure transfer settings optimized for video files
        self.video_transfer_config = TransferConfig(
            multipart_threshold=1024 * 50,  # 50MB threshold for multipart
            max_concurrency=8,              # 8 concurrent uploads
            multipart_chunksize=1024 * 50,  # 50MB chunks
            use_threads=True,
            max_bandwidth=None              # No bandwidth limit
        )
        
        # Configure transfer settings for thumbnails (smaller files)
        self.thumbnail_transfer_config = TransferConfig(
            multipart_threshold=1024 * 10,  # 10MB threshold
            max_concurrency=4,
            multipart_chunksize=1024 * 10,
            use_threads=True
        )
        
        logger.info(f"Initialized AWS Video Service for environment: {aws_config.environment}")
    
    async def store_rendered_video(self, 
                                  video_path: str, 
                                  job_id: str, 
                                  scene_number: int, 
                                  user_id: str,
                                  progress_callback: Optional[Callable[[float], None]] = None) -> Dict[str, Any]:
        """
        Store rendered video in S3 with comprehensive metadata and progress tracking.
        
        Args:
            video_path: Local path to the video file
            job_id: Associated job ID
            scene_number: Scene number for organization
            user_id: User ID from Clerk
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing video storage information
            
        Raises:
            FileNotFoundError: If video file doesn't exist
            RuntimeError: If upload fails
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            # Generate S3 key with organized structure
            bucket = self.config.buckets['videos']
            key = f"users/{user_id}/jobs/{job_id}/videos/scene_{scene_number:03d}/output.mp4"
            
            # Get video file information
            video_stats = os.stat(video_path)
            file_size = video_stats.st_size
            file_hash = await self._calculate_file_hash(video_path)
            
            # Extract video metadata using OpenCV
            video_metadata = await self._extract_video_metadata(video_path)
            
            # Prepare S3 metadata
            s3_metadata = {
                'user_id': user_id,
                'job_id': job_id,
                'scene_number': str(scene_number),
                'file_type': 'video',
                'content_type': 'video/mp4',
                'upload_timestamp': datetime.utcnow().isoformat(),
                'file_size': str(file_size),
                'file_hash': file_hash,
                'duration_seconds': str(video_metadata.get('duration_seconds', 0)),
                'width': str(video_metadata.get('width', 0)),
                'height': str(video_metadata.get('height', 0)),
                'frame_rate': str(video_metadata.get('frame_rate', 0))
            }
            
            extra_args = {
                'Metadata': s3_metadata,
                'ContentType': 'video/mp4',
                'StorageClass': 'STANDARD'  # Use standard storage for videos
            }
            
            # Create progress callback
            progress_tracker = ProgressCallback(
                video_path, job_id, scene_number, progress_callback
            )
            
            # Upload video with progress tracking
            logger.info(f"Starting video upload to S3: {bucket}/{key}")
            upload_start_time = datetime.utcnow()
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self._upload_video_with_retry,
                    video_path, bucket, key, extra_args, progress_tracker
                )
            
            upload_end_time = datetime.utcnow()
            upload_duration = (upload_end_time - upload_start_time).total_seconds()
            
            logger.info(f"Video upload completed in {upload_duration:.2f} seconds")
            
            # Store video metadata in database
            video_db_metadata = await self._store_video_metadata_in_db(
                user_id=user_id,
                job_id=job_id,
                scene_number=scene_number,
                bucket=bucket,
                key=key,
                file_size=file_size,
                file_hash=file_hash,
                video_metadata=video_metadata,
                upload_duration=upload_duration
            )
            
            # Generate streaming URL
            streaming_url = await self.generate_video_streaming_url(
                video_db_metadata.id, user_id
            )
            
            return {
                'video_id': video_db_metadata.id,
                's3_url': f"s3://{bucket}/{key}",
                'streaming_url': streaming_url,
                'file_size': file_size,
                'duration_seconds': video_metadata.get('duration_seconds'),
                'resolution': f"{video_metadata.get('width')}x{video_metadata.get('height')}",
                'upload_duration_seconds': upload_duration
            }
            
        except Exception as e:
            logger.error(f"Failed to store video {video_path}: {e}", exc_info=True)
            raise RuntimeError(f"Video storage failed: {e}")
    
    def _upload_video_with_retry(self, 
                                video_path: str, 
                                bucket: str, 
                                key: str, 
                                extra_args: Dict[str, Any], 
                                callback: ProgressCallback):
        """
        Upload video with automatic retry logic and exponential backoff.
        
        Args:
            video_path: Path to video file
            bucket: S3 bucket name
            key: S3 object key
            extra_args: Additional S3 upload arguments
            callback: Progress callback
        """
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.s3_client.upload_file(
                    video_path, bucket, key,
                    ExtraArgs=extra_args,
                    Config=self.video_transfer_config,
                    Callback=callback
                )
                logger.info(f"Video upload successful on attempt {attempt + 1}")
                return
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if attempt == max_retries - 1:
                    logger.error(f"Video upload failed after {max_retries} attempts: {e}")
                    raise
                
                # Exponential backoff for retryable errors
                if error_code in ['ServiceUnavailable', 'SlowDown', 'RequestTimeout']:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Upload attempt {attempt + 1} failed ({error_code}), retrying in {delay}s")
                    time.sleep(delay)
                else:
                    # Non-retryable error
                    logger.error(f"Non-retryable upload error: {e}")
                    raise
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Video upload failed after {max_retries} attempts: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Upload attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)
    
    async def generate_video_streaming_url(self, 
                                          video_id: str, 
                                          user_id: str,
                                          expiration: int = 7200) -> str:
        """
        Generate secure streaming URL for video playback.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            expiration: URL expiration time in seconds (default: 2 hours)
            
        Returns:
            Presigned URL for video streaming
            
        Raises:
            ValueError: If video not found or access denied
        """
        try:
            # Get video metadata from database
            video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
            
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found for user {user_id}")
            
            # Generate presigned URL with longer expiration for streaming
            streaming_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': video_metadata.s3_bucket,
                    'Key': video_metadata.s3_key
                },
                ExpiresIn=expiration
            )
            
            # Update view count
            await self._increment_video_view_count(video_id)
            
            logger.info(f"Generated streaming URL for video {video_id} (expires in {expiration}s)")
            return streaming_url
            
        except Exception as e:
            logger.error(f"Failed to generate streaming URL for video {video_id}: {e}")
            raise
    
    async def generate_video_thumbnail(self, 
                                      video_path: str, 
                                      video_id: str,
                                      user_id: str,
                                      job_id: str,
                                      scene_number: int,
                                      timestamp_seconds: float = 5.0) -> Dict[str, Any]:
        """
        Generate and store video thumbnail in S3.
        
        Args:
            video_path: Local path to video file
            video_id: Video ID for association
            user_id: User ID
            job_id: Job ID
            scene_number: Scene number
            timestamp_seconds: Video timestamp for thumbnail (default: 5 seconds)
            
        Returns:
            Dict containing thumbnail information
            
        Raises:
            RuntimeError: If thumbnail generation fails
        """
        try:
            # Generate thumbnail using OpenCV
            thumbnail_path = await self._extract_video_frame(
                video_path, timestamp_seconds
            )
            
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                raise RuntimeError("Failed to extract video frame for thumbnail")
            
            # Get thumbnail dimensions
            with Image.open(thumbnail_path) as img:
                width, height = img.size
            
            # Generate S3 key for thumbnail
            bucket = self.config.buckets['thumbnails']
            thumbnail_filename = f"thumbnail_{timestamp_seconds:.1f}s.jpg"
            key = f"users/{user_id}/jobs/{job_id}/thumbnails/scene_{scene_number:03d}/{thumbnail_filename}"
            
            # Upload thumbnail to S3
            file_size = os.path.getsize(thumbnail_path)
            
            extra_args = {
                'Metadata': {
                    'video_id': video_id,
                    'user_id': user_id,
                    'job_id': job_id,
                    'scene_number': str(scene_number),
                    'timestamp_seconds': str(timestamp_seconds),
                    'width': str(width),
                    'height': str(height),
                    'content_type': 'image/jpeg'
                },
                'ContentType': 'image/jpeg',
                'StorageClass': 'STANDARD_IA'  # Infrequent access for thumbnails
            }
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.upload_file,
                    thumbnail_path, bucket, key,
                    extra_args, self.thumbnail_transfer_config
                )
            
            # Store thumbnail metadata in database
            thumbnail_metadata = await self._store_thumbnail_metadata_in_db(
                video_id=video_id,
                filename=thumbnail_filename,
                bucket=bucket,
                key=key,
                file_size=file_size,
                width=width,
                height=height,
                timestamp_seconds=timestamp_seconds
            )
            
            # Generate thumbnail URL
            thumbnail_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=3600  # 1 hour expiration for thumbnails
            )
            
            # Clean up local thumbnail file
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                logger.warning(f"Failed to clean up thumbnail file {thumbnail_path}: {e}")
            
            logger.info(f"Generated thumbnail for video {video_id} at {timestamp_seconds}s")
            
            return {
                'thumbnail_id': thumbnail_metadata.id,
                'thumbnail_url': thumbnail_url,
                's3_url': f"s3://{bucket}/{key}",
                'width': width,
                'height': height,
                'file_size': file_size,
                'timestamp_seconds': timestamp_seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for video {video_id}: {e}", exc_info=True)
            raise RuntimeError(f"Thumbnail generation failed: {e}")
    
    async def get_video_metadata(self, video_id: str, user_id: str) -> Optional[VideoMetadata]:
        """
        Get comprehensive video metadata.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            
        Returns:
            VideoMetadata instance or None if not found
        """
        try:
            return await self._get_video_metadata_from_db(video_id, user_id)
        except Exception as e:
            logger.error(f"Failed to get video metadata for {video_id}: {e}")
            return None
    
    async def list_user_videos(self, 
                              user_id: str, 
                              limit: int = 20, 
                              offset: int = 0) -> List[VideoMetadata]:
        """
        List videos for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of videos to return
            offset: Number of videos to skip
            
        Returns:
            List of VideoMetadata instances
        """
        try:
            async with self.db_manager.get_session() as session:
                # Query videos for user with pagination using SQLAlchemy
                result = await session.execute(
                    text("""
                    SELECT * FROM file_metadata 
                    WHERE user_id = :user_id AND file_type = 'video' 
                    ORDER BY created_at DESC 
                    LIMIT :limit OFFSET :offset
                    """),
                    {"user_id": user_id, "limit": limit, "offset": offset}
                )
                rows = result.mappings().all()
                
                videos = []
                for row in rows:
                    # Convert database row to VideoMetadata
                    video_metadata = await self._db_row_to_video_metadata(dict(row))
                    if video_metadata:
                        videos.append(video_metadata)
                
                return videos
                
        except Exception as e:
            logger.error(f"Failed to list videos for user {user_id}: {e}")
            return []
    
    async def delete_video(self, video_id: str, user_id: str) -> bool:
        """
        Delete video and associated files from S3 and database.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Get video metadata
            video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
            if not video_metadata:
                logger.warning(f"Video {video_id} not found for deletion")
                return False
            
            # Delete video file from S3
            try:
                self.s3_client.delete_object(
                    Bucket=video_metadata.s3_bucket,
                    Key=video_metadata.s3_key
                )
                logger.info(f"Deleted video file from S3: {video_metadata.s3_key}")
            except ClientError as e:
                logger.warning(f"Failed to delete video file from S3: {e}")
            
            # Delete associated thumbnails
            await self._delete_video_thumbnails(video_id, user_id)
            
            # Mark video as deleted in database (soft delete)
            await self._mark_video_as_deleted(video_id)
            
            logger.info(f"Successfully deleted video {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete video {video_id}: {e}")
            return False
    
    async def generate_multiple_thumbnails(self, 
                                          video_path: str, 
                                          video_id: str,
                                          user_id: str,
                                          job_id: str,
                                          scene_number: int,
                                          timestamps: List[float] = None) -> List[Dict[str, Any]]:
        """
        Generate multiple thumbnails at different timestamps.
        
        Args:
            video_path: Local path to video file
            video_id: Video ID for association
            user_id: User ID
            job_id: Job ID
            scene_number: Scene number
            timestamps: List of timestamps in seconds (default: auto-generate)
            
        Returns:
            List of thumbnail information dictionaries
        """
        try:
            if not timestamps:
                # Auto-generate timestamps based on video duration
                video_metadata = await self._extract_video_metadata(video_path)
                duration = video_metadata.get('duration_seconds', 0)
                
                if duration > 0:
                    # Generate thumbnails at 10%, 25%, 50%, 75%, 90% of video duration
                    timestamps = [
                        duration * 0.1,
                        duration * 0.25,
                        duration * 0.5,
                        duration * 0.75,
                        duration * 0.9
                    ]
                else:
                    timestamps = [5.0]  # Default to 5 seconds if duration unknown
            
            thumbnails = []
            
            # Generate thumbnails concurrently
            tasks = []
            for timestamp in timestamps:
                task = self.generate_video_thumbnail(
                    video_path, video_id, user_id, job_id, scene_number, timestamp
                )
                tasks.append(task)
            
            # Wait for all thumbnails to be generated
            thumbnail_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(thumbnail_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate thumbnail at {timestamps[i]}s: {result}")
                else:
                    thumbnails.append(result)
            
            logger.info(f"Generated {len(thumbnails)} thumbnails for video {video_id}")
            return thumbnails
            
        except Exception as e:
            logger.error(f"Failed to generate multiple thumbnails: {e}")
            return []
    
    async def get_video_streaming_info(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive video streaming information including URLs and metadata.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            
        Returns:
            Dict containing streaming information
        """
        try:
            # Get video metadata
            video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")
            
            # Generate streaming URLs with different expiration times
            streaming_urls = {
                'short_term': self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': video_metadata.s3_bucket, 'Key': video_metadata.s3_key},
                    ExpiresIn=3600  # 1 hour
                ),
                'medium_term': self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': video_metadata.s3_bucket, 'Key': video_metadata.s3_key},
                    ExpiresIn=7200  # 2 hours
                ),
                'long_term': self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': video_metadata.s3_bucket, 'Key': video_metadata.s3_key},
                    ExpiresIn=86400  # 24 hours
                )
            }
            
            # Get thumbnail URLs
            thumbnail_urls = await self._get_video_thumbnail_urls(video_id)
            
            # Extract video properties from metadata
            metadata = video_metadata.metadata or {}
            
            streaming_info = {
                'video_id': video_id,
                'streaming_urls': streaming_urls,
                'thumbnail_urls': thumbnail_urls,
                'video_properties': {
                    'duration_seconds': metadata.get('duration_seconds'),
                    'width': metadata.get('width'),
                    'height': metadata.get('height'),
                    'frame_rate': metadata.get('frame_rate'),
                    'file_size': video_metadata.file_size,
                    'content_type': video_metadata.content_type
                },
                'access_info': {
                    'view_count': metadata.get('view_count', 0),
                    'created_at': video_metadata.created_at.isoformat(),
                    'last_accessed': datetime.utcnow().isoformat()
                }
            }
            
            # Update last accessed timestamp
            await self._update_last_accessed(video_id)
            
            return streaming_info
            
        except Exception as e:
            logger.error(f"Failed to get streaming info for video {video_id}: {e}")
            raise
    
    async def create_video_playlist(self, 
                                   user_id: str, 
                                   video_ids: List[str],
                                   playlist_name: str = "Generated Playlist") -> Dict[str, Any]:
        """
        Create a playlist with multiple videos for sequential streaming.
        
        Args:
            user_id: User ID
            video_ids: List of video IDs to include in playlist
            playlist_name: Name for the playlist
            
        Returns:
            Dict containing playlist information
        """
        try:
            playlist_id = str(uuid.uuid4())
            playlist_videos = []
            
            for video_id in video_ids:
                video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
                if video_metadata:
                    streaming_url = await self.generate_video_streaming_url(video_id, user_id, 7200)
                    thumbnail_urls = await self._get_video_thumbnail_urls(video_id)
                    
                    metadata = video_metadata.metadata or {}
                    playlist_videos.append({
                        'video_id': video_id,
                        'streaming_url': streaming_url,
                        'thumbnail_url': thumbnail_urls[0] if thumbnail_urls else None,
                        'duration_seconds': metadata.get('duration_seconds'),
                        'title': video_metadata.original_filename,
                        'created_at': video_metadata.created_at.isoformat()
                    })
            
            playlist_info = {
                'playlist_id': playlist_id,
                'name': playlist_name,
                'user_id': user_id,
                'videos': playlist_videos,
                'total_videos': len(playlist_videos),
                'total_duration_seconds': sum(
                    v.get('duration_seconds', 0) for v in playlist_videos if v.get('duration_seconds')
                ),
                'created_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Created playlist {playlist_id} with {len(playlist_videos)} videos")
            return playlist_info
            
        except Exception as e:
            logger.error(f"Failed to create video playlist: {e}")
            raise
    
    async def get_video_download_url(self, 
                                    video_id: str, 
                                    user_id: str,
                                    expiration: int = 3600) -> str:
        """
        Generate secure download URL for video file.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned download URL
        """
        try:
            video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")
            
            # Generate presigned URL with content-disposition for download
            download_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': video_metadata.s3_bucket,
                    'Key': video_metadata.s3_key,
                    'ResponseContentDisposition': f'attachment; filename="{video_metadata.original_filename}"'
                },
                ExpiresIn=expiration
            )
            
            # Increment download count
            await self._increment_download_count(video_id)
            
            logger.info(f"Generated download URL for video {video_id}")
            return download_url
            
        except Exception as e:
            logger.error(f"Failed to generate download URL for video {video_id}: {e}")
            raise
    
    async def organize_videos_by_job(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Organize user's videos by job ID for better management.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict mapping job IDs to lists of video information
        """
        try:
            videos = await self.list_user_videos(user_id, limit=1000)  # Get all videos
            
            organized_videos = {}
            
            for video in videos:
                job_id = video.job_id
                if job_id not in organized_videos:
                    organized_videos[job_id] = []
                
                # Get streaming and thumbnail info
                streaming_info = await self.get_video_streaming_info(video.id, user_id)
                
                video_info = {
                    'video_id': video.id,
                    'filename': video.filename,
                    'file_size': video.file_size,
                    'duration_seconds': video.duration_seconds,
                    'resolution': f"{video.width}x{video.height}" if video.width and video.height else None,
                    'created_at': video.created_at.isoformat(),
                    'streaming_url': streaming_info['streaming_urls']['medium_term'],
                    'thumbnail_urls': streaming_info['thumbnail_urls']
                }
                
                organized_videos[job_id].append(video_info)
            
            # Sort videos within each job by creation date
            for job_id in organized_videos:
                organized_videos[job_id].sort(key=lambda x: x['created_at'], reverse=True)
            
            logger.info(f"Organized {len(videos)} videos into {len(organized_videos)} jobs for user {user_id}")
            return organized_videos
            
        except Exception as e:
            logger.error(f"Failed to organize videos by job for user {user_id}: {e}")
            return {}
    
    # Private helper methods
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file for integrity checking."""
        hash_sha256 = hashlib.sha256()
        
        loop = asyncio.get_event_loop()
        
        def _hash_file():
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _hash_file)
    
    async def _extract_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """Extract video metadata using OpenCV."""
        loop = asyncio.get_event_loop()
        
        def _extract_metadata():
            try:
                cap = cv2.VideoCapture(video_path)
                
                if not cap.isOpened():
                    logger.warning(f"Could not open video file: {video_path}")
                    return {}
                
                # Get video properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                duration_seconds = frame_count / fps if fps > 0 else 0
                
                cap.release()
                
                return {
                    'width': width,
                    'height': height,
                    'frame_rate': fps,
                    'frame_count': frame_count,
                    'duration_seconds': duration_seconds
                }
                
            except Exception as e:
                logger.error(f"Failed to extract video metadata: {e}")
                return {}
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _extract_metadata)
    
    async def _extract_video_frame(self, video_path: str, timestamp_seconds: float) -> Optional[str]:
        """Extract a frame from video at specified timestamp."""
        loop = asyncio.get_event_loop()
        
        def _extract_frame():
            try:
                cap = cv2.VideoCapture(video_path)
                
                if not cap.isOpened():
                    return None
                
                # Set position to desired timestamp
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_number = int(timestamp_seconds * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                
                # Read frame
                ret, frame = cap.read()
                cap.release()
                
                if not ret:
                    return None
                
                # Save frame as JPEG
                thumbnail_path = f"/tmp/thumbnail_{uuid.uuid4().hex}.jpg"
                cv2.imwrite(thumbnail_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                return thumbnail_path
                
            except Exception as e:
                logger.error(f"Failed to extract video frame: {e}")
                return None
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _extract_frame)
    
    async def _store_video_metadata_in_db(self, **kwargs) -> FileMetadataDB:
        """Store video metadata in database."""
        try:
            async with self.db_manager.get_session() as session:
                # Create FileMetadataDB instance
                video_metadata = FileMetadataDB(
                    id=str(uuid.uuid4()),
                    user_id=kwargs['user_id'],
                    job_id=kwargs['job_id'],
                    file_type='video',
                    original_filename=f"scene_{kwargs['scene_number']:03d}_output.mp4",
                    s3_bucket=kwargs['bucket'],
                    s3_key=kwargs['key'],
                    file_size=kwargs['file_size'],
                    content_type='video/mp4',
                    metadata={
                        'scene_number': kwargs['scene_number'],
                        'duration_seconds': kwargs['video_metadata'].get('duration_seconds'),
                        'width': kwargs['video_metadata'].get('width'),
                        'height': kwargs['video_metadata'].get('height'),
                        'frame_rate': kwargs['video_metadata'].get('frame_rate'),
                        'file_hash': kwargs['file_hash'],
                        'upload_duration_seconds': kwargs['upload_duration']
                    }
                )
                
                # Insert into database using SQLAlchemy syntax
                await session.execute(
                    text("""
                    INSERT INTO file_metadata 
                    (id, user_id, job_id, file_type, original_filename, s3_bucket, s3_key, 
                     file_size, content_type, metadata, created_at)
                    VALUES (:id, :user_id, :job_id, :file_type, :filename, :bucket, :key, 
                            :file_size, :content_type, :metadata, :created_at)
                    """),
                    {
                        "id": video_metadata.id,
                        "user_id": video_metadata.user_id,
                        "job_id": video_metadata.job_id,
                        "file_type": video_metadata.file_type,
                        "filename": video_metadata.original_filename,
                        "bucket": video_metadata.s3_bucket,
                        "key": video_metadata.s3_key,
                        "file_size": video_metadata.file_size,
                        "content_type": video_metadata.content_type,
                        "metadata": json.dumps(video_metadata.metadata),
                        "created_at": video_metadata.created_at
                    }
                )
                
                await session.commit()
                
                logger.info(f"Stored video metadata in database: {video_metadata.id}")
                return video_metadata
                
        except Exception as e:
            logger.error(f"Failed to store video metadata in database: {e}")
            raise
    
    async def _get_video_metadata_from_db(self, video_id: str, user_id: str) -> Optional[FileMetadataDB]:
        """Get video metadata from database."""
        try:
            async with self.db_manager.get_session() as session:
                # Use SQLAlchemy syntax instead of asyncpg
                result = await session.execute(
                    text("""
                    SELECT * FROM file_metadata 
                    WHERE id = :video_id AND user_id = :user_id AND file_type = 'video'
                    """),
                    {"video_id": video_id, "user_id": user_id}
                )
                row = result.mappings().first()
                
                if row:
                    return FileMetadataDB(**dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Failed to get video metadata from database: {e}")
            return None
    
    async def _store_thumbnail_metadata_in_db(self, **kwargs) -> FileMetadataDB:
        """Store thumbnail metadata in database."""
        try:
            async with self.db_manager.get_session() as session:
                thumbnail_metadata = FileMetadataDB(
                    id=str(uuid.uuid4()),
                    user_id=kwargs.get('user_id', ''),  # Will be populated from video metadata
                    job_id=kwargs.get('job_id', ''),    # Will be populated from video metadata
                    file_type='thumbnail',
                    original_filename=kwargs['filename'],
                    s3_bucket=kwargs['bucket'],
                    s3_key=kwargs['key'],
                    file_size=kwargs['file_size'],
                    content_type='image/jpeg',
                    metadata={
                        'video_id': kwargs['video_id'],
                        'width': kwargs['width'],
                        'height': kwargs['height'],
                        'timestamp_seconds': kwargs['timestamp_seconds']
                    }
                )
                
                # Insert into database using SQLAlchemy syntax
                await session.execute(
                    text("""
                    INSERT INTO file_metadata 
                    (id, user_id, job_id, file_type, original_filename, s3_bucket, s3_key, 
                     file_size, content_type, metadata, created_at)
                    VALUES (:id, :user_id, :job_id, :file_type, :filename, :bucket, :key, 
                            :file_size, :content_type, :metadata, :created_at)
                    """),
                    {
                        "id": thumbnail_metadata.id,
                        "user_id": thumbnail_metadata.user_id,
                        "job_id": thumbnail_metadata.job_id,
                        "file_type": thumbnail_metadata.file_type,
                        "filename": thumbnail_metadata.original_filename,
                        "bucket": thumbnail_metadata.s3_bucket,
                        "key": thumbnail_metadata.s3_key,
                        "file_size": thumbnail_metadata.file_size,
                        "content_type": thumbnail_metadata.content_type,
                        "metadata": json.dumps(thumbnail_metadata.metadata),
                        "created_at": thumbnail_metadata.created_at
                    }
                )
                
                await session.commit()
                
                return thumbnail_metadata
                
        except Exception as e:
            logger.error(f"Failed to store thumbnail metadata: {e}")
            raise
    
    async def _increment_video_view_count(self, video_id: str):
        """Increment video view count in database."""
        try:
            async with self.db_manager.get_session() as session:
                await session.execute(
                    text("""
                    UPDATE file_metadata 
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'), 
                        '{view_count}', 
                        to_jsonb(COALESCE((metadata->>'view_count')::int, 0) + 1)
                    )
                    WHERE id = :video_id AND file_type = 'video'
                    """),
                    {"video_id": video_id}
                )
                await session.commit()
                
        except Exception as e:
            logger.warning(f"Failed to increment view count for video {video_id}: {e}")
    
    async def _delete_video_thumbnails(self, video_id: str, user_id: str):
        """Delete all thumbnails associated with a video."""
        try:
            async with self.db_manager.get_session() as session:
                # Get thumbnail metadata using SQLAlchemy
                result = await session.execute(
                    text("""
                    SELECT s3_bucket, s3_key FROM file_metadata 
                    WHERE file_type = 'thumbnail' AND metadata->>'video_id' = :video_id
                    """),
                    {"video_id": video_id}
                )
                rows = result.mappings().all()
                
                # Delete thumbnails from S3
                for row in rows:
                    try:
                        self.s3_client.delete_object(
                            Bucket=row['s3_bucket'],
                            Key=row['s3_key']
                        )
                    except ClientError as e:
                        logger.warning(f"Failed to delete thumbnail from S3: {e}")
                
                # Mark thumbnails as deleted in database
                await session.execute(
                    text("""
                    UPDATE file_metadata 
                    SET metadata = jsonb_set(metadata, '{deleted}', 'true')
                    WHERE file_type = 'thumbnail' AND metadata->>'video_id' = :video_id
                    """),
                    {"video_id": video_id}
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to delete video thumbnails: {e}")
    
    async def _mark_video_as_deleted(self, video_id: str):
        """Mark video as deleted in database (soft delete)."""
        try:
            async with self.db_manager.get_session() as session:
                await session.execute(
                    text("""
                    UPDATE file_metadata 
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'), 
                        '{deleted}', 
                        'true'
                    )
                    WHERE id = :video_id AND file_type = 'video'
                    """),
                    {"video_id": video_id}
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to mark video as deleted: {e}")
            raise
    
    async def _db_row_to_video_metadata(self, row) -> Optional[VideoMetadata]:
        """Convert database row to VideoMetadata instance."""
        try:
            metadata = row.get('metadata', {})
            
            return VideoMetadata(
                id=row['id'],
                job_id=row['job_id'],
                user_id=row['user_id'],
                filename=row['original_filename'],
                file_path=f"s3://{row['s3_bucket']}/{row['s3_key']}",
                file_size=row['file_size'],
                duration_seconds=metadata.get('duration_seconds'),
                width=metadata.get('width'),
                height=metadata.get('height'),
                format=VideoFormat.MP4,
                status=VideoStatus.READY,
                created_at=row['created_at']
            )
            
        except Exception as e:
            logger.error(f"Failed to convert database row to VideoMetadata: {e}")
            return None
    
    async def _get_video_thumbnail_urls(self, video_id: str) -> List[str]:
        """Get all thumbnail URLs for a video."""
        try:
            async with self.db_manager.get_session() as session:
                result = await session.execute(
                    text("""
                    SELECT s3_bucket, s3_key FROM file_metadata 
                    WHERE file_type = 'thumbnail' 
                    AND metadata->>'video_id' = :video_id
                    AND (metadata->>'deleted' IS NULL OR metadata->>'deleted' != 'true')
                    ORDER BY (metadata->>'timestamp_seconds')::float
                    """),
                    {"video_id": video_id}
                )
                rows = result.mappings().all()
                
                thumbnail_urls = []
                for row in rows:
                    try:
                        url = self.s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': row['s3_bucket'], 'Key': row['s3_key']},
                            ExpiresIn=3600  # 1 hour expiration
                        )
                        thumbnail_urls.append(url)
                    except Exception as e:
                        logger.warning(f"Failed to generate thumbnail URL: {e}")
                
                return thumbnail_urls
                
        except Exception as e:
            logger.error(f"Failed to get thumbnail URLs for video {video_id}: {e}")
            return []
    
    async def _update_last_accessed(self, video_id: str):
        """Update last accessed timestamp for video."""
        try:
            async with self.db_manager.get_session() as session:
                await session.execute(
                    text("""
                    UPDATE file_metadata 
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'), 
                        '{last_accessed}', 
                        to_jsonb(NOW())
                    )
                    WHERE id = :video_id AND file_type = 'video'
                    """),
                    {"video_id": video_id}
                )
                await session.commit()
                
        except Exception as e:
            logger.warning(f"Failed to update last accessed for video {video_id}: {e}")
    
    async def _increment_download_count(self, video_id: str):
        """Increment video download count in database."""
        try:
            async with self.db_manager.get_session() as session:
                await session.execute(
                    text("""
                    UPDATE file_metadata 
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'), 
                        '{download_count}', 
                        to_jsonb(COALESCE((metadata->>'download_count')::int, 0) + 1)
                    )
                    WHERE id = :video_id AND file_type = 'video'
                    """),
                    {"video_id": video_id}
                )
                await session.commit()
                
        except Exception as e:
            logger.warning(f"Failed to increment download count for video {video_id}: {e}")
    
    async def get_video_analytics(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get analytics data for a specific video.
        
        Args:
            video_id: Video ID
            user_id: User ID for access control
            
        Returns:
            Dict containing analytics data
        """
        try:
            video_metadata = await self._get_video_metadata_from_db(video_id, user_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")
            
            metadata = video_metadata.metadata or {}
            
            analytics = {
                'video_id': video_id,
                'basic_stats': {
                    'view_count': metadata.get('view_count', 0),
                    'download_count': metadata.get('download_count', 0),
                    'file_size_mb': round(video_metadata.file_size / (1024 * 1024), 2),
                    'duration_seconds': metadata.get('duration_seconds'),
                    'created_at': video_metadata.created_at.isoformat()
                },
                'technical_info': {
                    'width': metadata.get('width'),
                    'height': metadata.get('height'),
                    'frame_rate': metadata.get('frame_rate'),
                    'file_hash': metadata.get('file_hash'),
                    'upload_duration_seconds': metadata.get('upload_duration_seconds')
                },
                'storage_info': {
                    's3_bucket': video_metadata.s3_bucket,
                    's3_key': video_metadata.s3_key,
                    'content_type': video_metadata.content_type
                },
                'access_info': {
                    'last_accessed': metadata.get('last_accessed'),
                    'is_deleted': metadata.get('deleted') == 'true'
                }
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get analytics for video {video_id}: {e}")
            raise
    
    async def cleanup_expired_urls(self):
        """
        Cleanup method for any expired URL tracking (if implemented).
        This is a placeholder for future URL expiration management.
        """
        logger.info("URL cleanup not implemented - URLs expire automatically")
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the video service.
        
        Returns:
            Dict containing health status
        """
        health_status = {
            'service': 'AWSVideoService',
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Check S3 connectivity
            try:
                self.s3_client.list_buckets()
                health_status['checks']['s3_connectivity'] = {'status': 'ok'}
            except Exception as e:
                health_status['checks']['s3_connectivity'] = {'status': 'error', 'error': str(e)}
                health_status['status'] = 'unhealthy'
            
            # Check database connectivity
            try:
                async with self.db_manager.get_session() as session:
                    # Use SQLAlchemy syntax instead of asyncpg
                    result = await session.execute(text("SELECT 1"))
                    result.scalar()
                health_status['checks']['database_connectivity'] = {'status': 'ok'}
            except Exception as e:
                health_status['checks']['database_connectivity'] = {'status': 'error', 'error': str(e)}
                health_status['status'] = 'unhealthy'
            
            # Check bucket accessibility
            bucket_checks = {}
            for bucket_type, bucket_name in self.config.buckets.items():
                try:
                    self.s3_client.head_bucket(Bucket=bucket_name)
                    bucket_checks[bucket_type] = {'status': 'ok', 'bucket': bucket_name}
                except Exception as e:
                    bucket_checks[bucket_type] = {'status': 'error', 'bucket': bucket_name, 'error': str(e)}
                    health_status['status'] = 'unhealthy'
            
            health_status['checks']['buckets'] = bucket_checks
            
        except Exception as e:
            health_status['status'] = 'error'
            health_status['error'] = str(e)
        
        return health_status
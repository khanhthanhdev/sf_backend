"""
Storage Manager for handling both local and AWS S3 storage of generated videos.

This module provides a unified interface for storing video generation outputs
locally and/or in AWS S3, with configurable upload strategies and metadata tracking.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from src.config.config import Config
from src.app.services.aws_video_service import AWSVideoService
from src.app.database.connection import RDSConnectionManager

logger = logging.getLogger(__name__)


class StorageMode(Enum):
    """Storage mode configuration."""
    LOCAL_ONLY = "local_only"
    S3_ONLY = "s3_only"
    LOCAL_AND_S3 = "local_and_s3"


@dataclass
class VideoUploadResult:
    """Result of video upload operation."""
    success: bool
    local_path: Optional[str] = None
    s3_url: Optional[str] = None
    streaming_url: Optional[str] = None
    video_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StorageManager:
    """
    Unified storage manager for video generation outputs.
    
    Handles both local storage and AWS S3 uploads with configurable modes,
    progress tracking, and metadata management.
    """
    
    def __init__(self, 
                 storage_mode: StorageMode = StorageMode.LOCAL_ONLY,
                 aws_video_service: Optional[AWSVideoService] = None,
                 enable_thumbnails: bool = True,
                 cleanup_local: bool = False):
        """
        Initialize the storage manager.
        
        Args:
            storage_mode: Storage mode (local_only, s3_only, local_and_s3)
            aws_video_service: AWS video service instance (required for S3 modes)
            enable_thumbnails: Whether to generate thumbnails for uploaded videos
            cleanup_local: Whether to delete local files after S3 upload
        """
        self.storage_mode = storage_mode
        self.aws_video_service = aws_video_service
        self.enable_thumbnails = enable_thumbnails
        self.cleanup_local = cleanup_local
        
        # Validate configuration
        if storage_mode in [StorageMode.S3_ONLY, StorageMode.LOCAL_AND_S3]:
            if not aws_video_service:
                raise ValueError(f"AWS video service required for {storage_mode.value} mode")
        
        logger.info(f"Storage manager initialized with mode: {storage_mode.value}")
    
    async def store_video(self, 
                         local_video_path: str,
                         topic: str,
                         scene_number: int,
                         user_id: Optional[str] = None,
                         job_id: Optional[str] = None,
                         progress_callback: Optional[callable] = None) -> VideoUploadResult:
        """
        Store video according to configured storage mode.
        
        Args:
            local_video_path: Path to the locally generated video
            topic: Video topic/title
            scene_number: Scene number
            user_id: User ID (required for S3 uploads)
            job_id: Job ID (required for S3 uploads)
            progress_callback: Optional progress callback function
            
        Returns:
            VideoUploadResult with storage information
        """
        if not os.path.exists(local_video_path):
            return VideoUploadResult(
                success=False,
                error=f"Local video file not found: {local_video_path}"
            )
        
        result = VideoUploadResult(success=True, local_path=local_video_path)
        
        try:
            # Handle different storage modes
            if self.storage_mode == StorageMode.LOCAL_ONLY:
                result = await self._handle_local_only(local_video_path, result)
                
            elif self.storage_mode == StorageMode.S3_ONLY:
                if not user_id or not job_id:
                    raise ValueError("user_id and job_id required for S3-only mode")
                result = await self._handle_s3_only(
                    local_video_path, topic, scene_number, user_id, job_id, 
                    progress_callback, result
                )
                
            elif self.storage_mode == StorageMode.LOCAL_AND_S3:
                if not user_id or not job_id:
                    raise ValueError("user_id and job_id required for local_and_s3 mode")
                result = await self._handle_local_and_s3(
                    local_video_path, topic, scene_number, user_id, job_id, 
                    progress_callback, result
                )
            
            logger.info(f"Video storage completed: {self.storage_mode.value}")
            return result
            
        except Exception as e:
            logger.error(f"Video storage failed: {e}", exc_info=True)
            result.success = False
            result.error = str(e)
            return result
    
    async def _handle_local_only(self, 
                                local_video_path: str, 
                                result: VideoUploadResult) -> VideoUploadResult:
        """Handle local-only storage mode."""
        # For local-only mode, just verify the file exists and return local path
        result.metadata = {
            'storage_mode': 'local_only',
            'file_size': os.path.getsize(local_video_path),
            'storage_location': local_video_path
        }
        
        logger.info(f"Video stored locally: {local_video_path}")
        return result
    
    async def _handle_s3_only(self, 
                             local_video_path: str,
                             topic: str,
                             scene_number: int,
                             user_id: str,
                             job_id: str,
                             progress_callback: Optional[callable],
                             result: VideoUploadResult) -> VideoUploadResult:
        """Handle S3-only storage mode."""
        try:
            # Upload to S3
            upload_result = await self.aws_video_service.store_rendered_video(
                video_path=local_video_path,
                job_id=job_id,
                scene_number=scene_number,
                user_id=user_id,
                progress_callback=progress_callback
            )
            
            result.s3_url = upload_result.get('s3_url')
            result.streaming_url = upload_result.get('streaming_url')
            result.video_id = upload_result.get('video_id')
            result.metadata = {
                'storage_mode': 's3_only',
                'upload_duration': upload_result.get('upload_duration_seconds'),
                'file_size': upload_result.get('file_size'),
                'resolution': upload_result.get('resolution'),
                'duration_seconds': upload_result.get('duration_seconds')
            }
            
            # Generate thumbnail if enabled
            if self.enable_thumbnails and result.video_id:
                try:
                    thumbnail_result = await self.aws_video_service.generate_video_thumbnail(
                        video_path=local_video_path,
                        video_id=result.video_id,
                        user_id=user_id,
                        job_id=job_id,
                        scene_number=scene_number
                    )
                    result.metadata['thumbnail_url'] = thumbnail_result.get('thumbnail_url')
                except Exception as e:
                    logger.warning(f"Thumbnail generation failed: {e}")
            
            # Clean up local file if requested
            if self.cleanup_local:
                try:
                    os.remove(local_video_path)
                    result.local_path = None
                    logger.info(f"Cleaned up local file: {local_video_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up local file: {e}")
            
            logger.info(f"Video uploaded to S3: {result.s3_url}")
            return result
            
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise
    
    async def _handle_local_and_s3(self, 
                                  local_video_path: str,
                                  topic: str,
                                  scene_number: int,
                                  user_id: str,
                                  job_id: str,
                                  progress_callback: Optional[callable],
                                  result: VideoUploadResult) -> VideoUploadResult:
        """Handle local and S3 storage mode."""
        try:
            # Keep local file and upload to S3
            upload_result = await self.aws_video_service.store_rendered_video(
                video_path=local_video_path,
                job_id=job_id,
                scene_number=scene_number,
                user_id=user_id,
                progress_callback=progress_callback
            )
            
            result.s3_url = upload_result.get('s3_url')
            result.streaming_url = upload_result.get('streaming_url')
            result.video_id = upload_result.get('video_id')
            result.metadata = {
                'storage_mode': 'local_and_s3',
                'local_path': local_video_path,
                'upload_duration': upload_result.get('upload_duration_seconds'),
                'file_size': upload_result.get('file_size'),
                'resolution': upload_result.get('resolution'),
                'duration_seconds': upload_result.get('duration_seconds')
            }
            
            # Generate thumbnail if enabled
            if self.enable_thumbnails and result.video_id:
                try:
                    thumbnail_result = await self.aws_video_service.generate_video_thumbnail(
                        video_path=local_video_path,
                        video_id=result.video_id,
                        user_id=user_id,
                        job_id=job_id,
                        scene_number=scene_number
                    )
                    result.metadata['thumbnail_url'] = thumbnail_result.get('thumbnail_url')
                except Exception as e:
                    logger.warning(f"Thumbnail generation failed: {e}")
            
            logger.info(f"Video stored locally and uploaded to S3: {result.s3_url}")
            return result
            
        except Exception as e:
            logger.error(f"Local and S3 storage failed: {e}")
            # If S3 upload fails, at least we have local storage
            result.metadata = {
                'storage_mode': 'local_fallback',
                'error': f"S3 upload failed: {e}",
                'file_size': os.path.getsize(local_video_path)
            }
            logger.warning("S3 upload failed, falling back to local-only storage")
            return result
    
    async def store_multiple_videos(self, 
                                   video_paths: List[str],
                                   topic: str,
                                   user_id: Optional[str] = None,
                                   job_id: Optional[str] = None,
                                   progress_callback: Optional[callable] = None) -> List[VideoUploadResult]:
        """
        Store multiple videos concurrently.
        
        Args:
            video_paths: List of local video file paths
            topic: Video topic/title
            user_id: User ID (required for S3 uploads)
            job_id: Job ID (required for S3 uploads)
            progress_callback: Optional progress callback function
            
        Returns:
            List of VideoUploadResult instances
        """
        tasks = []
        
        for i, video_path in enumerate(video_paths):
            scene_number = i + 1
            task = asyncio.create_task(
                self.store_video(
                    local_video_path=video_path,
                    topic=topic,
                    scene_number=scene_number,
                    user_id=user_id,
                    job_id=job_id,
                    progress_callback=progress_callback
                )
            )
            tasks.append(task)
        
        # Execute all uploads concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(VideoUploadResult(
                    success=False,
                    error=str(result),
                    local_path=video_paths[i] if i < len(video_paths) else None
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    def get_video_url(self, result: VideoUploadResult) -> Optional[str]:
        """
        Get the appropriate video URL based on storage mode.
        
        Args:
            result: VideoUploadResult from store_video
            
        Returns:
            Video URL (streaming URL for S3, local path for local-only)
        """
        if result.streaming_url:
            return result.streaming_url
        elif result.s3_url:
            return result.s3_url
        elif result.local_path:
            return result.local_path
        else:
            return None
    
    @classmethod
    def create_from_config(cls, 
                          storage_mode: Optional[str] = None,
                          user_id: Optional[str] = None) -> 'StorageManager':
        """
        Create StorageManager instance from application configuration.
        
        Args:
            storage_mode: Override storage mode from config
            user_id: User ID for AWS service initialization
            
        Returns:
            Configured StorageManager instance
        """
        try:
            # Get storage mode from environment or default
            mode_str = storage_mode or os.getenv('VIDEO_STORAGE_MODE', 'local_only')
            mode = StorageMode(mode_str)
            
            # Initialize AWS service if needed
            aws_video_service = None
            if mode in [StorageMode.S3_ONLY, StorageMode.LOCAL_AND_S3]:
                try:
                    aws_config = Config.get_aws_config()
                    db_manager = RDSConnectionManager(aws_config)
                    aws_video_service = AWSVideoService(aws_config, db_manager)
                except Exception as e:
                    logger.error(f"Failed to initialize AWS video service: {e}")
                    if mode == StorageMode.S3_ONLY:
                        raise
                    # Fallback to local-only for local_and_s3 mode
                    mode = StorageMode.LOCAL_ONLY
                    logger.warning("Falling back to local-only storage mode")
            
            return cls(
                storage_mode=mode,
                aws_video_service=aws_video_service,
                enable_thumbnails=os.getenv('ENABLE_THUMBNAILS', 'true').lower() == 'true',
                cleanup_local=os.getenv('CLEANUP_LOCAL_FILES', 'false').lower() == 'true'
            )
            
        except Exception as e:
            logger.error(f"Failed to create storage manager from config: {e}")
            # Fallback to local-only mode
            return cls(storage_mode=StorageMode.LOCAL_ONLY)
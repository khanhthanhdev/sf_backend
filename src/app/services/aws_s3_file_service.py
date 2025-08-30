"""
AWS S3-based file service implementation.

This service provides S3-based file management operations including
upload handling, storage management, metadata tracking, and secure access.
"""

import logging
import asyncio
import os
import time
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.s3.transfer import TransferConfig
from fastapi import UploadFile, HTTPException, status

from ..models.file import FileType, FileMetadataResponse, FileUploadResponse
from ..models.common import PaginatedResponse
from ..utils.file_utils import FileMetadata, FileValidationResult, validate_upload_file
from src.config.aws_config import AWSConfig

logger = logging.getLogger(__name__)


class ProgressPercentage:
    """Progress callback for S3 uploads with thread safety."""
    
    def __init__(self, filename: str, file_size: int, callback=None):
        self._filename = filename
        self._size = float(file_size)
        self._seen_so_far = 0
        self._lock = threading.Lock()
        self._callback = callback
    
    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            
            if self._callback:
                self._callback(self._filename, percentage, self._seen_so_far, self._size)
            
            logger.debug(
                f"Upload progress - File: {self._filename}, "
                f"Progress: {percentage:.2f}% ({self._seen_so_far}/{self._size} bytes)"
            )


class AWSS3FileService:
    """AWS S3-based file service implementation."""
    
    def __init__(self, aws_config: AWSConfig):
        """
        Initialize S3 file service.
        
        Args:
            aws_config: AWS configuration object
        """
        self.config = aws_config
        
        # Create thread-safe session
        self.session = boto3.Session(
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        self.s3_client = self.session.client('s3')
        
        # Configure transfer settings for optimal performance
        self.transfer_config = TransferConfig(
            multipart_threshold=1024 * 25,  # 25MB
            max_concurrency=10,
            multipart_chunksize=1024 * 25,
            use_threads=True
        )
        
        # Large file transfer config for videos
        self.large_file_transfer_config = TransferConfig(
            multipart_threshold=1024 * 50,  # 50MB for large files
            max_concurrency=8,
            multipart_chunksize=1024 * 50,
            use_threads=True
        )
        
        logger.info(f"Initialized AWSS3FileService for environment: {aws_config.environment}")
    
    def _get_bucket_for_type(self, file_type: str) -> str:
        """
        Get appropriate S3 bucket for file type.
        
        Args:
            file_type: Type of file (video, image, document, etc.)
            
        Returns:
            str: S3 bucket name
            
        Raises:
            ValueError: If file type is not supported
        """
        type_to_bucket = {
            'video': 'videos',
            'image': 'thumbnails',
            'document': 'code',
            'code': 'code',
            'audio': 'videos',  # Store audio with videos
            'archive': 'code',
            'temp': 'temp'
        }
        
        bucket_type = type_to_bucket.get(file_type.lower(), 'temp')
        
        if bucket_type not in self.config.buckets:
            raise ValueError(f"Bucket type '{bucket_type}' not configured")
        
        return self.config.buckets[bucket_type]
    
    def _generate_s3_key(self, user_id: str, job_id: Optional[str], 
                        filename: str, file_type: str, scene_number: Optional[int] = None) -> str:
        """
        Generate S3 key with proper organization structure.
        
        Args:
            user_id: User identifier
            job_id: Job identifier (optional)
            filename: Original filename
            file_type: Type of file
            scene_number: Scene number for video files (optional)
            
        Returns:
            str: S3 key path
        """
        # Sanitize filename
        safe_filename = Path(filename).name
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if job_id:
            if scene_number is not None:
                # For video files with scene numbers
                return f"users/{user_id}/jobs/{job_id}/{file_type}/scene_{scene_number:03d}/{timestamp}_{safe_filename}"
            else:
                # For job-related files
                return f"users/{user_id}/jobs/{job_id}/{file_type}/{timestamp}_{safe_filename}"
        else:
            # For user files not associated with a job
            return f"users/{user_id}/{file_type}/{timestamp}_{safe_filename}"
    
    async def upload_file(
        self,
        file: UploadFile,
        user_id: str,
        file_type: Optional[str] = None,
        job_id: Optional[str] = None,
        scene_number: Optional[int] = None,
        progress_callback=None
    ) -> FileUploadResponse:
        """
        Upload file to S3 with proper error handling and metadata.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID for file ownership
            file_type: Optional file type override
            job_id: Optional job ID for organization
            scene_number: Optional scene number for video files
            progress_callback: Optional progress callback function
            
        Returns:
            FileUploadResponse: Upload result with S3 information
            
        Raises:
            HTTPException: If validation or upload fails
        """
        try:
            # Validate file
            validation_result = await validate_upload_file(file)
            
            if not validation_result.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "File validation failed",
                        "errors": validation_result.errors,
                        "warnings": validation_result.warnings
                    }
                )
            
            # Use detected file type if not provided
            if not file_type:
                file_type = validation_result.file_type
            
            # Get appropriate bucket and generate S3 key
            bucket = self._get_bucket_for_type(file_type)
            key = self._generate_s3_key(user_id, job_id, file.filename, file_type, scene_number)
            
            # Get file size
            file_size = 0
            if hasattr(file, 'size') and file.size:
                file_size = file.size
            else:
                # Read file to get size
                content = await file.read()
                file_size = len(content)
                # Reset file pointer
                await file.seek(0)
            
            # Prepare metadata
            extra_args = {
                'Metadata': {
                    'user_id': user_id,
                    'job_id': job_id or '',
                    'scene_number': str(scene_number) if scene_number is not None else '',
                    'file_type': file_type,
                    'original_filename': file.filename,
                    'upload_timestamp': str(datetime.utcnow()),
                    'file_size': str(file_size)
                },
                'ContentType': file.content_type or 'application/octet-stream'
            }
            
            # Choose transfer config based on file size
            transfer_config = (
                self.large_file_transfer_config if file_size > 50 * 1024 * 1024 
                else self.transfer_config
            )
            
            # Upload with progress tracking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self._upload_with_retry,
                    file.file, bucket, key, extra_args, transfer_config, 
                    file.filename, file_size, progress_callback
                )
            
            # Generate presigned URL for download
            download_url = self.generate_presigned_url(bucket, key, expiration=3600)
            
            logger.info(
                "File uploaded successfully to S3",
                extra={
                    "filename": file.filename,
                    "user_id": user_id,
                    "job_id": job_id,
                    "file_type": file_type,
                    "file_size": file_size,
                    "s3_bucket": bucket,
                    "s3_key": key
                }
            )
            
            return FileUploadResponse(
                file_id=key,  # Use S3 key as file ID
                filename=file.filename,
                file_type=FileType(file_type),
                file_size=file_size,
                download_url=download_url,
                created_at=datetime.utcnow()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {str(e)}"
            )
    
    def _upload_with_retry(self, file_obj: BinaryIO, bucket: str, key: str, 
                          extra_args: Dict[str, Any], transfer_config: TransferConfig,
                          filename: str, file_size: int, progress_callback=None):
        """
        Upload file with automatic retry logic and progress tracking.
        
        Args:
            file_obj: File object to upload
            bucket: S3 bucket name
            key: S3 key
            extra_args: Extra arguments for upload
            transfer_config: Transfer configuration
            filename: Original filename for progress tracking
            file_size: File size for progress tracking
            progress_callback: Optional progress callback
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Create progress callback if needed
                callback = None
                if progress_callback:
                    callback = ProgressPercentage(filename, file_size, progress_callback)
                
                self.s3_client.upload_fileobj(
                    file_obj, bucket, key,
                    ExtraArgs=extra_args,
                    Config=transfer_config,
                    Callback=callback
                )
                return
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if attempt == max_retries - 1:
                    # Last attempt failed
                    if error_code == 'NoSuchBucket':
                        raise ValueError(f"Bucket {bucket} does not exist")
                    elif error_code == 'AccessDenied':
                        raise PermissionError(f"Access denied to bucket {bucket}")
                    else:
                        raise RuntimeError(f"S3 upload failed: {e}")
                
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"Upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                
                # Reset file pointer for retry
                file_obj.seek(0)
            
            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"S3 upload failed: {e}")
                
                wait_time = 2 ** attempt
                logger.warning(f"Upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                file_obj.seek(0)
    
    async def download_file(self, s3_key: str, user_id: str) -> Optional[bytes]:
        """
        Download file from S3.
        
        Args:
            s3_key: S3 key of the file
            user_id: User ID for ownership verification
            
        Returns:
            bytes: File content if found and accessible
        """
        try:
            # Verify user owns this file by checking the key structure
            if not s3_key.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to access unauthorized file: {s3_key}")
                return None
            
            # Determine bucket from key structure
            bucket = self._determine_bucket_from_key(s3_key)
            
            # Download file
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    self.s3_client.get_object,
                    {'Bucket': bucket, 'Key': s3_key}
                )
            
            content = response['Body'].read()
            
            logger.info(f"Successfully downloaded file from S3: {s3_key}")
            return content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found in S3: {s3_key}")
                return None
            else:
                logger.error(f"Failed to download file from S3: {e}")
                raise RuntimeError(f"S3 download failed: {e}")
        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise RuntimeError(f"Download failed: {e}")
    
    def _determine_bucket_from_key(self, s3_key: str) -> str:
        """
        Determine appropriate bucket from S3 key structure.
        
        Args:
            s3_key: S3 key path
            
        Returns:
            str: Bucket name
        """
        # Parse key to determine file type and bucket
        key_parts = s3_key.split('/')
        
        if len(key_parts) >= 4:
            file_type = key_parts[3]  # users/{user_id}/jobs/{job_id}/{file_type}/...
        elif len(key_parts) >= 3:
            file_type = key_parts[2]  # users/{user_id}/{file_type}/...
        else:
            file_type = 'temp'  # Default to temp bucket
        
        return self._get_bucket_for_type(file_type)
    
    def generate_presigned_url(self, bucket: str, key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for secure file access.
        
        Args:
            bucket: S3 bucket name
            key: S3 key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL
            
        Raises:
            RuntimeError: If URL generation fails
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise RuntimeError(f"Failed to generate presigned URL: {e}")
    
    def generate_presigned_upload_url(self, bucket: str, key: str, 
                                    content_type: str, expiration: int = 3600) -> Dict[str, Any]:
        """
        Generate presigned URL for direct upload to S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 key
            content_type: File content type
            expiration: URL expiration time in seconds
            
        Returns:
            Dict containing presigned URL and fields
        """
        try:
            response = self.s3_client.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Fields={'Content-Type': content_type},
                Conditions=[
                    {'Content-Type': content_type},
                    ['content-length-range', 1, 100 * 1024 * 1024]  # 1 byte to 100MB
                ],
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            raise RuntimeError(f"Failed to generate presigned upload URL: {e}")
    
    async def delete_file(self, s3_key: str, user_id: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 key of the file
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if file was deleted successfully
        """
        try:
            # Verify user owns this file
            if not s3_key.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to delete unauthorized file: {s3_key}")
                return False
            
            # Determine bucket from key
            bucket = self._determine_bucket_from_key(s3_key)
            
            # Delete file
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.delete_object,
                    {'Bucket': bucket, 'Key': s3_key}
                )
            
            logger.info(f"Successfully deleted file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    async def list_user_files(
        self,
        user_id: str,
        file_type: Optional[str] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 20
    ) -> PaginatedResponse:
        """
        List user's files from S3 with pagination.
        
        Args:
            user_id: User ID
            file_type: Optional file type filter
            job_id: Optional job ID filter
            page: Page number (1-based)
            items_per_page: Items per page
            
        Returns:
            PaginatedResponse: Paginated list of file metadata
        """
        try:
            # Build prefix for listing
            if job_id and file_type:
                prefix = f"users/{user_id}/jobs/{job_id}/{file_type}/"
                bucket = self._get_bucket_for_type(file_type)
                buckets_to_search = [bucket]
            elif job_id:
                prefix = f"users/{user_id}/jobs/{job_id}/"
                buckets_to_search = list(self.config.buckets.values())
            elif file_type:
                prefix = f"users/{user_id}/"
                bucket = self._get_bucket_for_type(file_type)
                buckets_to_search = [bucket]
            else:
                prefix = f"users/{user_id}/"
                buckets_to_search = list(self.config.buckets.values())
            
            all_files = []
            
            # Search in relevant buckets
            for bucket in buckets_to_search:
                try:
                    files = await self._list_objects_in_bucket(bucket, prefix, file_type)
                    all_files.extend(files)
                except Exception as e:
                    logger.warning(f"Failed to list objects in bucket {bucket}: {e}")
                    continue
            
            # Sort by last modified (newest first)
            all_files.sort(key=lambda x: x.get('LastModified', datetime.min), reverse=True)
            
            # Apply pagination
            total_count = len(all_files)
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_files = all_files[start_idx:end_idx]
            
            # Convert to FileMetadataResponse objects
            file_responses = []
            for file_obj in paginated_files:
                try:
                    file_response = await self._s3_object_to_file_metadata(file_obj, user_id)
                    if file_response:
                        file_responses.append(file_response)
                except Exception as e:
                    logger.warning(f"Failed to convert S3 object to metadata: {e}")
                    continue
            
            return PaginatedResponse(
                items=file_responses,
                pagination={
                    'page': page,
                    'items_per_page': items_per_page,
                    'total_items': total_count,
                    'total_pages': (total_count + items_per_page - 1) // items_per_page,
                    'has_next': end_idx < total_count,
                    'has_previous': page > 1
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to list user files: {e}")
            return PaginatedResponse(
                items=[],
                pagination={
                    'page': page,
                    'items_per_page': items_per_page,
                    'total_items': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_previous': False
                }
            )
    
    async def _list_objects_in_bucket(self, bucket: str, prefix: str, 
                                    file_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List objects in a specific S3 bucket with prefix.
        
        Args:
            bucket: S3 bucket name
            prefix: Key prefix to filter objects
            file_type_filter: Optional file type filter
            
        Returns:
            List of S3 object dictionaries
        """
        objects = []
        continuation_token = None
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            while True:
                try:
                    # Prepare list_objects_v2 parameters
                    params = {
                        'Bucket': bucket,
                        'Prefix': prefix,
                        'MaxKeys': 1000
                    }
                    
                    if continuation_token:
                        params['ContinuationToken'] = continuation_token
                    
                    # List objects
                    response = await loop.run_in_executor(
                        executor,
                        lambda: self.s3_client.list_objects_v2(**params)
                    )
                    
                    # Process objects
                    for obj in response.get('Contents', []):
                        # Apply file type filter if specified
                        if file_type_filter:
                            key_parts = obj['Key'].split('/')
                            if len(key_parts) >= 4:
                                obj_file_type = key_parts[3]
                            elif len(key_parts) >= 3:
                                obj_file_type = key_parts[2]
                            else:
                                obj_file_type = 'unknown'
                            
                            if obj_file_type != file_type_filter:
                                continue
                        
                        # Add bucket info to object
                        obj['Bucket'] = bucket
                        objects.append(obj)
                    
                    # Check if there are more objects
                    if not response.get('IsTruncated', False):
                        break
                    
                    continuation_token = response.get('NextContinuationToken')
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'NoSuchBucket':
                        logger.warning(f"Bucket {bucket} does not exist")
                        break
                    else:
                        raise
        
        return objects
    
    async def _s3_object_to_file_metadata(self, s3_obj: Dict[str, Any], 
                                        user_id: str) -> Optional[FileMetadataResponse]:
        """
        Convert S3 object to FileMetadataResponse.
        
        Args:
            s3_obj: S3 object dictionary
            user_id: User ID for URL generation
            
        Returns:
            FileMetadataResponse or None if conversion fails
        """
        try:
            key = s3_obj['Key']
            bucket = s3_obj['Bucket']
            
            # Extract metadata from S3 object
            try:
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    head_response = await loop.run_in_executor(
                        executor,
                        self.s3_client.head_object,
                        {'Bucket': bucket, 'Key': key}
                    )
                
                metadata = head_response.get('Metadata', {})
                content_type = head_response.get('ContentType', 'application/octet-stream')
                
            except Exception as e:
                logger.warning(f"Failed to get object metadata for {key}: {e}")
                metadata = {}
                content_type = 'application/octet-stream'
            
            # Extract information from key and metadata
            original_filename = metadata.get('original_filename', Path(key).name)
            file_type = metadata.get('file_type', 'unknown')
            
            # Generate download URL
            download_url = self.generate_presigned_url(bucket, key, expiration=3600)
            
            return FileMetadataResponse(
                id=key,  # Use S3 key as ID
                filename=Path(key).name,
                original_filename=original_filename,
                file_type=FileType(file_type) if file_type in [ft.value for ft in FileType] else FileType.DOCUMENT,
                mime_type=content_type,
                file_size=s3_obj.get('Size', 0),
                checksum=s3_obj.get('ETag', '').strip('"'),
                created_at=s3_obj.get('LastModified', datetime.utcnow()),
                download_url=download_url,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to convert S3 object to file metadata: {e}")
            return None
    
    async def get_file_metadata(self, s3_key: str, user_id: str) -> Optional[FileMetadataResponse]:
        """
        Get file metadata from S3.
        
        Args:
            s3_key: S3 key of the file
            user_id: User ID for ownership verification
            
        Returns:
            FileMetadataResponse if found and accessible
        """
        try:
            # Verify user owns this file
            if not s3_key.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to access unauthorized file: {s3_key}")
                return None
            
            # Determine bucket from key
            bucket = self._determine_bucket_from_key(s3_key)
            
            # Get object metadata
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    head_response = await loop.run_in_executor(
                        executor,
                        self.s3_client.head_object,
                        {'Bucket': bucket, 'Key': s3_key}
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        return None
                    raise
            
            # Create S3 object dict for conversion
            s3_obj = {
                'Key': s3_key,
                'Bucket': bucket,
                'Size': head_response.get('ContentLength', 0),
                'LastModified': head_response.get('LastModified', datetime.utcnow()),
                'ETag': head_response.get('ETag', '')
            }
            
            return await self._s3_object_to_file_metadata(s3_obj, user_id)
            
        except Exception as e:
            logger.error(f"Failed to get file metadata from S3: {e}")
            return None
    
    async def copy_file(self, source_key: str, dest_key: str, user_id: str) -> bool:
        """
        Copy file within S3.
        
        Args:
            source_key: Source S3 key
            dest_key: Destination S3 key
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if copy was successful
        """
        try:
            # Verify user owns both files
            if not (source_key.startswith(f"users/{user_id}/") and 
                   dest_key.startswith(f"users/{user_id}/")):
                logger.warning(f"User {user_id} attempted unauthorized file copy")
                return False
            
            # Determine buckets
            source_bucket = self._determine_bucket_from_key(source_key)
            dest_bucket = self._determine_bucket_from_key(dest_key)
            
            # Copy file
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.copy_object,
                    {
                        'CopySource': copy_source,
                        'Bucket': dest_bucket,
                        'Key': dest_key
                    }
                )
            
            logger.info(f"Successfully copied file from {source_key} to {dest_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file in S3: {e}")
            return False
    
    async def get_file_versions(self, s3_key: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a file (if versioning is enabled).
        
        Args:
            s3_key: S3 key of the file
            user_id: User ID for ownership verification
            
        Returns:
            List of file version information
        """
        try:
            # Verify user owns this file
            if not s3_key.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to access unauthorized file versions: {s3_key}")
                return []
            
            # Determine bucket from key
            bucket = self._determine_bucket_from_key(s3_key)
            
            # List object versions
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    self.s3_client.list_object_versions,
                    {'Bucket': bucket, 'Prefix': s3_key}
                )
            
            versions = []
            for version in response.get('Versions', []):
                if version['Key'] == s3_key:
                    versions.append({
                        'version_id': version.get('VersionId'),
                        'last_modified': version.get('LastModified'),
                        'size': version.get('Size'),
                        'is_latest': version.get('IsLatest', False),
                        'etag': version.get('ETag', '').strip('"')
                    })
            
            # Sort by last modified (newest first)
            versions.sort(key=lambda x: x['last_modified'], reverse=True)
            
            return versions
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.warning(f"Bucket does not exist for key: {s3_key}")
                return []
            else:
                logger.error(f"Failed to get file versions: {e}")
                return []
        except Exception as e:
            logger.error(f"Failed to get file versions: {e}")
            return []
    
    async def cleanup_expired_files(self, retention_days: int = 30, 
                                  file_type: Optional[str] = None) -> Dict[str, int]:
        """
        Clean up expired files from S3.
        
        Args:
            retention_days: Number of days to retain files
            file_type: Optional file type filter
            
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            cleanup_stats = {'files_cleaned': 0, 'total_size_cleaned': 0}
            
            # Determine buckets to clean
            if file_type:
                buckets_to_clean = [self._get_bucket_for_type(file_type)]
            else:
                buckets_to_clean = list(self.config.buckets.values())
            
            for bucket in buckets_to_clean:
                try:
                    bucket_stats = await self._cleanup_bucket(bucket, cutoff_date)
                    cleanup_stats['files_cleaned'] += bucket_stats['files_cleaned']
                    cleanup_stats['total_size_cleaned'] += bucket_stats['total_size_cleaned']
                except Exception as e:
                    logger.warning(f"Failed to cleanup bucket {bucket}: {e}")
                    continue
            
            logger.info(
                f"File cleanup completed: {cleanup_stats['files_cleaned']} files, "
                f"{cleanup_stats['total_size_cleaned']} bytes cleaned"
            )
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired files: {e}")
            return {'files_cleaned': 0, 'total_size_cleaned': 0}
    
    async def _cleanup_bucket(self, bucket: str, cutoff_date: datetime) -> Dict[str, int]:
        """
        Clean up expired files in a specific bucket.
        
        Args:
            bucket: S3 bucket name
            cutoff_date: Files older than this date will be deleted
            
        Returns:
            Dictionary with cleanup statistics for the bucket
        """
        stats = {'files_cleaned': 0, 'total_size_cleaned': 0}
        
        try:
            # List all objects in bucket
            objects = await self._list_objects_in_bucket(bucket, '')
            
            # Find expired objects
            expired_objects = [
                obj for obj in objects 
                if obj.get('LastModified', datetime.utcnow()) < cutoff_date
            ]
            
            # Delete expired objects in batches
            batch_size = 1000  # S3 delete limit
            for i in range(0, len(expired_objects), batch_size):
                batch = expired_objects[i:i + batch_size]
                
                # Prepare delete request
                delete_objects = {
                    'Objects': [{'Key': obj['Key']} for obj in batch]
                }
                
                # Delete batch
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    response = await loop.run_in_executor(
                        executor,
                        self.s3_client.delete_objects,
                        {'Bucket': bucket, 'Delete': delete_objects}
                    )
                
                # Update statistics
                deleted_count = len(response.get('Deleted', []))
                deleted_size = sum(obj.get('Size', 0) for obj in batch[:deleted_count])
                
                stats['files_cleaned'] += deleted_count
                stats['total_size_cleaned'] += deleted_size
                
                # Log errors if any
                for error in response.get('Errors', []):
                    logger.warning(f"Failed to delete {error['Key']}: {error['Message']}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup bucket {bucket}: {e}")
        
        return stats


# Dependency function for FastAPI
async def get_aws_s3_file_service(aws_config: AWSConfig = None) -> AWSS3FileService:
    """
    Get AWS S3 file service instance.
    
    Args:
        aws_config: AWS configuration (will be loaded if not provided)
        
    Returns:
        AWSS3FileService: Configured S3 file service
    """
    if not aws_config:
        from src.config.aws_config import AWSConfigManager
        aws_config = AWSConfigManager.load_config()
    
    return AWSS3FileService(aws_config)
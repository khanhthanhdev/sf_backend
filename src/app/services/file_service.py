"""
File management service for handling file operations.

This service provides high-level file management operations including
upload handling, storage management, metadata tracking, and cleanup.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from redis.asyncio import Redis

from ..core.redis import get_redis, RedisKeyManager, redis_json_get, redis_json_set
from ..utils.file_utils import (
    FileManager, FileMetadata, FileValidationResult,
    validate_upload_file, store_upload_file, delete_stored_file,
    cleanup_old_files, generate_file_url
)
from ..utils.file_cache import (
    cache_file_metadata, get_cached_file_metadata,
    track_file_access, get_file_access_statistics
)
from ..models.common import PaginatedResponse

logger = logging.getLogger(__name__)


class FileService:
    """Service for file management operations."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize file service."""
        self.redis_client = redis_client
        self.file_manager = FileManager()
    
    async def upload_file(
        self,
        file: UploadFile,
        user_id: str,
        file_type: Optional[str] = None,
        subdirectory: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload and store a file with validation.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID for file ownership
            file_type: Optional file type override
            subdirectory: Optional subdirectory for organization
            
        Returns:
            FileMetadata with storage information
            
        Raises:
            HTTPException: If validation or storage fails
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
            
            # Store file
            file_metadata = await store_upload_file(
                file=file,
                user_id=user_id,
                file_type=file_type,
                subdirectory=subdirectory
            )
            
            # Store metadata in Redis
            if self.redis_client:
                await self._store_file_metadata_redis(file_metadata, user_id)
            
            logger.info(
                "File uploaded successfully",
                filename=file_metadata.filename,
                user_id=user_id,
                file_type=file_type,
                file_size=file_metadata.file_size
            )
            
            return file_metadata
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {str(e)}"
            )
    
    async def _store_file_metadata_redis(self, file_metadata: FileMetadata, user_id: str) -> None:
        """Store file metadata in Redis."""
        try:
            # Generate file ID from filename
            file_id = Path(file_metadata.filename).stem
            
            # Store file metadata
            file_key = RedisKeyManager.file_key(file_id)
            await redis_json_set(self.redis_client, file_key, file_metadata.dict())
            
            # Add to user's file index
            user_files_key = RedisKeyManager.user_files_key(user_id)
            await self.redis_client.sadd(user_files_key, file_id)
            
            # Set expiration for metadata (30 days)
            await self.redis_client.expire(file_key, 30 * 24 * 3600)
            
        except Exception as e:
            logger.warning(f"Failed to store file metadata in Redis: {e}")
    
    async def get_file_metadata(self, file_id: str, user_id: str) -> Optional[FileMetadata]:
        """
        Get file metadata by ID with caching.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            FileMetadata if found and accessible
        """
        try:
            if not self.redis_client:
                return None
            
            # Check if user owns this file
            user_files_key = RedisKeyManager.user_files_key(user_id)
            if not await self.redis_client.sismember(user_files_key, file_id):
                return None
            
            # Try to get from cache first
            cached_data = await get_cached_file_metadata(file_id)
            if cached_data:
                return FileMetadata(**cached_data)
            
            # Get file metadata from Redis
            file_key = RedisKeyManager.file_key(file_id)
            file_data = await redis_json_get(self.redis_client, file_key)
            
            if file_data:
                file_metadata = FileMetadata(**file_data)
                
                # Cache the metadata
                await cache_file_metadata(file_id, file_data)
                
                return file_metadata
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None
    
    async def get_user_files(
        self,
        user_id: str,
        file_type: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 20
    ) -> PaginatedResponse:
        """
        Get paginated list of user's files.
        
        Args:
            user_id: User ID
            file_type: Optional file type filter
            page: Page number (1-based)
            items_per_page: Items per page
            
        Returns:
            PaginatedResponse with file metadata
        """
        try:
            if not self.redis_client:
                return PaginatedResponse(data=[], total_count=0, page=page, items_per_page=items_per_page)
            
            # Get user's file IDs
            user_files_key = RedisKeyManager.user_files_key(user_id)
            file_ids = await self.redis_client.smembers(user_files_key)
            
            if not file_ids:
                return PaginatedResponse(data=[], total_count=0, page=page, items_per_page=items_per_page)
            
            # Get file metadata for each file
            files = []
            for file_id in file_ids:
                file_key = RedisKeyManager.file_key(file_id.decode() if isinstance(file_id, bytes) else file_id)
                file_data = await redis_json_get(self.redis_client, file_key)
                
                if file_data:
                    file_metadata = FileMetadata(**file_data)
                    
                    # Apply file type filter
                    if not file_type or file_metadata.file_type == file_type:
                        files.append(file_metadata)
            
            # Sort by creation date (newest first)
            files.sort(key=lambda x: x.created_at, reverse=True)
            
            # Apply pagination
            total_count = len(files)
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_files = files[start_idx:end_idx]
            
            return PaginatedResponse(
                data=paginated_files,
                total_count=total_count,
                page=page,
                items_per_page=items_per_page
            )
            
        except Exception as e:
            logger.error(f"Failed to get user files: {e}")
            return PaginatedResponse(data=[], total_count=0, page=page, items_per_page=items_per_page)
    
    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete a file and its metadata.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            True if file was deleted successfully
        """
        try:
            # Get file metadata first
            file_metadata = await self.get_file_metadata(file_id, user_id)
            if not file_metadata:
                return False
            
            # Delete physical file
            file_deleted = await delete_stored_file(file_metadata.file_path)
            
            if file_deleted and self.redis_client:
                # Remove from Redis
                file_key = RedisKeyManager.file_key(file_id)
                await self.redis_client.delete(file_key)
                
                # Remove from user's file index
                user_files_key = RedisKeyManager.user_files_key(user_id)
                await self.redis_client.srem(user_files_key, file_id)
            
            logger.info(
                "File deleted successfully",
                file_id=file_id,
                user_id=user_id,
                physical_deleted=file_deleted
            )
            
            return file_deleted
            
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def generate_download_url(self, file_id: str, user_id: str) -> Optional[str]:
        """
        Generate secure download URL for a file.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            Secure download URL if file exists and is accessible
        """
        try:
            file_metadata = await self.get_file_metadata(file_id, user_id)
            if not file_metadata:
                return None
            
            # Use secure URL generation with expiration
            from ..utils.secure_url_generator import generate_secure_file_url
            return generate_secure_file_url(
                file_id=file_id,
                user_id=user_id,
                file_type=file_metadata.file_type,
                expires_in=3600,  # 1 hour expiration
                inline=False
            )
            
        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            return None
    
    async def generate_file_urls(self, file_id: str, user_id: str) -> Optional[Dict[str, str]]:
        """
        Generate all available secure URLs for a file.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            Dictionary with all available secure URLs
        """
        try:
            file_metadata = await self.get_file_metadata(file_id, user_id)
            if not file_metadata:
                return None
            
            from ..utils.secure_url_generator import (
                generate_secure_file_url,
                generate_secure_thumbnail_url,
                generate_secure_streaming_url
            )
            
            urls = {
                "download": generate_secure_file_url(
                    file_id=file_id,
                    user_id=user_id,
                    file_type=file_metadata.file_type,
                    expires_in=3600,
                    inline=False
                ),
                "download_inline": generate_secure_file_url(
                    file_id=file_id,
                    user_id=user_id,
                    file_type=file_metadata.file_type,
                    expires_in=3600,
                    inline=True
                ),
            }
            
            # Add type-specific URLs
            if file_metadata.file_type in ['image', 'video']:
                urls.update({
                    "thumbnail_small": generate_secure_thumbnail_url(file_id, user_id, "small"),
                    "thumbnail_medium": generate_secure_thumbnail_url(file_id, user_id, "medium"),
                    "thumbnail_large": generate_secure_thumbnail_url(file_id, user_id, "large")
                })
            
            if file_metadata.file_type in ['video', 'audio']:
                urls["stream"] = generate_secure_streaming_url(file_id, user_id)
            
            return urls
            
        except Exception as e:
            logger.error(f"Failed to generate file URLs: {e}")
            return None
    
    async def cleanup_expired_files(self, retention_days: int = 30) -> Dict[str, int]:
        """
        Clean up expired files and metadata.
        
        Args:
            retention_days: Number of days to retain files
            
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Clean up physical files
            files_cleaned = await cleanup_old_files(retention_days)
            
            # Clean up Redis metadata
            metadata_cleaned = 0
            if self.redis_client:
                metadata_cleaned = await self._cleanup_expired_metadata(retention_days)
            
            logger.info(
                "File cleanup completed",
                files_cleaned=files_cleaned,
                metadata_cleaned=metadata_cleaned,
                retention_days=retention_days
            )
            
            return {
                "files_cleaned": files_cleaned,
                "metadata_cleaned": metadata_cleaned,
                "retention_days": retention_days
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired files: {e}")
            return {"files_cleaned": 0, "metadata_cleaned": 0, "retention_days": retention_days}
    
    async def _cleanup_expired_metadata(self, retention_days: int) -> int:
        """Clean up expired file metadata from Redis."""
        cleanup_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        try:
            # Get all file keys
            file_keys = await self.redis_client.keys("files:*")
            
            for key in file_keys:
                try:
                    file_data = await redis_json_get(self.redis_client, key.decode() if isinstance(key, bytes) else key)
                    if file_data:
                        file_metadata = FileMetadata(**file_data)
                        
                        if file_metadata.created_at < cutoff_date:
                            # Delete metadata
                            await self.redis_client.delete(key)
                            
                            # Remove from user index
                            file_id = key.decode().split(':')[-1] if isinstance(key, bytes) else key.split(':')[-1]
                            user_files_pattern = f"user_files:*"
                            user_keys = await self.redis_client.keys(user_files_pattern)
                            
                            for user_key in user_keys:
                                await self.redis_client.srem(user_key, file_id)
                            
                            cleanup_count += 1
                            
                except Exception as e:
                    logger.warning(f"Failed to cleanup metadata for key {key}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired metadata: {e}")
        
        return cleanup_count
    
    async def get_file_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get file statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with file statistics
        """
        try:
            if not self.redis_client:
                return {}
            
            # Get user's files
            user_files_key = RedisKeyManager.user_files_key(user_id)
            file_ids = await self.redis_client.smembers(user_files_key)
            
            if not file_ids:
                return {
                    "total_files": 0,
                    "total_size": 0,
                    "by_type": {},
                    "recent_uploads": 0
                }
            
            # Analyze files
            total_files = 0
            total_size = 0
            by_type = {}
            recent_uploads = 0
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            
            for file_id in file_ids:
                file_key = RedisKeyManager.file_key(file_id.decode() if isinstance(file_id, bytes) else file_id)
                file_data = await redis_json_get(self.redis_client, file_key)
                
                if file_data:
                    file_metadata = FileMetadata(**file_data)
                    
                    total_files += 1
                    total_size += file_metadata.file_size
                    
                    # Count by type
                    file_type = file_metadata.file_type
                    by_type[file_type] = by_type.get(file_type, 0) + 1
                    
                    # Count recent uploads
                    if file_metadata.created_at > recent_cutoff:
                        recent_uploads += 1
            
            return {
                "total_files": total_files,
                "total_size": total_size,
                "by_type": by_type,
                "recent_uploads": recent_uploads
            }
            
        except Exception as e:
            logger.error(f"Failed to get file stats: {e}")
            return {}


# Dependency function for FastAPI
async def get_file_service(redis_client: Redis = None) -> FileService:
    """Get file service instance."""
    if not redis_client:
        redis_client = await get_redis()
    return FileService(redis_client)
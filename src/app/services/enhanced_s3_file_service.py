"""
Enhanced AWS S3 File Service with Metadata Management and Versioning.

This service extends the basic S3 file service with comprehensive metadata
management, versioning support, and advanced file organization features.
"""

import logging
import asyncio
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from .aws_s3_file_service import AWSS3FileService
from .s3_metadata_manager import S3MetadataManager, S3FileMetadata, FileVersion, FileVersionStatus
from ..models.file import FileType, FileMetadataResponse, FileUploadResponse
from ..models.common import PaginatedResponse
from src.config.aws_config import AWSConfig

logger = logging.getLogger(__name__)


class EnhancedS3FileService(AWSS3FileService):
    """Enhanced S3 file service with metadata management and versioning."""
    
    def __init__(self, aws_config: AWSConfig):
        """
        Initialize enhanced S3 file service.
        
        Args:
            aws_config: AWS configuration object
        """
        super().__init__(aws_config)
        self.metadata_manager = S3MetadataManager(aws_config)
        
        logger.info("Initialized EnhancedS3FileService with metadata management")
    
    async def upload_file_with_metadata(
        self,
        file: UploadFile,
        user_id: str,
        file_type: Optional[str] = None,
        job_id: Optional[str] = None,
        scene_number: Optional[int] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        progress_callback=None
    ) -> FileUploadResponse:
        """
        Upload file with comprehensive metadata management.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID for file ownership
            file_type: Optional file type override
            job_id: Optional job ID for organization
            scene_number: Optional scene number for video files
            tags: Optional list of tags for organization
            custom_metadata: Optional custom metadata dictionary
            description: Optional file description
            progress_callback: Optional progress callback function
            
        Returns:
            FileUploadResponse: Upload result with metadata
        """
        try:
            # First upload the file using the base service
            upload_response = await super().upload_file(
                file, user_id, file_type, job_id, scene_number, progress_callback
            )
            
            # Calculate file checksum
            await file.seek(0)
            file_content = await file.read()
            checksum = hashlib.sha256(file_content).hexdigest()
            
            # Create comprehensive metadata
            metadata = S3FileMetadata(
                file_id=upload_response.file_id,  # S3 key
                user_id=user_id,
                job_id=job_id,
                scene_number=scene_number,
                original_filename=file.filename,
                file_type=upload_response.file_type.value,
                mime_type=file.content_type or 'application/octet-stream',
                file_size=upload_response.file_size,
                s3_bucket=self._determine_bucket_from_key(upload_response.file_id),
                s3_key=upload_response.file_id,
                version_id=None,  # Will be set if S3 versioning is enabled
                checksum=checksum,
                created_at=upload_response.created_at,
                updated_at=upload_response.created_at,
                status=FileVersionStatus.ACTIVE,
                tags=tags or [],
                custom_metadata=custom_metadata or {},
                access_count=0,
                last_accessed=None
            )
            
            # Add description to custom metadata if provided
            if description:
                metadata.custom_metadata['description'] = description
            
            # Store metadata
            await self.metadata_manager.store_file_metadata(metadata)
            
            # Create initial version entry
            initial_version = FileVersion(
                version_id=f"v1_{int(datetime.utcnow().timestamp())}",
                version_number=1,
                created_at=upload_response.created_at,
                file_size=upload_response.file_size,
                checksum=checksum,
                is_current=True,
                change_description="Initial upload",
                created_by=user_id
            )
            
            await self.metadata_manager.create_file_version(upload_response.file_id, initial_version)
            
            logger.info(
                f"Successfully uploaded file with metadata: {upload_response.file_id}",
                extra={
                    "user_id": user_id,
                    "file_type": file_type,
                    "tags": tags,
                    "has_custom_metadata": bool(custom_metadata)
                }
            )
            
            return upload_response
            
        except Exception as e:
            logger.error(f"Failed to upload file with metadata: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file with metadata: {str(e)}"
            )
    
    async def get_file_with_metadata(self, file_id: str, user_id: str) -> Optional[FileMetadataResponse]:
        """
        Get file information with comprehensive metadata.
        
        Args:
            file_id: File identifier (S3 key)
            user_id: User ID for ownership verification
            
        Returns:
            FileMetadataResponse with comprehensive metadata
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to access unauthorized file: {file_id}")
                return None
            
            # Get metadata from metadata manager
            metadata = await self.metadata_manager.get_file_metadata(file_id)
            if not metadata:
                # Fallback to basic S3 metadata
                return await super().get_file_metadata(file_id, user_id)
            
            # Track file access
            await self.metadata_manager.track_file_access(file_id, user_id)
            
            # Generate download URL
            download_url = self.generate_presigned_url(metadata.s3_bucket, metadata.s3_key)
            
            # Get current version info
            current_version = await self.metadata_manager.get_current_version(file_id)
            
            # Build comprehensive metadata response
            response_metadata = metadata.custom_metadata.copy()
            response_metadata.update({
                'tags': metadata.tags,
                'access_count': metadata.access_count,
                'last_accessed': metadata.last_accessed.isoformat() if metadata.last_accessed else None,
                'status': metadata.status.value,
                'current_version': current_version.version_number if current_version else 1,
                'total_versions': len(await self.metadata_manager.get_file_versions(file_id))
            })
            
            return FileMetadataResponse(
                id=metadata.file_id,
                filename=Path(metadata.s3_key).name,
                original_filename=metadata.original_filename,
                file_type=FileType(metadata.file_type),
                mime_type=metadata.mime_type,
                file_size=metadata.file_size,
                checksum=metadata.checksum,
                created_at=metadata.created_at,
                download_url=download_url,
                metadata=response_metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to get file with metadata: {e}")
            return None
    
    async def update_file_metadata(
        self,
        file_id: str,
        user_id: str,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update file metadata.
        
        Args:
            file_id: File identifier (S3 key)
            user_id: User ID for ownership verification
            tags: Optional new tags
            custom_metadata: Optional custom metadata updates
            description: Optional description update
            
        Returns:
            bool: True if metadata was updated successfully
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to update unauthorized file: {file_id}")
                return False
            
            # Prepare updates
            updates = {}
            
            if tags is not None:
                updates['tags'] = tags
            
            if custom_metadata is not None:
                # Get existing metadata to merge
                existing_metadata = await self.metadata_manager.get_file_metadata(file_id)
                if existing_metadata:
                    merged_metadata = existing_metadata.custom_metadata.copy()
                    merged_metadata.update(custom_metadata)
                    updates['custom_metadata'] = merged_metadata
                else:
                    updates['custom_metadata'] = custom_metadata
            
            if description is not None:
                # Add description to custom metadata
                existing_metadata = await self.metadata_manager.get_file_metadata(file_id)
                if existing_metadata:
                    merged_metadata = existing_metadata.custom_metadata.copy()
                    merged_metadata['description'] = description
                    updates['custom_metadata'] = merged_metadata
                else:
                    updates['custom_metadata'] = {'description': description}
            
            if not updates:
                return True  # No updates to apply
            
            # Apply updates
            return await self.metadata_manager.update_file_metadata(file_id, updates)
            
        except Exception as e:
            logger.error(f"Failed to update file metadata: {e}")
            return False
    
    async def create_file_version(
        self,
        file_id: str,
        user_id: str,
        new_file: UploadFile,
        change_description: Optional[str] = None
    ) -> Optional[FileVersion]:
        """
        Create a new version of an existing file.
        
        Args:
            file_id: Original file identifier (S3 key)
            user_id: User ID for ownership verification
            new_file: New file version to upload
            change_description: Optional description of changes
            
        Returns:
            FileVersion object if successful
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to version unauthorized file: {file_id}")
                return None
            
            # Get existing metadata
            existing_metadata = await self.metadata_manager.get_file_metadata(file_id)
            if not existing_metadata:
                logger.warning(f"Cannot create version for non-existent file: {file_id}")
                return None
            
            # Get existing versions to determine next version number
            existing_versions = await self.metadata_manager.get_file_versions(file_id)
            next_version_number = max(v.version_number for v in existing_versions) + 1 if existing_versions else 1
            
            # Generate new S3 key for the version
            key_parts = file_id.split('/')
            filename = key_parts[-1]
            base_path = '/'.join(key_parts[:-1])
            version_filename = f"v{next_version_number}_{filename}"
            new_s3_key = f"{base_path}/{version_filename}"
            
            # Upload new version
            bucket = existing_metadata.s3_bucket
            
            # Calculate checksum
            await new_file.seek(0)
            file_content = await new_file.read()
            checksum = hashlib.sha256(file_content).hexdigest()
            await new_file.seek(0)
            
            # Upload to S3
            extra_args = {
                'Metadata': {
                    'user_id': user_id,
                    'original_file_id': file_id,
                    'version_number': str(next_version_number),
                    'file_type': existing_metadata.file_type,
                    'original_filename': new_file.filename,
                    'upload_timestamp': str(datetime.utcnow())
                },
                'ContentType': new_file.content_type or existing_metadata.mime_type
            }
            
            loop = asyncio.get_event_loop()
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self._upload_with_retry,
                    new_file.file, bucket, new_s3_key, extra_args, self.transfer_config,
                    new_file.filename, len(file_content), None
                )
            
            # Create version entry
            new_version = FileVersion(
                version_id=f"v{next_version_number}_{int(datetime.utcnow().timestamp())}",
                version_number=next_version_number,
                created_at=datetime.utcnow(),
                file_size=len(file_content),
                checksum=checksum,
                is_current=True,
                change_description=change_description or f"Version {next_version_number}",
                created_by=user_id
            )
            
            # Store version
            success = await self.metadata_manager.create_file_version(file_id, new_version)
            
            if success:
                # Update main file metadata to point to new version
                await self.metadata_manager.update_file_metadata(file_id, {
                    'file_size': len(file_content),
                    'checksum': checksum,
                    's3_key': new_s3_key,  # Update to point to latest version
                    'updated_at': datetime.utcnow()
                })
                
                logger.info(f"Successfully created version {next_version_number} for file: {file_id}")
                return new_version
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create file version: {e}")
            return None
    
    async def list_file_versions(self, file_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        List all versions of a file.
        
        Args:
            file_id: File identifier (S3 key)
            user_id: User ID for ownership verification
            
        Returns:
            List of version information dictionaries
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to list versions of unauthorized file: {file_id}")
                return []
            
            versions = await self.metadata_manager.get_file_versions(file_id)
            
            version_list = []
            for version in versions:
                version_info = {
                    'version_id': version.version_id,
                    'version_number': version.version_number,
                    'created_at': version.created_at.isoformat(),
                    'file_size': version.file_size,
                    'checksum': version.checksum,
                    'is_current': version.is_current,
                    'change_description': version.change_description,
                    'created_by': version.created_by
                }
                
                # Generate download URL for this version if it's not the current one
                if not version.is_current:
                    # Construct version-specific S3 key
                    key_parts = file_id.split('/')
                    filename = key_parts[-1]
                    base_path = '/'.join(key_parts[:-1])
                    version_key = f"{base_path}/v{version.version_number}_{filename}"
                    
                    bucket = self._determine_bucket_from_key(file_id)
                    version_info['download_url'] = self.generate_presigned_url(bucket, version_key)
                
                version_list.append(version_info)
            
            return version_list
            
        except Exception as e:
            logger.error(f"Failed to list file versions: {e}")
            return []
    
    async def restore_file_version(self, file_id: str, version_id: str, user_id: str) -> bool:
        """
        Restore a specific version as the current version.
        
        Args:
            file_id: File identifier (S3 key)
            version_id: Version ID to restore
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if version was restored successfully
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to restore version of unauthorized file: {file_id}")
                return False
            
            return await self.metadata_manager.restore_file_version(file_id, version_id)
            
        except Exception as e:
            logger.error(f"Failed to restore file version: {e}")
            return False
    
    async def search_files(
        self,
        user_id: str,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 20
    ) -> PaginatedResponse:
        """
        Search files with advanced filtering.
        
        Args:
            user_id: User ID
            query: Text search query
            file_type: File type filter
            tags: Tags filter
            date_from: Start date filter
            date_to: End date filter
            job_id: Job ID filter
            page: Page number
            items_per_page: Items per page
            
        Returns:
            PaginatedResponse with search results
        """
        try:
            # Build search filters
            filters = {}
            
            if file_type:
                filters['file_type'] = file_type
            
            if tags:
                filters['tags'] = tags
            
            if date_from:
                filters['date_from'] = date_from.isoformat()
            
            if date_to:
                filters['date_to'] = date_to.isoformat()
            
            if job_id:
                filters['job_id'] = job_id
            
            # Search using metadata manager
            all_results = await self.metadata_manager.search_files_by_metadata(
                user_id, filters, limit=items_per_page * 10  # Get more for text filtering
            )
            
            # Apply text search if provided
            if query:
                query_lower = query.lower()
                filtered_results = []
                
                for metadata in all_results:
                    # Search in filename, description, and tags
                    searchable_text = ' '.join([
                        metadata.original_filename.lower(),
                        metadata.custom_metadata.get('description', '').lower(),
                        ' '.join(metadata.tags).lower()
                    ])
                    
                    if query_lower in searchable_text:
                        filtered_results.append(metadata)
                
                all_results = filtered_results
            
            # Apply pagination
            total_count = len(all_results)
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_results = all_results[start_idx:end_idx]
            
            # Convert to FileMetadataResponse objects
            file_responses = []
            for metadata in paginated_results:
                try:
                    download_url = self.generate_presigned_url(metadata.s3_bucket, metadata.s3_key)
                    
                    response_metadata = metadata.custom_metadata.copy()
                    response_metadata.update({
                        'tags': metadata.tags,
                        'access_count': metadata.access_count,
                        'status': metadata.status.value
                    })
                    
                    file_response = FileMetadataResponse(
                        id=metadata.file_id,
                        filename=Path(metadata.s3_key).name,
                        original_filename=metadata.original_filename,
                        file_type=FileType(metadata.file_type),
                        mime_type=metadata.mime_type,
                        file_size=metadata.file_size,
                        checksum=metadata.checksum,
                        created_at=metadata.created_at,
                        download_url=download_url,
                        metadata=response_metadata
                    )
                    
                    file_responses.append(file_response)
                    
                except Exception as e:
                    logger.warning(f"Failed to convert metadata to response: {e}")
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
            logger.error(f"Failed to search files: {e}")
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
    
    async def get_user_file_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive file statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with comprehensive file statistics
        """
        try:
            return await self.metadata_manager.get_file_statistics(user_id)
        except Exception as e:
            logger.error(f"Failed to get user file statistics: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'by_type': {},
                'by_status': {},
                'recent_uploads': 0,
                'total_versions': 0
            }
    
    async def delete_file_with_metadata(self, file_id: str, user_id: str) -> bool:
        """
        Delete file and all associated metadata and versions.
        
        Args:
            file_id: File identifier (S3 key)
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if file was deleted successfully
        """
        try:
            # Verify user owns this file
            if not file_id.startswith(f"users/{user_id}/"):
                logger.warning(f"User {user_id} attempted to delete unauthorized file: {file_id}")
                return False
            
            # Get all versions to delete
            versions = await self.metadata_manager.get_file_versions(file_id)
            
            # Delete all version files from S3
            bucket = self._determine_bucket_from_key(file_id)
            
            for version in versions:
                if not version.is_current:
                    # Construct version-specific S3 key
                    key_parts = file_id.split('/')
                    filename = key_parts[-1]
                    base_path = '/'.join(key_parts[:-1])
                    version_key = f"{base_path}/v{version.version_number}_{filename}"
                    
                    try:
                        await super().delete_file(version_key, user_id)
                    except Exception as e:
                        logger.warning(f"Failed to delete version file {version_key}: {e}")
            
            # Delete main file
            main_deleted = await super().delete_file(file_id, user_id)
            
            # Delete metadata
            metadata_deleted = await self.metadata_manager.delete_file_metadata(file_id)
            
            success = main_deleted and metadata_deleted
            
            if success:
                logger.info(f"Successfully deleted file with all metadata and versions: {file_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete file with metadata: {e}")
            return False


# Dependency function for FastAPI
async def get_enhanced_s3_file_service(aws_config: AWSConfig = None) -> EnhancedS3FileService:
    """
    Get enhanced S3 file service instance.
    
    Args:
        aws_config: AWS configuration (will be loaded if not provided)
        
    Returns:
        EnhancedS3FileService: Configured enhanced S3 file service
    """
    if not aws_config:
        from src.config.aws_config import AWSConfigManager
        aws_config = AWSConfigManager.load_config()
    
    return EnhancedS3FileService(aws_config)
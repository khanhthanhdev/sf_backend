"""
File Management Use Case - Orchestrates comprehensive file management operations.

This application service coordinates multiple domain services to implement
complete file management workflows.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from ...models.file import FileMetadataResponse as FileMetadata, FileUploadRequest as UploadFileRequest
from ...models.user import ClerkUser
from ...schemas.common import PaginationRequest
from ..interfaces.application import IFileManagementUseCase
from ..interfaces.domain import (
    IFileProcessingService, 
    IUserManagementService,
    INotificationService
)
from ..interfaces.infrastructure import IStorageService, IMetricsService, ILoggingService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class FileManagementUseCase(IFileManagementUseCase):
    """Use case for comprehensive file management operations."""
    
    def __init__(
        self,
        file_processing_service: IFileProcessingService,
        user_management_service: IUserManagementService,
        notification_service: INotificationService,
        storage_service: IStorageService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService
    ):
        self.file_processing_service = file_processing_service
        self.user_management_service = user_management_service
        self.notification_service = notification_service
        self.storage_service = storage_service
        self.metrics_service = metrics_service
        self.logging_service = logging_service
    
    @property
    def service_name(self) -> str:
        return "FileManagementUseCase"
    
    async def upload_file(
        self, 
        request: UploadFileRequest, 
        user: ClerkUser
    ) -> ServiceResult[FileMetadata]:
        """
        Complete file upload workflow including:
        - Validation
        - Virus scanning
        - Storage
        - Metadata creation
        - Quota checking
        """
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the upload start
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="file_upload_started",
                metadata={
                    "correlation_id": correlation_id,
                    "filename": request.filename,
                    "file_size": request.file_size,
                    "content_type": request.content_type
                }
            )
            
            # Step 1: Validate user permissions
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "file_upload"
            )
            if not permission_result.success:
                await self.metrics_service.increment_counter(
                    "file_upload_permission_denied",
                    tags={"subscription_tier": user.subscription_tier}
                )
                return permission_result
            
            # Step 2: Check storage quota
            quota_result = await self.user_management_service.check_storage_quota(
                user, request.file_size
            )
            if not quota_result.success:
                await self.metrics_service.increment_counter(
                    "file_upload_quota_exceeded",
                    tags={"subscription_tier": user.subscription_tier}
                )
                return quota_result
            
            # Step 3: Validate file through file processing service
            validation_result = await self.file_processing_service.validate_file_upload(request)
            if not validation_result.success:
                await self.metrics_service.increment_counter("file_upload_validation_failed")
                return validation_result
            
            # Step 4: Scan for viruses/malware
            scan_result = await self.file_processing_service.scan_file_for_threats(request)
            if not scan_result.success:
                await self.metrics_service.increment_counter("file_upload_security_failed")
                return scan_result
            
            # Step 5: Upload to storage
            storage_result = await self.storage_service.store_file(
                request.file_data,
                f"user_{user.clerk_user_id}/{request.filename}",
                request.content_type
            )
            if not storage_result.success:
                return storage_result
            
            # Step 6: Create file metadata
            metadata_result = await self.file_processing_service.create_file_metadata(
                request, user.clerk_user_id, storage_result.data
            )
            if not metadata_result.success:
                # Cleanup storage if metadata creation fails
                await self.storage_service.delete_file(storage_result.data["file_path"])
                return metadata_result
            
            file_metadata = metadata_result.data
            
            # Step 7: Update user storage usage
            await self.user_management_service.update_storage_usage(
                user, request.file_size, increment=True
            )
            
            # Step 8: Send notification
            await self.notification_service.send_file_upload_notification(user, file_metadata)
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "files_uploaded",
                tags={
                    "user_tier": user.subscription_tier,
                    "file_type": request.content_type,
                    "file_size_mb": str(request.file_size // (1024 * 1024))
                }
            )
            
            await self.metrics_service.record_histogram(
                "file_upload_size_bytes",
                request.file_size,
                tags={"user_tier": user.subscription_tier}
            )
            
            return ServiceResult.success(file_metadata)
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("file_upload_errors")
            return ServiceResult.error(
                error=f"Failed to upload file: {str(e)}",
                error_code="FILE_UPLOAD_ERROR"
            )
    
    async def download_file(
        self, 
        file_id: str, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Download file with permission checking."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the download request
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="file_download_requested",
                metadata={
                    "correlation_id": correlation_id,
                    "file_id": file_id
                }
            )
            
            # Step 1: Get file metadata and validate ownership
            metadata_result = await self.file_processing_service.get_file_metadata(file_id, user.clerk_user_id)
            if not metadata_result.success:
                return metadata_result
            
            file_metadata = metadata_result.data
            
            # Step 2: Validate download permissions
            permission_result = await self.user_management_service.validate_file_access(
                user, file_metadata, "download"
            )
            if not permission_result.success:
                await self.metrics_service.increment_counter("file_download_permission_denied")
                return permission_result
            
            # Step 3: Generate download URL or get file data
            download_result = await self.storage_service.generate_download_url(
                file_metadata.storage_path,
                expiration_hours=24
            )
            if not download_result.success:
                return download_result
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "files_downloaded",
                tags={
                    "user_tier": user.subscription_tier,
                    "file_type": file_metadata.content_type
                }
            )
            
            return ServiceResult.success({
                "file_metadata": file_metadata,
                "download_url": download_result.data["url"],
                "expires_at": download_result.data["expires_at"]
            })
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("file_download_errors")
            return ServiceResult.error(
                error=f"Failed to download file: {str(e)}",
                error_code="FILE_DOWNLOAD_ERROR"
            )
    
    async def delete_file(
        self, 
        file_id: str, 
        user: ClerkUser
    ) -> ServiceResult[bool]:
        """Delete file with cleanup and permission checking."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the deletion request
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="file_deletion_requested",
                metadata={
                    "correlation_id": correlation_id,
                    "file_id": file_id
                }
            )
            
            # Step 1: Get file metadata and validate ownership
            metadata_result = await self.file_processing_service.get_file_metadata(file_id, user.clerk_user_id)
            if not metadata_result.success:
                return metadata_result
            
            file_metadata = metadata_result.data
            
            # Step 2: Validate deletion permissions
            permission_result = await self.user_management_service.validate_file_access(
                user, file_metadata, "delete"
            )
            if not permission_result.success:
                await self.metrics_service.increment_counter("file_deletion_permission_denied")
                return permission_result
            
            # Step 3: Delete from storage
            storage_delete_result = await self.storage_service.delete_file(file_metadata.storage_path)
            if not storage_delete_result.success:
                return storage_delete_result
            
            # Step 4: Delete metadata
            metadata_delete_result = await self.file_processing_service.delete_file_metadata(file_id)
            if not metadata_delete_result.success:
                # Note: Storage file is already deleted, but metadata deletion failed
                logger.warning(f"Storage deleted but metadata deletion failed for file {file_id}")
                return metadata_delete_result
            
            # Step 5: Update user storage usage
            await self.user_management_service.update_storage_usage(
                user, file_metadata.file_size, increment=False
            )
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "files_deleted",
                tags={
                    "user_tier": user.subscription_tier,
                    "file_type": file_metadata.content_type
                }
            )
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("file_deletion_errors")
            return ServiceResult.error(
                error=f"Failed to delete file: {str(e)}",
                error_code="FILE_DELETION_ERROR"
            )
    
    async def get_user_files(
        self, 
        user: ClerkUser, 
        pagination: PaginationRequest,
        filters: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[List[FileMetadata]]:
        """Get paginated list of user files."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the request
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="get_user_files",
                metadata={
                    "correlation_id": correlation_id,
                    "pagination": pagination.model_dump(),
                    "filters": filters or {}
                }
            )
            
            # Validate user permissions
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "read_files"
            )
            if not permission_result.success:
                return permission_result
            
            # Get files from file processing service
            files_result = await self.file_processing_service.get_user_files(
                user.clerk_user_id, pagination, filters
            )
            if not files_result.success:
                return files_result
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "file_lists_retrieved",
                tags={
                    "user_tier": user.subscription_tier,
                    "file_count": str(len(files_result.data))
                }
            )
            
            return files_result
            
        except Exception as e:
            logger.error(f"Error getting user files: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("file_list_errors")
            return ServiceResult.error(
                error=f"Failed to retrieve files: {str(e)}",
                error_code="FILE_LIST_ERROR"
            )
    
    async def generate_download_url(
        self, 
        file_id: str, 
        user: ClerkUser, 
        expiration_hours: int = 24
    ) -> ServiceResult[str]:
        """Generate secure download URL."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the request
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="download_url_requested",
                metadata={
                    "correlation_id": correlation_id,
                    "file_id": file_id,
                    "expiration_hours": expiration_hours
                }
            )
            
            # Step 1: Get file metadata and validate ownership
            metadata_result = await self.file_processing_service.get_file_metadata(file_id, user.clerk_user_id)
            if not metadata_result.success:
                return metadata_result
            
            file_metadata = metadata_result.data
            
            # Step 2: Validate access permissions
            permission_result = await self.user_management_service.validate_file_access(
                user, file_metadata, "download"
            )
            if not permission_result.success:
                await self.metrics_service.increment_counter("download_url_permission_denied")
                return permission_result
            
            # Step 3: Generate secure URL
            url_result = await self.storage_service.generate_download_url(
                file_metadata.storage_path,
                expiration_hours=expiration_hours
            )
            if not url_result.success:
                return url_result
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "download_urls_generated",
                tags={
                    "user_tier": user.subscription_tier,
                    "expiration_hours": str(expiration_hours)
                }
            )
            
            return ServiceResult.success(url_result.data["url"])
            
        except Exception as e:
            logger.error(f"Error generating download URL: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("download_url_errors")
            return ServiceResult.error(
                error=f"Failed to generate download URL: {str(e)}",
                error_code="DOWNLOAD_URL_ERROR"
            )

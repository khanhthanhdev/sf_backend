"""
Application service interfaces (Use Cases) that orchestrate domain services.

These interfaces define the complete use cases that coordinate multiple
domain services to fulfill user requirements.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ...models.job import Job, JobCreateRequest, JobStatus
from ...models.video import VideoMetadata
from ...models.user import ClerkUser
from ...models.file import FileMetadataResponse as FileMetadata, FileUploadRequest as UploadFileRequest
from ...schemas.requests import VideoGenerationRequest
from ...schemas.common import PaginationRequest
from .base import IService, ServiceResult


class IVideoGenerationUseCase(IService):
    """Use case for complete video generation workflow."""
    
    @abstractmethod
    async def generate_video(
        self, 
        request: VideoGenerationRequest, 
        user: ClerkUser
    ) -> ServiceResult[Job]:
        """
        Complete workflow for video generation including:
        - Request validation
        - User permission checking
        - Cost calculation and credit deduction
        - Job creation
        - Queue submission
        - Notification setup
        """
        pass
    
    @abstractmethod
    async def generate_batch_videos(
        self, 
        requests: List[VideoGenerationRequest], 
        user: ClerkUser
    ) -> ServiceResult[List[Job]]:
        """Generate multiple videos in batch."""
        pass
    
    @abstractmethod
    async def cancel_video_generation(
        self, 
        job_id: str, 
        user: ClerkUser, 
        reason: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Cancel video generation and handle cleanup."""
        pass
    
    @abstractmethod
    async def get_video_generation_status(
        self, 
        job_id: str, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Get detailed status of video generation."""
        pass


class IJobManagementUseCase(IService):
    """Use case for comprehensive job management operations."""
    
    @abstractmethod
    async def get_user_jobs(
        self, 
        user: ClerkUser, 
        pagination: PaginationRequest,
        filters: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[List[Job]]:
        """Get paginated list of user jobs with filtering."""
        pass
    
    @abstractmethod
    async def update_job_progress(
        self, 
        job_id: str, 
        progress: float, 
        status: Optional[JobStatus] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[Job]:
        """Update job progress and notify stakeholders."""
        pass
    
    @abstractmethod
    async def handle_job_completion(
        self, 
        job_id: str, 
        result_metadata: Dict[str, Any]
    ) -> ServiceResult[Job]:
        """Handle job completion with notifications and cleanup."""
        pass
    
    @abstractmethod
    async def handle_job_failure(
        self, 
        job_id: str, 
        error: str, 
        retry: bool = False
    ) -> ServiceResult[Job]:
        """Handle job failure with error reporting and retry logic."""
        pass
    
    @abstractmethod
    async def cleanup_old_jobs(
        self, 
        retention_days: int = 30
    ) -> ServiceResult[int]:
        """Cleanup old completed jobs."""
        pass


class IFileManagementUseCase(IService):
    """Use case for comprehensive file management operations."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def download_file(
        self, 
        file_id: str, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Download file with permission checking."""
        pass
    
    @abstractmethod
    async def delete_file(
        self, 
        file_id: str, 
        user: ClerkUser
    ) -> ServiceResult[bool]:
        """Delete file with cleanup and permission checking."""
        pass
    
    @abstractmethod
    async def get_user_files(
        self, 
        user: ClerkUser, 
        pagination: PaginationRequest,
        filters: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[List[FileMetadata]]:
        """Get paginated list of user files."""
        pass
    
    @abstractmethod
    async def generate_download_url(
        self, 
        file_id: str, 
        user: ClerkUser, 
        expiration_hours: int = 24
    ) -> ServiceResult[str]:
        """Generate secure download URL."""
        pass


class IUserManagementUseCase(IService):
    """Use case for user management operations."""
    
    @abstractmethod
    async def create_user_profile(
        self, 
        clerk_user_data: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Create user profile from Clerk webhook data."""
        pass
    
    @abstractmethod
    async def update_user_profile(
        self, 
        user_id: str, 
        updates: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Update user profile."""
        pass
    
    @abstractmethod
    async def get_user_dashboard_data(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Get comprehensive user dashboard data."""
        pass
    
    @abstractmethod
    async def handle_subscription_change(
        self, 
        user_id: str, 
        subscription_data: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Handle user subscription changes."""
        pass
    
    @abstractmethod
    async def deactivate_user(
        self, 
        user_id: str, 
        reason: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Deactivate user and cleanup resources."""
        pass

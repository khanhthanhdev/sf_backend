"""
Domain service interfaces representing core business logic.

These interfaces define the business operations without concerns about
data persistence, external APIs, or infrastructure details.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ...models.job import Job, JobCreateRequest, JobStatus, JobProgress
from ...models.video import VideoMetadata
from ...models.user import ClerkUser
from ...models.file import FileMetadataResponse as FileMetadata, FileUploadRequest as UploadFileRequest
from ...schemas.requests import VideoGenerationRequest
from .base import IService, ServiceResult


class IVideoGenerationService(IService):
    """Domain service for video generation business logic."""
    
    @abstractmethod
    async def validate_generation_request(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate video generation request parameters."""
        pass
    
    @abstractmethod
    async def calculate_generation_cost(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[int]:
        """Calculate cost in credits for video generation."""
        pass
    
    @abstractmethod
    async def estimate_generation_time(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[int]:
        """Estimate generation time in seconds."""
        pass
    
    @abstractmethod
    async def apply_business_rules(
        self, 
        user: ClerkUser, 
        request: VideoGenerationRequest
    ) -> ServiceResult[Dict[str, Any]]:
        """Apply business rules for video generation."""
        pass


class IJobManagementService(IService):
    """Domain service for job lifecycle management."""
    
    @abstractmethod
    async def create_job(
        self, 
        request: JobCreateRequest, 
        user_id: str
    ) -> ServiceResult[Job]:
        """Create a new job with business validation."""
        pass
    
    @abstractmethod
    async def validate_job_transition(
        self, 
        job_id: str, 
        from_status: JobStatus, 
        to_status: JobStatus
    ) -> ServiceResult[bool]:
        """Validate if job status transition is allowed."""
        pass
    
    @abstractmethod
    async def apply_job_priority_rules(
        self, 
        job: Job, 
        user: ClerkUser
    ) -> ServiceResult[Job]:
        """Apply priority rules based on user subscription and job type."""
        pass
    
    @abstractmethod
    async def calculate_job_timeout(
        self, 
        job: Job
    ) -> ServiceResult[datetime]:
        """Calculate when job should timeout."""
        pass


class IFileProcessingService(IService):
    """Domain service for file processing business logic."""
    
    @abstractmethod
    async def validate_file_upload(
        self, 
        request: UploadFileRequest, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate file upload according to business rules."""
        pass
    
    @abstractmethod
    async def calculate_storage_quota(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, int]]:
        """Calculate available storage quota for user."""
        pass
    
    @abstractmethod
    async def determine_file_retention(
        self, 
        file_metadata: FileMetadata, 
        user: ClerkUser
    ) -> ServiceResult[datetime]:
        """Determine file retention period based on business rules."""
        pass


class IUserManagementService(IService):
    """Domain service for user management business logic."""
    
    @abstractmethod
    async def validate_user_permissions(
        self, 
        user: ClerkUser, 
        operation: str, 
        resource_id: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Validate user permissions for operation."""
        pass
    
    @abstractmethod
    async def calculate_user_limits(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, int]]:
        """Calculate user limits based on subscription."""
        pass
    
    @abstractmethod
    async def apply_rate_limiting_rules(
        self, 
        user: ClerkUser, 
        operation: str
    ) -> ServiceResult[Dict[str, Any]]:
        """Apply rate limiting rules for user operations."""
        pass


class INotificationService(IService):
    """Domain service for notification business logic."""
    
    @abstractmethod
    async def determine_notification_preferences(
        self, 
        user: ClerkUser, 
        notification_type: str
    ) -> ServiceResult[Dict[str, Any]]:
        """Determine user notification preferences."""
        pass
    
    @abstractmethod
    async def validate_notification_content(
        self, 
        content: Dict[str, Any], 
        notification_type: str
    ) -> ServiceResult[bool]:
        """Validate notification content according to business rules."""
        pass
    
    @abstractmethod
    async def calculate_notification_priority(
        self, 
        user: ClerkUser, 
        notification_type: str, 
        content: Dict[str, Any]
    ) -> ServiceResult[int]:
        """Calculate notification priority based on business rules."""
        pass

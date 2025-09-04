"""
Infrastructure service interfaces for external systems and technical concerns.

These interfaces define operations for data persistence, external APIs,
messaging, storage, and other infrastructure-related functionality.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import io

from ...models.job import Job, JobStatus
from ...models.video import VideoMetadata
from ...models.file import FileMetadataResponse as FileMetadata
from .base import IService, ServiceResult


class IQueueService(IService):
    """Interface for message queue operations."""
    
    @abstractmethod
    async def enqueue_job(
        self, 
        job: Job, 
        priority: Optional[int] = None
    ) -> ServiceResult[str]:
        """Enqueue job for processing."""
        pass
    
    @abstractmethod
    async def dequeue_job(
        self, 
        queue_name: str
    ) -> ServiceResult[Optional[Job]]:
        """Dequeue next job from queue."""
        pass
    
    @abstractmethod
    async def get_queue_size(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Get number of jobs in queue."""
        pass
    
    @abstractmethod
    async def clear_queue(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Clear all jobs from queue."""
        pass


class IStorageService(IService):
    """Interface for file storage operations."""
    
    @abstractmethod
    async def upload_file(
        self, 
        file_content: bytes, 
        file_path: str, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> ServiceResult[str]:
        """Upload file to storage."""
        pass
    
    @abstractmethod
    async def download_file(
        self, 
        file_path: str
    ) -> ServiceResult[bytes]:
        """Download file from storage."""
        pass
    
    @abstractmethod
    async def delete_file(
        self, 
        file_path: str
    ) -> ServiceResult[bool]:
        """Delete file from storage."""
        pass
    
    @abstractmethod
    async def generate_presigned_url(
        self, 
        file_path: str, 
        expiration_seconds: int = 3600,
        operation: str = "GET"
    ) -> ServiceResult[str]:
        """Generate presigned URL for file access."""
        pass
    
    @abstractmethod
    async def list_files(
        self, 
        prefix: str, 
        limit: Optional[int] = None
    ) -> ServiceResult[List[str]]:
        """List files with given prefix."""
        pass


class IExternalAPIService(IService):
    """Interface for external API integrations."""
    
    @abstractmethod
    async def call_video_generation_api(
        self, 
        request_data: Dict[str, Any]
    ) -> ServiceResult[Dict[str, Any]]:
        """Call external video generation API."""
        pass
    
    @abstractmethod
    async def validate_api_credentials(
        self, 
        provider: str, 
        credentials: Dict[str, str]
    ) -> ServiceResult[bool]:
        """Validate external API credentials."""
        pass
    
    @abstractmethod
    async def get_api_usage_stats(
        self, 
        provider: str, 
        date_range: Optional[tuple] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Get API usage statistics."""
        pass


class IEmailService(IService):
    """Interface for email operations."""
    
    @abstractmethod
    async def send_email(
        self, 
        to_addresses: List[str], 
        subject: str, 
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> ServiceResult[str]:
        """Send email."""
        pass
    
    @abstractmethod
    async def send_template_email(
        self, 
        to_addresses: List[str], 
        template_name: str, 
        template_data: Dict[str, Any]
    ) -> ServiceResult[str]:
        """Send templated email."""
        pass
    
    @abstractmethod
    async def validate_email_address(
        self, 
        email: str
    ) -> ServiceResult[bool]:
        """Validate email address format and deliverability."""
        pass


class IMetricsService(IService):
    """Interface for metrics collection and monitoring."""
    
    @abstractmethod
    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record a metric value."""
        pass
    
    @abstractmethod
    async def increment_counter(
        self, 
        counter_name: str, 
        increment: int = 1, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Increment a counter metric."""
        pass
    
    @abstractmethod
    async def record_duration(
        self, 
        operation_name: str, 
        duration_ms: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record operation duration."""
        pass
    
    @abstractmethod
    async def get_metrics(
        self, 
        metric_names: List[str], 
        time_range: Optional[tuple] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Get metric values for specified time range."""
        pass


class ILoggingService(IService):
    """Interface for structured logging operations."""
    
    @abstractmethod
    async def log_event(
        self, 
        level: str, 
        message: str, 
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Log structured event."""
        pass
    
    @abstractmethod
    async def log_user_action(
        self, 
        user_id: str, 
        action: str, 
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[bool]:
        """Log user action for audit trail."""
        pass
    
    @abstractmethod
    async def log_system_event(
        self, 
        event_type: str, 
        component: str, 
        details: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """Log system event."""
        pass
    
    @abstractmethod
    async def search_logs(
        self, 
        query: str, 
        time_range: Optional[tuple] = None,
        limit: int = 100
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """Search logs with query."""
        pass


class ICacheService(IService):
    """Interface for caching operations."""
    
    @abstractmethod
    async def get(
        self, 
        key: str
    ) -> ServiceResult[Optional[Any]]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: Optional[int] = None
    ) -> ServiceResult[bool]:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(
        self, 
        key: str
    ) -> ServiceResult[bool]:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def clear_pattern(
        self, 
        pattern: str
    ) -> ServiceResult[int]:
        """Clear all keys matching pattern."""
        pass
    
    @abstractmethod
    async def get_cache_stats(self) -> ServiceResult[Dict[str, Any]]:
        """Get cache statistics."""
        pass

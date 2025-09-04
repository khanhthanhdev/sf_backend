"""
Domain layer for the video generation system.

This package contains the core business logic, domain entities, value objects,
and domain services that are independent of external frameworks and infrastructure.

The domain layer follows Domain-Driven Design (DDD) principles and implements:
- Rich domain entities with business logic
- Value objects for complex data types
- Domain services for business operations
- Result pattern for error handling
- Aggregate roots for consistency boundaries
"""

from .common import (
    Result,
    DomainEvent,
    Entity,
    ValueObject,
    AggregateRoot,
    BusinessRuleViolation,
    DomainError,
    Specification,
)

from .value_objects import (
    # Identifiers
    UserId,
    VideoId,
    JobId,
    FileId,
    EmailAddress,
    PhoneNumber,
    
    # Video value objects
    VideoQuality,
    VideoFormat,
    VideoResolution,
    VideoStatus,
    VideoTitle,
    VideoDescription,
    VideoTopic,
    VideoContext,
    VideoProcessingConfig,
    FileSize,
    
    # Job value objects
    JobStatus,
    JobPriority,
    JobType,
    JobProgress,
    JobError,
    JobMetrics,
)

from .entities import (
    # User
    User,
    UserCreated,
    UserUpdated,
    UserDeactivated,
    UserStatus as UserStatusEnum,
    UserRole,
    
    # Video
    Video,
    VideoCreated,
    VideoProcessingStarted,
    VideoProcessingCompleted,
    VideoProcessingFailed,
    VideoArchived,
    
    # Job
    Job,
    JobCreated,
    JobStarted,
    JobProgressUpdated,
    JobCompleted,
    JobFailed,
    JobCancelled,
    
    # File
    File,
    FileUploaded,
    FileProcessed,
    FileDeleted,
    FileType,
)

__all__ = [
    # Common
    "Result",
    "DomainEvent",
    "Entity",
    "ValueObject",
    "AggregateRoot",
    "BusinessRuleViolation",
    "DomainError",
    "Specification",
    
    # Value objects - Identifiers
    "UserId",
    "VideoId",
    "JobId",
    "FileId",
    "EmailAddress",
    "PhoneNumber",
    
    # Value objects - Video
    "VideoQuality",
    "VideoFormat",
    "VideoResolution",
    "VideoStatus",
    "VideoTitle",
    "VideoDescription",
    "VideoTopic",
    "VideoContext",
    "VideoProcessingConfig",
    "FileSize",
    
    # Value objects - Job
    "JobStatus",
    "JobPriority",
    "JobType",
    "JobProgress",
    "JobError",
    "JobMetrics",
    
    # Entities - User
    "User",
    "UserCreated",
    "UserUpdated",
    "UserDeactivated",
    "UserStatusEnum",
    "UserRole",
    
    # Entities - Video
    "Video",
    "VideoCreated",
    "VideoProcessingStarted",
    "VideoProcessingCompleted",
    "VideoProcessingFailed",
    "VideoArchived",
    
    # Entities - Job
    "Job",
    "JobCreated",
    "JobStarted",
    "JobProgressUpdated",
    "JobCompleted",
    "JobFailed",
    "JobCancelled",
    
    # Entities - File
    "File",
    "FileUploaded",
    "FileProcessed",
    "FileDeleted",
    "FileType",
]

"""
Value objects for the video generation domain.
"""

from .identifiers import (
    UserId,
    VideoId,
    JobId,
    FileId,
    EmailAddress,
    PhoneNumber,
)

from .video import (
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
)

from .job import (
    JobStatus,
    JobPriority,
    JobType,
    JobProgress,
    JobError,
    JobMetrics,
    JobConfiguration,
)

from .file import (
    FileType,
    FilePath,
    S3Location,
)

__all__ = [
    # Identifiers
    "UserId",
    "VideoId", 
    "JobId",
    "FileId",
    "EmailAddress",
    "PhoneNumber",
    
    # Video value objects
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
    
    # Job value objects
    "JobStatus",
    "JobPriority",
    "JobType",
    "JobProgress",
    "JobError",
    "JobMetrics",
    "JobConfiguration",
    
    # File value objects
    "FileType",
    "FilePath",
    "S3Location",
]

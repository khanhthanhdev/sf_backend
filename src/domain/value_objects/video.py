"""
Video-related value objects for the domain.

This module contains value objects specific to video processing,
including quality settings, formats, and processing configuration.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

from ..common import ValueObject, BusinessRuleViolation


class VideoQuality(str, Enum):
    """Video quality enumeration with specific requirements."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


class VideoFormat(str, Enum):
    """Supported video output formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"


class VideoResolution(str, Enum):
    """Standard video resolutions."""
    SD_480P = "480p"      # 854x480
    HD_720P = "720p"      # 1280x720
    FHD_1080P = "1080p"   # 1920x1080
    UHD_4K = "4k"         # 3840x2160


class VideoStatus(str, Enum):
    """Video processing status."""
    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class VideoTitle(ValueObject):
    """
    Value object representing a video title with validation.
    
    Ensures titles meet business requirements for length,
    content, and formatting.
    """
    
    value: str
    
    def validate(self) -> None:
        """Validate the video title."""
        if not self.value:
            raise BusinessRuleViolation(
                "VideoTitle.NotEmpty",
                "Video title cannot be empty"
            )
        
        if len(self.value.strip()) == 0:
            raise BusinessRuleViolation(
                "VideoTitle.NotOnlyWhitespace",
                "Video title cannot contain only whitespace"
            )
        
        if len(self.value) > 200:
            raise BusinessRuleViolation(
                "VideoTitle.TooLong",
                "Video title cannot exceed 200 characters"
            )
        
        if len(self.value) < 1:
            raise BusinessRuleViolation(
                "VideoTitle.TooShort",
                "Video title must be at least 1 character long"
            )
        
        # Check for invalid characters that might cause issues
        invalid_chars = ['<', '>', '"', '|', ':', '*', '?', '\\', '/']
        for char in invalid_chars:
            if char in self.value:
                raise BusinessRuleViolation(
                    "VideoTitle.InvalidCharacters",
                    f"Video title cannot contain invalid character: {char}"
                )
    
    @property
    def trimmed(self) -> str:
        """Get the trimmed version of the title."""
        return self.value.strip()
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"VideoTitle('{self.value}')"


@dataclass(frozen=True)
class VideoDescription(ValueObject):
    """
    Value object representing a video description with validation.
    """
    
    value: str
    
    def validate(self) -> None:
        """Validate the video description."""
        if len(self.value) > 2000:
            raise BusinessRuleViolation(
                "VideoDescription.TooLong",
                "Video description cannot exceed 2000 characters"
            )
    
    @property
    def trimmed(self) -> str:
        """Get the trimmed version of the description."""
        return self.value.strip()
    
    @property
    def is_empty(self) -> bool:
        """Check if the description is empty or only whitespace."""
        return len(self.value.strip()) == 0
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"VideoDescription('{self.value[:50]}{'...' if len(self.value) > 50 else ''}')"


@dataclass(frozen=True)
class VideoTopic(ValueObject):
    """
    Value object representing a video topic/subject with validation.
    
    Topics are used for content generation and must meet specific
    business requirements.
    """
    
    value: str
    
    def validate(self) -> None:
        """Validate the video topic."""
        if not self.value:
            raise BusinessRuleViolation(
                "VideoTopic.NotEmpty",
                "Video topic cannot be empty"
            )
        
        if len(self.value.strip()) == 0:
            raise BusinessRuleViolation(
                "VideoTopic.NotOnlyWhitespace",
                "Video topic cannot contain only whitespace"
            )
        
        if len(self.value) > 500:
            raise BusinessRuleViolation(
                "VideoTopic.TooLong",
                "Video topic cannot exceed 500 characters"
            )
        
        if len(self.value) < 3:
            raise BusinessRuleViolation(
                "VideoTopic.TooShort",
                "Video topic must be at least 3 characters long"
            )
    
    @property
    def trimmed(self) -> str:
        """Get the trimmed version of the topic."""
        return self.value.strip()
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"VideoTopic('{self.value[:50]}{'...' if len(self.value) > 50 else ''}')"


@dataclass(frozen=True)
class VideoContext(ValueObject):
    """
    Value object representing detailed video context for content generation.
    
    Context provides additional information to guide the AI in generating
    appropriate video content.
    """
    
    value: str
    
    def validate(self) -> None:
        """Validate the video context."""
        if not self.value:
            raise BusinessRuleViolation(
                "VideoContext.NotEmpty",
                "Video context cannot be empty"
            )
        
        if len(self.value.strip()) == 0:
            raise BusinessRuleViolation(
                "VideoContext.NotOnlyWhitespace",
                "Video context cannot contain only whitespace"
            )
        
        if len(self.value) > 2000:
            raise BusinessRuleViolation(
                "VideoContext.TooLong",
                "Video context cannot exceed 2000 characters"
            )
        
        if len(self.value) < 10:
            raise BusinessRuleViolation(
                "VideoContext.TooShort",
                "Video context must be at least 10 characters long"
            )
    
    @property
    def trimmed(self) -> str:
        """Get the trimmed version of the context."""
        return self.value.strip()
    
    @property
    def word_count(self) -> int:
        """Get the approximate word count of the context."""
        return len(self.value.split())
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"VideoContext('{self.value[:50]}{'...' if len(self.value) > 50 else ''}')"


@dataclass(frozen=True)
class VideoProcessingConfig(ValueObject):
    """
    Value object representing video processing configuration.
    
    Encapsulates all the settings needed for video generation
    with proper validation and business rules.
    """
    
    quality: VideoQuality
    format: VideoFormat
    resolution: Optional[VideoResolution]
    enable_subtitles: bool
    enable_thumbnails: bool
    use_rag: bool
    model: Optional[str]
    custom_config: Optional[Dict[str, Any]]
    
    def validate(self) -> None:
        """Validate the processing configuration."""
        # Quality validation
        if not isinstance(self.quality, VideoQuality):
            raise BusinessRuleViolation(
                "VideoProcessingConfig.InvalidQuality",
                f"Invalid video quality: {self.quality}"
            )
        
        # Format validation
        if not isinstance(self.format, VideoFormat):
            raise BusinessRuleViolation(
                "VideoProcessingConfig.InvalidFormat",
                f"Invalid video format: {self.format}"
            )
        
        # Resolution validation for quality combinations
        if self.quality == VideoQuality.ULTRA and self.resolution not in [VideoResolution.FHD_1080P, VideoResolution.UHD_4K]:
            raise BusinessRuleViolation(
                "VideoProcessingConfig.InvalidResolutionForQuality",
                "Ultra quality requires 1080p or 4K resolution"
            )
        
        # Model validation
        if self.model is not None:
            if len(self.model.strip()) == 0:
                raise BusinessRuleViolation(
                    "VideoProcessingConfig.EmptyModel",
                    "Model name cannot be empty if specified"
                )
            
            if len(self.model) > 200:
                raise BusinessRuleViolation(
                    "VideoProcessingConfig.ModelNameTooLong",
                    "Model name cannot exceed 200 characters"
                )
        
        # Custom config validation
        if self.custom_config is not None:
            if not isinstance(self.custom_config, dict):
                raise BusinessRuleViolation(
                    "VideoProcessingConfig.InvalidCustomConfig",
                    "Custom config must be a dictionary"
                )
    
    @property
    def requires_high_resources(self) -> bool:
        """Check if this configuration requires high computational resources."""
        return (self.quality in [VideoQuality.HIGH, VideoQuality.ULTRA] or
                self.resolution in [VideoResolution.FHD_1080P, VideoResolution.UHD_4K])
    
    @property
    def estimated_processing_time_minutes(self) -> int:
        """Estimate processing time in minutes based on configuration."""
        base_time = 5  # Base processing time in minutes
        
        # Quality multipliers
        quality_multipliers = {
            VideoQuality.LOW: 1.0,
            VideoQuality.MEDIUM: 1.5,
            VideoQuality.HIGH: 2.0,
            VideoQuality.ULTRA: 3.0
        }
        
        # Resolution multipliers
        resolution_multipliers = {
            VideoResolution.SD_480P: 1.0,
            VideoResolution.HD_720P: 1.2,
            VideoResolution.FHD_1080P: 1.5,
            VideoResolution.UHD_4K: 2.0
        }
        
        multiplier = quality_multipliers[self.quality]
        
        if self.resolution:
            multiplier *= resolution_multipliers[self.resolution]
        
        if self.enable_subtitles:
            multiplier += 0.2
        
        if self.enable_thumbnails:
            multiplier += 0.1
        
        if self.use_rag:
            multiplier += 0.3
        
        return int(base_time * multiplier)
    
    def __repr__(self) -> str:
        return (f"VideoProcessingConfig(quality={self.quality}, format={self.format}, "
                f"resolution={self.resolution}, subtitles={self.enable_subtitles}, "
                f"thumbnails={self.enable_thumbnails}, rag={self.use_rag})")


@dataclass(frozen=True)
class FileSize(ValueObject):
    """
    Value object representing file size with validation and formatting.
    """
    
    bytes: int
    
    @classmethod
    def create(cls, bytes_value: int) -> "FileSize":
        """Create a FileSize with validation."""
        return cls(bytes=bytes_value)
    
    def validate(self) -> None:
        """Validate the file size."""
        if self.bytes < 0:
            raise BusinessRuleViolation(
                "FileSize.Negative",
                "File size cannot be negative"
            )
        
        # 10GB limit for video files
        max_size = 10 * 1024 * 1024 * 1024  # 10GB in bytes
        if self.bytes > max_size:
            raise BusinessRuleViolation(
                "FileSize.TooLarge",
                f"File size cannot exceed {self.human_readable(max_size)}"
            )
    
    @property
    def kilobytes(self) -> float:
        """Get size in kilobytes."""
        return self.bytes / 1024
    
    @property
    def megabytes(self) -> float:
        """Get size in megabytes."""
        return self.bytes / (1024 * 1024)
    
    @property
    def gigabytes(self) -> float:
        """Get size in gigabytes."""
        return self.bytes / (1024 * 1024 * 1024)
    
    def human_readable(self, size_bytes: Optional[int] = None) -> str:
        """Get human-readable file size format."""
        size = size_bytes if size_bytes is not None else self.bytes
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"
    
    def __str__(self) -> str:
        return self.human_readable()
    
    def __repr__(self) -> str:
        return f"FileSize({self.bytes} bytes)"

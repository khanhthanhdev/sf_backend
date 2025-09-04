"""
Video domain entity.

This module defines the Video aggregate root with business logic,
validation rules, and domain events for video management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from ..common import AggregateRoot, DomainEvent, BusinessRuleViolation, Result
from ..value_objects import (
    VideoId, UserId, VideoTitle, VideoDescription, VideoTopic, 
    VideoContext, VideoStatus, VideoProcessingConfig, FileSize
)


@dataclass(frozen=True)
class VideoCreated(DomainEvent):
    """Domain event raised when a video is created."""
    video_id: VideoId
    user_id: UserId
    title: VideoTitle
    topic: VideoTopic


@dataclass(frozen=True)
class VideoProcessingStarted(DomainEvent):
    """Domain event raised when video processing starts."""
    video_id: VideoId
    processing_config: VideoProcessingConfig


@dataclass(frozen=True)
class VideoProcessingCompleted(DomainEvent):
    """Domain event raised when video processing completes."""
    video_id: VideoId
    result_url: str
    file_size: FileSize


@dataclass(frozen=True)
class VideoProcessingFailed(DomainEvent):
    """Domain event raised when video processing fails."""
    video_id: VideoId
    error_message: str
    is_retryable: bool


@dataclass(frozen=True)
class VideoArchived(DomainEvent):
    """Domain event raised when a video is archived."""
    video_id: VideoId
    archived_by: UserId
    reason: str


class Video(AggregateRoot):
    """
    Video aggregate root representing a video in the system.
    
    Videos are created by users and go through a processing pipeline
    to generate the final video content with optional features like
    subtitles and thumbnails.
    
    Business Rules:
    - Must have a valid title and topic
    - Can only be processed if status is UPLOADED or CREATED
    - Cannot be deleted while processing
    - Must belong to an active user
    - Processing configuration must be valid for the video type
    """
    
    def __init__(
        self,
        video_id: VideoId,
        user_id: UserId,
        title: VideoTitle,
        topic: VideoTopic,
        context: VideoContext,
        processing_config: VideoProcessingConfig,
        description: Optional[VideoDescription] = None,
        status: VideoStatus = VideoStatus.CREATED,
        result_url: Optional[str] = None,
        file_size: Optional[FileSize] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        processing_started_at: Optional[datetime] = None,
        processing_completed_at: Optional[datetime] = None,
        last_error: Optional[str] = None
    ):
        super().__init__(video_id.value)
        
        self._video_id = video_id
        self._user_id = user_id
        self._title = title
        self._description = description or VideoDescription("")
        self._topic = topic
        self._context = context
        self._processing_config = processing_config
        self._status = status
        self._result_url = result_url
        self._file_size = file_size
        self._tags = tags or []
        self._metadata = metadata or {}
        self._created_at = created_at or datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._processing_started_at = processing_started_at
        self._processing_completed_at = processing_completed_at
        self._last_error = last_error
        self._is_deleted = False
        self._deleted_at = None
        self._retry_count = 0
        self._max_retries = 3
        
        # Validate business rules
        self._validate_business_rules()
    
    @classmethod
    def create(
        cls,
        user_id: UserId,
        title: VideoTitle,
        topic: VideoTopic,
        context: VideoContext,
        processing_config: VideoProcessingConfig,
        description: Optional[VideoDescription] = None,
        tags: Optional[List[str]] = None
    ) -> Result["Video"]:
        """
        Create a new video with business rule validation.
        
        Returns:
            Result containing the created Video or error message
        """
        try:
            # Generate new video ID
            video_id = VideoId.generate()
            
            # Create video instance
            video = cls(
                video_id=video_id,
                user_id=user_id,
                title=title,
                topic=topic,
                context=context,
                processing_config=processing_config,
                description=description,
                tags=tags
            )
            
            # Add domain event
            video.add_domain_event(VideoCreated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=video.id,
                version=video.version,
                video_id=video_id,
                user_id=user_id,
                title=title,
                topic=topic
            ))
            
            return Result.ok(video)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Properties
    @property
    def video_id(self) -> VideoId:
        """Get the video ID."""
        return self._video_id
    
    @property
    def user_id(self) -> UserId:
        """Get the user ID who owns this video."""
        return self._user_id
    
    @property
    def title(self) -> VideoTitle:
        """Get the video title."""
        return self._title
    
    @property
    def description(self) -> VideoDescription:
        """Get the video description."""
        return self._description
    
    @property
    def topic(self) -> VideoTopic:
        """Get the video topic."""
        return self._topic
    
    @property
    def context(self) -> VideoContext:
        """Get the video context."""
        return self._context
    
    @property
    def processing_config(self) -> VideoProcessingConfig:
        """Get the processing configuration."""
        return self._processing_config
    
    @property
    def status(self) -> VideoStatus:
        """Get the video status."""
        return self._status
    
    @property
    def result_url(self) -> Optional[str]:
        """Get the result URL if processing is completed."""
        return self._result_url
    
    @property
    def file_size(self) -> Optional[FileSize]:
        """Get the file size if available."""
        return self._file_size
    
    @property
    def tags(self) -> List[str]:
        """Get the video tags."""
        return self._tags.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get the video metadata."""
        return self._metadata.copy()
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def processing_started_at(self) -> Optional[datetime]:
        """Get processing start timestamp."""
        return self._processing_started_at
    
    @property
    def processing_completed_at(self) -> Optional[datetime]:
        """Get processing completion timestamp."""
        return self._processing_completed_at
    
    @property
    def processing_duration_seconds(self) -> Optional[int]:
        """Get processing duration in seconds if completed."""
        if self._processing_started_at and self._processing_completed_at:
            duration = self._processing_completed_at - self._processing_started_at
            return int(duration.total_seconds())
        return None
    
    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error
    
    @property
    def retry_count(self) -> int:
        """Get the current retry count."""
        return self._retry_count
    
    @property
    def max_retries(self) -> int:
        """Get the maximum number of retries."""
        return self._max_retries
    
    @property
    def is_deleted(self) -> bool:
        """Check if video is soft deleted."""
        return self._is_deleted
    
    @property
    def deleted_at(self) -> Optional[datetime]:
        """Get deletion timestamp."""
        return self._deleted_at
    
    # Business logic methods
    def can_be_processed(self) -> bool:
        """Check if the video can be processed."""
        return self._status in [VideoStatus.CREATED, VideoStatus.UPLOADED]
    
    def can_be_deleted(self) -> bool:
        """Check if the video can be deleted."""
        return self._status != VideoStatus.PROCESSING
    
    def can_be_retried(self) -> bool:
        """Check if the video processing can be retried."""
        return (self._status == VideoStatus.FAILED and 
                self._retry_count < self._max_retries)
    
    def is_processing_complete(self) -> bool:
        """Check if processing is complete."""
        return self._status == VideoStatus.COMPLETED
    
    def is_processing_failed(self) -> bool:
        """Check if processing failed."""
        return self._status == VideoStatus.FAILED
    
    def needs_user_attention(self) -> bool:
        """Check if the video needs user attention."""
        return (self._status == VideoStatus.FAILED and 
                not self.can_be_retried())
    
    # Mutation methods
    def update_metadata(
        self,
        title: Optional[VideoTitle] = None,
        description: Optional[VideoDescription] = None,
        tags: Optional[List[str]] = None
    ) -> Result[None]:
        """Update video metadata."""
        try:
            # Business rule: Cannot update while processing
            if self._status == VideoStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Video.CannotUpdateWhileProcessing",
                    "Cannot update video metadata while processing"
                )
            
            if title is not None:
                self._title = title
            
            if description is not None:
                self._description = description
            
            if tags is not None:
                self._validate_tags(tags)
                self._tags = tags
            
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def start_processing(self) -> Result[None]:
        """Start video processing."""
        try:
            if not self.can_be_processed():
                raise BusinessRuleViolation(
                    "Video.CannotStartProcessing",
                    f"Cannot start processing video in status: {self._status}"
                )
            
            self._status = VideoStatus.PROCESSING
            self._processing_started_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(VideoProcessingStarted(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                video_id=self._video_id,
                processing_config=self._processing_config
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def complete_processing(
        self,
        result_url: str,
        file_size: FileSize,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Result[None]:
        """Complete video processing with results."""
        try:
            if self._status != VideoStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Video.NotProcessing",
                    "Video is not currently being processed"
                )
            
            if not result_url or len(result_url.strip()) == 0:
                raise BusinessRuleViolation(
                    "Video.ResultUrlRequired",
                    "Result URL is required for completion"
                )
            
            self._status = VideoStatus.COMPLETED
            self._result_url = result_url
            self._file_size = file_size
            self._processing_completed_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self._last_error = None  # Clear any previous errors
            
            if metadata:
                self._metadata.update(metadata)
            
            self.increment_version()
            
            self.add_domain_event(VideoProcessingCompleted(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                video_id=self._video_id,
                result_url=result_url,
                file_size=file_size
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def fail_processing(
        self,
        error_message: str,
        is_retryable: bool = True
    ) -> Result[None]:
        """Mark processing as failed with error information."""
        try:
            if self._status != VideoStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Video.NotProcessing",
                    "Video is not currently being processed"
                )
            
            if not error_message or len(error_message.strip()) == 0:
                raise BusinessRuleViolation(
                    "Video.ErrorMessageRequired",
                    "Error message is required for failure"
                )
            
            self._status = VideoStatus.FAILED
            self._last_error = error_message
            self._updated_at = datetime.utcnow()
            
            if is_retryable:
                self._retry_count += 1
            
            self.increment_version()
            
            self.add_domain_event(VideoProcessingFailed(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                video_id=self._video_id,
                error_message=error_message,
                is_retryable=is_retryable and self.can_be_retried()
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def retry_processing(self) -> Result[None]:
        """Retry processing if allowed."""
        try:
            if not self.can_be_retried():
                raise BusinessRuleViolation(
                    "Video.CannotRetry",
                    "Video processing cannot be retried"
                )
            
            self._status = VideoStatus.CREATED
            self._last_error = None
            self._processing_started_at = None
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def archive(self, archived_by: UserId, reason: str) -> Result[None]:
        """Archive the video."""
        try:
            if self._status == VideoStatus.PROCESSING:
                raise BusinessRuleViolation(
                    "Video.CannotArchiveWhileProcessing",
                    "Cannot archive video while processing"
                )
            
            if not reason or len(reason.strip()) == 0:
                raise BusinessRuleViolation(
                    "Video.ArchiveReasonRequired",
                    "Archive reason is required"
                )
            
            self._status = VideoStatus.ARCHIVED
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(VideoArchived(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                video_id=self._video_id,
                archived_by=archived_by,
                reason=reason
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def soft_delete(self) -> Result[None]:
        """Soft delete the video."""
        try:
            if not self.can_be_deleted():
                raise BusinessRuleViolation(
                    "Video.CannotDelete",
                    "Cannot delete video while processing"
                )
            
            self._is_deleted = True
            self._deleted_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Validation methods
    def _validate_business_rules(self) -> None:
        """Validate all business rules for the video."""
        self._validate_title()
        self._validate_topic()
        self._validate_context()
        self._validate_processing_config()
        self._validate_tags(self._tags)
        self._validate_status()
    
    def _validate_title(self) -> None:
        """Validate video title."""
        if not self._title:
            raise BusinessRuleViolation(
                "Video.TitleRequired",
                "Video title is required"
            )
    
    def _validate_topic(self) -> None:
        """Validate video topic."""
        if not self._topic:
            raise BusinessRuleViolation(
                "Video.TopicRequired",
                "Video topic is required"
            )
    
    def _validate_context(self) -> None:
        """Validate video context."""
        if not self._context:
            raise BusinessRuleViolation(
                "Video.ContextRequired",
                "Video context is required"
            )
    
    def _validate_processing_config(self) -> None:
        """Validate processing configuration."""
        if not self._processing_config:
            raise BusinessRuleViolation(
                "Video.ProcessingConfigRequired",
                "Video processing configuration is required"
            )
    
    def _validate_tags(self, tags: List[str]) -> None:
        """Validate video tags."""
        if len(tags) > 20:
            raise BusinessRuleViolation(
                "Video.TooManyTags",
                "Video cannot have more than 20 tags"
            )
        
        for tag in tags:
            if not tag or len(tag.strip()) == 0:
                raise BusinessRuleViolation(
                    "Video.EmptyTag",
                    "Video tags cannot be empty"
                )
            
            if len(tag) > 50:
                raise BusinessRuleViolation(
                    "Video.TagTooLong",
                    "Video tags cannot exceed 50 characters"
                )
    
    def _validate_status(self) -> None:
        """Validate video status."""
        valid_statuses = [
            VideoStatus.CREATED,
            VideoStatus.UPLOADED,
            VideoStatus.PROCESSING,
            VideoStatus.COMPLETED,
            VideoStatus.FAILED,
            VideoStatus.ARCHIVED
        ]
        if self._status not in valid_statuses:
            raise BusinessRuleViolation(
                "Video.InvalidStatus",
                f"Invalid video status: {self._status}"
            )
    
    def __repr__(self) -> str:
        return f"Video(id={self._video_id}, title='{self._title}', status={self._status})"

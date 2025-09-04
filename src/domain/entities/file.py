"""
File domain entity.

This module defines the File aggregate root with business logic,
validation rules, and domain events for file management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from ..common import AggregateRoot, DomainEvent, BusinessRuleViolation, Result
from ..value_objects import FileId, UserId, JobId, FileSize


@dataclass(frozen=True)
class FileUploaded(DomainEvent):
    """Domain event raised when a file is uploaded."""
    file_id: FileId
    user_id: UserId
    file_type: str
    file_size: FileSize


@dataclass(frozen=True)
class FileProcessed(DomainEvent):
    """Domain event raised when a file is processed."""
    file_id: FileId
    job_id: JobId
    processing_metadata: Dict[str, Any]


@dataclass(frozen=True)
class FileDeleted(DomainEvent):
    """Domain event raised when a file is deleted."""
    file_id: FileId
    deleted_by: UserId
    reason: str


class FileType:
    """File type constants."""
    VIDEO_INPUT = "video_input"
    VIDEO_OUTPUT = "video_output"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    THUMBNAIL = "thumbnail"
    SUBTITLE = "subtitle"
    METADATA = "metadata"


class File(AggregateRoot):
    """
    File aggregate root representing a file in the system.
    
    Files can be uploaded by users and associated with jobs for processing.
    They track metadata, storage information, and processing history.
    
    Business Rules:
    - Must have a valid file type and size
    - Cannot be deleted if associated with active jobs
    - File size must be within allowed limits for the file type
    - Original filename must be preserved for audit purposes
    - S3 storage information must be valid and unique
    """
    
    def __init__(
        self,
        file_id: FileId,
        user_id: UserId,
        file_type: str,
        original_filename: str,
        stored_filename: str,
        s3_bucket: str,
        s3_key: str,
        file_size: FileSize,
        content_type: str,
        job_id: Optional[JobId] = None,
        s3_version_id: Optional[str] = None,
        checksum: Optional[str] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        last_accessed_at: Optional[datetime] = None
    ):
        super().__init__(file_id.value)
        
        self._file_id = file_id
        self._user_id = user_id
        self._job_id = job_id
        self._file_type = file_type
        self._original_filename = original_filename
        self._stored_filename = stored_filename
        self._s3_bucket = s3_bucket
        self._s3_key = s3_key
        self._s3_version_id = s3_version_id
        self._file_size = file_size
        self._content_type = content_type
        self._checksum = checksum
        self._file_metadata = file_metadata or {}
        self._description = description
        self._tags = tags or []
        self._created_at = created_at or datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._last_accessed_at = last_accessed_at
        self._is_deleted = False
        self._deleted_at = None
        
        # Validate business rules
        self._validate_business_rules()
    
    @classmethod
    def create(
        cls,
        user_id: UserId,
        file_type: str,
        original_filename: str,
        stored_filename: str,
        s3_bucket: str,
        s3_key: str,
        file_size: FileSize,
        content_type: str,
        job_id: Optional[JobId] = None,
        checksum: Optional[str] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Result["File"]:
        """
        Create a new file with business rule validation.
        
        Returns:
            Result containing the created File or error message
        """
        try:
            # Generate new file ID
            file_id = FileId.generate()
            
            # Create file instance
            file = cls(
                file_id=file_id,
                user_id=user_id,
                file_type=file_type,
                original_filename=original_filename,
                stored_filename=stored_filename,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
                file_size=file_size,
                content_type=content_type,
                job_id=job_id,
                checksum=checksum,
                file_metadata=file_metadata,
                description=description,
                tags=tags
            )
            
            # Add domain event
            file.add_domain_event(FileUploaded(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=file.id,
                version=file.version,
                file_id=file_id,
                user_id=user_id,
                file_type=file_type,
                file_size=file_size
            ))
            
            return Result.ok(file)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Properties
    @property
    def file_id(self) -> FileId:
        """Get the file ID."""
        return self._file_id
    
    @property
    def user_id(self) -> UserId:
        """Get the user ID who owns this file."""
        return self._user_id
    
    @property
    def job_id(self) -> Optional[JobId]:
        """Get the job ID associated with this file."""
        return self._job_id
    
    @property
    def file_type(self) -> str:
        """Get the file type."""
        return self._file_type
    
    @property
    def original_filename(self) -> str:
        """Get the original filename."""
        return self._original_filename
    
    @property
    def stored_filename(self) -> str:
        """Get the stored filename."""
        return self._stored_filename
    
    @property
    def s3_bucket(self) -> str:
        """Get the S3 bucket name."""
        return self._s3_bucket
    
    @property
    def s3_key(self) -> str:
        """Get the S3 object key."""
        return self._s3_key
    
    @property
    def s3_version_id(self) -> Optional[str]:
        """Get the S3 version ID."""
        return self._s3_version_id
    
    @property
    def file_size(self) -> FileSize:
        """Get the file size."""
        return self._file_size
    
    @property
    def content_type(self) -> str:
        """Get the content type."""
        return self._content_type
    
    @property
    def checksum(self) -> Optional[str]:
        """Get the file checksum."""
        return self._checksum
    
    @property
    def file_metadata(self) -> Dict[str, Any]:
        """Get the file metadata."""
        return self._file_metadata.copy()
    
    @property
    def description(self) -> Optional[str]:
        """Get the file description."""
        return self._description
    
    @property
    def tags(self) -> List[str]:
        """Get the file tags."""
        return self._tags.copy()
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def last_accessed_at(self) -> Optional[datetime]:
        """Get last access timestamp."""
        return self._last_accessed_at
    
    @property
    def is_deleted(self) -> bool:
        """Check if file is soft deleted."""
        return self._is_deleted
    
    @property
    def deleted_at(self) -> Optional[datetime]:
        """Get deletion timestamp."""
        return self._deleted_at
    
    # Business logic methods
    def is_image(self) -> bool:
        """Check if the file is an image."""
        return self._file_type == FileType.IMAGE or self._content_type.startswith('image/')
    
    def is_video(self) -> bool:
        """Check if the file is a video."""
        return (self._file_type in [FileType.VIDEO_INPUT, FileType.VIDEO_OUTPUT] or 
                self._content_type.startswith('video/'))
    
    def is_audio(self) -> bool:
        """Check if the file is audio."""
        return self._file_type == FileType.AUDIO or self._content_type.startswith('audio/')
    
    def is_document(self) -> bool:
        """Check if the file is a document."""
        return self._file_type == FileType.DOCUMENT
    
    def is_output_file(self) -> bool:
        """Check if the file is a processing output."""
        return self._file_type in [FileType.VIDEO_OUTPUT, FileType.THUMBNAIL, FileType.SUBTITLE]
    
    def is_input_file(self) -> bool:
        """Check if the file is a processing input."""
        return self._file_type == FileType.VIDEO_INPUT
    
    def can_be_deleted(self) -> bool:
        """Check if the file can be deleted."""
        # Cannot delete if associated with an active job (this would need job status check)
        # For now, allow deletion unless explicitly protected
        return not self._is_deleted
    
    def is_large_file(self) -> bool:
        """Check if the file is considered large (>100MB)."""
        return self._file_size.megabytes > 100
    
    def needs_virus_scan(self) -> bool:
        """Check if the file needs virus scanning."""
        # Scan all uploaded files except known safe outputs
        return not self.is_output_file()
    
    def get_s3_url(self) -> str:
        """Get the S3 URL for this file."""
        return f"s3://{self._s3_bucket}/{self._s3_key}"
    
    def get_file_extension(self) -> str:
        """Get the file extension from the original filename."""
        if '.' in self._original_filename:
            return self._original_filename.split('.')[-1].lower()
        return ""
    
    # Mutation methods
    def associate_with_job(self, job_id: JobId) -> Result[None]:
        """Associate the file with a job."""
        try:
            if self._job_id is not None:
                raise BusinessRuleViolation(
                    "File.AlreadyAssociatedWithJob",
                    f"File is already associated with job: {self._job_id}"
                )
            
            self._job_id = job_id
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def update_metadata(
        self,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        file_metadata: Optional[Dict[str, Any]] = None
    ) -> Result[None]:
        """Update file metadata."""
        try:
            if description is not None:
                self._validate_description(description)
                self._description = description
            
            if tags is not None:
                self._validate_tags(tags)
                self._tags = tags
            
            if file_metadata is not None:
                self._file_metadata.update(file_metadata)
            
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def mark_processed(
        self,
        job_id: JobId,
        processing_metadata: Optional[Dict[str, Any]] = None
    ) -> Result[None]:
        """Mark the file as processed by a job."""
        try:
            if processing_metadata:
                self._file_metadata.update(processing_metadata)
            
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(FileProcessed(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                file_id=self._file_id,
                job_id=job_id,
                processing_metadata=processing_metadata or {}
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def record_access(self) -> None:
        """Record file access timestamp."""
        self._last_accessed_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
    
    def update_checksum(self, checksum: str) -> Result[None]:
        """Update file checksum."""
        try:
            if not checksum or len(checksum.strip()) == 0:
                raise BusinessRuleViolation(
                    "File.InvalidChecksum",
                    "Checksum cannot be empty"
                )
            
            if len(checksum) != 64:  # SHA-256 is 64 characters
                raise BusinessRuleViolation(
                    "File.InvalidChecksumLength",
                    "Checksum must be 64 characters (SHA-256)"
                )
            
            self._checksum = checksum
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def soft_delete(self, deleted_by: UserId, reason: str) -> Result[None]:
        """Soft delete the file."""
        try:
            if not self.can_be_deleted():
                raise BusinessRuleViolation(
                    "File.CannotDelete",
                    "File cannot be deleted"
                )
            
            if not reason or len(reason.strip()) == 0:
                raise BusinessRuleViolation(
                    "File.DeleteReasonRequired",
                    "Delete reason is required"
                )
            
            self._is_deleted = True
            self._deleted_at = datetime.utcnow()
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(FileDeleted(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                file_id=self._file_id,
                deleted_by=deleted_by,
                reason=reason
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Validation methods
    def _validate_business_rules(self) -> None:
        """Validate all business rules for the file."""
        self._validate_file_type()
        self._validate_filenames()
        self._validate_s3_info()
        self._validate_content_type()
        self._validate_file_size_for_type()
        if self._description:
            self._validate_description(self._description)
        self._validate_tags(self._tags)
        if self._checksum:
            self._validate_checksum()
    
    def _validate_file_type(self) -> None:
        """Validate file type."""
        valid_types = [
            FileType.VIDEO_INPUT,
            FileType.VIDEO_OUTPUT,
            FileType.IMAGE,
            FileType.AUDIO,
            FileType.DOCUMENT,
            FileType.THUMBNAIL,
            FileType.SUBTITLE,
            FileType.METADATA
        ]
        if self._file_type not in valid_types:
            raise BusinessRuleViolation(
                "File.InvalidFileType",
                f"Invalid file type: {self._file_type}"
            )
    
    def _validate_filenames(self) -> None:
        """Validate filenames."""
        if not self._original_filename or len(self._original_filename.strip()) == 0:
            raise BusinessRuleViolation(
                "File.OriginalFilenameRequired",
                "Original filename is required"
            )
        
        if len(self._original_filename) > 255:
            raise BusinessRuleViolation(
                "File.OriginalFilenameTooLong",
                "Original filename cannot exceed 255 characters"
            )
        
        if not self._stored_filename or len(self._stored_filename.strip()) == 0:
            raise BusinessRuleViolation(
                "File.StoredFilenameRequired",
                "Stored filename is required"
            )
        
        if len(self._stored_filename) > 255:
            raise BusinessRuleViolation(
                "File.StoredFilenameTooLong",
                "Stored filename cannot exceed 255 characters"
            )
    
    def _validate_s3_info(self) -> None:
        """Validate S3 storage information."""
        if not self._s3_bucket or len(self._s3_bucket.strip()) == 0:
            raise BusinessRuleViolation(
                "File.S3BucketRequired",
                "S3 bucket is required"
            )
        
        if len(self._s3_bucket) > 255:
            raise BusinessRuleViolation(
                "File.S3BucketTooLong",
                "S3 bucket name cannot exceed 255 characters"
            )
        
        if not self._s3_key or len(self._s3_key.strip()) == 0:
            raise BusinessRuleViolation(
                "File.S3KeyRequired",
                "S3 key is required"
            )
        
        if len(self._s3_key) > 500:
            raise BusinessRuleViolation(
                "File.S3KeyTooLong",
                "S3 key cannot exceed 500 characters"
            )
    
    def _validate_content_type(self) -> None:
        """Validate content type."""
        if not self._content_type or len(self._content_type.strip()) == 0:
            raise BusinessRuleViolation(
                "File.ContentTypeRequired",
                "Content type is required"
            )
        
        if len(self._content_type) > 100:
            raise BusinessRuleViolation(
                "File.ContentTypeTooLong",
                "Content type cannot exceed 100 characters"
            )
        
        # Basic MIME type validation
        if '/' not in self._content_type:
            raise BusinessRuleViolation(
                "File.InvalidContentType",
                "Content type must be a valid MIME type"
            )
    
    def _validate_file_size_for_type(self) -> None:
        """Validate file size based on file type."""
        # Define size limits for different file types (in bytes)
        size_limits = {
            FileType.VIDEO_INPUT: 5 * 1024 * 1024 * 1024,   # 5GB
            FileType.VIDEO_OUTPUT: 10 * 1024 * 1024 * 1024,  # 10GB
            FileType.IMAGE: 50 * 1024 * 1024,                # 50MB
            FileType.AUDIO: 500 * 1024 * 1024,               # 500MB
            FileType.DOCUMENT: 100 * 1024 * 1024,            # 100MB
            FileType.THUMBNAIL: 10 * 1024 * 1024,            # 10MB
            FileType.SUBTITLE: 1 * 1024 * 1024,              # 1MB
            FileType.METADATA: 1 * 1024 * 1024,              # 1MB
        }
        
        if self._file_type in size_limits:
            max_size = size_limits[self._file_type]
            if self._file_size.bytes > max_size:
                max_size_obj = FileSize(max_size)
                raise BusinessRuleViolation(
                    "File.FileSizeExceedsLimit",
                    f"File size ({self._file_size}) exceeds limit for {self._file_type}: {max_size_obj}"
                )
    
    def _validate_description(self, description: str) -> None:
        """Validate file description."""
        if len(description) > 1000:
            raise BusinessRuleViolation(
                "File.DescriptionTooLong",
                "File description cannot exceed 1000 characters"
            )
    
    def _validate_tags(self, tags: List[str]) -> None:
        """Validate file tags."""
        if len(tags) > 20:
            raise BusinessRuleViolation(
                "File.TooManyTags",
                "File cannot have more than 20 tags"
            )
        
        for tag in tags:
            if not tag or len(tag.strip()) == 0:
                raise BusinessRuleViolation(
                    "File.EmptyTag",
                    "File tags cannot be empty"
                )
            
            if len(tag) > 50:
                raise BusinessRuleViolation(
                    "File.TagTooLong",
                    "File tags cannot exceed 50 characters"
                )
    
    def _validate_checksum(self) -> None:
        """Validate file checksum."""
        if len(self._checksum) != 64:
            raise BusinessRuleViolation(
                "File.InvalidChecksumLength",
                "Checksum must be 64 characters (SHA-256)"
            )
        
        # Check if it's a valid hex string
        try:
            int(self._checksum, 16)
        except ValueError:
            raise BusinessRuleViolation(
                "File.InvalidChecksumFormat",
                "Checksum must be a valid hexadecimal string"
            )
    
    def __repr__(self) -> str:
        return f"File(id={self._file_id}, filename='{self._original_filename}', type={self._file_type})"

"""
File-related value objects for the domain.

This module contains value objects specific to file management,
including file types, paths, and storage locations.
"""

from dataclasses import dataclass
from typing import Optional
import re
import os

from ..common import ValueObject, BusinessRuleViolation


@dataclass(frozen=True)
class FileType(ValueObject):
    """
    Value object representing file type with validation.
    """
    
    value: str
    
    @classmethod
    def create(cls, value: str) -> "Result[FileType]":
        """
        Create file type with validation.
        
        Args:
            value: File type string
            
        Returns:
            Result containing FileType or error
        """
        from .. import Result
        
        try:
            if not isinstance(value, str):
                return Result.fail("File type must be a string")
            
            value = value.strip().lower()
            
            if not value:
                return Result.fail("File type cannot be empty")
            
            instance = cls(value=value)
            instance.validate()
            
            return Result.ok(instance)
            
        except Exception as e:
            return Result.fail(f"Invalid file type: {str(e)}")
    
    def validate(self) -> None:
        """Validate file type."""
        if not self.value:
            raise BusinessRuleViolation(
                "FileType.Empty",
                "File type cannot be empty"
            )
        
        if len(self.value) > 50:
            raise BusinessRuleViolation(
                "FileType.TooLong",
                "File type cannot exceed 50 characters"
            )
        
        # Check for valid characters (alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-z0-9_-]+$', self.value):
            raise BusinessRuleViolation(
                "FileType.InvalidCharacters",
                "File type can only contain lowercase letters, numbers, underscores, and hyphens"
            )
    
    @property
    def is_video(self) -> bool:
        """Check if file type is video."""
        return self.value in ['video', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm']
    
    @property
    def is_audio(self) -> bool:
        """Check if file type is audio."""
        return self.value in ['audio', 'mp3', 'wav', 'aac', 'flac', 'ogg']
    
    @property
    def is_image(self) -> bool:
        """Check if file type is image."""
        return self.value in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg']
    
    @property
    def is_document(self) -> bool:
        """Check if file type is document."""
        return self.value in ['document', 'pdf', 'doc', 'docx', 'txt', 'rtf']
    
    def __repr__(self) -> str:
        return f"FileType({self.value})"


@dataclass(frozen=True)
class FilePath(ValueObject):
    """
    Value object representing file path with validation.
    """
    
    value: str
    
    @classmethod
    def create(cls, value: str) -> "Result[FilePath]":
        """
        Create file path with validation.
        
        Args:
            value: File path string
            
        Returns:
            Result containing FilePath or error
        """
        from .. import Result
        
        try:
            if not isinstance(value, str):
                return Result.fail("File path must be a string")
            
            value = value.strip()
            
            if not value:
                return Result.fail("File path cannot be empty")
            
            instance = cls(value=value)
            instance.validate()
            
            return Result.ok(instance)
            
        except Exception as e:
            return Result.fail(f"Invalid file path: {str(e)}")
    
    def validate(self) -> None:
        """Validate file path."""
        if not self.value:
            raise BusinessRuleViolation(
                "FilePath.Empty",
                "File path cannot be empty"
            )
        
        if len(self.value) > 1000:
            raise BusinessRuleViolation(
                "FilePath.TooLong",
                "File path cannot exceed 1000 characters"
            )
        
        # Check for dangerous characters
        dangerous_chars = ['..', '<', '>', '|', '"', '?', '*']
        for char in dangerous_chars:
            if char in self.value:
                raise BusinessRuleViolation(
                    "FilePath.DangerousCharacters",
                    f"File path cannot contain dangerous character: {char}"
                )
        
        # Check for null bytes
        if '\x00' in self.value:
            raise BusinessRuleViolation(
                "FilePath.NullByte",
                "File path cannot contain null bytes"
            )
    
    @property
    def filename(self) -> str:
        """Get filename from path."""
        return os.path.basename(self.value)
    
    @property
    def directory(self) -> str:
        """Get directory from path."""
        return os.path.dirname(self.value)
    
    @property
    def extension(self) -> str:
        """Get file extension."""
        _, ext = os.path.splitext(self.value)
        return ext.lower()
    
    def __repr__(self) -> str:
        return f"FilePath({self.value})"


@dataclass(frozen=True)
class S3Location(ValueObject):
    """
    Value object representing S3 storage location.
    """
    
    bucket: str
    key: str
    version_id: Optional[str] = None
    
    def validate(self) -> None:
        """Validate S3 location."""
        # Bucket validation
        if not self.bucket:
            raise BusinessRuleViolation(
                "S3Location.EmptyBucket",
                "S3 bucket name cannot be empty"
            )
        
        if len(self.bucket) < 3 or len(self.bucket) > 63:
            raise BusinessRuleViolation(
                "S3Location.InvalidBucketLength",
                "S3 bucket name must be between 3 and 63 characters"
            )
        
        # Simple bucket name validation (more restrictive than AWS)
        if not re.match(r'^[a-z0-9.-]+$', self.bucket):
            raise BusinessRuleViolation(
                "S3Location.InvalidBucketName",
                "S3 bucket name can only contain lowercase letters, numbers, dots, and hyphens"
            )
        
        # Key validation
        if not self.key:
            raise BusinessRuleViolation(
                "S3Location.EmptyKey",
                "S3 key cannot be empty"
            )
        
        if len(self.key) > 1024:
            raise BusinessRuleViolation(
                "S3Location.KeyTooLong",
                "S3 key cannot exceed 1024 characters"
            )
        
        # Version ID validation
        if self.version_id is not None:
            if not self.version_id.strip():
                raise BusinessRuleViolation(
                    "S3Location.EmptyVersionId",
                    "S3 version ID cannot be empty if specified"
                )
            
            if len(self.version_id) > 1024:
                raise BusinessRuleViolation(
                    "S3Location.VersionIdTooLong",
                    "S3 version ID cannot exceed 1024 characters"
                )
    
    @property
    def url(self) -> str:
        """Get S3 URL for the object."""
        base_url = f"s3://{self.bucket}/{self.key}"
        if self.version_id:
            base_url += f"?versionId={self.version_id}"
        return base_url
    
    @property
    def https_url(self) -> str:
        """Get HTTPS URL for the object."""
        base_url = f"https://{self.bucket}.s3.amazonaws.com/{self.key}"
        if self.version_id:
            base_url += f"?versionId={self.version_id}"
        return base_url
    
    def with_version(self, version_id: str) -> "S3Location":
        """Create new S3 location with different version ID."""
        return S3Location(
            bucket=self.bucket,
            key=self.key,
            version_id=version_id
        )
    
    def __repr__(self) -> str:
        version = f", version={self.version_id}" if self.version_id else ""
        return f"S3Location(bucket={self.bucket}, key={self.key}{version})"

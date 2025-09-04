"""
Core value objects for the video generation domain.

This module defines fundamental value objects that represent
important domain concepts with built-in validation and behavior.
"""

import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from ..common import ValueObject, BusinessRuleViolation


@dataclass(frozen=True)
class UserId(ValueObject):
    """
    Value object representing a user identifier.
    
    Supports both UUID-based internal IDs and external Clerk user IDs.
    
    Examples:
        # UUID-based ID
        user_id = UserId.from_uuid(uuid4())
        
        # Clerk user ID
        user_id = UserId.from_clerk_id("user_2NiWoZK2iKDvEFEHaakTrHVfcrq")
        
        # String representation
        str(user_id)  # Returns the string value
    """
    
    value: str
    
    @classmethod
    def from_uuid(cls, uuid_value: UUID) -> "UserId":
        """Create a UserId from a UUID."""
        return cls(str(uuid_value))
    
    @classmethod
    def from_clerk_id(cls, clerk_id: str) -> "UserId":
        """Create a UserId from a Clerk user ID."""
        return cls(clerk_id)
    
    @classmethod
    def from_string(cls, value: str) -> "UserId":
        """Create a UserId from a string value."""
        return cls(value)
    
    def validate(self) -> None:
        """Validate the user ID format and requirements."""
        if not self.value:
            raise BusinessRuleViolation(
                "UserId.NotEmpty", 
                "User ID cannot be empty"
            )
        
        if len(self.value) < 3:
            raise BusinessRuleViolation(
                "UserId.MinLength", 
                "User ID must be at least 3 characters long"
            )
        
        if len(self.value) > 255:
            raise BusinessRuleViolation(
                "UserId.MaxLength", 
                "User ID cannot exceed 255 characters"
            )
        
        # Allow alphanumeric characters, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.value):
            raise BusinessRuleViolation(
                "UserId.InvalidFormat", 
                "User ID can only contain alphanumeric characters, hyphens, and underscores"
            )
    
    def is_uuid_format(self) -> bool:
        """Check if the user ID is in UUID format."""
        try:
            UUID(self.value)
            return True
        except ValueError:
            return False
    
    def is_clerk_format(self) -> bool:
        """Check if the user ID is in Clerk format."""
        return self.value.startswith('user_')
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"UserId('{self.value}')"


@dataclass(frozen=True)
class VideoId(ValueObject):
    """
    Value object representing a video identifier.
    
    Video IDs are UUID-based for consistency and uniqueness.
    
    Examples:
        # Create new video ID
        video_id = VideoId.generate()
        
        # From existing UUID
        video_id = VideoId.from_uuid(existing_uuid)
        
        # From string
        video_id = VideoId.from_string("550e8400-e29b-41d4-a716-446655440000")
    """
    
    value: UUID
    
    @classmethod
    def generate(cls) -> "VideoId":
        """Generate a new unique video ID."""
        return cls(uuid4())
    
    @classmethod
    def from_uuid(cls, uuid_value: UUID) -> "VideoId":
        """Create a VideoId from an existing UUID."""
        return cls(uuid_value)
    
    @classmethod
    def from_string(cls, value: str) -> "VideoId":
        """Create a VideoId from a string representation."""
        try:
            uuid_value = UUID(value)
            return cls(uuid_value)
        except ValueError as e:
            raise BusinessRuleViolation(
                "VideoId.InvalidFormat", 
                f"Invalid UUID format for video ID: {value}"
            ) from e
    
    def validate(self) -> None:
        """Validate the video ID."""
        if self.value is None:
            raise BusinessRuleViolation(
                "VideoId.NotNull", 
                "Video ID cannot be null"
            )
        
        # UUID validation is handled by the UUID type itself
        if self.value.version not in [1, 4]:
            raise BusinessRuleViolation(
                "VideoId.InvalidVersion", 
                f"Video ID must be UUID version 1 or 4, got version {self.value.version}"
            )
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"VideoId('{self.value}')"


@dataclass(frozen=True)
class JobId(ValueObject):
    """
    Value object representing a job identifier.
    
    Job IDs are UUID-based for consistency and uniqueness.
    """
    
    value: UUID
    
    @classmethod
    def generate(cls) -> "JobId":
        """Generate a new unique job ID."""
        return cls(uuid4())
    
    @classmethod
    def from_uuid(cls, uuid_value: UUID) -> "JobId":
        """Create a JobId from an existing UUID."""
        return cls(uuid_value)
    
    @classmethod
    def from_string(cls, value: str) -> "JobId":
        """Create a JobId from a string representation."""
        try:
            uuid_value = UUID(value)
            return cls(uuid_value)
        except ValueError as e:
            raise BusinessRuleViolation(
                "JobId.InvalidFormat", 
                f"Invalid UUID format for job ID: {value}"
            ) from e
    
    def validate(self) -> None:
        """Validate the job ID."""
        if self.value is None:
            raise BusinessRuleViolation(
                "JobId.NotNull", 
                "Job ID cannot be null"
            )
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"JobId('{self.value}')"


@dataclass(frozen=True)
class FileId(ValueObject):
    """
    Value object representing a file identifier.
    
    File IDs are UUID-based for consistency and uniqueness.
    """
    
    value: UUID
    
    @classmethod
    def generate(cls) -> "FileId":
        """Generate a new unique file ID."""
        return cls(uuid4())
    
    @classmethod
    def from_uuid(cls, uuid_value: UUID) -> "FileId":
        """Create a FileId from an existing UUID."""
        return cls(uuid_value)
    
    @classmethod
    def from_string(cls, value: str) -> "FileId":
        """Create a FileId from a string representation."""
        try:
            uuid_value = UUID(value)
            return cls(uuid_value)
        except ValueError as e:
            raise BusinessRuleViolation(
                "FileId.InvalidFormat", 
                f"Invalid UUID format for file ID: {value}"
            ) from e
    
    def validate(self) -> None:
        """Validate the file ID."""
        if self.value is None:
            raise BusinessRuleViolation(
                "FileId.NotNull", 
                "File ID cannot be null"
            )
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"FileId('{self.value}')"


@dataclass(frozen=True)
class EmailAddress(ValueObject):
    """
    Value object representing an email address with validation.
    
    Examples:
        email = EmailAddress("user@example.com")
        print(email.local_part)  # "user"
        print(email.domain)      # "example.com"
    """
    
    value: str
    
    @classmethod
    def create(cls, value: str) -> "EmailAddress":
        """Create an EmailAddress with validation."""
        return cls(value)
    
    def validate(self) -> None:
        """Validate the email address format."""
        if not self.value:
            raise BusinessRuleViolation(
                "EmailAddress.NotEmpty", 
                "Email address cannot be empty"
            )
        
        if len(self.value) > 254:  # RFC 5321 limit
            raise BusinessRuleViolation(
                "EmailAddress.TooLong", 
                "Email address cannot exceed 254 characters"
            )
        
        # Basic email validation regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.value):
            raise BusinessRuleViolation(
                "EmailAddress.InvalidFormat", 
                f"Invalid email address format: {self.value}"
            )
        
        local_part, domain = self.value.split('@')
        
        if len(local_part) > 64:  # RFC 5321 limit
            raise BusinessRuleViolation(
                "EmailAddress.LocalPartTooLong", 
                "Email local part cannot exceed 64 characters"
            )
        
        if len(domain) > 253:  # RFC 5321 limit
            raise BusinessRuleViolation(
                "EmailAddress.DomainTooLong", 
                "Email domain cannot exceed 253 characters"
            )
    
    @property
    def local_part(self) -> str:
        """Get the local part of the email address (before @)."""
        return self.value.split('@')[0]
    
    @property
    def domain(self) -> str:
        """Get the domain part of the email address (after @)."""
        return self.value.split('@')[1]
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"EmailAddress('{self.value}')"


@dataclass(frozen=True)
class PhoneNumber(ValueObject):
    """
    Value object representing a phone number with validation.
    
    Supports international format validation.
    """
    
    value: str
    
    def validate(self) -> None:
        """Validate the phone number format."""
        if not self.value:
            raise BusinessRuleViolation(
                "PhoneNumber.NotEmpty", 
                "Phone number cannot be empty"
            )
        
        # Remove common formatting characters for validation
        cleaned = re.sub(r'[\s\-\(\)\+\.]', '', self.value)
        
        # Basic phone number validation (digits only after cleaning)
        if not re.match(r'^\d{7,15}$', cleaned):
            raise BusinessRuleViolation(
                "PhoneNumber.InvalidFormat", 
                f"Invalid phone number format: {self.value}"
            )
        
        if len(self.value) > 50:
            raise BusinessRuleViolation(
                "PhoneNumber.TooLong", 
                "Phone number cannot exceed 50 characters"
            )
    
    @property
    def normalized(self) -> str:
        """Get the normalized phone number (digits only)."""
        return re.sub(r'[\s\-\(\)\+\.]', '', self.value)
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"PhoneNumber('{self.value}')"

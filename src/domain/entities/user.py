"""
User domain entity.

This module defines the User aggregate root with business logic,
validation rules, and domain events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from ..common import AggregateRoot, DomainEvent, BusinessRuleViolation, Result
from ..value_objects import UserId, EmailAddress, PhoneNumber


@dataclass(frozen=True)
class UserCreated(DomainEvent):
    """Domain event raised when a user is created."""
    user_id: UserId
    clerk_user_id: str
    email: EmailAddress


@dataclass(frozen=True)
class UserUpdated(DomainEvent):
    """Domain event raised when a user is updated."""
    user_id: UserId
    updated_fields: List[str]


@dataclass(frozen=True)
class UserDeactivated(DomainEvent):
    """Domain event raised when a user is deactivated."""
    user_id: UserId
    reason: str


class UserStatus:
    """User status constants."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserRole:
    """User role constants."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(AggregateRoot):
    """
    User aggregate root representing a user in the system.
    
    Users are authenticated through Clerk and have associated
    profile information, roles, and video generation history.
    
    Business Rules:
    - Must have a valid Clerk user ID
    - Must have at least one verified email address
    - Cannot be deleted if they have active video generation jobs
    - Admin users cannot be suspended by non-admin users
    """
    
    def __init__(
        self,
        user_id: UserId,
        clerk_user_id: str,
        primary_email: EmailAddress,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        image_url: Optional[str] = None,
        role: str = UserRole.USER,
        status: str = UserStatus.ACTIVE,
        email_addresses: Optional[List[EmailAddress]] = None,
        phone_numbers: Optional[List[PhoneNumber]] = None,
        email_verified: bool = False,
        phone_verified: bool = False,
        two_factor_enabled: bool = False,
        user_metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        last_sign_in_at: Optional[datetime] = None,
        last_active_at: Optional[datetime] = None
    ):
        super().__init__(user_id.value if isinstance(user_id.value, UUID) else uuid4())
        
        self._user_id = user_id
        self._clerk_user_id = clerk_user_id
        self._username = username
        self._first_name = first_name
        self._last_name = last_name
        self._image_url = image_url
        self._primary_email = primary_email
        self._role = role
        self._status = status
        self._email_addresses = email_addresses or [primary_email]
        self._phone_numbers = phone_numbers or []
        self._primary_phone = phone_numbers[0] if phone_numbers else None
        self._email_verified = email_verified
        self._phone_verified = phone_verified
        self._two_factor_enabled = two_factor_enabled
        self._user_metadata = user_metadata or {}
        self._created_at = created_at or datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._last_sign_in_at = last_sign_in_at
        self._last_active_at = last_active_at
        self._is_deleted = False
        self._deleted_at = None
        
        # Validate business rules
        self._validate_business_rules()
    
    @classmethod
    def create(
        cls,
        clerk_user_id: str,
        primary_email: EmailAddress,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email_addresses: Optional[List[EmailAddress]] = None
    ) -> Result["User"]:
        """
        Create a new user with business rule validation.
        
        Returns:
            Result containing the created User or error message
        """
        try:
            # Generate new user ID
            user_id = UserId.from_uuid(uuid4())
            
            # Create user instance
            user = cls(
                user_id=user_id,
                clerk_user_id=clerk_user_id,
                primary_email=primary_email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                email_addresses=email_addresses
            )
            
            # Add domain event
            user.add_domain_event(UserCreated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=user.id,
                version=user.version,
                user_id=user_id,
                clerk_user_id=clerk_user_id,
                email=primary_email
            ))
            
            return Result.ok(user)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    # Properties
    @property
    def user_id(self) -> UserId:
        """Get the user ID."""
        return self._user_id
    
    @property
    def clerk_user_id(self) -> str:
        """Get the Clerk user ID."""
        return self._clerk_user_id
    
    @property
    def username(self) -> Optional[str]:
        """Get the username."""
        return self._username
    
    @property
    def first_name(self) -> Optional[str]:
        """Get the first name."""
        return self._first_name
    
    @property
    def last_name(self) -> Optional[str]:
        """Get the last name."""
        return self._last_name
    
    @property
    def full_name(self) -> str:
        """Get the full name combining first and last name."""
        parts = []
        if self._first_name:
            parts.append(self._first_name)
        if self._last_name:
            parts.append(self._last_name)
        return " ".join(parts) if parts else self._username or "Unknown User"
    
    @property
    def image_url(self) -> Optional[str]:
        """Get the image URL."""
        return self._image_url
    
    @property
    def primary_email(self) -> EmailAddress:
        """Get the primary email address."""
        return self._primary_email
    
    @property
    def role(self) -> str:
        """Get the user role."""
        return self._role
    
    @property
    def status(self) -> str:
        """Get the user status."""
        return self._status
    
    @property
    def email_addresses(self) -> List[EmailAddress]:
        """Get all email addresses."""
        return self._email_addresses.copy()
    
    @property
    def phone_numbers(self) -> List[PhoneNumber]:
        """Get all phone numbers."""
        return self._phone_numbers.copy()
    
    @property
    def primary_phone(self) -> Optional[PhoneNumber]:
        """Get the primary phone number."""
        return self._primary_phone
    
    @property
    def email_verified(self) -> bool:
        """Check if email is verified."""
        return self._email_verified
    
    @property
    def phone_verified(self) -> bool:
        """Check if phone is verified."""
        return self._phone_verified
    
    @property
    def two_factor_enabled(self) -> bool:
        """Check if two-factor authentication is enabled."""
        return self._two_factor_enabled
    
    @property
    def user_metadata(self) -> Dict[str, Any]:
        """Get user metadata."""
        return self._user_metadata.copy()
    
    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at
    
    @property
    def last_sign_in_at(self) -> Optional[datetime]:
        """Get last sign-in timestamp."""
        return self._last_sign_in_at
    
    @property
    def last_active_at(self) -> Optional[datetime]:
        """Get last activity timestamp."""
        return self._last_active_at
    
    @property
    def is_deleted(self) -> bool:
        """Check if user is soft deleted."""
        return self._is_deleted
    
    @property
    def deleted_at(self) -> Optional[datetime]:
        """Get deletion timestamp."""
        return self._deleted_at
    
    # Business logic methods
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self._role == UserRole.ADMIN
    
    def is_moderator(self) -> bool:
        """Check if user has moderator role."""
        return self._role == UserRole.MODERATOR
    
    def is_active(self) -> bool:
        """Check if user is active."""
        return self._status == UserStatus.ACTIVE and not self._is_deleted
    
    def can_generate_videos(self) -> bool:
        """Check if user can generate videos."""
        return self.is_active() and self._email_verified
    
    def can_access_admin_features(self) -> bool:
        """Check if user can access admin features."""
        return self.is_active() and self.is_admin()
    
    def can_moderate_content(self) -> bool:
        """Check if user can moderate content."""
        return self.is_active() and (self.is_admin() or self.is_moderator())
    
    # Mutation methods
    def update_profile(
        self,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Result[None]:
        """Update user profile information."""
        try:
            updated_fields = []
            
            if username is not None and username != self._username:
                self._validate_username(username)
                self._username = username
                updated_fields.append("username")
            
            if first_name is not None and first_name != self._first_name:
                self._validate_name(first_name, "first_name")
                self._first_name = first_name
                updated_fields.append("first_name")
            
            if last_name is not None and last_name != self._last_name:
                self._validate_name(last_name, "last_name")
                self._last_name = last_name
                updated_fields.append("last_name")
            
            if image_url is not None and image_url != self._image_url:
                self._validate_image_url(image_url)
                self._image_url = image_url
                updated_fields.append("image_url")
            
            if updated_fields:
                self._updated_at = datetime.utcnow()
                self.increment_version()
                
                self.add_domain_event(UserUpdated(
                    event_id=uuid4(),
                    occurred_at=datetime.utcnow(),
                    aggregate_id=self.id,
                    version=self.version,
                    user_id=self._user_id,
                    updated_fields=updated_fields
                ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def change_role(self, new_role: str, changed_by_admin: bool = False) -> Result[None]:
        """Change user role with authorization check."""
        try:
            # Validate role
            valid_roles = [UserRole.USER, UserRole.ADMIN, UserRole.MODERATOR]
            if new_role not in valid_roles:
                raise BusinessRuleViolation(
                    "User.InvalidRole",
                    f"Invalid role: {new_role}"
                )
            
            # Business rule: Only admins can change roles
            if not changed_by_admin:
                raise BusinessRuleViolation(
                    "User.UnauthorizedRoleChange",
                    "Only admins can change user roles"
                )
            
            if new_role != self._role:
                self._role = new_role
                self._updated_at = datetime.utcnow()
                self.increment_version()
                
                self.add_domain_event(UserUpdated(
                    event_id=uuid4(),
                    occurred_at=datetime.utcnow(),
                    aggregate_id=self.id,
                    version=self.version,
                    user_id=self._user_id,
                    updated_fields=["role"]
                ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def suspend(self, reason: str, suspended_by_admin: bool = False) -> Result[None]:
        """Suspend the user account."""
        try:
            # Business rule: Only admins can suspend users
            if not suspended_by_admin:
                raise BusinessRuleViolation(
                    "User.UnauthorizedSuspension",
                    "Only admins can suspend users"
                )
            
            # Business rule: Cannot suspend admin users unless done by another admin
            if self.is_admin() and not suspended_by_admin:
                raise BusinessRuleViolation(
                    "User.CannotSuspendAdmin",
                    "Cannot suspend admin users"
                )
            
            if not reason or len(reason.strip()) == 0:
                raise BusinessRuleViolation(
                    "User.SuspensionReasonRequired",
                    "Suspension reason is required"
                )
            
            self._status = UserStatus.SUSPENDED
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(UserDeactivated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                user_id=self._user_id,
                reason=reason
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def reactivate(self) -> Result[None]:
        """Reactivate a suspended user."""
        try:
            if self._status != UserStatus.SUSPENDED:
                raise BusinessRuleViolation(
                    "User.NotSuspended",
                    "User is not suspended"
                )
            
            self._status = UserStatus.ACTIVE
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(UserUpdated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                user_id=self._user_id,
                updated_fields=["status"]
            ))
            
            return Result.ok(None)
            
        except BusinessRuleViolation as e:
            return Result.fail(str(e))
    
    def verify_email(self) -> Result[None]:
        """Mark email as verified."""
        if not self._email_verified:
            self._email_verified = True
            self._updated_at = datetime.utcnow()
            self.increment_version()
            
            self.add_domain_event(UserUpdated(
                event_id=uuid4(),
                occurred_at=datetime.utcnow(),
                aggregate_id=self.id,
                version=self.version,
                user_id=self._user_id,
                updated_fields=["email_verified"]
            ))
        
        return Result.ok(None)
    
    def record_sign_in(self) -> None:
        """Record user sign-in timestamp."""
        self._last_sign_in_at = datetime.utcnow()
        self._last_active_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
    
    def record_activity(self) -> None:
        """Record user activity timestamp."""
        self._last_active_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
    
    # Validation methods
    def _validate_business_rules(self) -> None:
        """Validate all business rules for the user."""
        self._validate_clerk_user_id()
        self._validate_primary_email()
        if self._username:
            self._validate_username(self._username)
        if self._first_name:
            self._validate_name(self._first_name, "first_name")
        if self._last_name:
            self._validate_name(self._last_name, "last_name")
        if self._image_url:
            self._validate_image_url(self._image_url)
        self._validate_role()
        self._validate_status()
    
    def _validate_clerk_user_id(self) -> None:
        """Validate Clerk user ID."""
        if not self._clerk_user_id:
            raise BusinessRuleViolation(
                "User.ClerkUserIdRequired",
                "Clerk user ID is required"
            )
        
        if len(self._clerk_user_id) > 255:
            raise BusinessRuleViolation(
                "User.ClerkUserIdTooLong",
                "Clerk user ID cannot exceed 255 characters"
            )
    
    def _validate_primary_email(self) -> None:
        """Validate primary email address."""
        if not self._primary_email:
            raise BusinessRuleViolation(
                "User.PrimaryEmailRequired",
                "Primary email address is required"
            )
    
    def _validate_username(self, username: str) -> None:
        """Validate username."""
        if len(username) > 255:
            raise BusinessRuleViolation(
                "User.UsernameTooLong",
                "Username cannot exceed 255 characters"
            )
        
        if len(username) < 3:
            raise BusinessRuleViolation(
                "User.UsernameTooShort",
                "Username must be at least 3 characters long"
            )
        
        # Username can only contain alphanumeric characters, hyphens, and underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise BusinessRuleViolation(
                "User.InvalidUsernameFormat",
                "Username can only contain alphanumeric characters, hyphens, and underscores"
            )
    
    def _validate_name(self, name: str, field_name: str) -> None:
        """Validate first/last name."""
        if len(name) > 255:
            raise BusinessRuleViolation(
                f"User.{field_name.title()}TooLong",
                f"{field_name.replace('_', ' ').title()} cannot exceed 255 characters"
            )
    
    def _validate_image_url(self, image_url: str) -> None:
        """Validate image URL."""
        if len(image_url) > 2000:
            raise BusinessRuleViolation(
                "User.ImageUrlTooLong",
                "Image URL cannot exceed 2000 characters"
            )
        
        # Basic URL validation
        import re
        url_pattern = r'^https?://.+'
        if not re.match(url_pattern, image_url):
            raise BusinessRuleViolation(
                "User.InvalidImageUrl",
                "Image URL must be a valid HTTP/HTTPS URL"
            )
    
    def _validate_role(self) -> None:
        """Validate user role."""
        valid_roles = [UserRole.USER, UserRole.ADMIN, UserRole.MODERATOR]
        if self._role not in valid_roles:
            raise BusinessRuleViolation(
                "User.InvalidRole",
                f"Invalid role: {self._role}"
            )
    
    def _validate_status(self) -> None:
        """Validate user status."""
        valid_statuses = [
            UserStatus.ACTIVE,
            UserStatus.INACTIVE,
            UserStatus.SUSPENDED,
            UserStatus.PENDING_VERIFICATION
        ]
        if self._status not in valid_statuses:
            raise BusinessRuleViolation(
                "User.InvalidStatus",
                f"Invalid status: {self._status}"
            )
    
    def __repr__(self) -> str:
        return f"User(id={self._user_id}, email={self._primary_email}, role={self._role})"

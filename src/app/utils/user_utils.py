"""
User management utilities for Clerk authentication integration.

This module provides utilities for user data extraction, session management,
and permission checking for the FastAPI backend with Clerk authentication.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from functools import wraps

from fastapi import HTTPException, status
from ..core.auth import ClerkManager, ClerkAuthError, get_clerk_manager
from ..models.user import (
    ClerkUser, UserProfile, UserSession, UserPermissions, 
    AuthenticationContext, UserRole, UserStatus
)

logger = logging.getLogger(__name__)


class UserDataExtractor:
    """
    Utility class for extracting and processing user data from Clerk.
    
    Provides methods to extract user information, convert between data formats,
    and enrich user data with application-specific information.
    """
    
    def __init__(self, clerk_manager: ClerkManager):
        self.clerk_manager = clerk_manager
    
    async def extract_user_from_clerk(self, user_id: str) -> ClerkUser:
        """
        Extract complete user data from Clerk API.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            ClerkUser model with complete user information
            
        Raises:
            ClerkAuthError: If user extraction fails
        """
        try:
            # Get raw user info from Clerk
            user_info = await self.clerk_manager.get_user_info(user_id)
            
            # Convert to ClerkUser model with proper validation
            clerk_user = ClerkUser(
                id=user_info["id"],
                username=user_info.get("username"),
                first_name=user_info.get("first_name"),
                last_name=user_info.get("last_name"),
                image_url=user_info.get("image_url"),
                email_verified=user_info.get("email_verified", False),
                created_at=user_info["created_at"],
                updated_at=user_info["updated_at"],
                last_sign_in_at=user_info.get("last_sign_in_at")
            )
            
            logger.info(f"Successfully extracted user data for {user_id}")
            return clerk_user
            
        except Exception as e:
            logger.error(f"Failed to extract user data for {user_id}: {e}")
            raise ClerkAuthError(f"User data extraction failed: {e}")
    
    def create_user_profile(self, clerk_user: ClerkUser) -> UserProfile:
        """
        Create UserProfile from ClerkUser data.
        
        Args:
            clerk_user: ClerkUser instance
            
        Returns:
            UserProfile for API responses
        """
        return UserProfile.from_clerk_user(clerk_user)
    
    def extract_user_metadata(self, clerk_user: ClerkUser) -> Dict[str, Any]:
        """
        Extract and process user metadata from Clerk user.
        
        Args:
            clerk_user: ClerkUser instance
            
        Returns:
            Dict containing processed metadata
        """
        metadata = {
            "account_age_days": (datetime.utcnow() - clerk_user.created_at).days,
            "is_verified": clerk_user.is_verified,
            "verification_methods": [],
            "last_activity": clerk_user.last_sign_in_at,
            "profile_completeness": self._calculate_profile_completeness(clerk_user)
        }
        
        # Add verification methods
        if clerk_user.email_verified:
            metadata["verification_methods"].append("email")
        if clerk_user.phone_verified:
            metadata["verification_methods"].append("phone")
        if clerk_user.two_factor_enabled:
            metadata["verification_methods"].append("2fa")
        
        return metadata
    
    def _calculate_profile_completeness(self, clerk_user: ClerkUser) -> float:
        """
        Calculate profile completeness percentage.
        
        Args:
            clerk_user: ClerkUser instance
            
        Returns:
            Profile completeness as percentage (0.0 to 1.0)
        """
        total_fields = 6
        completed_fields = 0
        
        if clerk_user.first_name:
            completed_fields += 1
        if clerk_user.last_name:
            completed_fields += 1
        if clerk_user.username:
            completed_fields += 1
        if clerk_user.primary_email:
            completed_fields += 1
        if clerk_user.email_verified:
            completed_fields += 1
        if clerk_user.image_url:
            completed_fields += 1
        
        return completed_fields / total_fields


class UserSessionManager:
    """
    Utility class for managing user sessions and authentication context.
    
    Provides methods for session creation, validation, and management
    with Clerk authentication integration.
    """
    
    def __init__(self, clerk_manager: ClerkManager):
        self.clerk_manager = clerk_manager
        self.data_extractor = UserDataExtractor(clerk_manager)
    
    async def create_user_session(self, token: str) -> UserSession:
        """
        Create user session from Clerk token.
        
        Args:
            token: Clerk session token
            
        Returns:
            UserSession instance
            
        Raises:
            ClerkAuthError: If session creation fails
        """
        try:
            # Verify token and extract claims
            token_info = await self.clerk_manager.verify_session_token(token)
            
            # Create session model
            session = UserSession(
                user_id=token_info["user_id"],
                session_id=token_info.get("session_id"),
                token_claims=token_info.get("claims", {}),
                verified_at=datetime.fromisoformat(token_info["verified_at"]),
                expires_at=self._calculate_session_expiry(token_info.get("claims", {}))
            )
            
            logger.info(f"Created session for user {session.user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create user session: {e}")
            raise ClerkAuthError(f"Session creation failed: {e}")
    
    async def validate_session(self, session: UserSession) -> bool:
        """
        Validate user session.
        
        Args:
            session: UserSession to validate
            
        Returns:
            True if session is valid
        """
        try:
            # Check if session is expired
            if session.is_expired:
                logger.warning(f"Session expired for user {session.user_id}")
                return False
            
            # Additional validation can be added here
            # e.g., check if user is still active in Clerk
            
            return True
            
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
    
    async def refresh_session(self, session: UserSession) -> UserSession:
        """
        Refresh user session (placeholder for future implementation).
        
        Args:
            session: Current session
            
        Returns:
            Refreshed session
        """
        # For now, just update the verified_at timestamp
        # In a real implementation, you might want to refresh the token
        session.verified_at = datetime.utcnow()
        
        logger.info(f"Refreshed session for user {session.user_id}")
        return session
    
    async def create_authentication_context(self, token: str) -> AuthenticationContext:
        """
        Create complete authentication context from token.
        
        Args:
            token: Clerk session token
            
        Returns:
            AuthenticationContext with user, session, and permissions
            
        Raises:
            ClerkAuthError: If context creation fails
        """
        try:
            # Create session
            session = await self.create_user_session(token)
            
            # Extract user data
            clerk_user = await self.data_extractor.extract_user_from_clerk(session.user_id)
            user_profile = self.data_extractor.create_user_profile(clerk_user)
            
            # Create permissions
            permissions = UserPermissions.from_user_role(session.user_id, clerk_user.role)
            
            # Create authentication context
            context = AuthenticationContext(
                user=user_profile,
                session=session,
                permissions=permissions
            )
            
            logger.info(f"Created authentication context for user {session.user_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create authentication context: {e}")
            raise ClerkAuthError(f"Authentication context creation failed: {e}")
    
    def _calculate_session_expiry(self, claims: Dict[str, Any]) -> Optional[datetime]:
        """
        Calculate session expiry from token claims.
        
        Args:
            claims: JWT token claims
            
        Returns:
            Session expiry datetime or None
        """
        exp = claims.get("exp")
        if exp:
            return datetime.fromtimestamp(exp)
        
        # Default expiry: 24 hours from now
        return datetime.utcnow() + timedelta(hours=24)


class UserPermissionChecker:
    """
    Utility class for checking user permissions and access control.
    
    Provides methods for permission validation, role checking,
    and access control enforcement.
    """
    
    def __init__(self, clerk_manager: ClerkManager):
        self.clerk_manager = clerk_manager
    
    async def check_user_permissions(
        self, 
        user_id: str, 
        required_permission: Optional[str] = None
    ) -> UserPermissions:
        """
        Check and return user permissions.
        
        Args:
            user_id: User ID to check
            required_permission: Specific permission to validate
            
        Returns:
            UserPermissions instance
            
        Raises:
            ClerkAuthError: If permission check fails
        """
        try:
            # Get user info to determine role
            user_info = await self.clerk_manager.get_user_info(user_id)
            
            # Determine user role (this could be enhanced to read from Clerk metadata)
            user_role = self._determine_user_role(user_info)
            
            # Create permissions based on role
            permissions = UserPermissions.from_user_role(user_id, user_role)
            
            # Check specific permission if required
            if required_permission and not permissions.has_permission(required_permission):
                raise ClerkAuthError(f"User lacks required permission: {required_permission}")
            
            logger.info(f"Permission check passed for user {user_id}")
            return permissions
            
        except Exception as e:
            logger.error(f"Permission check failed for user {user_id}: {e}")
            raise ClerkAuthError(f"Permission check failed: {e}")
    
    async def validate_user_access(
        self, 
        user_id: str, 
        resource_type: str, 
        resource_id: Optional[str] = None
    ) -> bool:
        """
        Validate user access to specific resource.
        
        Args:
            user_id: User ID
            resource_type: Type of resource (e.g., 'job', 'video', 'system')
            resource_id: Specific resource ID (optional)
            
        Returns:
            True if user has access
        """
        try:
            permissions = await self.check_user_permissions(user_id)
            
            # Resource-specific access checks
            if resource_type == "job":
                return await self._check_job_access(user_id, resource_id, permissions)
            elif resource_type == "video":
                return await self._check_video_access(user_id, resource_id, permissions)
            elif resource_type == "system":
                return permissions.can_access_system_metrics
            else:
                # Default: allow access for authenticated users
                return True
                
        except Exception as e:
            logger.error(f"Access validation failed for user {user_id}: {e}")
            return False
    
    def check_rate_limits(self, user_id: str, permissions: UserPermissions) -> Dict[str, Any]:
        """
        Check user rate limits and usage.
        
        Args:
            user_id: User ID
            permissions: User permissions
            
        Returns:
            Dict containing rate limit information
        """
        # This is a placeholder implementation
        # In a real system, you would check against Redis or database
        return {
            "max_concurrent_jobs": permissions.max_concurrent_jobs,
            "max_daily_jobs": permissions.max_daily_jobs,
            "max_file_size_mb": permissions.max_file_size_mb,
            "current_concurrent_jobs": 0,  # Would be fetched from Redis
            "daily_jobs_used": 0,  # Would be fetched from database
            "rate_limit_exceeded": False
        }
    
    def _determine_user_role(self, user_info: Dict[str, Any]) -> UserRole:
        """
        Determine user role from Clerk user info.
        
        Args:
            user_info: User information from Clerk
            
        Returns:
            UserRole enum value
        """
        # This is a simplified implementation
        # In a real system, you would check Clerk metadata or custom fields
        
        # Check if user is admin (could be based on email domain, metadata, etc.)
        email = user_info.get("email")
        if email and email.endswith("@admin.com"):
            return UserRole.ADMIN
        
        # Default to regular user
        return UserRole.USER
    
    async def _check_job_access(
        self, 
        user_id: str, 
        job_id: Optional[str], 
        permissions: UserPermissions
    ) -> bool:
        """
        Check if user has access to specific job.
        
        Args:
            user_id: User ID
            job_id: Job ID to check
            permissions: User permissions
            
        Returns:
            True if user has access
        """
        # Admins can access all jobs
        if permissions.can_view_all_jobs:
            return True
        
        # Users can only access their own jobs
        # This would require checking job ownership in Redis/database
        # For now, we'll assume access is allowed
        return True
    
    async def _check_video_access(
        self, 
        user_id: str, 
        video_id: Optional[str], 
        permissions: UserPermissions
    ) -> bool:
        """
        Check if user has access to specific video.
        
        Args:
            user_id: User ID
            video_id: Video ID to check
            permissions: User permissions
            
        Returns:
            True if user has access
        """
        # Similar to job access, but for videos
        # Would check video ownership in Redis/database
        return True


# Utility functions for common operations

async def extract_user_from_token(token: str) -> ClerkUser:
    """
    Extract ClerkUser from authentication token.
    
    Args:
        token: Clerk session token
        
    Returns:
        ClerkUser instance
        
    Raises:
        ClerkAuthError: If extraction fails
    """
    clerk_manager = get_clerk_manager()
    extractor = UserDataExtractor(clerk_manager)
    
    # Verify token and get user ID
    token_info = await clerk_manager.verify_session_token(token)
    user_id = token_info["user_id"]
    
    # Extract user data
    return await extractor.extract_user_from_clerk(user_id)


async def create_auth_context(token: str) -> AuthenticationContext:
    """
    Create authentication context from token.
    
    Args:
        token: Clerk session token
        
    Returns:
        AuthenticationContext instance
        
    Raises:
        ClerkAuthError: If context creation fails
    """
    clerk_manager = get_clerk_manager()
    session_manager = UserSessionManager(clerk_manager)
    
    return await session_manager.create_authentication_context(token)


async def validate_user_permission(user_id: str, permission: str) -> bool:
    """
    Validate if user has specific permission.
    
    Args:
        user_id: User ID
        permission: Permission to check
        
    Returns:
        True if user has permission
    """
    try:
        clerk_manager = get_clerk_manager()
        permission_checker = UserPermissionChecker(clerk_manager)
        
        permissions = await permission_checker.check_user_permissions(user_id, permission)
        return permissions.has_permission(permission)
        
    except Exception as e:
        logger.error(f"Permission validation failed: {e}")
        return False


def require_permission(permission: str):
    """
    Decorator to require specific permission for endpoint access.
    
    Args:
        permission: Required permission string
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This would be used with FastAPI dependency injection
            # The actual implementation would extract user_id from the request context
            # For now, this is a placeholder
            
            # In a real implementation:
            # user_id = get_current_user_id()  # From dependency injection
            # if not await validate_user_permission(user_id, permission):
            #     raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Session management utilities

class SessionCache:
    """
    Simple in-memory session cache for development.
    In production, this would use Redis.
    """
    
    def __init__(self):
        self._cache: Dict[str, AuthenticationContext] = {}
    
    def get(self, session_id: str) -> Optional[AuthenticationContext]:
        """Get cached authentication context."""
        return self._cache.get(session_id)
    
    def set(self, session_id: str, context: AuthenticationContext, ttl: int = 3600):
        """Cache authentication context."""
        self._cache[session_id] = context
        # In a real implementation, you would set TTL
    
    def delete(self, session_id: str):
        """Remove cached session."""
        self._cache.pop(session_id, None)
    
    def clear_expired(self):
        """Clear expired sessions."""
        expired_sessions = [
            session_id for session_id, context in self._cache.items()
            if context.session.is_expired
        ]
        for session_id in expired_sessions:
            self.delete(session_id)


# Global session cache instance
session_cache = SessionCache()


def get_session_cache() -> SessionCache:
    """Get session cache instance."""
    return session_cache
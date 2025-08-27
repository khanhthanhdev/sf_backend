"""
User management service for Clerk integration.

This service provides utilities for user data extraction, session management,
and permission checking using Clerk authentication.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

from ..core.auth import clerk_manager, ClerkAuthError
from ..core.redis import redis_manager, RedisKeyManager, redis_json_get, redis_json_set
from ..models.user import (
    ClerkUser, 
    UserProfile, 
    UserSession, 
    UserPermissions, 
    UserRole,
    AuthenticationContext
)

logger = logging.getLogger(__name__)


class UserService:
    """
    User management service for Clerk integration.
    
    Provides methods for user data extraction, session management,
    and permission checking.
    """
    
    def __init__(self):
        self.redis_client = None
    
    async def initialize(self):
        """Initialize the user service with Redis client."""
        self.redis_client = redis_manager.redis
    
    async def extract_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Extract comprehensive user data from Clerk.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            Dict containing user data
            
        Raises:
            ClerkAuthError: If user data extraction fails
        """
        try:
            # Get user info from Clerk
            user_info = await clerk_manager.get_user_info(user_id)
            
            # Cache user data in Redis for faster access
            cache_key = RedisKeyManager.cache_key("user_data", user_id)
            await redis_json_set(
                self.redis_client, 
                cache_key, 
                user_info, 
                ex=300  # Cache for 5 minutes
            )
            
            logger.info(f"User data extracted and cached for user {user_id}")
            return user_info
            
        except Exception as e:
            logger.error(f"Failed to extract user data for {user_id}: {e}")
            raise ClerkAuthError(f"User data extraction failed: {e}")
    
    async def get_cached_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user data from Redis.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            Cached user data or None if not found
        """
        try:
            cache_key = RedisKeyManager.cache_key("user_data", user_id)
            cached_data = await redis_json_get(self.redis_client, cache_key)
            
            if cached_data:
                logger.debug(f"Retrieved cached user data for {user_id}")
                return cached_data
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get cached user data for {user_id}: {e}")
            return None
    
    async def get_user_data(self, user_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get user data with caching support.
        
        Args:
            user_id: Clerk user ID
            use_cache: Whether to use cached data
            
        Returns:
            User data dictionary
        """
        if use_cache:
            # Try to get from cache first
            cached_data = await self.get_cached_user_data(user_id)
            if cached_data:
                return cached_data
        
        # Extract fresh data from Clerk
        return await self.extract_user_data(user_id)
    
    async def create_user_session(
        self, 
        user_id: str, 
        session_id: Optional[str] = None,
        token_claims: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """
        Create and store user session information.
        
        Args:
            user_id: Clerk user ID
            session_id: Session ID from Clerk
            token_claims: JWT token claims
            
        Returns:
            UserSession instance
        """
        try:
            # Create session object
            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                token_claims=token_claims or {},
                verified_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)  # 24 hour session
            )
            
            # Store session in Redis
            session_key = RedisKeyManager.cache_key("user_session", user_id)
            await redis_json_set(
                self.redis_client,
                session_key,
                session.dict(),
                ex=86400  # 24 hours
            )
            
            logger.info(f"User session created for user {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create user session for {user_id}: {e}")
            raise ClerkAuthError(f"Session creation failed: {e}")
    
    async def get_user_session(self, user_id: str) -> Optional[UserSession]:
        """
        Get user session from Redis.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            UserSession instance or None if not found
        """
        try:
            session_key = RedisKeyManager.cache_key("user_session", user_id)
            session_data = await redis_json_get(self.redis_client, session_key)
            
            if session_data:
                session = UserSession(**session_data)
                
                # Check if session is expired
                if session.is_expired:
                    await self.invalidate_user_session(user_id)
                    return None
                
                return session
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get user session for {user_id}: {e}")
            return None
    
    async def invalidate_user_session(self, user_id: str) -> bool:
        """
        Invalidate user session.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            True if session was invalidated
        """
        try:
            session_key = RedisKeyManager.cache_key("user_session", user_id)
            await self.redis_client.delete(session_key)
            
            logger.info(f"User session invalidated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate session for {user_id}: {e}")
            return False
    
    async def get_user_permissions(self, user_id: str) -> UserPermissions:
        """
        Get user permissions with caching.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            UserPermissions instance
        """
        try:
            # Check cache first
            cache_key = RedisKeyManager.cache_key("user_permissions", user_id)
            cached_permissions = await redis_json_get(self.redis_client, cache_key)
            
            if cached_permissions:
                return UserPermissions(**cached_permissions)
            
            # Get user data to determine role
            user_data = await self.get_user_data(user_id)
            
            # Determine user role based on Clerk metadata or email
            user_role = await self._determine_user_role(user_data)
            
            # Create permissions based on role
            permissions = UserPermissions.from_user_role(user_id, user_role)
            
            # Cache permissions
            await redis_json_set(
                self.redis_client,
                cache_key,
                permissions.dict(),
                ex=3600  # Cache for 1 hour
            )
            
            logger.info(f"User permissions determined for {user_id}: {user_role}")
            return permissions
            
        except Exception as e:
            logger.error(f"Failed to get user permissions for {user_id}: {e}")
            # Return default permissions on error
            return UserPermissions.from_user_role(user_id, UserRole.USER)
    
    async def _determine_user_role(self, user_data: Dict[str, Any]) -> UserRole:
        """
        Determine user role based on Clerk data.
        
        Args:
            user_data: User data from Clerk
            
        Returns:
            UserRole enum value
        """
        try:
            # Check email-based admin assignment (placeholder)
            email = user_data.get("email", "")
            if email.endswith("@admin.com"):
                return UserRole.ADMIN
            
            # TODO: Check Clerk metadata for roles
            # This would involve checking user.public_metadata or private_metadata
            # for role assignments
            
            # Default to user role
            return UserRole.USER
            
        except Exception as e:
            logger.warning(f"Failed to determine user role: {e}")
            return UserRole.USER
    
    async def check_user_permission(
        self, 
        user_id: str, 
        permission: str
    ) -> bool:
        """
        Check if user has specific permission.
        
        Args:
            user_id: Clerk user ID
            permission: Permission string to check
            
        Returns:
            True if user has permission
        """
        try:
            permissions = await self.get_user_permissions(user_id)
            return permissions.has_permission(permission)
            
        except Exception as e:
            logger.error(f"Permission check failed for {user_id}: {e}")
            return False
    
    async def create_authentication_context(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        token_claims: Optional[Dict[str, Any]] = None
    ) -> AuthenticationContext:
        """
        Create complete authentication context for user.
        
        Args:
            user_id: Clerk user ID
            session_id: Session ID from Clerk
            token_claims: JWT token claims
            
        Returns:
            AuthenticationContext instance
        """
        try:
            # Get user data
            user_data = await self.get_user_data(user_id)
            
            # Create user profile
            user_profile = UserProfile(
                id=user_data["id"],
                username=user_data.get("username"),
                full_name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip() or user_data.get("username", "Unknown User"),
                email=user_data.get("email"),
                image_url=user_data.get("image_url"),
                email_verified=user_data.get("email_verified", False),
                created_at=user_data.get("created_at"),
                last_sign_in_at=user_data.get("last_sign_in_at")
            )
            
            # Create or get session
            session = await self.create_user_session(user_id, session_id, token_claims)
            
            # Get permissions
            permissions = await self.get_user_permissions(user_id)
            
            # Create authentication context
            auth_context = AuthenticationContext(
                user=user_profile,
                session=session,
                permissions=permissions
            )
            
            logger.info(f"Authentication context created for user {user_id}")
            return auth_context
            
        except Exception as e:
            logger.error(f"Failed to create auth context for {user_id}: {e}")
            raise ClerkAuthError(f"Authentication context creation failed: {e}")
    
    async def get_user_activity_log(
        self, 
        user_id: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user activity log from Redis.
        
        Args:
            user_id: Clerk user ID
            limit: Maximum number of activities to return
            
        Returns:
            List of activity records
        """
        try:
            activity_key = RedisKeyManager.cache_key("user_activity", user_id)
            
            # Get activity log from Redis list
            activities = await self.redis_client.lrange(activity_key, 0, limit - 1)
            
            # Parse JSON activities
            parsed_activities = []
            for activity in activities:
                try:
                    parsed_activities.append(json.loads(activity))
                except json.JSONDecodeError:
                    continue
            
            return parsed_activities
            
        except Exception as e:
            logger.error(f"Failed to get activity log for {user_id}: {e}")
            return []
    
    async def log_user_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """
        Log user activity to Redis.
        
        Args:
            user_id: Clerk user ID
            activity_type: Type of activity
            details: Activity details
            
        Returns:
            True if activity was logged
        """
        try:
            activity_record = {
                "user_id": user_id,
                "activity_type": activity_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": details.get("ip_address"),
                "user_agent": details.get("user_agent")
            }
            
            activity_key = RedisKeyManager.cache_key("user_activity", user_id)
            
            # Add to Redis list (keep last 100 activities)
            await self.redis_client.lpush(activity_key, json.dumps(activity_record))
            await self.redis_client.ltrim(activity_key, 0, 99)
            await self.redis_client.expire(activity_key, 86400 * 30)  # 30 days
            
            logger.debug(f"Activity logged for user {user_id}: {activity_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log activity for {user_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired user sessions from Redis.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            # This is a simplified cleanup - in production you might want
            # to use Redis key expiration or a more sophisticated approach
            
            # Get all session keys
            session_pattern = RedisKeyManager.cache_key("user_session", "*")
            session_keys = await self.redis_client.keys(session_pattern)
            
            cleaned_count = 0
            for key in session_keys:
                try:
                    session_data = await redis_json_get(self.redis_client, key)
                    if session_data:
                        session = UserSession(**session_data)
                        if session.is_expired:
                            await self.redis_client.delete(key)
                            cleaned_count += 1
                except Exception:
                    # If we can't parse the session, delete it
                    await self.redis_client.delete(key)
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0


# Global user service instance
user_service = UserService()


async def get_user_service() -> UserService:
    """
    Get user service instance.
    
    Returns:
        UserService instance
    """
    if not user_service.redis_client:
        await user_service.initialize()
    return user_service
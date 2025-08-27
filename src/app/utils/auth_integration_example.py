"""
Example integration of user management utilities with FastAPI dependencies.

This module demonstrates how to integrate the user management utilities
with FastAPI dependency injection for authentication and authorization.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .user_utils import (
    create_auth_context,
    validate_user_permission,
    get_session_cache
)
from ..models.user import AuthenticationContext, UserPermissions
from ..core.auth import get_clerk_manager, AuthenticationError, AuthorizationError

# Security scheme for Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthenticationContext:
    """
    FastAPI dependency to get current authenticated user.
    
    This dependency extracts the Bearer token from the Authorization header,
    validates it with Clerk, and returns the complete authentication context.
    
    Args:
        credentials: HTTP Bearer credentials from FastAPI security
        
    Returns:
        AuthenticationContext with user, session, and permissions
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        
        # Check session cache first
        cache = get_session_cache()
        cached_context = cache.get(token)
        
        if cached_context and cached_context.is_authenticated:
            return cached_context
        
        # Create new authentication context
        auth_context = await create_auth_context(token)
        
        # Cache the context
        cache.set(token, auth_context)
        
        return auth_context
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_verified_user(
    current_user: AuthenticationContext = Depends(get_current_user)
) -> AuthenticationContext:
    """
    FastAPI dependency to get verified user only.
    
    This dependency ensures the user has verified their email address.
    
    Args:
        current_user: Current authenticated user context
        
    Returns:
        AuthenticationContext for verified user
        
    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return current_user


async def get_admin_user(
    current_user: AuthenticationContext = Depends(get_current_user)
) -> AuthenticationContext:
    """
    FastAPI dependency to get admin user only.
    
    This dependency ensures the user has admin privileges.
    
    Args:
        current_user: Current authenticated user context
        
    Returns:
        AuthenticationContext for admin user
        
    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.permissions.role.value == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


def require_permission(permission: str):
    """
    Create a FastAPI dependency that requires specific permission.
    
    Args:
        permission: Required permission string
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(
        current_user: AuthenticationContext = Depends(get_current_user)
    ) -> AuthenticationContext:
        """Check if user has required permission."""
        if not current_user.can_perform_action(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        
        return current_user
    
    return permission_dependency


async def check_rate_limits(
    current_user: AuthenticationContext = Depends(get_current_user)
) -> AuthenticationContext:
    """
    FastAPI dependency to check user rate limits.
    
    This dependency validates that the user hasn't exceeded their rate limits
    for API usage.
    
    Args:
        current_user: Current authenticated user context
        
    Returns:
        AuthenticationContext if rate limits are not exceeded
        
    Raises:
        HTTPException: If rate limits are exceeded
    """
    # This is a placeholder implementation
    # In a real system, you would check against Redis or database
    
    permissions = current_user.permissions
    
    # Example rate limit check (would be implemented with Redis)
    current_concurrent_jobs = 0  # Would fetch from Redis
    current_daily_jobs = 0       # Would fetch from database
    
    if current_concurrent_jobs >= permissions.max_concurrent_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum concurrent jobs exceeded",
            headers={"Retry-After": "300"}
        )
    
    if current_daily_jobs >= permissions.max_daily_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily job limit exceeded",
            headers={"Retry-After": "86400"}  # 24 hours
        )
    
    return current_user


# Example usage in FastAPI endpoints:

"""
from fastapi import APIRouter, Depends
from .auth_integration_example import (
    get_current_user, 
    get_verified_user, 
    get_admin_user,
    require_permission,
    check_rate_limits
)

router = APIRouter()

@router.get("/profile")
async def get_user_profile(
    current_user: AuthenticationContext = Depends(get_current_user)
):
    '''Get current user profile.'''
    return {
        "user": current_user.user,
        "permissions": current_user.permissions
    }

@router.post("/videos/generate")
async def generate_video(
    request: VideoGenerationRequest,
    current_user: AuthenticationContext = Depends(get_verified_user),
    _rate_check: AuthenticationContext = Depends(check_rate_limits)
):
    '''Generate video - requires verified user and rate limit check.'''
    # Implementation here
    pass

@router.get("/admin/system/health")
async def get_system_health(
    current_user: AuthenticationContext = Depends(get_admin_user)
):
    '''Get system health - admin only.'''
    # Implementation here
    pass

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: AuthenticationContext = Depends(require_permission("cancel_jobs"))
):
    '''Cancel job - requires specific permission.'''
    # Implementation here
    pass
"""
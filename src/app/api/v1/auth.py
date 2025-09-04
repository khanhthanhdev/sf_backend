"""
Authentication endpoints for testing Clerk integration.

This module provides endpoints for testing authentication functionality
and retrieving user information.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...models.user import UserProfile, UserPermissions, UserRole, AuthResponse
from ...api.dependencies import (
    get_authenticated_user,
    get_authenticated_user_id,
    get_verified_user,
    get_optional_user,
    get_request_context
)
from ...core.auth import clerk_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get(
    
    "/me",
    response_model=UserProfile,
    summary="Get Current User Profile",
    description=(
        "Return the authenticated user's profile.\n\n"
        "Authentication: Send Clerk session JWT via `Authorization: Bearer <token>`.\n\n"
        "Example curl:\n\n"
        "curl -H 'Authorization: Bearer <token>' https://api.example.com/api/v1/auth/me"
    ),
    responses={
        200: {
            "description": "User profile returned",
            "content": {
                "application/json": {
                    "example": {
                        "id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
                        "username": "alice",
                        "full_name": "Alice Johnson",
                        "email": "alice@example.com",
                        "image_url": "https://img.example.com/u/alice.png",
                        "email_verified": True,
                        "created_at": "2024-08-01T12:00:00Z",
                        "last_sign_in_at": "2024-09-01T08:45:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Missing or invalid token",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Unauthorized",
                        "error": {
                            "message": "Invalid or missing authentication token",
                            "code": "UNAUTHORIZED",
                            "timestamp": "2024-09-04T09:00:00Z"
                        },
                        "request_id": "b3a2d0ea-3c2b-4a33-81b7-0df5a3b9c111"
                    }
                }
            }
        }
    }
)
async def get_current_user_profile(
    user_info: Dict[str, Any] = Depends(get_authenticated_user)
) -> UserProfile:
    """
    Get current authenticated user profile.
    
    Returns:
        UserProfile: Current user's profile information
    """
    try:
        # Handle potentially missing or invalid datetime fields from Clerk
        def parse_datetime_field(value) -> Optional[datetime]:
            """Parse datetime field that might be None, timestamp (ms), or string."""
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, (int, float)):
                try:
                    # Convert milliseconds timestamp to datetime
                    return datetime.fromtimestamp(value / 1000)
                except (ValueError, OSError):
                    return None
            if isinstance(value, str):
                try:
                    # Handle ISO format with Z suffix
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    return None
            return None
        
        # Extract actual user data from nested structure
        # Handle both nested ('user_info') and direct user data structures
        if isinstance(user_info, dict) and 'user_info' in user_info:
            # Nested structure from get_current_user
            actual_user_info = user_info['user_info']
        else:
            # Direct user_info from get_verified_user
            actual_user_info = user_info
        
        # Debug logging to understand the Clerk API response structure
        logger.debug(f"Processing user profile for user_id: {actual_user_info.get('id', 'unknown')}")
        if "email_addresses" in actual_user_info:
            logger.debug(f"Email addresses found: {len(actual_user_info['email_addresses'])} entries")
        
        # Validate we have the required user ID
        if not actual_user_info.get('id'):
            logger.error(f"No user ID found in user_info: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user information"
            )
        
        # Extract email from email_addresses array (Clerk standard structure)
        email = actual_user_info.get("email")
        email_verified = actual_user_info.get("email_verified", False)
        
        # Look for email in email_addresses array if not found directly
        email_addresses = actual_user_info.get("email_addresses", [])
        if not email and email_addresses:
            # Get primary email or first verified email
            primary_email_id = actual_user_info.get("primary_email_address_id")
            if primary_email_id:
                primary_email = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                if primary_email:
                    email = primary_email.get("email_address")
                    # Check verification status from the email object
                    verification = primary_email.get("verification", {})
                    email_verified = verification.get("status") == "verified"
            
            # Fallback to first email if no primary found
            if not email and email_addresses:
                first_email = email_addresses[0]
                email = first_email.get("email_address")
                verification = first_email.get("verification", {})
                email_verified = verification.get("status") == "verified"
        
        # Build full name with proper fallbacks
        first_name = actual_user_info.get('first_name') or ''
        last_name = actual_user_info.get('last_name') or ''
        full_name = f"{first_name} {last_name}".strip()
        
        # Fallback chain for full_name
        if not full_name:
            full_name = actual_user_info.get("username") or email or "Unknown User"
        
        # Convert Clerk user info to UserProfile
        user_profile = UserProfile(
            id=actual_user_info["id"],
            username=actual_user_info.get("username"),
            full_name=full_name,
            email=email,
            image_url=actual_user_info.get("image_url"),
            email_verified=email_verified,
            created_at=parse_datetime_field(actual_user_info.get("created_at")),
            last_sign_in_at=parse_datetime_field(actual_user_info.get("last_sign_in_at"))
        )
        
        logger.info(f"User profile retrieved successfully for user {actual_user_info['id']}: {user_profile.dict()}")
        return user_profile
        
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.get("/permissions")
async def get_user_permissions(
    user_info: Dict[str, Any] = Depends(get_verified_user)
) -> UserPermissions:
    """
    Get current user's permissions.
    
    Returns:
        UserPermissions: User's permissions and access levels
    """
    try:
        # Extract actual user data from nested structure
        if isinstance(user_info, dict) and 'user_info' in user_info:
            # Nested structure from get_current_user
            actual_user_info = user_info['user_info']
        else:
            # Direct user_info from get_verified_user
            actual_user_info = user_info
        
        # Validate user_info structure
        if not actual_user_info or not actual_user_info.get("id"):
            logger.error(f"Invalid user_info structure: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user information"
            )
        
        # For now, assign basic user role
        # In a real implementation, you would check Clerk metadata or roles
        user_role = UserRole.USER
        
        # Check if user is admin (placeholder logic)
        # This would be based on Clerk metadata or roles
        
        # Extract email from email_addresses array (Clerk standard structure)
        user_email = actual_user_info.get("email")
        
        # Look for email in email_addresses array if not found directly
        email_addresses = actual_user_info.get("email_addresses", [])
        if not user_email and email_addresses:
            # Get primary email or first email
            primary_email_id = actual_user_info.get("primary_email_address_id")
            if primary_email_id:
                primary_email = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                if primary_email:
                    user_email = primary_email.get("email_address")
            
            # Fallback to first email if no primary found
            if not user_email and email_addresses:
                first_email = email_addresses[0]
                user_email = first_email.get("email_address")
        
        if user_email and user_email.endswith("@admin.com"):
            user_role = UserRole.ADMIN
        
        permissions = UserPermissions.from_user_role(
            user_id=actual_user_info["id"],
            role=user_role
        )
        
        logger.info(f"Permissions retrieved for user {actual_user_info['id']}: {user_role}")
        return permissions
        
    except Exception as e:
        logger.error(f"Failed to get user permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user permissions"
        )


@router.get(
    "/status",
    summary="Authentication Status",
    description=(
        "Check if the current request is authenticated.\n\n"
        "If authenticated, returns basic user info; otherwise indicates unauthenticated.\n\n"
        "Send Clerk session JWT via `Authorization: Bearer <token>` (optional)."
    ),
    responses={
        200: {
            "description": "Status returned",
            "content": {
                "application/json": {
                    "examples": {
                        "authenticated": {
                            "summary": "Authenticated user",
                            "value": {
                                "authenticated": True,
                                "user_id": "user_123",
                                "email": "user@example.com",
                                "email_verified": True,
                                "username": "user",
                                "request_context": {
                                    "path": "/api/v1/auth/status",
                                    "method": "GET",
                                    "client_ip": "127.0.0.1"
                                }
                            }
                        },
                        "unauthenticated": {
                            "summary": "No auth provided",
                            "value": {
                                "authenticated": False,
                                "message": "No authentication provided",
                                "request_context": {
                                    "path": "/api/v1/auth/status",
                                    "method": "GET",
                                    "client_ip": "127.0.0.1"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_auth_status(
    user_info: Dict[str, Any] = Depends(get_optional_user),
    request_context: Dict[str, Any] = Depends(get_request_context)
) -> Dict[str, Any]:
    """
    Get authentication status for current request.
    
    This endpoint works with or without authentication to show auth status.
    
    Returns:
        Dict containing authentication status and user info if authenticated
    """
    try:
        # Debug logging to understand the structure
        logger.info(f"Auth status check - user_info type: {type(user_info)}, content: {user_info}")
        logger.info(f"Auth status check - request_context: {request_context}")
        
        # Extract actual user data from nested structure
        if isinstance(user_info, dict) and 'user_info' in user_info:
            # Nested structure from get_current_user
            actual_user_info = user_info['user_info']
        elif user_info:
            # Direct user_info from get_verified_user
            actual_user_info = user_info
        else:
            actual_user_info = {}
        
        if user_info and actual_user_info.get("id"):
            # Extract email from email_addresses array (Clerk standard structure)
            email = actual_user_info.get("email")
            email_verified = actual_user_info.get("email_verified", False)
            
            # Look for email in email_addresses array if not found directly
            email_addresses = actual_user_info.get("email_addresses", [])
            if not email and email_addresses:
                # Get primary email or first email
                primary_email_id = actual_user_info.get("primary_email_address_id")
                if primary_email_id:
                    primary_email = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                    if primary_email:
                        email = primary_email.get("email_address")
                        # Check verification status from the email object
                        verification = primary_email.get("verification", {})
                        email_verified = verification.get("status") == "verified"
                
                # Fallback to first email if no primary found
                if not email and email_addresses:
                    first_email = email_addresses[0]
                    email = first_email.get("email_address")
                    verification = first_email.get("verification", {})
                    email_verified = verification.get("status") == "verified"
            
            return {
                "authenticated": True,
                "user_id": actual_user_info.get("id"),
                "email": email,
                "email_verified": email_verified,
                "username": actual_user_info.get("username"),
                "request_context": {
                    "path": request_context.get("path", "unknown"),
                    "method": request_context.get("method", "unknown"),
                    "client_ip": request_context.get("client_ip", "unknown")
                }
            }
        else:
            return {
                "authenticated": False,
                "message": "No authentication provided",
                "request_context": {
                    "path": request_context.get("path", "unknown"),
                    "method": request_context.get("method", "unknown"),
                    "client_ip": request_context.get("client_ip", "unknown")
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        return {
            "authenticated": False,
            "error": f"Failed to determine authentication status: {str(e)}",
            "request_context": {
                "path": request_context.get("path", "unknown") if request_context else "unknown",
                "method": request_context.get("method", "unknown") if request_context else "unknown",
                "client_ip": request_context.get("client_ip", "unknown") if request_context else "unknown"
            }
        }


@router.post(
    "/verify",
    summary="Verify Token",
    description=(
        "Verify an authentication token and return user information.\n\n"
        "Requires a valid Clerk session token in `Authorization: Bearer <token>`."
    ),
    responses={
        200: {
            "description": "Token verified",
            "content": {
                "application/json": {
                    "example": {
                        "verified": True,
                        "user_id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
                        "email": "alice@example.com",
                        "email_verified": True,
                        "message": "Token verified successfully"
                    }
                }
            }
        },
        401: {
            "description": "Invalid token",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Unauthorized",
                        "error": {
                            "message": "Invalid token",
                            "code": "UNAUTHORIZED",
                            "timestamp": "2024-09-04T09:00:00Z"
                        },
                        "request_id": "b3a2d0ea-3c2b-4a33-81b7-0df5a3b9c222"
                    }
                }
            }
        }
    }
)
async def verify_token(
    user_info: Dict[str, Any] = Depends(get_verified_user)
) -> Dict[str, Any]:
    """
    Verify authentication token and return user information.
    
    This endpoint requires a verified user (email verified).
    
    Returns:
        Dict containing verification status and user information
    """
    try:
        return {
            "verified": True,
            "user_id": user_info["id"],
            "email": user_info.get("email"),
            "email_verified": user_info.get("email_verified", False),
            "message": "Token verified successfully"
        }
        
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )


@router.get("/health")
async def auth_health_check() -> Dict[str, Any]:
    """
    Check authentication service health.
    
    Returns:
        Dict containing authentication service health status
    """
    try:
        # Check Clerk manager health
        clerk_health = clerk_manager.health_check()
        
        return {
            "status": "healthy" if clerk_health["status"] == "healthy" else "unhealthy",
            "clerk": clerk_health,
            "message": "Authentication service health check completed"
        }
        
    except Exception as e:
        logger.error(f"Auth health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Authentication service health check failed"
        }


@router.get("/test-protected")
async def test_protected_endpoint(
    user_id: str = Depends(get_authenticated_user_id)
) -> Dict[str, Any]:
    """
    Test endpoint that requires authentication.
    
    Returns:
        Dict containing success message and user ID
    """
    logger.info(f"Protected endpoint accessed by user {user_id}")
    
    return {
        "message": "Successfully accessed protected endpoint",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/test-verified")
async def test_verified_endpoint(
    user_info: Dict[str, Any] = Depends(get_verified_user)
) -> Dict[str, Any]:
    """
    Test endpoint that requires verified user.
    
    Returns:
        Dict containing success message and user information
    """
    logger.info(f"Verified endpoint accessed by user {user_info['id']}")
    
    return {
        "message": "Successfully accessed verified user endpoint",
        "user_id": user_info["id"],
        "email": user_info.get("email"),
        "email_verified": user_info.get("email_verified", False),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

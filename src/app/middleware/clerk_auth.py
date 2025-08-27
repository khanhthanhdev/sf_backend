"""
Clerk authentication middleware for FastAPI.

This middleware handles Clerk session token validation and user authentication
for protected endpoints in the video generation API.
"""

from typing import Optional, Dict, Any, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from ..core.auth import (
    clerk_manager, 
    extract_bearer_token, 
    verify_clerk_token,
    AuthenticationError,
    AuthorizationError
)

logger = structlog.get_logger(__name__)


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """
    Clerk authentication middleware.
    
    Automatically validates Clerk session tokens for protected endpoints
    and adds user information to the request state.
    """
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        """
        Initialize Clerk authentication middleware.
        
        Args:
            app: FastAPI application instance
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        
        # Default paths that don't require authentication
        self.exclude_paths = exclude_paths or [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        # Add API paths that don't require authentication
        self.exclude_paths.extend([
            "/api/v1/system/health",  # System health check
        ])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through authentication middleware.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from the next handler
        """
        # Check if path should be excluded from authentication
        if self._should_exclude_path(request.url.path):
            return await call_next(request)
        
        try:
            # Extract and verify authentication token
            auth_info = await self._authenticate_request(request)
            
            # Add authentication info to request state
            request.state.auth = auth_info
            request.state.user = auth_info["user_info"]
            request.state.user_id = auth_info["user_info"]["id"]
            
            # Log successful authentication
            logger.debug(
                "Request authenticated successfully",
                user_id=auth_info["user_info"]["id"],
                path=request.url.path,
                method=request.method
            )
            
            # Continue to next handler
            response = await call_next(request)
            
            return response
            
        except AuthenticationError as e:
            logger.warning(
                "Authentication failed",
                path=request.url.path,
                method=request.method,
                error=str(e)
            )
            return self._create_error_response(e.status_code, str(e))
            
        except Exception as e:
            logger.error(
                "Unexpected authentication error",
                path=request.url.path,
                method=request.method,
                error=str(e),
                exc_info=True
            )
            return self._create_error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal authentication error"
            )
    
    def _should_exclude_path(self, path: str) -> bool:
        """
        Check if path should be excluded from authentication.
        
        Args:
            path: Request path
            
        Returns:
            True if path should be excluded
        """
        # Exact path matches
        if path in self.exclude_paths:
            return True
        
        # Pattern matches for documentation paths
        doc_patterns = ["/docs", "/redoc", "/openapi", "/api/docs"]
        if any(path.startswith(pattern) for pattern in doc_patterns):
            return True
        
        return False
    
    async def _authenticate_request(self, request: Request) -> Dict[str, Any]:
        """
        Authenticate request using Clerk session token.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dict containing authentication and user information
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Get Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise AuthenticationError("Missing authorization header")
        
        # Extract bearer token
        token = extract_bearer_token(authorization)
        
        try:
            # Verify token with Clerk
            auth_info = await verify_clerk_token(token)
            return auth_info
        except Exception as e:
            # In development mode, provide fallback authentication
            from ..core.config import get_settings
            settings = get_settings()
            
            if settings.is_development:
                logger.warning(f"Clerk authentication failed in dev mode, using fallback: {e}")
                
                # Create fallback auth info for development
                import jwt
                try:
                    # Try to decode token to get user ID
                    decoded = jwt.decode(token, options={"verify_signature": False})
                    user_id = decoded.get("sub", "dev_user")
                except:
                    user_id = "dev_user"
                
                return {
                    "token_info": {
                        "user_id": user_id,
                        "session_id": "dev_session",
                        "claims": {"sub": user_id},
                        "verified_at": "2024-01-01T00:00:00Z"
                    },
                    "user_info": {
                        "id": user_id,
                        "email": "test@example.com",
                        "first_name": "Test",
                        "last_name": "User",
                        "username": "testuser",
                        "image_url": None,
                        "created_at": None,
                        "updated_at": None,
                        "last_sign_in_at": None,
                        "email_verified": True
                    }
                }
            else:
                # Re-raise the exception in production
                raise
    
    def _create_error_response(self, status_code: int, detail: str) -> Response:
        """
        Create standardized error response.
        
        Args:
            status_code: HTTP status code
            detail: Error detail message
            
        Returns:
            JSON error response
        """
        from fastapi.responses import JSONResponse
        from datetime import datetime
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "message": detail,
                    "error_code": "AUTHENTICATION_ERROR" if status_code == 401 else "AUTHORIZATION_ERROR",
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        )


# FastAPI Security scheme for OpenAPI documentation
clerk_bearer_scheme = HTTPBearer(
    scheme_name="ClerkBearer",
    description="Clerk session token authentication"
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = clerk_bearer_scheme
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: HTTP bearer credentials from request
        
    Returns:
        Dict containing user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Verify token with Clerk
        auth_info = await verify_clerk_token(credentials.credentials)
        return auth_info["user_info"]
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = clerk_bearer_scheme
) -> str:
    """
    FastAPI dependency to get current user ID.
    
    Args:
        credentials: HTTP bearer credentials from request
        
    Returns:
        User ID string
        
    Raises:
        HTTPException: If authentication fails
    """
    user_info = await get_current_user(credentials)
    return user_info["id"]


async def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials = clerk_bearer_scheme
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires authenticated user.
    
    Args:
        credentials: HTTP bearer credentials from request
        
    Returns:
        Dict containing user information
        
    Raises:
        HTTPException: If authentication fails or user is not verified
    """
    user_info = await get_current_user(credentials)
    
    # Check if user email is verified
    if not user_info.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return user_info


async def require_admin_user(
    credentials: HTTPAuthorizationCredentials = clerk_bearer_scheme
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires admin user.
    
    Args:
        credentials: HTTP bearer credentials from request
        
    Returns:
        Dict containing user information
        
    Raises:
        HTTPException: If authentication fails or user is not admin
    """
    user_info = await require_authenticated_user(credentials)
    
    # TODO: Implement admin role checking
    # This would check user roles/metadata in Clerk
    # For now, we'll use a placeholder implementation
    
    # Check if user has admin role (placeholder)
    # In a real implementation, you would check Clerk user metadata or roles
    is_admin = False  # TODO: Implement actual admin check
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return user_info


class OptionalAuth:
    """
    Optional authentication dependency.
    
    Returns user information if authenticated, None otherwise.
    Useful for endpoints that work with or without authentication.
    """
    
    def __init__(self):
        self.bearer_scheme = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Get user information if authenticated.
        
        Args:
            request: FastAPI request object
            
        Returns:
            User information dict or None if not authenticated
        """
        try:
            # Try to get credentials
            credentials = await self.bearer_scheme(request)
            if not credentials:
                return None
            
            # Verify token
            auth_info = await verify_clerk_token(credentials.credentials)
            return auth_info["user_info"]
            
        except Exception:
            # If authentication fails, return None (optional auth)
            return None


# Create instance for dependency injection
optional_auth = OptionalAuth()


def create_permission_dependency(required_permission: str):
    """
    Create a dependency that requires specific permission.
    
    Args:
        required_permission: Required permission string
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(
        credentials: HTTPAuthorizationCredentials = clerk_bearer_scheme
    ) -> Dict[str, Any]:
        """Check if user has required permission."""
        user_info = await require_authenticated_user(credentials)
        
        # Validate user permissions
        has_permission = await clerk_manager.validate_user_permissions(
            user_info["id"], 
            required_permission
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {required_permission}"
            )
        
        return user_info
    
    return permission_dependency
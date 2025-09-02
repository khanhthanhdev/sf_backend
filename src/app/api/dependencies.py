"""
FastAPI dependencies for authentication, services, and common utilities.

This module provides reusable dependencies for FastAPI endpoints,
including authentication, service injection, and request validation.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, status, Request, Header
from redis.asyncio import Redis

from ..core.auth import verify_clerk_token, AuthenticationError, extract_bearer_token
from ..core.redis import get_redis
from ..services.video_service import VideoService
from ..services.enhanced_video_service import EnhancedVideoService
from ..services.job_service import JobService
from ..services.queue_service import QueueService
from ..services.file_service import FileService
from ..services.aws_service_factory import AWSServiceFactory
from ..services.aws_video_service import AWSVideoService
from ..services.aws_job_service import AWSJobService
from ..services.aws_s3_file_service import AWSS3FileService
from ..services.aws_user_service import AWSUserService
from ..database.connection import RDSConnectionManager

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user.
    
    Extracts and validates the Clerk session token from the Authorization header,
    then returns user information and token claims.
    
    Args:
        authorization: Authorization header with Bearer token
        redis_client: Redis client for caching user info
        
    Returns:
        Dict containing user information and token claims
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        if not authorization:
            raise AuthenticationError("Missing authorization header")
        
        # Extract bearer token
        token = extract_bearer_token(authorization)
        
        # Verify token and get user info
        auth_info = await verify_clerk_token(token)
        
        # Extract email safely for logging
        user_info = auth_info["user_info"]
        user_id = user_info.get("id", "unknown")
        
        # Extract email from email_addresses array if available
        email = user_info.get("email")
        if not email and "email_addresses" in user_info:
            email_addresses = user_info.get("email_addresses", [])
            if email_addresses:
                primary_email_id = user_info.get("primary_email_address_id")
                if primary_email_id:
                    primary_email = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                    if primary_email:
                        email = primary_email.get("email_address")
                # Fallback to first email
                if not email:
                    email = email_addresses[0].get("email_address")
        
        logger.debug(
            "User authenticated successfully",
            extra={
                "user_id": user_id,
                "email": email or "no-email"
            }
        )
        
        return auth_info
        
    except AuthenticationError as e:
        logger.warning("Authentication failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error("Authentication error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    redis_client: Redis = Depends(get_redis)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to get current user if authenticated (optional).
    
    Similar to get_current_user but returns None if no authentication
    is provided instead of raising an exception.
    
    Args:
        authorization: Authorization header with Bearer token (optional)
        redis_client: Redis client for caching user info
        
    Returns:
        Dict containing user information or None if not authenticated
    """
    try:
        if not authorization:
            return None
        
        return await get_current_user(authorization, redis_client)
        
    except HTTPException:
        # Return None for optional authentication
        return None
    except Exception as e:
        logger.error("Optional authentication error", extra={"error": str(e)}, exc_info=True)
        return None


def get_job_service(
    redis_client: Redis = Depends(get_redis)
) -> JobService:
    """
    FastAPI dependency to get JobService instance.
    
    Args:
        redis_client: Redis client dependency
        
    Returns:
        JobService instance
    """
    return JobService(redis_client)


def get_queue_service(
    redis_client: Redis = Depends(get_redis)
) -> QueueService:
    """
    FastAPI dependency to get QueueService instance.
    
    Args:
        redis_client: Redis client dependency
        
    Returns:
        QueueService instance
    """
    return QueueService(redis_client)


def get_file_service(
    redis_client: Redis = Depends(get_redis)
) -> FileService:
    """
    FastAPI dependency to get FileService instance.
    
    Args:
        redis_client: Redis client dependency
        
    Returns:
        FileService instance
    """
    return FileService(redis_client)


# AWS Service Dependencies

def get_aws_service_factory(request: Request) -> Optional[AWSServiceFactory]:
    """
    FastAPI dependency to get AWS Service Factory instance.
    
    Args:
        request: FastAPI request object to access app state
        
    Returns:
        AWSServiceFactory instance or None if not initialized
    """
    return getattr(request.app.state, 'aws_service_factory', None)


def get_rds_connection_manager(
    aws_factory: Optional[AWSServiceFactory] = Depends(get_aws_service_factory)
) -> RDSConnectionManager:
    """
    FastAPI dependency to get RDS Connection Manager instance.
    
    Args:
        aws_factory: AWS service factory dependency
        
    Returns:
        RDSConnectionManager instance
        
    Raises:
        HTTPException: If RDS connection not available
    """
    if not aws_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS services not available"
        )
    
    if not aws_factory.rds_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RDS connection not available"
        )
    
    return aws_factory.rds_manager


def get_aws_file_service(
    aws_factory: Optional[AWSServiceFactory] = Depends(get_aws_service_factory)
) -> AWSS3FileService:
    """
    FastAPI dependency to get AWS S3 File Service instance.
    
    Args:
        aws_factory: AWS service factory dependency
        
    Returns:
        AWSS3FileService instance
        
    Raises:
        HTTPException: If AWS services not available
    """
    if not aws_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS services not available"
        )
    
    try:
        return aws_factory.create_file_service()
    except Exception as e:
        logger.error("Failed to create AWS file service", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS file service unavailable"
        )


def get_aws_video_service(
    aws_factory: Optional[AWSServiceFactory] = Depends(get_aws_service_factory)
) -> AWSVideoService:
    """
    FastAPI dependency to get AWS Video Service instance.
    
    Args:
        aws_factory: AWS service factory dependency
        
    Returns:
        AWSVideoService instance
        
    Raises:
        HTTPException: If AWS services not available
    """
    if not aws_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS services not available"
        )
    
    try:
        return aws_factory.create_video_service()
    except Exception as e:
        logger.error("Failed to create AWS video service", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS video service unavailable"
        )


def get_aws_job_service(
    aws_factory: Optional[AWSServiceFactory] = Depends(get_aws_service_factory)
) -> AWSJobService:
    """
    FastAPI dependency to get AWS Job Service instance.
    
    Args:
        aws_factory: AWS service factory dependency
        
    Returns:
        AWSJobService instance
        
    Raises:
        HTTPException: If AWS services not available
    """
    if not aws_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS services not available"
        )
    
    try:
        return aws_factory.create_job_service()
    except Exception as e:
        logger.error("Failed to create AWS job service", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS job service unavailable"
        )


def get_aws_user_service(
    aws_factory: Optional[AWSServiceFactory] = Depends(get_aws_service_factory)
) -> AWSUserService:
    """
    FastAPI dependency to get AWS User Service instance.
    
    Args:
        aws_factory: AWS service factory dependency
        
    Returns:
        AWSUserService instance
        
    Raises:
        HTTPException: If AWS services not available
    """
    if not aws_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS services not available"
        )
    
    try:
        return aws_factory.create_user_service()
    except Exception as e:
        logger.error("Failed to create AWS user service", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS user service unavailable"
        )


def get_video_service(
    db_manager: RDSConnectionManager = Depends(get_rds_connection_manager),
    aws_video_service: AWSVideoService = Depends(get_aws_video_service)
) -> VideoService:
    """
    FastAPI dependency to get VideoService instance.
    
    Args:
        db_manager: RDS connection manager dependency
        aws_video_service: AWS video service dependency
        
    Returns:
        VideoService instance
    """
    return VideoService(db_manager, aws_video_service)


def get_enhanced_video_service(
    video_service: VideoService = Depends(get_video_service),
    aws_video_service: AWSVideoService = Depends(get_aws_video_service)
) -> EnhancedVideoService:
    """
    FastAPI dependency to get EnhancedVideoService instance.
    
    This service integrates the FastAPI backend with the core video generation pipeline
    from generate_video.py and src/core/ components.
    
    Args:
        video_service: Base video service dependency
        aws_video_service: AWS video service dependency
        
    Returns:
        EnhancedVideoService instance
    """
    return EnhancedVideoService(video_service, aws_video_service)


class PaginationParams:
    """
    Pagination parameters for list endpoints.
    """
    
    def __init__(
        self,
        page: int = 1,
        items_per_page: int = 10,
        max_items_per_page: int = 100
    ):
        # Validate page number
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page number must be greater than 0"
            )
        
        # Validate items per page
        if items_per_page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Items per page must be greater than 0"
            )
        
        if items_per_page > max_items_per_page:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Items per page cannot exceed {max_items_per_page}"
            )
        
        self.page = page
        self.items_per_page = items_per_page
        self.offset = (page - 1) * items_per_page
    
    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.items_per_page


def get_pagination_params(
    page: int = 1,
    items_per_page: int = 10
) -> PaginationParams:
    """
    FastAPI dependency to get pagination parameters.
    
    Args:
        page: Page number (1-based)
        items_per_page: Number of items per page
        
    Returns:
        PaginationParams instance
        
    Raises:
        HTTPException: If parameters are invalid
    """
    return PaginationParams(page=page, items_per_page=items_per_page)


class JobFilters:
    """
    Filtering parameters for job list endpoints.
    """
    
    def __init__(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        priority: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None
    ):
        self.status = status
        self.job_type = job_type
        self.priority = priority
        self.created_after = created_after
        self.created_before = created_before
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filters to dictionary for service layer."""
        return {
            k: v for k, v in {
                "status": self.status,
                "job_type": self.job_type,
                "priority": self.priority,
                "created_after": self.created_after,
                "created_before": self.created_before
            }.items() if v is not None
        }


def get_job_filters(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    priority: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None
) -> JobFilters:
    """
    FastAPI dependency to get job filtering parameters.
    
    Args:
        status: Filter by job status
        job_type: Filter by job type
        priority: Filter by job priority
        created_after: Filter jobs created after this date (ISO format)
        created_before: Filter jobs created before this date (ISO format)
        
    Returns:
        JobFilters instance
    """
    return JobFilters(
        status=status,
        job_type=job_type,
        priority=priority,
        created_after=created_after,
        created_before=created_before
    )


def validate_job_ownership(
    job_user_id: str,
    current_user: Dict[str, Any]
) -> None:
    """
    Validate that the current user owns the specified job.
    
    Args:
        job_user_id: User ID from the job
        current_user: Current authenticated user
        
    Raises:
        HTTPException: If user doesn't own the job
    """
    if job_user_id != current_user["user_info"]["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't own this resource"
        )


def validate_request_size(
    request: Request,
    max_size_mb: int = 10
) -> None:
    """
    Validate request content size.
    
    Args:
        request: FastAPI request object
        max_size_mb: Maximum allowed size in MB
        
    Raises:
        HTTPException: If request is too large
    """
    content_length = request.headers.get("content-length")
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request too large. Maximum size: {max_size_mb}MB"
            )


async def rate_limit_check(
    current_user: Dict[str, Any],
    redis_client: Redis,
    operation: str,
    limit: int = 10,
    window_seconds: int = 60
) -> None:
    """
    Check rate limits for user operations.
    
    Args:
        current_user: Current authenticated user
        redis_client: Redis client for rate limit storage
        operation: Operation name for rate limiting
        limit: Maximum operations per window
        window_seconds: Time window in seconds
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    user_id = current_user["user_info"]["id"]
    key = f"rate_limit:{user_id}:{operation}"
    
    try:
        # Get current count
        current_count = await redis_client.get(key)
        current_count = int(current_count) if current_count else 0
        
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {operation}. Try again later.",
                headers={"Retry-After": str(window_seconds)}
            )
        
        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        await pipe.execute()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Rate limit check failed", extra={"error": str(e)}, exc_info=True)
        # Don't block requests if rate limiting fails
        pass


# Additional authentication dependencies for compatibility
async def get_authenticated_user(
    authorization: Optional[str] = Header(None),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Alias for get_current_user for backward compatibility.
    
    Returns the user_info portion of the authentication data.
    """
    auth_info = await get_current_user(authorization, redis_client)
    return auth_info["user_info"]


async def get_authenticated_user_id(
    authorization: Optional[str] = Header(None),
    redis_client: Redis = Depends(get_redis)
) -> str:
    """
    Get just the user ID from authentication.
    
    Returns:
        str: The authenticated user's ID
    """
    auth_info = await get_current_user(authorization, redis_client)
    return auth_info["user_info"]["id"]


async def get_verified_user(
    authorization: Optional[str] = Header(None),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get authenticated user that has verified email.
    
    Returns:
        Dict containing verified user information
        
    Raises:
        HTTPException: If user is not verified
    """
    auth_info = await get_current_user(authorization, redis_client)
    user_info = auth_info["user_info"]
    
    # Check email verification status from email_addresses array
    email_verified = user_info.get("email_verified", False)
    
    # If not directly available, check in email_addresses array
    if not email_verified and "email_addresses" in user_info:
        email_addresses = user_info.get("email_addresses", [])
        if email_addresses:
            primary_email_id = user_info.get("primary_email_address_id")
            if primary_email_id:
                primary_email = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                if primary_email:
                    verification = primary_email.get("verification", {})
                    email_verified = verification.get("status") == "verified"
            
            # Fallback to first email verification
            if not email_verified and email_addresses:
                first_email = email_addresses[0]
                verification = first_email.get("verification", {})
                email_verified = verification.get("status") == "verified"
    
    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return user_info


async def get_request_context(request: Request) -> Dict[str, Any]:
    """
    Get request context information.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict containing request context
    """
    return {
        "path": str(request.url.path),
        "method": request.method,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "timestamp": logger.info("Request context retrieved")
    }
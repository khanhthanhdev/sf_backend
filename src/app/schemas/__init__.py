"""
API request and response schemas for the FastAPI video generation backend.

This package contains Pydantic schemas specifically designed for API endpoints,
including request validation, response formatting, and API documentation.
"""

# Request schemas
from .requests import (
    VideoGenerationRequest,
    BatchVideoGenerationRequest,
    JobCancelRequest,
    JobFilterRequest,
    FileUploadRequest,
    UserPreferencesRequest,
)

# Response schemas
from .responses import (
    JobResponse,
    JobStatusResponse,
    JobListResponse,
    BatchJobResponse,
    VideoDownloadResponse,
    VideoMetadataResponse,
    SystemHealthResponse,
    SystemMetricsResponse,
)

# Common schemas
from .common import (
    SortOrder,
    PaginationRequest,
    SortRequest,
    FilterRequest,
    BulkOperationRequest,
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,
    NotFoundResponse,
    UnauthorizedResponse,
    ForbiddenResponse,
    ConflictResponse,
    RateLimitResponse,
    InternalServerErrorResponse,
    ServiceUnavailableResponse,
    HealthCheckResponse,
    BulkOperationResponse,
)

__all__ = [
    # Request schemas
    "VideoGenerationRequest",
    "BatchVideoGenerationRequest", 
    "JobCancelRequest",
    "JobFilterRequest",
    "FileUploadRequest",
    "UserPreferencesRequest",
    
    # Response schemas
    "JobResponse",
    "JobStatusResponse",
    "JobListResponse",
    "BatchJobResponse",
    "VideoDownloadResponse",
    "VideoMetadataResponse",
    "SystemHealthResponse",
    "SystemMetricsResponse",
    
    # Common schemas
    "SortOrder",
    "PaginationRequest",
    "SortRequest",
    "FilterRequest",
    "BulkOperationRequest",
    "SuccessResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    "NotFoundResponse",
    "UnauthorizedResponse",
    "ForbiddenResponse",
    "ConflictResponse",
    "RateLimitResponse",
    "InternalServerErrorResponse",
    "ServiceUnavailableResponse",
    "HealthCheckResponse",
    "BulkOperationResponse",
]
"""
Common schemas for API requests and responses.

This module defines shared Pydantic schemas for pagination, filtering, sorting,
error handling, and other common API patterns.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Generic, TypeVar
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum

from ..models.common import ErrorCode, FieldError, ErrorDetail, ResponseStatus

# Generic type for responses
T = TypeVar('T')


class SortOrder(str, Enum):
    """Sort order enumeration."""
    ASC = "asc"
    DESC = "desc"


class PaginationRequest(BaseModel):
    """
    Request schema for pagination parameters.
    
    Provides standardized pagination controls for list endpoints.
    """
    
    page: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Page number (1-based)",
        example=1
    )
    items_per_page: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of items per page",
        example=10
    )
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.items_per_page
    
    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.items_per_page
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "items_per_page": 10
            }
        }
    )


class SortRequest(BaseModel):
    """
    Request schema for sorting parameters.
    
    Provides standardized sorting controls for list endpoints.
    """
    
    sort_by: str = Field(
        default="created_at",
        description="Field to sort by",
        example="created_at"
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESC,
        description="Sort order (asc or desc)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sort_by": "created_at",
                "sort_order": "desc"
            }
        }
    )
    
    @validator("sort_by")
    def validate_sort_field(cls, v):
        """Validate sort field contains only safe characters."""
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError("Sort field contains invalid characters")
        return v


class FilterRequest(BaseModel):
    """
    Base request schema for filtering parameters.
    
    Provides common filtering options that can be extended by specific endpoints.
    """
    
    search: Optional[str] = Field(
        None,
        max_length=100,
        description="Search query string",
        example="mathematics"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Filter items created after this date",
        example="2024-01-01T00:00:00Z"
    )
    created_before: Optional[datetime] = Field(
        None,
        description="Filter items created before this date",
        example="2024-12-31T23:59:59Z"
    )
    updated_after: Optional[datetime] = Field(
        None,
        description="Filter items updated after this date"
    )
    updated_before: Optional[datetime] = Field(
        None,
        description="Filter items updated before this date"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "search": "mathematics",
                "created_after": "2024-01-01T00:00:00Z",
                "created_before": "2024-12-31T23:59:59Z"
            }
        }
    )
    
    @validator("created_before")
    def validate_created_date_range(cls, v, values):
        """Validate created date range is logical."""
        created_after = values.get("created_after")
        if created_after and v and v <= created_after:
            raise ValueError("created_before must be after created_after")
        return v
    
    @validator("updated_before")
    def validate_updated_date_range(cls, v, values):
        """Validate updated date range is logical."""
        updated_after = values.get("updated_after")
        if updated_after and v and v <= updated_after:
            raise ValueError("updated_before must be after updated_after")
        return v
    
    @validator("search")
    def validate_search_query(cls, v):
        """Validate and clean search query."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 2:
                raise ValueError("Search query must be at least 2 characters long")
        return v


class BulkOperationRequest(BaseModel):
    """
    Request schema for bulk operations.
    
    Allows performing operations on multiple items at once.
    """
    
    ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of item IDs to operate on"
    )
    operation: str = Field(
        ...,
        description="Operation to perform",
        example="delete"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional parameters for the operation"
    )
    confirm: bool = Field(
        default=False,
        description="Confirmation flag for destructive operations"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "550e8400-e29b-41d4-a716-446655440001"
                ],
                "operation": "cancel",
                "parameters": {
                    "reason": "Bulk cancellation requested by user"
                },
                "confirm": True
            }
        }
    )
    
    @validator("ids")
    def validate_ids_unique(cls, v):
        """Ensure all IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("All IDs must be unique")
        return v
    
    @validator("operation")
    def validate_operation(cls, v):
        """Validate operation is allowed."""
        allowed_operations = [
            "delete", "cancel", "retry", "archive", 
            "restore", "update_priority", "add_tags"
        ]
        if v not in allowed_operations:
            raise ValueError(f"Operation '{v}' not allowed")
        return v


class SuccessResponse(BaseModel, Generic[T]):
    """
    Generic success response schema.
    
    Provides a consistent format for successful API responses.
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.SUCCESS,
        description="Response status"
    )
    message: str = Field(
        ...,
        description="Success message",
        example="Operation completed successfully"
    )
    data: T = Field(
        ...,
        description="Response data"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    request_id: Optional[str] = Field(
        None,
        description="Request ID for tracking"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "message": "Job created successfully",
                "data": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "queued"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }
    )


class ErrorResponse(BaseModel):
    """
    Standard error response schema.
    
    Provides consistent error formatting across all API endpoints.
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ERROR,
        description="Response status"
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        example="An error occurred while processing your request"
    )
    error: ErrorDetail = Field(
        ...,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    request_id: Optional[str] = Field(
        None,
        description="Request ID for tracking"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "message": "Job not found",
                "error": {
                    "message": "The requested job was not found",
                    "code": "JOB_NOT_FOUND",
                    "details": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000"
                    },
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }
    )


class ValidationErrorResponse(BaseModel):
    """
    Validation error response schema.
    
    Provides detailed information about validation failures.
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ERROR,
        description="Response status"
    )
    message: str = Field(
        default="Validation failed",
        description="Error message"
    )
    error: ErrorDetail = Field(
        ...,
        description="Validation error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    request_id: Optional[str] = Field(
        None,
        description="Request ID for tracking"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "message": "Validation failed",
                "error": {
                    "message": "The request contains invalid data",
                    "code": "VALIDATION_ERROR",
                    "field_errors": [
                        {
                            "field": "topic",
                            "message": "Topic cannot be empty",
                            "code": "REQUIRED_FIELD",
                            "value": ""
                        },
                        {
                            "field": "context",
                            "message": "Context must be at least 10 characters long",
                            "code": "MIN_LENGTH",
                            "value": "short"
                        }
                    ],
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }
    )


# HTTP Status Code Specific Responses

class NotFoundResponse(ErrorResponse):
    """404 Not Found response schema."""
    
    def __init__(self, resource: str = "Resource", resource_id: str = None, **kwargs):
        error_details = {"resource_type": resource}
        if resource_id:
            error_details["resource_id"] = resource_id
            
        super().__init__(
            message=f"{resource} not found",
            error=ErrorDetail(
                message=f"The requested {resource.lower()} was not found",
                code=ErrorCode.NOT_FOUND,
                details=error_details
            ),
            **kwargs
        )


class UnauthorizedResponse(ErrorResponse):
    """401 Unauthorized response schema."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="Authentication required",
            error=ErrorDetail(
                message="Valid authentication credentials are required to access this resource",
                code=ErrorCode.UNAUTHORIZED,
                details={"authentication_required": True}
            ),
            **kwargs
        )


class ForbiddenResponse(ErrorResponse):
    """403 Forbidden response schema."""
    
    def __init__(self, resource: str = "resource", **kwargs):
        super().__init__(
            message="Access forbidden",
            error=ErrorDetail(
                message=f"You do not have permission to access this {resource}",
                code=ErrorCode.FORBIDDEN,
                details={"required_permission": f"access_{resource}"}
            ),
            **kwargs
        )


class ConflictResponse(ErrorResponse):
    """409 Conflict response schema."""
    
    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(
            message=message,
            error=ErrorDetail(
                message=message,
                code=ErrorCode.CONFLICT
            ),
            **kwargs
        )


class RateLimitResponse(ErrorResponse):
    """429 Rate Limit Exceeded response schema."""
    
    def __init__(self, retry_after: int = None, limit: int = None, **kwargs):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        if limit:
            details["rate_limit"] = limit
            
        super().__init__(
            message="Rate limit exceeded",
            error=ErrorDetail(
                message="Too many requests. Please try again later.",
                code=ErrorCode.RATE_LIMIT_EXCEEDED,
                details=details if details else None
            ),
            **kwargs
        )


class InternalServerErrorResponse(ErrorResponse):
    """500 Internal Server Error response schema."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="Internal server error",
            error=ErrorDetail(
                message="An unexpected error occurred. Please try again later.",
                code=ErrorCode.INTERNAL_ERROR,
                details={"support_contact": "support@example.com"}
            ),
            **kwargs
        )


class ServiceUnavailableResponse(ErrorResponse):
    """503 Service Unavailable response schema."""
    
    def __init__(self, service: str = "system", retry_after: int = None, **kwargs):
        details = {"service": service}
        if retry_after:
            details["retry_after_seconds"] = retry_after
            
        super().__init__(
            message="Service temporarily unavailable",
            error=ErrorDetail(
                message=f"The {service} is temporarily unavailable. Please try again later.",
                code=ErrorCode.SERVICE_UNAVAILABLE,
                details=details
            ),
            **kwargs
        )


# Utility response schemas

class HealthCheckResponse(BaseModel):
    """Simple health check response."""
    
    status: str = Field(..., description="Health status", example="healthy")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Check timestamp"
    )
    version: str = Field(..., description="Application version", example="1.0.0")
    uptime_seconds: float = Field(..., description="Uptime in seconds", example=86400.0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0",
                "uptime_seconds": 86400.0
            }
        }
    )


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations."""
    
    operation: str = Field(..., description="Operation that was performed")
    total_requested: int = Field(..., ge=0, description="Total items requested")
    successful: int = Field(..., ge=0, description="Successfully processed items")
    failed: int = Field(..., ge=0, description="Failed items")
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Errors for failed items"
    )
    processing_time_seconds: float = Field(
        ...,
        description="Total processing time"
    )
    
    @property
    def success_rate_percent(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requested == 0:
            return 100.0
        return round((self.successful / self.total_requested) * 100, 2)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation": "cancel",
                "total_requested": 10,
                "successful": 8,
                "failed": 2,
                "errors": [
                    {
                        "id": "job_123",
                        "error": "Job already completed"
                    },
                    {
                        "id": "job_456", 
                        "error": "Job not found"
                    }
                ],
                "processing_time_seconds": 2.5
            }
        }
    )
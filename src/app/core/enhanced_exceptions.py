"""
Enhanced Exception Hierarchy for T2M Application

This module provides a comprehensive, structured exception hierarchy with proper
HTTP status code mapping, correlation IDs, and detailed error context for better
debugging and API responses.

Following SOLID principles and enterprise-grade error handling patterns.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field


class ErrorSeverity(str, Enum):
    """Error severity levels for logging and alerting."""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification and handling."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    INFRASTRUCTURE = "infrastructure"
    SYSTEM = "system"
    RATE_LIMITING = "rate_limiting"


@dataclass
class ErrorContext:
    """
    Rich error context for debugging and monitoring.
    """
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    operation: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    service_name: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "service_name": self.service_name,
            "additional_data": self.additional_data
        }


class T2MBaseException(Exception):
    """
    Enhanced base exception class for all T2M application exceptions.
    
    Provides structured error information with HTTP status mapping,
    correlation IDs, and rich context for debugging and monitoring.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        http_status_code: int = 500,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Optional[ErrorContext] = None,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        retry_after: Optional[int] = None,
        documentation_url: Optional[str] = None
    ):
        """
        Initialize base exception with rich error information.
        
        Args:
            message: Technical error message for developers
            error_code: Machine-readable error code
            http_status_code: HTTP status code for API responses
            severity: Error severity level
            category: Error category for classification
            context: Rich error context
            details: Additional error details
            user_message: User-friendly error message
            retry_after: Seconds to wait before retrying (for rate limiting)
            documentation_url: URL to relevant documentation
        """
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.http_status_code = http_status_code
        self.severity = severity
        self.category = category
        self.context = context or ErrorContext()
        self.details = details or {}
        self.user_message = user_message or message
        self.retry_after = retry_after
        self.documentation_url = documentation_url
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "message": self.user_message,
            "error_code": self.error_code,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context.to_dict(),
            "details": self.details
        }
        
        if self.retry_after:
            result["retry_after"] = self.retry_after
        
        if self.documentation_url:
            result["documentation_url"] = self.documentation_url
            
        return result


# ============================================================================
# Validation Exceptions (4xx Client Errors)
# ============================================================================

class ValidationException(T2MBaseException):
    """Base class for validation errors."""
    
    def __init__(self, message: str, field_errors: Optional[List[Dict[str, Any]]] = None, **kwargs):
        kwargs.setdefault('http_status_code', 400)
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        kwargs.setdefault('severity', ErrorSeverity.LOW)
        
        if field_errors:
            kwargs.setdefault('details', {}).update({"field_errors": field_errors})
        
        super().__init__(message, **kwargs)


class InvalidInputException(ValidationException):
    """Raised when input data is invalid."""
    
    def __init__(self, message: str = "Invalid input data provided", **kwargs):
        kwargs.setdefault('error_code', 'INVALID_INPUT')
        super().__init__(message, **kwargs)


class MissingFieldException(ValidationException):
    """Raised when required fields are missing."""
    
    def __init__(self, field_name: str, **kwargs):
        message = f"Required field '{field_name}' is missing"
        kwargs.setdefault('error_code', 'MISSING_FIELD')
        kwargs.setdefault('details', {}).update({"missing_field": field_name})
        super().__init__(message, **kwargs)


class InvalidFieldValueException(ValidationException):
    """Raised when field values are invalid."""
    
    def __init__(self, field_name: str, value: Any, reason: str = "", **kwargs):
        message = f"Invalid value for field '{field_name}'"
        if reason:
            message += f": {reason}"
        
        kwargs.setdefault('error_code', 'INVALID_FIELD_VALUE')
        kwargs.setdefault('details', {}).update({
            "field_name": field_name,
            "provided_value": str(value),
            "reason": reason
        })
        super().__init__(message, **kwargs)


# ============================================================================
# Authentication & Authorization Exceptions (401, 403)
# ============================================================================

class AuthenticationException(T2MBaseException):
    """Base class for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        kwargs.setdefault('http_status_code', 401)
        kwargs.setdefault('category', ErrorCategory.AUTHENTICATION)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('error_code', 'AUTHENTICATION_FAILED')
        super().__init__(message, **kwargs)


class InvalidTokenException(AuthenticationException):
    """Raised when authentication token is invalid."""
    
    def __init__(self, message: str = "Invalid or expired authentication token", **kwargs):
        kwargs.setdefault('error_code', 'INVALID_TOKEN')
        super().__init__(message, **kwargs)


class TokenExpiredException(AuthenticationException):
    """Raised when authentication token has expired."""
    
    def __init__(self, message: str = "Authentication token has expired", **kwargs):
        kwargs.setdefault('error_code', 'TOKEN_EXPIRED')
        super().__init__(message, **kwargs)


class AuthorizationException(T2MBaseException):
    """Base class for authorization errors."""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        kwargs.setdefault('http_status_code', 403)
        kwargs.setdefault('category', ErrorCategory.AUTHORIZATION)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('error_code', 'ACCESS_DENIED')
        super().__init__(message, **kwargs)


class InsufficientPermissionsException(AuthorizationException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, required_permission: str, **kwargs):
        message = f"Insufficient permissions. Required: {required_permission}"
        kwargs.setdefault('error_code', 'INSUFFICIENT_PERMISSIONS')
        kwargs.setdefault('details', {}).update({"required_permission": required_permission})
        super().__init__(message, **kwargs)


# ============================================================================
# Resource Not Found Exceptions (404)
# ============================================================================

class ResourceNotFoundException(T2MBaseException):
    """Base class for resource not found errors."""
    
    def __init__(self, resource_type: str, resource_id: Union[str, int], **kwargs):
        message = f"{resource_type} not found"
        kwargs.setdefault('http_status_code', 404)
        kwargs.setdefault('category', ErrorCategory.BUSINESS_LOGIC)
        kwargs.setdefault('severity', ErrorSeverity.LOW)
        kwargs.setdefault('error_code', 'RESOURCE_NOT_FOUND')
        kwargs.setdefault('details', {}).update({
            "resource_type": resource_type,
            "resource_id": str(resource_id)
        })
        super().__init__(message, **kwargs)


class VideoNotFoundException(ResourceNotFoundException):
    """Raised when a video is not found."""
    
    def __init__(self, video_id: str, **kwargs):
        super().__init__("Video", video_id, error_code="VIDEO_NOT_FOUND", **kwargs)


class JobNotFoundException(ResourceNotFoundException):
    """Raised when a job is not found."""
    
    def __init__(self, job_id: str, **kwargs):
        super().__init__("Job", job_id, error_code="JOB_NOT_FOUND", **kwargs)


class UserNotFoundException(ResourceNotFoundException):
    """Raised when a user is not found."""
    
    def __init__(self, user_id: str, **kwargs):
        super().__init__("User", user_id, error_code="USER_NOT_FOUND", **kwargs)


class FileNotFoundException(ResourceNotFoundException):
    """Raised when a file is not found."""
    
    def __init__(self, file_path: str, **kwargs):
        super().__init__("File", file_path, error_code="FILE_NOT_FOUND", **kwargs)


# ============================================================================
# Business Logic Exceptions (422)
# ============================================================================

class BusinessLogicException(T2MBaseException):
    """Base class for business rule violations."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('http_status_code', 422)
        kwargs.setdefault('category', ErrorCategory.BUSINESS_LOGIC)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        super().__init__(message, **kwargs)


class InvalidStateException(BusinessLogicException):
    """Raised when an operation is attempted on an entity in invalid state."""
    
    def __init__(self, entity_type: str, current_state: str, required_state: str, **kwargs):
        message = f"{entity_type} is in state '{current_state}', but operation requires '{required_state}'"
        kwargs.setdefault('error_code', 'INVALID_STATE')
        kwargs.setdefault('details', {}).update({
            "entity_type": entity_type,
            "current_state": current_state,
            "required_state": required_state
        })
        super().__init__(message, **kwargs)


class ResourceConflictException(BusinessLogicException):
    """Raised when there's a conflict with existing resources."""
    
    def __init__(self, resource_type: str, conflict_reason: str, **kwargs):
        message = f"{resource_type} conflict: {conflict_reason}"
        kwargs.setdefault('http_status_code', 409)
        kwargs.setdefault('error_code', 'RESOURCE_CONFLICT')
        kwargs.setdefault('details', {}).update({
            "resource_type": resource_type,
            "conflict_reason": conflict_reason
        })
        super().__init__(message, **kwargs)


class VideoProcessingException(BusinessLogicException):
    """Raised when video processing operations fail."""
    
    def __init__(self, message: str, processing_stage: str = "", **kwargs):
        kwargs.setdefault('error_code', 'VIDEO_PROCESSING_ERROR')
        if processing_stage:
            kwargs.setdefault('details', {}).update({"processing_stage": processing_stage})
        super().__init__(message, **kwargs)


# ============================================================================
# Rate Limiting Exceptions (429)
# ============================================================================

class RateLimitException(T2MBaseException):
    """Base class for rate limiting errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60, **kwargs):
        kwargs.setdefault('http_status_code', 429)
        kwargs.setdefault('category', ErrorCategory.RATE_LIMITING)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('error_code', 'RATE_LIMIT_EXCEEDED')
        kwargs['retry_after'] = retry_after
        super().__init__(message, **kwargs)


class APIRateLimitException(RateLimitException):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, limit: int, window: int, **kwargs):
        message = f"API rate limit exceeded: {limit} requests per {window} seconds"
        kwargs.setdefault('details', {}).update({
            "limit": limit,
            "window": window,
            "limit_type": "api"
        })
        super().__init__(message, **kwargs)


class ProcessingQuotaException(RateLimitException):
    """Raised when processing quotas are exceeded."""
    
    def __init__(self, quota_type: str, limit: int, **kwargs):
        message = f"Processing quota exceeded for {quota_type}: {limit}"
        kwargs.setdefault('error_code', 'QUOTA_EXCEEDED')
        kwargs.setdefault('details', {}).update({
            "quota_type": quota_type,
            "limit": limit
        })
        super().__init__(message, **kwargs)


# ============================================================================
# External Service Exceptions (502, 503, 504)
# ============================================================================

class ExternalServiceException(T2MBaseException):
    """Base class for external service errors."""
    
    def __init__(self, service_name: str, message: str, **kwargs):
        kwargs.setdefault('http_status_code', 502)
        kwargs.setdefault('category', ErrorCategory.EXTERNAL_SERVICE)
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('details', {}).update({"service_name": service_name})
        super().__init__(message, **kwargs)


class ServiceUnavailableException(ExternalServiceException):
    """Raised when external services are unavailable."""
    
    def __init__(self, service_name: str, **kwargs):
        message = f"{service_name} service is temporarily unavailable"
        kwargs.setdefault('http_status_code', 503)
        kwargs.setdefault('error_code', 'SERVICE_UNAVAILABLE')
        super().__init__(service_name, message, **kwargs)


class ServiceTimeoutException(ExternalServiceException):
    """Raised when external service calls timeout."""
    
    def __init__(self, service_name: str, timeout: int, **kwargs):
        message = f"{service_name} service request timed out after {timeout} seconds"
        kwargs.setdefault('http_status_code', 504)
        kwargs.setdefault('error_code', 'SERVICE_TIMEOUT')
        kwargs.setdefault('details', {}).update({"timeout": timeout})
        super().__init__(service_name, message, **kwargs)


class AWSServiceException(ExternalServiceException):
    """Raised for AWS service errors."""
    
    def __init__(self, service_name: str, aws_error_code: str, message: str, **kwargs):
        kwargs.setdefault('error_code', 'AWS_SERVICE_ERROR')
        kwargs.setdefault('details', {}).update({"aws_error_code": aws_error_code})
        super().__init__(service_name, message, **kwargs)


class DatabaseException(ExternalServiceException):
    """Raised for database operation errors."""
    
    def __init__(self, operation: str, message: str, **kwargs):
        kwargs.setdefault('http_status_code', 503)
        kwargs.setdefault('error_code', 'DATABASE_ERROR')
        kwargs.setdefault('details', {}).update({"operation": operation})
        super().__init__("Database", message, **kwargs)


class DatabaseConnectionException(DatabaseException):
    """Raised when database connection fails."""
    
    def __init__(self, **kwargs):
        message = "Database connection failed"
        kwargs.setdefault('error_code', 'DATABASE_CONNECTION_ERROR')
        super().__init__("connection", message, **kwargs)


class DatabaseTimeoutException(DatabaseException):
    """Raised when database operations timeout."""
    
    def __init__(self, operation: str, timeout: int, **kwargs):
        message = f"Database {operation} timed out after {timeout} seconds"
        kwargs.setdefault('http_status_code', 504)
        kwargs.setdefault('error_code', 'DATABASE_TIMEOUT')
        kwargs.setdefault('details', {}).update({"timeout": timeout})
        super().__init__(operation, message, **kwargs)


# ============================================================================
# System/Infrastructure Exceptions (500)
# ============================================================================

class SystemException(T2MBaseException):
    """Base class for system/infrastructure errors."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('http_status_code', 500)
        kwargs.setdefault('category', ErrorCategory.SYSTEM)
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        super().__init__(message, **kwargs)


class ConfigurationException(SystemException):
    """Raised when system configuration is invalid."""
    
    def __init__(self, config_key: str, message: str = "", **kwargs):
        error_msg = f"Configuration error for '{config_key}'"
        if message:
            error_msg += f": {message}"
        
        kwargs.setdefault('error_code', 'CONFIGURATION_ERROR')
        kwargs.setdefault('severity', ErrorSeverity.CRITICAL)
        kwargs.setdefault('details', {}).update({"config_key": config_key})
        super().__init__(error_msg, **kwargs)


class InfrastructureException(SystemException):
    """Raised for infrastructure-related errors."""
    
    def __init__(self, component: str, message: str, **kwargs):
        error_msg = f"Infrastructure error in {component}: {message}"
        kwargs.setdefault('error_code', 'INFRASTRUCTURE_ERROR')
        kwargs.setdefault('severity', ErrorSeverity.CRITICAL)
        kwargs.setdefault('details', {}).update({"component": component})
        super().__init__(error_msg, **kwargs)


class CircuitBreakerOpenException(SystemException):
    """Raised when circuit breaker is open."""
    
    def __init__(self, service_name: str, failure_count: int, **kwargs):
        message = f"Circuit breaker open for {service_name} (failures: {failure_count})"
        kwargs.setdefault('http_status_code', 503)
        kwargs.setdefault('error_code', 'CIRCUIT_BREAKER_OPEN')
        kwargs.setdefault('retry_after', 60)
        kwargs.setdefault('details', {}).update({
            "service_name": service_name,
            "failure_count": failure_count
        })
        super().__init__(message, **kwargs)


# ============================================================================
# Utility Functions for Error Mapping
# ============================================================================

def map_http_status_to_exception(
    status_code: int,
    message: str = "",
    error_code: str = "",
    **kwargs
) -> T2MBaseException:
    """
    Map HTTP status codes to appropriate exception types.
    
    Args:
        status_code: HTTP status code
        message: Error message
        error_code: Machine-readable error code
        **kwargs: Additional exception arguments
    
    Returns:
        Appropriate exception instance
    """
    status_to_exception = {
        400: ValidationException,
        401: AuthenticationException,
        403: AuthorizationException,
        404: ResourceNotFoundException,
        409: ResourceConflictException,
        422: BusinessLogicException,
        429: RateLimitException,
        500: SystemException,
        502: ExternalServiceException,
        503: ServiceUnavailableException,
        504: ServiceTimeoutException,
    }
    
    exception_class = status_to_exception.get(status_code, SystemException)
    
    if not message:
        message = f"HTTP {status_code} error occurred"
    
    if status_code == 404 and 'resource_type' not in kwargs:
        kwargs['resource_type'] = "Resource"
        kwargs['resource_id'] = "unknown"
    
    return exception_class(message, error_code=error_code, **kwargs)


def create_error_context(
    operation: str = "",
    user_id: str = "",
    request_id: str = "",
    service_name: str = "",
    **additional_data
) -> ErrorContext:
    """
    Create error context with common information.
    
    Args:
        operation: Operation being performed
        user_id: User ID if available
        request_id: Request ID for tracing
        service_name: Service name
        **additional_data: Additional context data
    
    Returns:
        ErrorContext instance
    """
    return ErrorContext(
        operation=operation or None,
        user_id=user_id or None,
        request_id=request_id or None,
        service_name=service_name or None,
        additional_data=additional_data
    )

# Enhanced Error Handling System Documentation

## Overview

The T2M application implements a comprehensive, enterprise-grade error handling system that follows SOLID principles and best practices for large-scale applications. This system provides structured error hierarchies, circuit breaker patterns, correlation ID tracking, and comprehensive logging.

## Architecture

### Components

1. **Enhanced Exception Hierarchy** (`core/enhanced_exceptions.py`)
   - Structured exception classes with HTTP status mapping
   - Rich error context with correlation IDs
   - Severity levels and error categorization
   - Comprehensive error details for debugging

2. **Circuit Breaker Pattern** (`core/circuit_breaker.py`)
   - Automatic failure detection and recovery
   - Configurable thresholds and timeouts
   - Exponential backoff strategies
   - Comprehensive monitoring and metrics

3. **Global Exception Handlers** (`core/enhanced_exception_handlers.py`)
   - Correlation ID middleware for request tracking
   - Structured error logging with context
   - Consistent error response formatting
   - Security-aware error message sanitization

4. **Enhanced AWS Error Handler** (`utils/enhanced_aws_error_handler.py`)
   - AWS service error mapping and categorization
   - Circuit breaker integration for AWS operations
   - Comprehensive retry strategies
   - Service health monitoring

## Error Hierarchy

### Base Exception Classes

#### T2MBaseException
The root of all application exceptions with rich error context:

```python
class T2MBaseException(Exception):
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
    )
```

### Exception Categories

#### 1. Validation Exceptions (4xx Client Errors)

- **ValidationException**: Base validation error
- **InvalidInputException**: Invalid input data
- **MissingFieldException**: Required fields missing
- **InvalidFieldValueException**: Invalid field values

```python
# Example usage
raise InvalidInputException(
    message="Invalid email format",
    field_errors=[{
        "field": "email",
        "message": "Email must be a valid email address",
        "type": "value_error.email"
    }]
)
```

#### 2. Authentication & Authorization Exceptions (401, 403)

- **AuthenticationException**: Authentication failures
- **InvalidTokenException**: Invalid/expired tokens
- **AuthorizationException**: Access denied
- **InsufficientPermissionsException**: Missing permissions

```python
# Example usage
raise InsufficientPermissionsException(
    required_permission="video:create",
    context=create_error_context(
        operation="create_video",
        user_id=user_id
    )
)
```

#### 3. Resource Not Found Exceptions (404)

- **ResourceNotFoundException**: Base not found error
- **VideoNotFoundException**: Video not found
- **JobNotFoundException**: Job not found
- **UserNotFoundException**: User not found

```python
# Example usage
raise VideoNotFoundException(
    video_id="123e4567-e89b-12d3-a456-426614174000",
    context=error_context
)
```

#### 4. Business Logic Exceptions (422)

- **BusinessLogicException**: Business rule violations
- **InvalidStateException**: Invalid entity state
- **ResourceConflictException**: Resource conflicts
- **VideoProcessingException**: Video processing errors

```python
# Example usage
raise InvalidStateException(
    entity_type="Video",
    current_state="processing",
    required_state="uploaded"
)
```

#### 5. Rate Limiting Exceptions (429)

- **RateLimitException**: Rate limit exceeded
- **APIRateLimitException**: API rate limits
- **ProcessingQuotaException**: Processing quotas

```python
# Example usage
raise APIRateLimitException(
    limit=100,
    window=3600,
    retry_after=300
)
```

#### 6. External Service Exceptions (502, 503, 504)

- **ExternalServiceException**: External service errors
- **ServiceUnavailableException**: Service unavailable
- **ServiceTimeoutException**: Service timeouts
- **AWSServiceException**: AWS-specific errors
- **DatabaseException**: Database errors

## Circuit Breaker Pattern

### Configuration

```python
config = CircuitBreakerConfig(
    failure_threshold=5,        # Failures before opening
    success_threshold=3,        # Successes to close
    timeout=60,                # Timeout before retry
    call_timeout=30,           # Individual call timeout
    exponential_backoff=True,   # Use exponential backoff
    max_timeout=300            # Maximum timeout
)
```

### Usage Examples

#### Decorator Pattern
```python
@circuit_breaker_decorator("external_api")
async def call_external_service():
    # Implementation
    pass
```

#### Context Manager Pattern
```python
async with circuit_breaker("aws_s3") as cb:
    result = await cb(s3_client.upload_file, file_path, bucket, key)
```

#### AWS Operations
```python
@aws_circuit_breaker("s3", "upload_file")
async def upload_to_s3(file_path: str, bucket: str, key: str):
    # Implementation with automatic circuit breaker protection
    pass
```

## Error Response Format

### Standard Error Response

```json
{
  "status": "error",
  "message": "Video not found",
  "error": {
    "message": "The requested video was not found",
    "code": "VIDEO_NOT_FOUND",
    "details": {
      "video_id": "123e4567-e89b-12d3-a456-426614174000"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789",
  "correlation_id": "corr_789012345",
  "severity": "medium",
  "category": "business_logic"
}
```

### Enhanced Error Response (with circuit breaker)

```json
{
  "status": "error",
  "message": "Service temporarily unavailable",
  "error": {
    "message": "Circuit breaker open for AWS S3 (failures: 5)",
    "code": "CIRCUIT_BREAKER_OPEN",
    "details": {
      "service_name": "aws_s3",
      "failure_count": 5,
      "circuit_state": "open"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "retry_after": 60,
  "documentation_url": "https://docs.api.com/errors/circuit-breaker"
}
```

## Error Codes Reference

### Validation Errors (400-499)
- `VALIDATION_ERROR`: General validation failure
- `INVALID_INPUT`: Invalid input data
- `MISSING_FIELD`: Required field missing
- `INVALID_FIELD_VALUE`: Invalid field value
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Access denied
- `NOT_FOUND`: Resource not found
- `CONFLICT`: Resource conflict
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded

### External Service Errors (500-599)
- `SERVICE_UNAVAILABLE`: External service unavailable
- `SERVICE_TIMEOUT`: External service timeout
- `AWS_SERVICE_ERROR`: AWS service error
- `DATABASE_ERROR`: Database operation error
- `CIRCUIT_BREAKER_OPEN`: Circuit breaker is open
- `INTERNAL_ERROR`: Internal server error

## Correlation ID Tracking

### Automatic Injection
Correlation IDs are automatically injected into all requests via middleware:

```python
# Middleware automatically adds correlation ID to request scope
correlation_id = str(uuid.uuid4())
scope["correlation_id"] = correlation_id

# Available in exception handlers
correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
```

### Response Headers
All responses include correlation ID in headers:
```
X-Correlation-ID: 123e4567-e89b-12d3-a456-426614174000
```

### Logging Integration
All error logs include correlation IDs for distributed tracing:

```python
logger.error(
    "Application error occurred",
    extra={
        "correlation_id": context.correlation_id,
        "user_id": context.user_id,
        "operation": context.operation,
        "error_code": exc.error_code
    }
)
```

## Monitoring and Metrics

### Error Metrics Endpoint
```
GET /api/v1/system/error-metrics
```

Response:
```json
{
  "error_counts": {
    "VIDEO_NOT_FOUND": 15,
    "VALIDATION_ERROR": 8,
    "RATE_LIMIT_EXCEEDED": 3
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Circuit Breaker Metrics
```python
# Get metrics for all circuit breakers
metrics = await circuit_breaker_registry.get_all_metrics()

# Get unhealthy services
unhealthy = await circuit_breaker_registry.get_unhealthy_services()
```

### Health Check Integration
```
GET /health/detailed
```

Includes circuit breaker status:
```json
{
  "overall_status": "healthy",
  "aws": {
    "overall_status": "healthy",
    "circuit_breakers": {
      "aws_s3": {
        "state": "closed",
        "success_rate": 0.95,
        "failure_count": 2
      }
    }
  }
}
```

## Best Practices

### 1. Exception Creation
```python
# Good: Rich context and proper categorization
raise VideoNotFoundException(
    video_id=video_id,
    context=create_error_context(
        operation="get_video",
        user_id=user_id,
        service_name="video_service"
    )
)

# Bad: Generic exception without context
raise Exception("Video not found")
```

### 2. AWS Operations
```python
# Good: Circuit breaker protection
@aws_circuit_breaker("s3", "upload_file")
async def upload_video(file_path: str, bucket: str, key: str):
    # Implementation

# Bad: Direct AWS call without protection
async def upload_video(file_path: str, bucket: str, key: str):
    # Direct S3 call - no circuit breaker protection
```

### 3. Error Handling in Services
```python
# Good: Structured error handling
try:
    result = await video_service.create_video(request)
except VideoNotFoundException as e:
    # Log with context and re-raise
    logger.warning("Video not found during operation", extra=e.context.to_dict())
    raise
except Exception as e:
    # Convert to application exception
    raise SystemException(
        message=f"Unexpected error in video creation: {str(e)}",
        context=create_error_context(operation="create_video")
    ) from e
```

### 4. Circuit Breaker Configuration
```python
# Production configuration
production_config = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=3,
    timeout=60,
    call_timeout=30,
    exponential_backoff=True,
    max_timeout=300
)

# Development configuration (more lenient)
dev_config = CircuitBreakerConfig(
    failure_threshold=10,
    success_threshold=2,
    timeout=30,
    call_timeout=60
)
```

## Migration Guide

### From Old Exception System

1. **Replace basic exceptions**:
   ```python
   # Old
   raise HTTPException(status_code=404, detail="Video not found")
   
   # New
   raise VideoNotFoundException(video_id=video_id)
   ```

2. **Add circuit breaker protection**:
   ```python
   # Old
   async def upload_to_s3(file_path: str):
       return await s3_client.upload_file(file_path)
   
   # New
   @aws_circuit_breaker("s3", "upload_file")
   async def upload_to_s3(file_path: str):
       return await s3_client.upload_file(file_path)
   ```

3. **Update error handling**:
   ```python
   # Old
   try:
       result = await operation()
   except Exception as e:
       logger.error(f"Error: {e}")
       raise HTTPException(status_code=500, detail=str(e))
   
   # New
   try:
       result = await operation()
   except T2MBaseException:
       # Re-raise application exceptions as-is
       raise
   except Exception as e:
       # Convert to application exception with context
       raise SystemException(
           message=f"Unexpected error: {str(e)}",
           context=create_error_context(operation="operation_name")
       ) from e
   ```

## Testing Error Handling

### Unit Tests
```python
import pytest
from app.core.enhanced_exceptions import VideoNotFoundException

async def test_video_not_found_exception():
    with pytest.raises(VideoNotFoundException) as exc_info:
        raise VideoNotFoundException(video_id="test-id")
    
    assert exc_info.value.http_status_code == 404
    assert exc_info.value.error_code == "VIDEO_NOT_FOUND"
    assert "test-id" in exc_info.value.details["resource_id"]
```

### Integration Tests
```python
async def test_error_response_format(client):
    response = await client.get("/api/v1/videos/nonexistent")
    
    assert response.status_code == 404
    assert "correlation_id" in response.headers
    
    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "VIDEO_NOT_FOUND"
    assert "correlation_id" in data
```

### Circuit Breaker Tests
```python
async def test_circuit_breaker_opens_on_failures():
    cb = await circuit_breaker_registry.get_or_create("test_service")
    
    # Simulate failures
    for _ in range(5):
        with pytest.raises(ExternalServiceException):
            await cb.call(failing_operation)
    
    # Circuit should be open
    assert cb.state == CircuitState.OPEN
    
    # Next call should raise circuit breaker exception
    with pytest.raises(CircuitBreakerOpenException):
        await cb.call(operation)
```

This enhanced error handling system provides a robust foundation for enterprise-grade error management, monitoring, and resilience patterns in the T2M application.

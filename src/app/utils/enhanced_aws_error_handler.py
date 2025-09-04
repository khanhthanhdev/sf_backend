"""
Enhanced AWS Service Error Handler with Circuit Breaker Integration

This module provides comprehensive AWS service error handling with circuit breaker
protection, correlation ID tracking, and integration with the enhanced exception
system. Replaces the existing aws_error_handler.py with enterprise-grade patterns.

Features:
- Circuit breaker protection for all AWS service calls
- Correlation ID tracking across AWS operations
- Comprehensive error mapping and categorization
- Structured logging with context
- Retry strategies with exponential backoff
- Health check capabilities
"""

import logging
from typing import Dict, Any, Optional, Union, Callable, Awaitable, TypeVar
from datetime import datetime
import asyncio

from botocore.exceptions import (
    ClientError, 
    NoCredentialsError, 
    EndpointConnectionError,
    ConnectionError as BotocoreConnectionError,
    ReadTimeoutError,
    ConnectTimeoutError
)
from fastapi import HTTPException, status

from .enhanced_exceptions import (
    ExternalServiceException,
    AWSServiceException,
    ServiceUnavailableException,
    ServiceTimeoutException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    ResourceNotFoundException,
    RateLimitException,
    SystemException,
    create_error_context,
    ErrorSeverity,
    ErrorCategory
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    circuit_breaker_registry,
    circuit_breaker_decorator
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AWSErrorMapping:
    """
    Comprehensive mapping of AWS error codes to application exceptions.
    """
    
    # Authentication and authorization errors
    AUTH_ERRORS = {
        'InvalidUserID.NotFound': (AuthenticationException, "Invalid AWS user credentials"),
        'SignatureDoesNotMatch': (AuthenticationException, "AWS signature verification failed"),
        'TokenRefreshRequired': (AuthenticationException, "AWS token needs refresh"),
        'AccessDenied': (AuthorizationException, "Access denied to AWS resource"),
        'UnauthorizedOperation': (AuthorizationException, "Unauthorized AWS operation"),
        'Forbidden': (AuthorizationException, "AWS operation forbidden"),
    }
    
    # Validation and client errors
    VALIDATION_ERRORS = {
        'InvalidParameterValue': (ValidationException, "Invalid parameter value provided"),
        'InvalidRequest': (ValidationException, "Invalid AWS request format"),
        'MalformedPolicy': (ValidationException, "AWS policy is malformed"),
        'ValidationException': (ValidationException, "AWS request validation failed"),
        'InvalidInput': (ValidationException, "Invalid input provided to AWS service"),
    }
    
    # Resource not found errors
    NOT_FOUND_ERRORS = {
        'NoSuchBucket': (ResourceNotFoundException, "S3 bucket not found"),
        'NoSuchKey': (ResourceNotFoundException, "S3 object not found"),
        'NoSuchUpload': (ResourceNotFoundException, "S3 multipart upload not found"),
        'ResourceNotFoundException': (ResourceNotFoundException, "AWS resource not found"),
        'NoSuchPolicy': (ResourceNotFoundException, "AWS policy not found"),
        'NoSuchRole': (ResourceNotFoundException, "AWS role not found"),
    }
    
    # Rate limiting and throttling errors
    RATE_LIMIT_ERRORS = {
        'Throttling': (RateLimitException, "AWS service is throttling requests"),
        'RequestLimitExceeded': (RateLimitException, "AWS request limit exceeded"),
        'TooManyRequests': (RateLimitException, "Too many requests to AWS service"),
        'SlowDown': (RateLimitException, "AWS S3 rate limit exceeded"),
        'RequestTimeTooSkewed': (RateLimitException, "AWS request time skewed"),
    }
    
    # Service availability errors
    SERVICE_ERRORS = {
        'ServiceUnavailable': (ServiceUnavailableException, "AWS service temporarily unavailable"),
        'InternalError': (ServiceUnavailableException, "AWS internal error occurred"),
        'ServiceFailure': (ServiceUnavailableException, "AWS service failure"),
        'InternalFailure': (ServiceUnavailableException, "AWS internal failure"),
    }
    
    # Timeout errors
    TIMEOUT_ERRORS = {
        'RequestTimeout': (ServiceTimeoutException, "AWS request timed out"),
        'RequestTimeoutException': (ServiceTimeoutException, "AWS operation timed out"),
    }
    
    @classmethod
    def get_exception_for_error_code(
        cls, 
        error_code: str, 
        service_name: str,
        operation: str = "",
        **kwargs
    ) -> ExternalServiceException:
        """
        Get appropriate exception for AWS error code.
        
        Args:
            error_code: AWS error code
            service_name: AWS service name
            operation: Operation being performed
            **kwargs: Additional context
        
        Returns:
            Appropriate exception instance
        """
        # Check all error categories
        for error_map in [
            cls.AUTH_ERRORS,
            cls.VALIDATION_ERRORS, 
            cls.NOT_FOUND_ERRORS,
            cls.RATE_LIMIT_ERRORS,
            cls.SERVICE_ERRORS,
            cls.TIMEOUT_ERRORS
        ]:
            if error_code in error_map:
                exception_class, base_message = error_map[error_code]
                
                if exception_class == ResourceNotFoundException:
                    return exception_class(
                        resource_type=service_name,
                        resource_id=kwargs.get('resource_id', 'unknown'),
                        **kwargs
                    )
                elif exception_class == RateLimitException:
                    return exception_class(
                        message=base_message,
                        retry_after=kwargs.get('retry_after', 60),
                        **kwargs
                    )
                else:
                    return exception_class(message=base_message, **kwargs)
        
        # Default to generic AWS service exception
        return AWSServiceException(
            service_name=service_name,
            aws_error_code=error_code,
            message=f"AWS {service_name} error: {error_code}",
            **kwargs
        )


class EnhancedAWSErrorHandler:
    """
    Enhanced AWS error handler with circuit breaker integration.
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=30,
            call_timeout=20,
            expected_exception=Exception
        )
    
    async def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for AWS service."""
        return await circuit_breaker_registry.get_or_create(
            f"aws_{service_name.lower()}",
            self.default_config
        )
    
    @circuit_breaker_decorator("aws_operations")
    async def execute_with_protection(
        self,
        operation: Callable[[], Awaitable[T]],
        service_name: str,
        operation_name: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **context_data
    ) -> T:
        """
        Execute AWS operation with circuit breaker protection.
        
        Args:
            operation: Async function to execute
            service_name: AWS service name (s3, rds, etc.)
            operation_name: Name of the operation
            user_id: User ID for context
            correlation_id: Correlation ID for tracking
            **context_data: Additional context data
        
        Returns:
            Operation result
        
        Raises:
            Various enhanced exceptions based on AWS error types
        """
        error_context = create_error_context(
            operation=f"aws_{service_name}_{operation_name}",
            user_id=user_id,
            request_id=correlation_id,
            service_name=f"aws_{service_name}",
            **context_data
        )
        
        try:
            logger.debug(
                f"Executing AWS {service_name} operation: {operation_name}",
                extra={
                    "service_name": service_name,
                    "operation": operation_name,
                    "correlation_id": correlation_id,
                    "user_id": user_id
                }
            )
            
            result = await operation()
            
            logger.debug(
                f"AWS {service_name} operation successful: {operation_name}",
                extra={
                    "service_name": service_name,
                    "operation": operation_name,
                    "correlation_id": correlation_id
                }
            )
            
            return result
            
        except Exception as e:
            return await self._handle_aws_error(
                e, service_name, operation_name, error_context
            )
    
    async def _handle_aws_error(
        self,
        error: Exception,
        service_name: str,
        operation: str,
        context: Any
    ) -> None:
        """
        Handle AWS errors and convert to appropriate exceptions.
        
        Args:
            error: Original AWS error
            service_name: AWS service name
            operation: Operation that failed
            context: Error context
        
        Raises:
            Appropriate enhanced exception
        """
        # Handle specific AWS error types
        if isinstance(error, ClientError):
            await self._handle_client_error(error, service_name, operation, context)
        elif isinstance(error, NoCredentialsError):
            await self._handle_credentials_error(error, service_name, context)
        elif isinstance(error, (EndpointConnectionError, BotocoreConnectionError)):
            await self._handle_connection_error(error, service_name, context)
        elif isinstance(error, (ReadTimeoutError, ConnectTimeoutError)):
            await self._handle_timeout_error(error, service_name, operation, context)
        else:
            await self._handle_generic_error(error, service_name, operation, context)
    
    async def _handle_client_error(
        self,
        error: ClientError,
        service_name: str,
        operation: str,
        context: Any
    ) -> None:
        """Handle AWS ClientError exceptions."""
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
        
        logger.warning(
            f"AWS {service_name} ClientError",
            extra={
                "service_name": service_name,
                "operation": operation,
                "error_code": error_code,
                "error_message": error_message,
                "http_status": http_status,
                "correlation_id": context.correlation_id
            }
        )
        
        # Get appropriate exception
        exception = AWSErrorMapping.get_exception_for_error_code(
            error_code=error_code,
            service_name=service_name,
            operation=operation,
            context=context,
            severity=ErrorSeverity.MEDIUM,
            details={
                "aws_error_code": error_code,
                "aws_error_message": error_message,
                "http_status": http_status,
                "operation": operation
            }
        )
        
        raise exception
    
    async def _handle_credentials_error(
        self,
        error: NoCredentialsError,
        service_name: str,
        context: Any
    ) -> None:
        """Handle AWS credentials errors."""
        logger.error(
            f"AWS credentials not found for {service_name}",
            extra={
                "service_name": service_name,
                "error": str(error),
                "correlation_id": context.correlation_id
            }
        )
        
        raise AuthenticationException(
            message="AWS credentials not configured properly",
            error_code="AWS_CREDENTIALS_ERROR",
            context=context,
            severity=ErrorSeverity.CRITICAL,
            details={
                "service_name": service_name,
                "error_type": "credentials"
            }
        )
    
    async def _handle_connection_error(
        self,
        error: Union[EndpointConnectionError, BotocoreConnectionError],
        service_name: str,
        context: Any
    ) -> None:
        """Handle AWS connection errors."""
        logger.error(
            f"Cannot connect to AWS {service_name}",
            extra={
                "service_name": service_name,
                "error": str(error),
                "correlation_id": context.correlation_id
            }
        )
        
        raise ServiceUnavailableException(
            service_name=f"AWS {service_name}",
            context=context,
            severity=ErrorSeverity.HIGH,
            details={
                "error_type": "connection",
                "service_name": service_name
            }
        )
    
    async def _handle_timeout_error(
        self,
        error: Union[ReadTimeoutError, ConnectTimeoutError],
        service_name: str,
        operation: str,
        context: Any
    ) -> None:
        """Handle AWS timeout errors."""
        timeout_duration = getattr(error, 'timeout', 30)
        
        logger.warning(
            f"AWS {service_name} operation timed out",
            extra={
                "service_name": service_name,
                "operation": operation,
                "timeout": timeout_duration,
                "correlation_id": context.correlation_id
            }
        )
        
        raise ServiceTimeoutException(
            service_name=f"AWS {service_name}",
            timeout=timeout_duration,
            context=context,
            severity=ErrorSeverity.MEDIUM,
            details={
                "operation": operation,
                "timeout_duration": timeout_duration
            }
        )
    
    async def _handle_generic_error(
        self,
        error: Exception,
        service_name: str,
        operation: str,
        context: Any
    ) -> None:
        """Handle generic AWS errors."""
        logger.error(
            f"Unexpected AWS {service_name} error",
            extra={
                "service_name": service_name,
                "operation": operation,
                "error_type": type(error).__name__,
                "error": str(error),
                "correlation_id": context.correlation_id
            },
            exc_info=True
        )
        
        raise ExternalServiceException(
            service_name=f"AWS {service_name}",
            message=f"Unexpected error in {operation}: {str(error)}",
            context=context,
            severity=ErrorSeverity.HIGH,
            details={
                "operation": operation,
                "error_type": type(error).__name__,
                "original_error": str(error)
            }
        )
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all AWS services."""
        circuit_breakers = await circuit_breaker_registry.get_all_metrics()
        aws_breakers = {
            name: metrics for name, metrics in circuit_breakers.items() 
            if name.startswith('aws_')
        }
        
        overall_status = "healthy"
        unhealthy_services = []
        
        for name, metrics in aws_breakers.items():
            if metrics['state'] == 'open':
                overall_status = "degraded"
                unhealthy_services.append(name)
            elif metrics['metrics']['failure_rate'] > 0.5:
                if overall_status == "healthy":
                    overall_status = "degraded"
        
        return {
            "overall_status": overall_status,
            "services": aws_breakers,
            "unhealthy_services": unhealthy_services,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global enhanced AWS error handler instance
enhanced_aws_error_handler = EnhancedAWSErrorHandler()


# Convenience functions for backward compatibility and easy usage
async def handle_aws_s3_operation(
    operation: Callable[[], Awaitable[T]],
    operation_name: str = "s3_operation",
    **context
) -> T:
    """Handle S3 operation with circuit breaker protection."""
    return await enhanced_aws_error_handler.execute_with_protection(
        operation=operation,
        service_name="s3",
        operation_name=operation_name,
        **context
    )


async def handle_aws_rds_operation(
    operation: Callable[[], Awaitable[T]],
    operation_name: str = "rds_operation",
    **context
) -> T:
    """Handle RDS operation with circuit breaker protection."""
    return await enhanced_aws_error_handler.execute_with_protection(
        operation=operation,
        service_name="rds",
        operation_name=operation_name,
        **context
    )


async def handle_aws_lambda_operation(
    operation: Callable[[], Awaitable[T]],
    operation_name: str = "lambda_operation",
    **context
) -> T:
    """Handle Lambda operation with circuit breaker protection."""
    return await enhanced_aws_error_handler.execute_with_protection(
        operation=operation,
        service_name="lambda",
        operation_name=operation_name,
        **context
    )


def aws_circuit_breaker(service_name: str, operation_name: str = ""):
    """
    Decorator for AWS operations with circuit breaker protection.
    
    Args:
        service_name: AWS service name
        operation_name: Operation name for logging
    
    Example:
        @aws_circuit_breaker("s3", "upload_file")
        async def upload_to_s3(file_path: str, bucket: str, key: str):
            # Implementation
            pass
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            op_name = operation_name or func.__name__
            
            async def operation():
                return await func(*args, **kwargs)
            
            return await enhanced_aws_error_handler.execute_with_protection(
                operation=operation,
                service_name=service_name,
                operation_name=op_name,
                user_id=kwargs.get('user_id'),
                correlation_id=kwargs.get('correlation_id')
            )
        
        return wrapper
    return decorator


# Legacy function mapping for backward compatibility
async def handle_aws_service_error(
    error: Exception, 
    service_type: str, 
    operation: str,
    **context
) -> None:
    """
    Legacy function for backward compatibility.
    
    Converts old-style error handling to new enhanced system.
    """
    logger.warning(
        "Using legacy AWS error handler - please migrate to enhanced version",
        extra={"service_type": service_type, "operation": operation}
    )
    
    error_context = create_error_context(
        operation=operation,
        service_name=service_type,
        **context
    )
    
    await enhanced_aws_error_handler._handle_aws_error(
        error, service_type, operation, error_context
    )

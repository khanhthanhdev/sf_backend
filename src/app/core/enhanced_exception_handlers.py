"""
Enhanced Global Exception Handlers

This module provides comprehensive global exception handling for the FastAPI
application with correlation IDs, structured logging, and proper HTTP response
formatting. Integrates with the enhanced exception system and circuit breaker
patterns.

Features:
- Correlation ID tracking across requests
- Structured error logging with context
- Consistent error response formatting
- Security-aware error message sanitization
- Comprehensive error metrics and monitoring
"""

import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from .enhanced_exceptions import (
    T2MBaseException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
    BusinessLogicException,
    RateLimitException,
    ExternalServiceException,
    SystemException,
    CircuitBreakerOpenException,
    ErrorContext,
    ErrorSeverity,
    create_error_context
)
from .logger import get_logger, bind_correlation_id, clear_log_context
from .config import get_settings
from ..schemas.common import ErrorResponse, ErrorDetail, ErrorCode

logger = get_logger(__name__)
settings = get_settings()


class CorrelationIDMiddleware:
    """
    Middleware to inject correlation IDs into requests for error tracking.
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Try to use incoming header; otherwise generate a new correlation ID
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        incoming = headers.get(settings.correlation_id_header.lower()) or headers.get("x-correlation-id") or headers.get("x-request-id")
        correlation_id = incoming or str(uuid.uuid4())
        
        # Add to scope and state for access in handlers and request
        scope["correlation_id"] = correlation_id
        state = scope.setdefault("state", {})
        state["correlation_id"] = correlation_id

        # Bind correlation ID to structlog contextvars
        bind_correlation_id(correlation_id)
        
        # Add correlation ID to response headers
        async def send_with_correlation_id(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Primary correlation header from settings
                headers.append([settings.correlation_id_header.encode().lower(), correlation_id.encode()])
                # Backward-compatible X-Request-ID header
                headers.append([b"x-request-id", correlation_id.encode()])
                message["headers"] = headers
            await send(message)
        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            # Clear contextvars to avoid leaking between requests
            clear_log_context()


class EnhancedExceptionHandler:
    """
    Enhanced exception handler with comprehensive error processing.
    """
    
    def __init__(self, debug: bool = False, include_traceback: bool = False):
        self.debug = debug
        self.include_traceback = include_traceback
        self.error_metrics: Dict[str, int] = {}
    
    async def handle_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """
        Handle any exception and return appropriate JSON response.
        
        Args:
            request: FastAPI request object
            exc: Exception that occurred
        
        Returns:
            JSONResponse with structured error information
        """
        # Get correlation ID from request
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        
        # Create error context
        error_context = self._create_error_context(request, correlation_id)
        
        # Handle different exception types
        if isinstance(exc, T2MBaseException):
            return await self._handle_application_exception(exc, error_context)
        elif isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, error_context)
        elif isinstance(exc, RequestValidationError):
            return await self._handle_validation_error(exc, error_context)
        elif isinstance(exc, ResponseValidationError):
            return await self._handle_response_validation_error(exc, error_context)
        else:
            return await self._handle_unexpected_exception(exc, error_context)
    
    async def _handle_application_exception(
        self,
        exc: T2MBaseException,
        error_context: ErrorContext
    ) -> JSONResponse:
        """Handle application-specific exceptions."""
        # Update exception context with request context
        exc.context.correlation_id = error_context.correlation_id
        exc.context.request_id = error_context.request_id
        exc.context.user_id = error_context.user_id
        
        # Log error based on severity
        log_data = {
            "error_code": exc.error_code,
            "category": exc.category.value,
            "severity": exc.severity.value,
            "correlation_id": exc.context.correlation_id,
            "user_id": exc.context.user_id,
            "operation": exc.context.operation,
            "details": exc.details
        }
        
        if exc.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.error(f"Application error: {exc.message}", extra=log_data, exc_info=True)
        elif exc.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Application warning: {exc.message}", extra=log_data)
        else:
            logger.info(f"Application info: {exc.message}", extra=log_data)
        
        # Update metrics
        self._update_error_metrics(exc.error_code)
        
        # Create response
        error_response = ErrorResponse(
            message=exc.user_message,
            error=ErrorDetail(
                message=exc.user_message,
                code=exc.error_code,
                details=exc.details,
                timestamp=datetime.utcnow()
            ),
            request_id=exc.context.correlation_id
        )
        
        # Add retry information for rate limiting
        headers = {}
        if isinstance(exc, RateLimitException) and exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        
        return JSONResponse(
            status_code=exc.http_status_code,
            content=error_response.model_dump(),
            headers=headers
        )
    
    async def _handle_http_exception(
        self,
        exc: HTTPException,
        error_context: ErrorContext
    ) -> JSONResponse:
        """Handle FastAPI HTTPException."""
        logger.warning(
            f"HTTP exception: {exc.detail}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "correlation_id": error_context.correlation_id,
                "user_id": error_context.user_id
            }
        )
        
        # Map to standard error codes
        error_code_map = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE
        }
        
        error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        self._update_error_metrics(error_code)
        
        error_response = ErrorResponse(
            message=str(exc.detail),
            error=ErrorDetail(
                message=str(exc.detail),
                code=error_code,
                timestamp=datetime.utcnow()
            ),
            request_id=error_context.correlation_id
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=getattr(exc, "headers", None)
        )
    
    async def _handle_validation_error(
        self,
        exc: RequestValidationError,
        error_context: ErrorContext
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        # Extract field errors
        field_errors = []
        for error in exc.errors():
            field_path = " -> ".join(str(x) for x in error["loc"])
            field_errors.append({
                "field": field_path,
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        logger.warning(
            "Request validation error",
            extra={
                "field_errors": field_errors,
                "correlation_id": error_context.correlation_id,
                "user_id": error_context.user_id
            }
        )
        
        self._update_error_metrics(ErrorCode.VALIDATION_ERROR)
        
        error_response = ErrorResponse(
            message="Request validation failed",
            error=ErrorDetail(
                message="The request contains invalid data",
                code=ErrorCode.VALIDATION_ERROR,
                details={"field_errors": field_errors},
                timestamp=datetime.utcnow()
            ),
            request_id=error_context.correlation_id
        )
        
        return JSONResponse(
            status_code=422,
            content=error_response.model_dump()
        )
    
    async def _handle_response_validation_error(
        self,
        exc: ResponseValidationError,
        error_context: ErrorContext
    ) -> JSONResponse:
        """Handle response validation errors (should not happen in production)."""
        logger.error(
            "Response validation error - this indicates a bug in the API",
            extra={
                "error": str(exc),
                "correlation_id": error_context.correlation_id
            },
            exc_info=True
        )
        
        self._update_error_metrics(ErrorCode.INTERNAL_ERROR)
        
        # Don't expose internal details in production
        if self.debug:
            message = f"Response validation error: {str(exc)}"
        else:
            message = "Internal server error occurred"
        
        error_response = ErrorResponse(
            message=message,
            error=ErrorDetail(
                message=message,
                code=ErrorCode.INTERNAL_ERROR,
                timestamp=datetime.utcnow()
            ),
            request_id=error_context.correlation_id
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump()
        )
    
    async def _handle_unexpected_exception(
        self,
        exc: Exception,
        error_context: ErrorContext
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        exc_info = {
            "type": type(exc).__name__,
            "message": str(exc),
            "correlation_id": error_context.correlation_id,
            "user_id": error_context.user_id,
            "operation": error_context.operation
        }
        
        if self.include_traceback:
            exc_info["traceback"] = traceback.format_exc()
        
        logger.error(
            "Unexpected exception occurred",
            extra=exc_info,
            exc_info=True
        )
        
        self._update_error_metrics("UNEXPECTED_ERROR")
        
        # Sanitize error message for production
        if self.debug:
            message = f"Unexpected error: {str(exc)}"
            details = {"type": type(exc).__name__}
            if self.include_traceback:
                details["traceback"] = traceback.format_exc()
        else:
            message = "An unexpected error occurred. Please try again later."
            details = {}
        
        error_response = ErrorResponse(
            message=message,
            error=ErrorDetail(
                message=message,
                code=ErrorCode.INTERNAL_ERROR,
                details=details,
                timestamp=datetime.utcnow()
            ),
            request_id=error_context.correlation_id
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump()
        )
    
    def _create_error_context(
        self,
        request: Request,
        correlation_id: str
    ) -> ErrorContext:
        """Create error context from request."""
        # Extract user ID from request state if available
        user_id = getattr(request.state, "user_id", None)
        
        # Extract operation from route if available
        operation = None
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope["route"]
            if hasattr(route, "name"):
                operation = route.name
        
        return ErrorContext(
            correlation_id=correlation_id,
            operation=operation,
            user_id=user_id,
            request_id=correlation_id,
            additional_data={
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None
            }
        )
    
    def _update_error_metrics(self, error_code: str):
        """Update error metrics for monitoring."""
        self.error_metrics[error_code] = self.error_metrics.get(error_code, 0) + 1
    
    def get_error_metrics(self) -> Dict[str, int]:
        """Get current error metrics."""
        return self.error_metrics.copy()
    
    def reset_error_metrics(self):
        """Reset error metrics."""
        self.error_metrics.clear()


def setup_enhanced_exception_handlers(app: FastAPI, debug: bool = False):
    """
    Set up enhanced exception handlers for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        debug: Whether to include debug information in error responses
    """
    handler = EnhancedExceptionHandler(
        debug=debug,
        include_traceback=debug
    )
    
    # Correlation ID middleware is added in middleware setup to ensure ordering
    
    # Application exceptions
    @app.exception_handler(T2MBaseException)
    async def handle_application_exception(request: Request, exc: T2MBaseException):
        return await handler.handle_exception(request, exc)
    
    # HTTP exceptions
    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        return await handler.handle_exception(request, exc)
    
    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
        return await handler.handle_exception(request, exc)
    
    # Validation exceptions
    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        return await handler.handle_exception(request, exc)
    
    @app.exception_handler(ResponseValidationError)
    async def handle_response_validation_exception(request: Request, exc: ResponseValidationError):
        return await handler.handle_exception(request, exc)
    
    # Catch-all for unexpected exceptions
    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        return await handler.handle_exception(request, exc)
    
    # Add metrics endpoint for monitoring
    @app.get("/api/v1/system/error-metrics", include_in_schema=False)
    async def get_error_metrics():
        """Get current error metrics for monitoring."""
        return {
            "error_counts": handler.get_error_metrics(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    logger.info("Enhanced exception handlers configured")
    
    return handler


def create_application_exception(
    status_code: int,
    message: str,
    error_code: str = "",
    context: Optional[ErrorContext] = None,
    **kwargs
) -> T2MBaseException:
    """
    Utility function to create appropriate application exceptions.
    
    Args:
        status_code: HTTP status code
        message: Error message
        error_code: Machine-readable error code
        context: Error context
        **kwargs: Additional exception arguments
    
    Returns:
        Appropriate T2MBaseException subclass
    """
    kwargs.update({
        "error_code": error_code,
        "context": context
    })
    
    # Map status codes to exception types
    if status_code == 400:
        return ValidationException(message, **kwargs)
    elif status_code == 401:
        return AuthenticationException(message, **kwargs)
    elif status_code == 403:
        return AuthorizationException(message, **kwargs)
    elif status_code == 404:
        if 'resource_type' not in kwargs:
            kwargs['resource_type'] = "Resource"
            kwargs['resource_id'] = "unknown"
        return ResourceNotFoundException(kwargs['resource_type'], kwargs['resource_id'], **kwargs)
    elif status_code == 422:
        return BusinessLogicException(message, **kwargs)
    elif status_code == 429:
        return RateLimitException(message, **kwargs)
    elif status_code in [502, 503, 504]:
        service_name = kwargs.pop('service_name', 'External Service')
        return ExternalServiceException(service_name, message, **kwargs)
    else:
        return SystemException(message, **kwargs)

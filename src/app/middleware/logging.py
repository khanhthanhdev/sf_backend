"""
Request/response logging middleware with performance metrics.
Comprehensive logging for monitoring and debugging.
"""

import time
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses with performance metrics.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        skip_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1024,
    ):
        super().__init__(app)
        self.skip_paths = skip_paths or [
            "/health",
            "/favicon.ico",
            "/robots.txt",
            "/metrics",
        ]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response with comprehensive logging.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response with added headers
        """
        # Skip logging for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Start timing
        start_time = time.time()
        
        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        content_length = request.headers.get("content-length", "0")
        
        # Log request
        request_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "content_length": content_length,
            "headers": dict(request.headers) if settings.debug else {},
        }
        
        # Log request body if enabled and not too large
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    request_data["body"] = body.decode("utf-8", errors="ignore")
                else:
                    request_data["body"] = f"<body too large: {len(body)} bytes>"
            except Exception as e:
                request_data["body_error"] = str(e)
        
        logger.info("HTTP request started", **request_data)
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "HTTP request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract response information
        response_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "response_size": response.headers.get("content-length", "unknown"),
        }
        
        # Add performance metrics
        if duration_ms > 1000:  # Slow request threshold
            response_data["performance_warning"] = "slow_request"
        
        # Log response body if enabled (for debugging)
        if self.log_response_body and settings.debug:
            try:
                # Note: This is complex with streaming responses
                response_data["response_headers"] = dict(response.headers)
            except Exception as e:
                response_data["response_body_error"] = str(e)
        
        # Log response
        if response.status_code >= 400:
            logger.warning("HTTP request completed with error", **response_data)
        else:
            logger.info("HTTP request completed", **response_data)
        
        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(duration_ms, 2))
        
        # Add performance metrics headers
        if duration_ms > 5000:  # Very slow request
            response.headers["X-Performance-Warning"] = "very-slow"
        elif duration_ms > 1000:  # Slow request
            response.headers["X-Performance-Warning"] = "slow"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: HTTP request
            
        Returns:
            str: Client IP address
        """
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"


class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting and exposing performance metrics.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.total_duration = 0.0
        self.slow_requests = 0
        self.error_count = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Collect performance metrics for each request.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response with metrics headers
        """
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Update metrics
            duration = time.time() - start_time
            self.request_count += 1
            self.total_duration += duration
            
            if duration > 1.0:  # Slow request threshold
                self.slow_requests += 1
            
            if response.status_code >= 400:
                self.error_count += 1
            
            # Add metrics headers
            response.headers["X-Request-Count"] = str(self.request_count)
            response.headers["X-Average-Duration"] = str(
                round(self.total_duration / self.request_count * 1000, 2)
            )
            response.headers["X-Slow-Requests"] = str(self.slow_requests)
            response.headers["X-Error-Count"] = str(self.error_count)
            
            return response
            
        except Exception as e:
            self.error_count += 1
            raise


def setup_logging_middleware(app: ASGIApp, **kwargs) -> None:
    """
    Setup request logging middleware with default configuration.
    
    Args:
        app: FastAPI application instance
        **kwargs: Additional logging configuration options
    """
    logging_config = {
        "skip_paths": [
            "/health",
            "/favicon.ico", 
            "/robots.txt",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ],
        "log_request_body": settings.debug,
        "log_response_body": False,  # Usually too verbose
        "max_body_size": 1024,
    }
    
    # Override with any provided kwargs
    logging_config.update(kwargs)
    
    logger.info(
        "Setting up request logging middleware",
        skip_paths=logging_config["skip_paths"],
        log_request_body=logging_config["log_request_body"],
        debug_mode=settings.debug,
    )
    
    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware, **logging_config)
    
    # Add performance metrics middleware
    app.add_middleware(PerformanceMetricsMiddleware)
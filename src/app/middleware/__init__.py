"""
Custom middleware package.
Contains all custom middleware implementations for the FastAPI application.
"""

from .cors import EnhancedCORSMiddleware, setup_cors_middleware
from .logging import RequestLoggingMiddleware, PerformanceMetricsMiddleware, setup_logging_middleware
from .compression import EnhancedCompressionMiddleware, setup_compression_middleware
from .security import SecurityHeadersMiddleware, RateLimitHeadersMiddleware, setup_security_middleware
from .clerk_auth import ClerkAuthMiddleware
from .performance import setup_performance_middleware, setup_async_middleware, AsyncProcessingMiddleware

__all__ = [
    # CORS middleware
    "EnhancedCORSMiddleware",
    "setup_cors_middleware",
    
    # Logging middleware
    "RequestLoggingMiddleware", 
    "PerformanceMetricsMiddleware",
    "setup_logging_middleware",
    
    # Compression middleware
    "EnhancedCompressionMiddleware",
    "setup_compression_middleware",
    
    # Security middleware
    "SecurityHeadersMiddleware",
    "RateLimitHeadersMiddleware", 
    "setup_security_middleware",
    
    # Authentication middleware
    "ClerkAuthMiddleware",
    
    # Performance middleware
    "setup_performance_middleware",
    "setup_async_middleware",
    "AsyncProcessingMiddleware",
]
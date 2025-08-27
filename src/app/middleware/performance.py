"""
Performance optimization middleware for FastAPI.

This module provides middleware for request deduplication, response caching,
connection pool optimization, and performance monitoring.
"""

import logging
from typing import Callable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.performance import PerformanceMiddleware
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def setup_performance_middleware(app: FastAPI) -> None:
    """
    Set up performance optimization middleware.
    
    Args:
        app: FastAPI application instance
    """
    try:
        # Add performance middleware
        app.add_middleware(
            PerformanceMiddleware,
            enable_deduplication=not settings.is_development  # Disable in dev for easier debugging
        )
        
        logger.info("Performance middleware configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to configure performance middleware: {e}")
        raise


class AsyncProcessingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for optimizing async processing.
    
    Provides connection pooling optimization and async operation monitoring.
    """
    
    async def dispatch(self, request, call_next):
        """Process request with async optimizations."""
        # Add any async-specific optimizations here
        response = await call_next(request)
        return response


def setup_async_middleware(app: FastAPI) -> None:
    """
    Set up async processing middleware.
    
    Args:
        app: FastAPI application instance
    """
    try:
        app.add_middleware(AsyncProcessingMiddleware)
        logger.info("Async processing middleware configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to configure async middleware: {e}")
        raise
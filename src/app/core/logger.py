"""
Logging configuration using structlog for structured logging.
Supports both JSON and text formats with proper log levels and
automatic inclusion of correlation IDs via contextvars.
"""

import sys
import logging
from typing import Any, Dict
from pathlib import Path

import structlog
from structlog.types import FilteringBoundLogger
from structlog.contextvars import bind_contextvars, merge_contextvars, clear_contextvars

from .config import get_settings

settings = get_settings()


def configure_logging() -> FilteringBoundLogger:
    """
    Configure structured logging with structlog.
    
    Returns:
        FilteringBoundLogger: Configured logger instance
    """
    # Configure structlog processors
    base_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        merge_contextvars,  # include contextvars such as correlation_id
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Create renderer depending on environment
    if settings.is_development:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    processors = [*base_processors, renderer]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Bridge standard logging to use structlog's ProcessorFormatter so modules
    # using logging.getLogger(...) also emit structured logs consistently.
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=base_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Create and return logger
    logger = structlog.get_logger("fastapi_video_backend")
    
    # Log configuration
    logger.info(
        "Logging configured",
        log_level=settings.log_level,
        log_format=settings.log_format,
        environment=settings.environment,
    )
    
    return logger


def get_logger(name: str = None) -> FilteringBoundLogger:
    """
    Get a logger instance with optional name.
    
    Args:
        name: Logger name (optional)
        
    Returns:
        FilteringBoundLogger: Logger instance
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def bind_correlation_id(correlation_id: str) -> None:
    """Bind correlation ID into structlog contextvars for automatic inclusion."""
    try:
        bind_contextvars(correlation_id=correlation_id)
    except Exception:
        # Contextvars may not be available in some execution contexts
        pass


def clear_log_context() -> None:
    """Clear any bound context variables (e.g., at end of request)."""
    try:
        clear_contextvars()
    except Exception:
        pass


def log_request_info(
    logger: FilteringBoundLogger,
    method: str,
    url: str,
    user_id: str = None,
    **kwargs: Any
) -> None:
    """
    Log request information with consistent format.
    
    Args:
        logger: Logger instance
        method: HTTP method
        url: Request URL
        user_id: User ID (optional)
        **kwargs: Additional context
    """
    context = {
        "method": method,
        "url": str(url),
        **kwargs
    }
    
    if user_id:
        context["user_id"] = user_id
    
    logger.info("Request received", **context)


def log_response_info(
    logger: FilteringBoundLogger,
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    user_id: str = None,
    **kwargs: Any
) -> None:
    """
    Log response information with consistent format.
    
    Args:
        logger: Logger instance
        method: HTTP method
        url: Request URL
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: User ID (optional)
        **kwargs: Additional context
    """
    context = {
        "method": method,
        "url": str(url),
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        **kwargs
    }
    
    if user_id:
        context["user_id"] = user_id
    
    # Log level based on status code
    if status_code >= 500:
        logger.error("Request completed with server error", **context)
    elif status_code >= 400:
        logger.warning("Request completed with client error", **context)
    else:
        logger.info("Request completed successfully", **context)


def log_job_event(
    logger: FilteringBoundLogger,
    job_id: str,
    event: str,
    user_id: str = None,
    **kwargs: Any
) -> None:
    """
    Log job-related events with consistent format.
    
    Args:
        logger: Logger instance
        job_id: Job ID
        event: Event type (created, started, completed, failed, etc.)
        user_id: User ID (optional)
        **kwargs: Additional context
    """
    context = {
        "event": "job_event",
        "job_id": job_id,
        "job_event": event,
        **kwargs
    }
    
    if user_id:
        context["user_id"] = user_id
    
    logger.info(f"Job {event}", **context)


def log_error(
    logger: FilteringBoundLogger,
    error: Exception,
    context: Dict[str, Any] = None,
    user_id: str = None
) -> None:
    """
    Log error with consistent format and context.
    
    Args:
        logger: Logger instance
        error: Exception instance
        context: Additional context (optional)
        user_id: User ID (optional)
    """
    error_context = {
        "event": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {})
    }
    
    if user_id:
        error_context["user_id"] = user_id
    
    logger.error("Error occurred", extra=error_context, exc_info=True)


def log_security_event(
    logger: FilteringBoundLogger,
    event: str,
    user_id: str = None,
    ip_address: str = None,
    **kwargs: Any
) -> None:
    """
    Log security-related events.
    
    Args:
        logger: Logger instance
        event: Security event type
        user_id: User ID (optional)
        ip_address: Client IP address (optional)
        **kwargs: Additional context
    """
    context = {
        "event": "security_event",
        "security_event": event,
        **kwargs
    }
    
    if user_id:
        context["user_id"] = user_id
    if ip_address:
        context["ip_address"] = ip_address
    
    logger.warning(f"Security event: {event}", **context)


# Initialize logging on module import
logger = configure_logging()

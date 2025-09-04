"""
Configurable middleware pipeline setup for FastAPI.

Provides an ordered, configurable way to install cross-cutting concerns
like security, CORS, compression, correlation IDs, logging, and auth.
"""

from typing import Callable, Dict, List

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .logger import get_logger
from .enhanced_exception_handlers import CorrelationIDMiddleware
from ..middleware import (
    setup_cors_middleware,
    setup_logging_middleware,
    setup_compression_middleware,
    setup_security_middleware,
    setup_performance_middleware,
    setup_async_middleware,
    ClerkAuthMiddleware,
)


logger = get_logger(__name__)


def _install_trusted_host(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_trusted_hosts or settings.is_production:
        hosts = settings.get_trusted_hosts()
        logger.info("Adding TrustedHostMiddleware", allowed_hosts=hosts)
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)


def _install_security(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_security_middleware:
        setup_security_middleware(app)


def _install_cors(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_cors_middleware:
        setup_cors_middleware(app)


def _install_compression(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_compression_middleware:
        setup_compression_middleware(app)


def _install_performance(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_performance_middleware:
        setup_performance_middleware(app)


def _install_async(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_async_middleware:
        setup_async_middleware(app)


def _install_correlation(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_correlation_middleware:
        logger.info("Adding CorrelationIDMiddleware", header=settings.correlation_id_header)
        app.add_middleware(CorrelationIDMiddleware)


def _install_logging(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_logging_middleware:
        # Ensure correlation is added before logging
        setup_logging_middleware(app)


def _install_auth(app: FastAPI) -> None:
    settings = get_settings()
    if settings.enable_auth_middleware:
        exclude_paths = [
            "/",
            "/health",
            settings.docs_url,
            settings.redoc_url,
            settings.openapi_url,
            "/favicon.ico",
            "/.well-known/appspecific/com.chrome.devtools.json",
            "/api/docs",
            f"{settings.api_v1_prefix}/system/health",
            f"{settings.api_v1_prefix}/auth/health",
            f"{settings.api_v1_prefix}/auth/status",
        ]
        logger.info("Adding ClerkAuthMiddleware", exclude_paths=len(exclude_paths))
        app.add_middleware(ClerkAuthMiddleware, exclude_paths=exclude_paths)


MIDDLEWARE_REGISTRY: Dict[str, Callable[[FastAPI], None]] = {
    # Security and platform
    "trusted_host": _install_trusted_host,
    "security": _install_security,

    # Network boundaries and payload
    "cors": _install_cors,
    "compression": _install_compression,

    # Performance/instrumentation
    "performance": _install_performance,
    "async": _install_async,
    "correlation": _install_correlation,
    "logging": _install_logging,

    # Auth
    "auth": _install_auth,
}


def setup_middleware_pipeline(app: FastAPI, order: List[str] | None = None) -> None:
    """
    Configure the middleware pipeline using configured or provided order.
    Ensures correct ordering of cross-cutting concerns.
    """
    settings = get_settings()
    pipeline = order or settings.get_middleware_order()

    # Enforce critical ordering constraints by reordering if needed
    def ensure_order(items: List[str], must_precede: tuple[str, str]) -> List[str]:
        a, b = must_precede
        if a in items and b in items:
            ia, ib = items.index(a), items.index(b)
            if ia > ib:
                items.pop(ia)
                items.insert(items.index(b), a)
        return items

    # correlation must precede logging
    pipeline = ensure_order(pipeline, ("correlation", "logging"))
    # security and cors should happen before auth
    for pair in [("security", "auth"), ("cors", "auth")]:
        pipeline = ensure_order(pipeline, pair)

    logger.info("Configuring middleware pipeline", order=pipeline)

    for key in pipeline:
        install = MIDDLEWARE_REGISTRY.get(key)
        if not install:
            logger.warning("Unknown middleware key in pipeline; skipping", key=key)
            continue
        try:
            install(app)
        except Exception as e:
            logger.error("Failed to install middleware", key=key, error=str(e))
            if settings.is_production:
                raise


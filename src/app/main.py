"""
FastAPI application entry point.
Main application initialization with middleware, routers, and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.logger import get_logger
from .core.redis import redis_manager
from .core.auth import clerk_manager
from .core.openapi import OpenAPIConfig, setup_openapi_documentation
from .services.aws_service_factory import AWSServiceFactory
from src.config.aws_config import AWSConfigManager
from .middleware import (
    setup_cors_middleware,
    setup_logging_middleware,
    setup_compression_middleware,
    setup_security_middleware,
    setup_performance_middleware,
    setup_async_middleware,
    ClerkAuthMiddleware,
)

# Get settings and logger
settings = get_settings()
logger = get_logger(__name__)

# Global AWS service factory instance
aws_service_factory: Optional[AWSServiceFactory] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    global aws_service_factory
    
    # Startup
    logger.info(
        "Starting FastAPI Video Backend",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug,
    )
    
    # Initialize AWS Service Factory
    try:
        logger.info("Initializing AWS Service Factory...")
        aws_config = AWSConfigManager.load_config(settings.environment)
        aws_service_factory = AWSServiceFactory(aws_config)
        
        # Initialize the factory
        initialization_success = await aws_service_factory.initialize()
        if not initialization_success:
            raise RuntimeError("AWS Service Factory initialization failed")
        
        logger.info("AWS Service Factory initialized successfully")
        
        # Store factory in app state for access in dependencies
        app.state.aws_service_factory = aws_service_factory
        
    except Exception as e:
        logger.error("Failed to initialize AWS Service Factory", extra={"error": str(e)}, exc_info=True)
        if settings.is_production:
            raise
        else:
            logger.warning("Continuing without AWS services in development mode")
            aws_service_factory = None
    
    # Initialize Redis connection pool (optional for caching)
    try:
        await redis_manager.initialize()
        logger.info("Redis connection initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Redis", extra={"error": str(e)}, exc_info=True)
        # Don't fail startup for Redis issues in development
        if settings.is_production:
            raise
    
    # Initialize Clerk authentication
    try:
        clerk_manager.initialize()
        logger.info("Clerk authentication initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Clerk", extra={"error": str(e)}, exc_info=True)
        # Don't fail startup for Clerk issues in development
        if settings.is_production:
            raise
    
    logger.info("Application startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Close AWS Service Factory
    if aws_service_factory:
        try:
            await aws_service_factory.close()
            logger.info("AWS Service Factory closed")
        except Exception as e:
            logger.error("Error closing AWS Service Factory", extra={"error": str(e)}, exc_info=True)
    
    # Close Redis connections
    try:
        await redis_manager.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error("Error closing Redis connections", extra={"error": str(e)}, exc_info=True)
    
    logger.info("Application shutdown completed")


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        FastAPI: Configured application instance
    """
    # Create FastAPI app with enhanced OpenAPI configuration
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=OpenAPIConfig.get_api_description(),
        summary="FastAPI backend for multi-agent video generation system",
        terms_of_service="https://example.com/terms/",
        contact={
            "name": "API Support",
            "url": "https://example.com/contact/",
            "email": "support@example.com",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        docs_url=settings.docs_url if not settings.is_production else None,
        redoc_url=settings.redoc_url if not settings.is_production else None,
        openapi_url=settings.openapi_url if not settings.is_production else None,
        openapi_tags=OpenAPIConfig.get_openapi_tags(),
        servers=OpenAPIConfig.get_api_servers(),
        lifespan=lifespan,
        # Enhanced Swagger UI configuration
        swagger_ui_parameters={
            "syntaxHighlight.activate": True,
            "syntaxHighlight.theme": "agate",
            "syntaxHighlight.maxLines": 100,
            "syntaxHighlight.wrapLines": True,
            "displayRequestDuration": True,
            "docExpansion": "list",  # Show operations expanded
            "deepLinking": True,
            "displayOperationId": False,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "defaultModelRendering": "example",
            "showExtensions": True,
            "showCommonExtensions": True,
            "tryItOutEnabled": True,
        },
    )
    
    # Add middleware
    setup_middleware(app)
    
    # Add routers
    setup_routers(app)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI) -> None:
    """
    Configure application middleware.
    
    Args:
        app: FastAPI application instance
    """
    # Trusted host middleware (security) - should be first
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # TODO: Configure with actual allowed hosts
        )
    
    # Security headers middleware - early in the chain
    setup_security_middleware(app)
    
    # CORS middleware - before authentication
    setup_cors_middleware(app)
    
    # Response compression middleware
    setup_compression_middleware(app)
    
    # Performance optimization middleware
    setup_performance_middleware(app)
    setup_async_middleware(app)
    
    # Request logging middleware with performance metrics
    setup_logging_middleware(app)
    
    # Clerk authentication middleware - after logging but before business logic
    app.add_middleware(
        ClerkAuthMiddleware,
        exclude_paths=[
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/.well-known/appspecific/com.chrome.devtools.json",  # Chrome DevTools
            "/api/docs",  # Alternative docs path
            "/api/v1/system/health",
            "/api/v1/auth/health",
            "/api/v1/auth/status"  # This endpoint handles optional auth internally
        ]
    )


def setup_routers(app: FastAPI) -> None:
    """
    Configure application routers.
    
    Args:
        app: FastAPI application instance
    """
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }
    
    # AWS services health check endpoint
    @app.get("/health/aws")
    async def aws_health_check():
        """AWS services health check endpoint."""
        if not aws_service_factory:
            return {
                "status": "unavailable",
                "message": "AWS Service Factory not initialized",
                "services": {}
            }
        
        try:
            health_status = await aws_service_factory.health_check()
            return health_status
        except Exception as e:
            logger.error("AWS health check failed", extra={"error": str(e)}, exc_info=True)
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "services": {}
            }
    
    # Detailed health check endpoint
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check including all services."""
        health_info = {
            "app": {
                "status": "healthy",
                "name": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            },
            "redis": {"status": "unknown"},
            "aws": {"status": "unknown"}
        }
        
        # Check Redis health
        try:
            if redis_manager and redis_manager.redis_client:
                await redis_manager.redis_client.ping()
                health_info["redis"]["status"] = "healthy"
            else:
                health_info["redis"]["status"] = "not_initialized"
        except Exception as e:
            health_info["redis"]["status"] = "unhealthy"
            health_info["redis"]["error"] = str(e)
        
        # Check AWS health
        if aws_service_factory:
            try:
                aws_health = await aws_service_factory.health_check()
                health_info["aws"] = aws_health
            except Exception as e:
                health_info["aws"]["status"] = "error"
                health_info["aws"]["error"] = str(e)
        else:
            health_info["aws"]["status"] = "not_initialized"
        
        # Determine overall status
        overall_status = "healthy"
        if health_info["aws"]["overall_status"] != "healthy":
            overall_status = "degraded"
        if health_info["redis"]["status"] == "unhealthy":
            overall_status = "degraded"
        
        return {
            "overall_status": overall_status,
            "timestamp": None,  # Will be set by health check
            **health_info
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with basic information."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs_url": settings.docs_url,
            "health_url": "/health",
        }
    
    # Test endpoint for Swagger UI
    @app.get("/test-swagger", tags=["testing"])
    async def test_swagger_ui():
        """Test endpoint to verify Swagger UI functionality."""
        return {
            "message": "Swagger UI is working correctly!",
            "timestamp": "2024-01-15T10:30:00Z",
            "features": [
                "Interactive API documentation",
                "Request/response examples",
                "Authentication testing",
                "Schema validation"
            ]
        }
    
    # Add API v1 routers
    from .api.v1 import auth, videos, jobs, system, files
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(videos.router, prefix=settings.api_v1_prefix, tags=["videos"])
    app.include_router(jobs.router, prefix=settings.api_v1_prefix, tags=["jobs"])
    app.include_router(system.router, prefix=settings.api_v1_prefix, tags=["system"])
    app.include_router(files.router, prefix=settings.api_v1_prefix, tags=["files"])


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configure global exception handlers.
    
    Args:
        app: FastAPI application instance
    """
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(
            "Unhandled exception",
            extra={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "url": str(request.url),
                "method": request.method,
            },
            exc_info=True,
        )
        
        # Don't expose internal errors in production
        if settings.is_production:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal server error",
                        "error_code": "INTERNAL_ERROR",
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": str(exc),
                        "error_code": "INTERNAL_ERROR",
                        "type": type(exc).__name__,
                    }
                }
            )


# Create application instance
app = create_application()

# Set up comprehensive OpenAPI documentation
setup_openapi_documentation(app)


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "Starting development server",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
    
    uvicorn.run(
        "src.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )


def run_dev():
    """Entry point for development server."""
    import uvicorn
    
    logger.info(
        "Starting development server via entry point",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
    
    uvicorn.run(
        "src.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )


def run_prod():
    """Entry point for production server."""
    import uvicorn
    
    logger.info(
        "Starting production server via entry point",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
    
    uvicorn.run(
        "src.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
        workers=1,  # Single worker for uvicorn; use gunicorn for multiple workers
    )
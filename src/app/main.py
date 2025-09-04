"""
FastAPI application entry point.
Main application initialization with dependency injection, service factory,
and comprehensive lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Dict, Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.logger import get_logger
from .core.auth import clerk_manager
from .core.openapi import OpenAPIConfig, setup_openapi_documentation
from .core.service_factory import (
    ApplicationServiceFactory, 
    initialize_service_factory, 
    cleanup_service_factory,
    get_service_factory
)
from .core.container import setup_service_container, initialize_container, cleanup_container
from src.config.aws_config import AWSConfigManager
from .core.middleware_pipeline import setup_middleware_pipeline

# Get settings and logger
settings = get_settings()
logger = get_logger(__name__)

# Global service factory instance (managed via DI container)
service_factory: Optional[ApplicationServiceFactory] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager with dependency injection and service factory.
    Handles startup and shutdown events with proper service lifecycle management.
    """
    global service_factory
    
    # Startup
    logger.info(
        "Starting FastAPI Video Backend with DI Container",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug,
    )
    
    try:
        # Step 1: Setup dependency injection container
        logger.info("Setting up dependency injection container")
        container = setup_service_container()
        
        # Step 2: Initialize service factory with AWS configuration
        logger.info("Initializing service factory")
        aws_config = None
        try:
            aws_config = AWSConfigManager.load_config(settings.environment)
        except Exception as e:
            logger.warning(f"AWS configuration not available: {e}")
            if settings.is_production:
                logger.error("AWS configuration required in production")
                raise
        
        service_factory = await initialize_service_factory(
            aws_config=aws_config,
            container=container
        )
        
        # Step 3: Store service factory in app state for dependencies
        app.state.service_factory = service_factory
        app.state.container = container
        
        # For backward compatibility, also store AWS service factory
        aws_service_factory = None
        if service_factory.aws_service_factory:
            aws_service_factory = service_factory.aws_service_factory
            app.state.aws_service_factory = aws_service_factory
        
        # Step 4: Initialize Clerk authentication
        try:
            clerk_manager.initialize()
            logger.info("Clerk authentication initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Clerk", extra={"error": str(e)}, exc_info=True)
            if settings.is_production:
                raise
        
        logger.info("Application startup completed successfully")
        
        yield
        
        # Shutdown
        logger.info("Shutting down application")
        
        try:
            # Step 1: Cleanup service factory (includes AWS services)
            if service_factory:
                logger.info("Cleaning up service factory")
                await service_factory.cleanup()
            
            # Step 2: Cleanup DI container
            logger.info("Cleaning up dependency injection container") 
            await cleanup_container()
            
            # Step 3: Final cleanup
            await cleanup_service_factory()
            
            logger.info("Application shutdown completed successfully")
            
        except Exception as e:
            logger.error("Error during application shutdown", extra={"error": str(e)}, exc_info=True)
    
    except Exception as e:
        logger.error("Failed to start application", extra={"error": str(e)}, exc_info=True)
        
        # Attempt emergency cleanup
        try:
            if service_factory:
                await service_factory.cleanup()
            await cleanup_container()
            await cleanup_service_factory()
        except Exception as cleanup_error:
            logger.error("Error during emergency cleanup", extra={"error": str(cleanup_error)})
        
        raise


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
    # Delegate to the centralized, configurable middleware pipeline
    setup_middleware_pipeline(app)


def setup_routers(app: FastAPI) -> None:
    """
    Configure application routers.
    
    Args:
        app: FastAPI application instance
    """
    # Health check endpoint
    @app.get("/health")
    async def health_check(request: Request):
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }
    
    # Service factory health check endpoint
    @app.get("/health/services")
    async def services_health_check(request: Request):
        """Service factory and DI container health check endpoint."""
        service_factory = getattr(request.app.state, 'service_factory', None)
        
        if not service_factory:
            return {
                "status": "unavailable",
                "message": "Service factory not initialized",
                "services": {}
            }
        
        try:
            health_status = service_factory.get_health_status()
            return health_status
        except Exception as e:
            logger.error("Service factory health check failed", extra={"error": str(e)}, exc_info=True)
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "services": {}
            }
    
    # AWS services health check endpoint (for backward compatibility)
    @app.get("/health/aws")
    async def aws_health_check(request: Request):
        """AWS services health check endpoint."""
        service_factory = getattr(request.app.state, 'service_factory', None)
        aws_service_factory = getattr(request.app.state, 'aws_service_factory', None)
        
        if not service_factory or not aws_service_factory:
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
    async def detailed_health_check(request: Request):
        """Detailed health check including all services and DI container."""
        service_factory = getattr(request.app.state, 'service_factory', None)
        aws_service_factory = getattr(request.app.state, 'aws_service_factory', None)
        container = getattr(request.app.state, 'container', None)
        
        health_info = {
            "app": {
                "status": "healthy",
                "name": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            },
            "dependency_injection": {"status": "unknown"},
            "service_factory": {"status": "unknown"},
            "aws": {"status": "unknown"}
        }
        
        # Check DI container health
        if container:
            try:
                container_health = container.get_health_status()
                health_info["dependency_injection"] = container_health
            except Exception as e:
                health_info["dependency_injection"] = {"status": "error", "error": str(e)}
        else:
            health_info["dependency_injection"] = {"status": "not_initialized"}
        
        # Check service factory health
        if service_factory:
            try:
                factory_health = service_factory.get_health_status()
                health_info["service_factory"] = factory_health
            except Exception as e:
                health_info["service_factory"] = {"status": "error", "error": str(e)}
        else:
            health_info["service_factory"] = {"status": "not_initialized"}
        
        # Check AWS health
        if aws_service_factory:
            try:
                aws_health = await aws_service_factory.health_check()
                health_info["aws"] = aws_health
            except Exception as e:
                health_info["aws"] = {"status": "error", "error": str(e)}
        else:
            health_info["aws"] = {"status": "not_available"}
        
        # Determine overall status
        overall_status = "healthy"
        
        # Check critical components
        if (health_info["dependency_injection"].get("health") != "healthy" or
            health_info["service_factory"].get("health") != "healthy"):
            overall_status = "degraded"
        
        # AWS is optional, so only degrade if it was expected to be available
        if (aws_service_factory and 
            health_info["aws"].get("overall_status") != "healthy"):
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
    Configure enhanced global exception handlers with correlation IDs,
    structured logging, and comprehensive error response formatting.
    
    Args:
        app: FastAPI application instance
    """
    from .core.enhanced_exception_handlers import setup_enhanced_exception_handlers
    
    # Set up enhanced exception handlers with debug mode based on settings
    handler = setup_enhanced_exception_handlers(
        app=app,
        debug=settings.debug
    )
    
    logger.info(
        "Enhanced exception handlers configured",
        extra={
            "debug_mode": settings.debug,
            "include_traceback": settings.debug,
            "environment": settings.environment
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

"""
Enhanced FastAPI dependencies using dependency injection container and service factory.

This module provides FastAPI dependencies that integrate with the DI container
and service factory for consistent service resolution and lifecycle management.
"""

from typing import Optional, Type, TypeVar
from fastapi import Depends, Request, HTTPException, status
import logging

from ..core.service_factory import ApplicationServiceFactory
from ..core.container import DependencyContainer
from ..services.aws_service_factory import AWSServiceFactory
from ..database.connection import RDSConnectionManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


def get_service_factory(request: Request) -> ApplicationServiceFactory:
    """
    FastAPI dependency to get the service factory instance.
    
    Args:
        request: FastAPI request object
        
    Returns:
        ApplicationServiceFactory instance
        
    Raises:
        HTTPException: If service factory not available
    """
    service_factory = getattr(request.app.state, 'service_factory', None)
    if not service_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service factory not available"
        )
    
    if not service_factory.is_initialized():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service factory not initialized"
        )
    
    return service_factory


def get_dependency_container(request: Request) -> DependencyContainer:
    """
    FastAPI dependency to get the DI container instance.
    
    Args:
        request: FastAPI request object
        
    Returns:
        DependencyContainer instance
        
    Raises:
        HTTPException: If container not available
    """
    container = getattr(request.app.state, 'container', None)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependency injection container not available"
        )
    
    return container


def get_aws_service_factory(request: Request) -> Optional[AWSServiceFactory]:
    """
    FastAPI dependency to get AWS Service Factory instance.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AWSServiceFactory instance or None if not available
    """
    return getattr(request.app.state, 'aws_service_factory', None)


def get_rds_connection_manager(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
) -> Optional[RDSConnectionManager]:
    """
    FastAPI dependency to get RDS connection manager.
    
    Args:
        service_factory: Service factory dependency
        
    Returns:
        RDSConnectionManager instance or None if not available
    """
    try:
        return service_factory.get_service(RDSConnectionManager)
    except (ValueError, RuntimeError):
        # RDS connection manager may not be available in development
        return None


def create_service_dependency(service_type: Type[T]):
    """
    Create a FastAPI dependency function for a specific service type.
    
    Args:
        service_type: The service type to resolve
        
    Returns:
        FastAPI dependency function
    """
    def get_service(
        service_factory: ApplicationServiceFactory = Depends(get_service_factory)
    ) -> T:
        try:
            return service_factory.get_service(service_type)
        except ValueError as e:
            logger.error(f"Failed to resolve service {service_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service {service_type.__name__} not available"
            )
        except RuntimeError as e:
            logger.error(f"Service factory error for {service_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service factory not ready"
            )
    
    return get_service


def create_async_service_dependency(service_type: Type[T]):
    """
    Create an async FastAPI dependency function for a specific service type.
    
    Args:
        service_type: The service type to resolve
        
    Returns:
        Async FastAPI dependency function
    """
    async def get_service_async(
        service_factory: ApplicationServiceFactory = Depends(get_service_factory)
    ) -> T:
        try:
            return await service_factory.get_service_async(service_type)
        except ValueError as e:
            logger.error(f"Failed to resolve async service {service_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service {service_type.__name__} not available"
            )
        except RuntimeError as e:
            logger.error(f"Service factory error for {service_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service factory not ready"
            )
    
    return get_service_async


# Specific service dependencies for common services
def get_user_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get UserService instance from the service factory."""
    from ...services.user_service import UserService
    return create_service_dependency(UserService)(service_factory)


def get_job_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get JobService instance from the service factory."""
    from ...services.job_service import JobService
    return create_service_dependency(JobService)(service_factory)


def get_file_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get FileService instance from the service factory.""" 
    from ...services.file_service import FileService
    return create_service_dependency(FileService)(service_factory)


def get_queue_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get QueueService instance from the service factory."""
    from ...services.queue_service import QueueService
    return create_service_dependency(QueueService)(service_factory)


# AWS service dependencies (with graceful fallback)
def get_aws_video_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get AWSVideoService instance from the service factory."""
    from ...services.aws_video_service import AWSVideoService
    try:
        return service_factory.get_service(AWSVideoService)
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS Video Service not available"
        )


def get_aws_file_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get AWSS3FileService instance from the service factory."""
    from ...services.aws_s3_file_service import AWSS3FileService
    try:
        return service_factory.get_service(AWSS3FileService)
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS S3 File Service not available"
        )


def get_aws_job_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get AWSJobService instance from the service factory."""
    from ...services.aws_job_service import AWSJobService
    try:
        return service_factory.get_service(AWSJobService)
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS Job Service not available"
        )


def get_aws_user_service(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory)
):
    """Get AWSUserService instance from the service factory."""
    from ...services.aws_user_service import AWSUserService
    try:
        return service_factory.get_service(AWSUserService)
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS User Service not available"
        )


# Health check dependency
def get_health_check_info(
    service_factory: ApplicationServiceFactory = Depends(get_service_factory),
    container: DependencyContainer = Depends(get_dependency_container)
) -> dict:
    """
    Get comprehensive health check information.
    
    Returns:
        Dictionary with health status of all components
    """
    health_info = {
        "service_factory": service_factory.get_health_status(),
        "container": container.get_health_status(),
        "services": {}
    }
    
    # Try to get status of registered services
    try:
        registration_info = container.get_registration_info()
        health_info["services"] = {
            name: {
                "registered": True,
                "initialized": info.get("initialized", False),
                "lifetime": info.get("lifetime", "unknown")
            }
            for name, info in registration_info.items()
        }
    except Exception as e:
        health_info["services"] = {"error": str(e)}
    
    return health_info

"""
Service registration module for dependency injection container.

This module handles the registration of all services with their
appropriate lifetimes and dependencies, integrating with existing
AWS services and infrastructure.
"""

import logging
from typing import Optional

from .dependency_container import DependencyContainer, get_container

logger = logging.getLogger(__name__)


def register_core_infrastructure_services(container: DependencyContainer) -> None:
    """Register core infrastructure services."""
    logger.info("Registering core infrastructure services")
    
    # These will be registered by the ApplicationServiceFactory
    # as they require complex initialization with database connections, etc.
    pass


def register_existing_application_services(container: DependencyContainer) -> None:
    """Register existing application services that are already implemented."""
    logger.info("Registering existing application services")
    
    # Import existing services
    from ...services.user_service import UserService
    from ...services.job_service import JobService
    from ...services.file_service import FileService
    from ...services.queue_service import QueueService
    from ...services.video_service import VideoService
    
    # These services will be registered as factories since they need
    # database connections and other dependencies
    # The actual registration happens in ApplicationServiceFactory
    logger.debug("Existing services will be registered via ApplicationServiceFactory")


def register_aws_integrated_services(container: DependencyContainer) -> None:
    """Register AWS-integrated services."""
    logger.info("Registering AWS-integrated services")
    
    # AWS services will be registered by ApplicationServiceFactory
    # since they depend on the AWS service factory initialization
    logger.debug("AWS services will be registered via ApplicationServiceFactory")


def register_middleware_and_utilities(container: DependencyContainer) -> None:
    """Register middleware and utility services."""
    logger.info("Registering middleware and utility services")
    
    # Import utility services
    from ...core.logger import get_logger
    from ...core.config import get_settings
    
    # Register configuration as singleton instance
    settings = get_settings()
    container.register_instance(type(settings), settings)
    
    # Logger is typically not registered in DI container as it's used statically
    logger.debug("Configuration services registered")


def setup_service_container(container: Optional[DependencyContainer] = None) -> DependencyContainer:
    """
    Set up the complete service container with all registrations.
    
    Args:
        container: Optional container to use, creates new one if None
        
    Returns:
        Configured dependency container
    """
    if container is None:
        container = get_container()
    
    logger.info("Setting up service container")
    
    try:
        # Register services in dependency order
        register_middleware_and_utilities(container)
        register_core_infrastructure_services(container)
        register_existing_application_services(container)
        register_aws_integrated_services(container)
        
        logger.info("Service container setup completed")
        
        # Log registration summary
        registration_info = container.get_registration_info()
        logger.info(f"Registered {len(registration_info)} services")
        for service_name, info in registration_info.items():
            logger.debug(f"  {service_name}: {info['implementation']} ({info['lifetime']})")
        
        return container
        
    except Exception as e:
        logger.error(f"Failed to setup service container: {e}")
        raise


def create_test_container() -> DependencyContainer:
    """
    Create a container configured for testing.
    
    This can be used to register mock implementations
    for testing purposes.
    """
    container = DependencyContainer()
    
    logger.info("Creating test container")
    
    # Register test/mock implementations
    # Example:
    # from ...tests.mocks import MockVideoService, MockJobService
    # container.register_singleton(VideoService, MockVideoService)
    # container.register_singleton(JobService, MockJobService)
    
    return container


# Convenience functions for common service resolution
def get_video_generation_use_case():
    """Get video generation use case from container."""
    container = get_container()
    # This will be implemented when the use case classes are available
    # return container.resolve(IVideoGenerationUseCase)
    logger.warning("Video generation use case not yet implemented")
    return None


def get_job_management_use_case():
    """Get job management use case from container."""
    container = get_container()
    # For now, return the existing JobService
    from ...services.job_service import JobService
    try:
        return container.resolve(JobService)
    except ValueError:
        logger.warning("JobService not registered in container")
        return None


def get_file_management_use_case():
    """Get file management use case from container."""
    container = get_container()
    # For now, return the existing FileService
    from ...services.file_service import FileService
    try:
        return container.resolve(FileService)
    except ValueError:
        logger.warning("FileService not registered in container")
        return None


def get_user_management_use_case():
    """Get user management use case from container."""
    container = get_container()
    # For now, return the existing UserService
    from ...services.user_service import UserService
    try:
        return container.resolve(UserService)
    except ValueError:
        logger.warning("UserService not registered in container")
        return None

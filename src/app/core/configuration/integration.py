"""
Integration between configuration management and dependency injection.

This module provides integration points between the new configuration
system and the existing dependency injection container.
"""

from typing import Any, Dict, Optional
import logging

from app.services.dependency_injection import DIContainer, ServiceLifetime
from app.interfaces.base import ServiceResult, IService

from .factory import ConfigurationFactory, get_configuration
from .application import ApplicationConfig
from .base import Environment


logger = logging.getLogger(__name__)


# Global configuration instance for synchronous access
_config_instance: Optional[ApplicationConfig] = None


def get_configuration_sync() -> ApplicationConfig:
    """
    Get configuration synchronously.
    
    Returns cached configuration instance or creates new one.
    This is useful for FastAPI dependencies and other synchronous contexts.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ApplicationConfig()
    return _config_instance


def set_configuration_instance(config: ApplicationConfig) -> None:
    """Set the global configuration instance."""
    global _config_instance
    _config_instance = config


class ConfigurationService(IService):
    """Service wrapper for configuration management."""
    
    def __init__(self, config: ApplicationConfig):
        self.config = config
    
    @property
    def service_name(self) -> str:
        """Get service name."""
        return "ConfigurationService"
    
    async def initialize(self) -> ServiceResult[bool]:
        """Initialize configuration service."""
        try:
            # Validate configuration
            logger.info(f"Configuration service initialized for environment: {self.config.environment}")
            return ServiceResult.success(True)
        except Exception as e:
            logger.error(f"Failed to initialize configuration service: {e}")
            return ServiceResult.error(f"Configuration initialization failed: {e}")
    
    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Perform health check."""
        try:
            # Handle environment value properly
            env_value = self.config.environment
            if hasattr(env_value, 'value'):
                env_value = env_value.value
            
            health_info = {
                "status": "healthy",
                "environment": env_value,
                "debug_mode": self.config.debug,
                "features_enabled": list(self.config.features_enabled),
            }
            
            # Check database configuration
            if self.config.database.host:
                health_info["database_configured"] = True
            
            # Check AWS configuration
            if self.config.aws.access_key_id:
                health_info["aws_configured"] = True
            
            return ServiceResult.success(health_info)
        except Exception as e:
            logger.error(f"Configuration health check failed: {e}")
            return ServiceResult.error(f"Health check failed: {e}")
    
    async def cleanup(self) -> ServiceResult[bool]:
        """Cleanup configuration service."""
        logger.info("Configuration service cleanup completed")
        return ServiceResult.success(True)


def register_configuration_services(
    container: DIContainer,
    environment: Optional[Environment] = None,
    config_overrides: Optional[Dict[str, Any]] = None
) -> DIContainer:
    """
    Register configuration services with the dependency injection container.
    
    Args:
        container: DI container to register services with
        environment: Target environment (auto-detected if None)
        config_overrides: Configuration overrides
        
    Returns:
        Updated DI container
    """
    logger.info("Registering configuration services with DI container")
    
    # Register configuration factory
    if environment == Environment.PRODUCTION:
        factory = ConfigurationFactory.create_production_factory()
    elif environment == Environment.TESTING:
        factory = ConfigurationFactory.create_testing_factory()
    else:
        factory = ConfigurationFactory.create_development_factory()
    
    container.register_singleton(
        ConfigurationFactory,
        factory=lambda: factory
    )
    
    # Register configuration instance
    async def create_config() -> ApplicationConfig:
        """Factory function to create configuration."""
        return await factory.create_configuration(**(config_overrides or {}))
    
    # Note: This is a simplified registration - in practice, you'd want to
    # handle the async nature properly in your DI container
    container.register_singleton(
        ApplicationConfig,
        factory=lambda: get_configuration_sync()
    )
    
    # Register configuration service
    container.register_singleton(
        ConfigurationService,
        factory=lambda: ConfigurationService(get_configuration_sync())
    )
    
    # Register individual configuration sections for convenience
    def get_database_config() -> Any:
        return get_configuration_sync().database
    
    def get_aws_config() -> Any:
        return get_configuration_sync().aws
    
    def get_security_config() -> Any:
        return get_configuration_sync().security
    
    def get_logging_config() -> Any:
        return get_configuration_sync().logging
    
    container.register_singleton("DatabaseConfig", factory=get_database_config)
    container.register_singleton("AWSConfig", factory=get_aws_config)
    container.register_singleton("SecurityConfig", factory=get_security_config)
    container.register_singleton("LoggingConfig", factory=get_logging_config)
    
    logger.info("Configuration services registered successfully")
    return container


def create_environment_container(
    environment: Environment,
    config_overrides: Optional[Dict[str, Any]] = None
) -> DIContainer:
    """
    Create a DI container configured for a specific environment.
    
    Args:
        environment: Target environment
        config_overrides: Configuration overrides
        
    Returns:
        Configured DI container
    """
    from app.services.service_factory import ServiceFactory
    
    # Create base container for the environment
    if environment == Environment.PRODUCTION:
        container = ServiceFactory.create_production_container()
    elif environment == Environment.TESTING:
        container = ServiceFactory.create_testing_container()
    else:
        container = ServiceFactory.create_development_container()
    
    # Register configuration services
    container = register_configuration_services(
        container, 
        environment, 
        config_overrides
    )
    
    return container


def update_service_factory_with_config():
    """
    Update the existing service factory to use the new configuration system.
    
    This function modifies the existing ServiceFactory to integrate with
    the new configuration management system.
    """
    from app.services.service_factory import ServiceFactory
    
    # Store original methods
    original_create_development = ServiceFactory.create_development_container
    original_create_production = ServiceFactory.create_production_container
    
    @staticmethod
    def create_development_container_with_config():
        """Create development container with configuration."""
        container = original_create_development()
        return register_configuration_services(container, Environment.DEVELOPMENT)
    
    @staticmethod
    def create_production_container_with_config():
        """Create production container with configuration."""
        container = original_create_production()
        return register_configuration_services(container, Environment.PRODUCTION)
    
    # Replace methods
    ServiceFactory.create_development_container = create_development_container_with_config
    ServiceFactory.create_production_container = create_production_container_with_config
    
    logger.info("Service factory updated with configuration integration")


# FastAPI dependency functions
def get_application_config() -> ApplicationConfig:
    """FastAPI dependency to get application configuration."""
    return get_configuration_sync()


def get_database_config():
    """FastAPI dependency to get database configuration."""
    return get_configuration_sync().database


def get_aws_config():
    """FastAPI dependency to get AWS configuration."""
    return get_configuration_sync().aws


def get_security_config():
    """FastAPI dependency to get security configuration."""
    return get_configuration_sync().security


def get_logging_config():
    """FastAPI dependency to get logging configuration."""
    return get_configuration_sync().logging


def get_cors_config():
    """FastAPI dependency to get CORS configuration."""
    return get_configuration_sync().cors


def get_file_storage_config():
    """FastAPI dependency to get file storage configuration."""
    return get_configuration_sync().file_storage


def get_video_config():
    """FastAPI dependency to get video configuration."""
    return get_configuration_sync().video


def get_authentication_config():
    """FastAPI dependency to get authentication configuration."""
    return get_configuration_sync().authentication

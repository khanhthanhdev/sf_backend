"""
Configuration management module.

This module provides comprehensive configuration management with:
- Hierarchical configuration classes with Pydantic validation
- Environment-specific configuration loading and validation
- Secure handling of sensitive configuration and secrets
- Configuration factory with dependency injection support

Usage:
    from app.core.configuration import get_configuration, ConfigurationFactory
    
    # Async configuration loading
    config = await get_configuration()
    
    # Environment-specific factories
    factory = ConfigurationFactory.create_production_factory()
    config = await factory.create_configuration()
    
    # Dependency injection
    from app.core.configuration import ApplicationConfig
    
    def my_service(config: ApplicationConfig = Depends(get_configuration_sync)):
        pass
"""

from .base import (
    # Base classes
    BaseConfiguration,
    
    # Enums
    Environment,
    LogLevel,
    LogFormat,
    VideoQuality,
    
    # Configuration sections
    SecurityConfig,
    DatabaseConfig,
    AWSConfig,
    LoggingConfig,
    CORSConfig,
)

from .application import (
    ApplicationConfig,
    ServerConfig,
    APIConfig,
    FileStorageConfig,
    VideoConfig,
    AuthenticationConfig,
)

from .factory import (
    # Factory classes
    ConfigurationFactory,
    ConfigurationValidator,
    EnvironmentOverrideManager,
    
    # Secret managers
    SecretManager,
    EnvironmentSecretManager,
    FileSecretManager,
    AWSSecretsManager,
    
    # Exceptions
    ConfigurationError,
    
    # Functions
    get_configuration,
    get_configuration_sync,
    set_configuration_factory,
    create_development_configuration,
    create_production_configuration,
    create_testing_configuration,
)

from .templates import (
    # Template functions
    get_development_template,
    get_testing_template,
    get_staging_template,
    get_production_template,
    create_environment_config_file,
    ENVIRONMENT_TEMPLATES,
)

from .integration import (
    # Services
    ConfigurationService,
    
    # Configuration access
    get_configuration_sync,
    set_configuration_instance,
    
    # DI integration
    register_configuration_services,
    create_environment_container,
    update_service_factory_with_config,
    
    # FastAPI dependencies
    get_application_config,
    get_database_config,
    get_aws_config,
    get_security_config,
    get_logging_config,
    get_cors_config,
    get_file_storage_config,
    get_video_config,
    get_authentication_config,
)

__all__ = [
    # Base classes and enums
    "BaseConfiguration",
    "Environment",
    "LogLevel", 
    "LogFormat",
    "VideoQuality",
    
    # Configuration sections
    "SecurityConfig",
    "DatabaseConfig",
    "AWSConfig",
    "LoggingConfig",
    "CORSConfig",
    "ServerConfig",
    "APIConfig",
    "FileStorageConfig",
    "VideoConfig",
    "AuthenticationConfig",
    
    # Main configuration
    "ApplicationConfig",
    
    # Factory and management
    "ConfigurationFactory",
    "ConfigurationValidator",
    "EnvironmentOverrideManager",
    
    # Secret management
    "SecretManager",
    "EnvironmentSecretManager",
    "FileSecretManager",
    "AWSSecretsManager",
    
    # Exceptions
    "ConfigurationError",
    
    # Functions
    "get_configuration",
    "get_configuration_sync",
    "set_configuration_factory",
    "create_development_configuration",
    "create_production_configuration",
    "create_testing_configuration",
    
    # Templates
    "get_development_template",
    "get_testing_template",
    "get_staging_template",
    "get_production_template",
    "create_environment_config_file",
    "ENVIRONMENT_TEMPLATES",
    
    # Integration
    "ConfigurationService",
    "get_configuration_sync",
    "set_configuration_instance",
    "register_configuration_services",
    "create_environment_container",
    "update_service_factory_with_config",
    
    # FastAPI dependencies
    "get_application_config",
    "get_database_config",
    "get_aws_config",
    "get_security_config",
    "get_logging_config",
    "get_cors_config",
    "get_file_storage_config",
    "get_video_config",
    "get_authentication_config",
]

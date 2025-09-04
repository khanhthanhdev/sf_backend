"""
Configuration factory with environment-specific settings and dependency injection support.

This module provides factory classes for creating and managing configuration
instances with environment-specific overrides and secure secret handling.
"""

from typing import Dict, Any, Optional, Type, TypeVar, Union, Callable
from pathlib import Path
import os
import logging
from functools import lru_cache
from abc import ABC, abstractmethod

from pydantic import ValidationError
from pydantic.types import SecretStr

from .base import Environment
from .application import ApplicationConfig


logger = logging.getLogger(__name__)

T = TypeVar('T', bound=ApplicationConfig)


class ConfigurationError(Exception):
    """Configuration-related errors."""
    pass


class SecretManager(ABC):
    """Abstract base class for secret management."""
    
    @abstractmethod
    async def get_secret(self, secret_name: str) -> str:
        """Get a secret value by name."""
        pass
    
    @abstractmethod
    async def set_secret(self, secret_name: str, secret_value: str) -> None:
        """Set a secret value."""
        pass
    
    @abstractmethod
    async def delete_secret(self, secret_name: str) -> None:
        """Delete a secret."""
        pass


class EnvironmentSecretManager(SecretManager):
    """Secret manager that uses environment variables."""
    
    def __init__(self, prefix: str = "SECRET_"):
        self.prefix = prefix
    
    async def get_secret(self, secret_name: str) -> str:
        """Get secret from environment variable."""
        env_name = f"{self.prefix}{secret_name.upper()}"
        value = os.getenv(env_name)
        if value is None:
            raise ConfigurationError(f"Secret '{secret_name}' not found in environment")
        return value
    
    async def set_secret(self, secret_name: str, secret_value: str) -> None:
        """Set secret in environment variable."""
        env_name = f"{self.prefix}{secret_name.upper()}"
        os.environ[env_name] = secret_value
    
    async def delete_secret(self, secret_name: str) -> None:
        """Delete secret from environment variable."""
        env_name = f"{self.prefix}{secret_name.upper()}"
        if env_name in os.environ:
            del os.environ[env_name]


class FileSecretManager(SecretManager):
    """Secret manager that reads secrets from files (e.g., Docker secrets)."""
    
    def __init__(self, secrets_dir: Path = Path("/run/secrets")):
        self.secrets_dir = Path(secrets_dir)
    
    async def get_secret(self, secret_name: str) -> str:
        """Get secret from file."""
        secret_file = self.secrets_dir / secret_name
        try:
            return secret_file.read_text().strip()
        except FileNotFoundError:
            raise ConfigurationError(f"Secret file '{secret_file}' not found")
        except Exception as e:
            raise ConfigurationError(f"Error reading secret '{secret_name}': {e}")
    
    async def set_secret(self, secret_name: str, secret_value: str) -> None:
        """Set secret in file."""
        secret_file = self.secrets_dir / secret_name
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secret_value)
        secret_file.chmod(0o600)  # Read-only for owner
    
    async def delete_secret(self, secret_name: str) -> None:
        """Delete secret file."""
        secret_file = self.secrets_dir / secret_name
        if secret_file.exists():
            secret_file.unlink()


class AWSSecretsManager(SecretManager):
    """Secret manager that uses AWS Secrets Manager."""
    
    def __init__(self, region: str = "us-west-2"):
        self.region = region
        self._client = None
    
    @property
    def client(self):
        """Get AWS Secrets Manager client."""
        if self._client is None:
            import boto3
            self._client = boto3.client("secretsmanager", region_name=self.region)
        return self._client
    
    async def get_secret(self, secret_name: str) -> str:
        """Get secret from AWS Secrets Manager."""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response["SecretString"]
        except Exception as e:
            raise ConfigurationError(f"Error getting secret '{secret_name}' from AWS: {e}")
    
    async def set_secret(self, secret_name: str, secret_value: str) -> None:
        """Set secret in AWS Secrets Manager."""
        try:
            self.client.create_secret(Name=secret_name, SecretString=secret_value)
        except self.client.exceptions.ResourceExistsException:
            self.client.update_secret(SecretId=secret_name, SecretString=secret_value)
        except Exception as e:
            raise ConfigurationError(f"Error setting secret '{secret_name}' in AWS: {e}")
    
    async def delete_secret(self, secret_name: str) -> None:
        """Delete secret from AWS Secrets Manager."""
        try:
            self.client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
        except Exception as e:
            raise ConfigurationError(f"Error deleting secret '{secret_name}' from AWS: {e}")


class ConfigurationValidator:
    """Validates configuration based on environment and business rules."""
    
    def __init__(self, environment: Environment):
        self.environment = environment
    
    def validate_configuration(self, config: ApplicationConfig) -> None:
        """Validate configuration for the current environment."""
        self._validate_environment_consistency(config)
        self._validate_security_settings(config)
        self._validate_production_requirements(config)
        self._validate_development_settings(config)
        self._validate_dependencies(config)
    
    def _validate_environment_consistency(self, config: ApplicationConfig) -> None:
        """Validate environment consistency."""
        if config.environment != self.environment:
            logger.warning(
                f"Configuration environment ({config.environment}) doesn't match "
                f"expected environment ({self.environment})"
            )
    
    def _validate_security_settings(self, config: ApplicationConfig) -> None:
        """Validate security settings."""
        # Check for default/weak secrets
        if config.security.secret_key.get_secret_value() in [
            "dev-secret-key-change-in-production",
            "secret",
            "password",
            "changeme"
        ]:
            if config.is_production:
                raise ConfigurationError("Default secret key cannot be used in production")
            else:
                logger.warning("Using default secret key in non-production environment")
        
        # Validate JWT settings
        if config.security.jwt_access_token_expire_minutes > 1440:  # 24 hours
            logger.warning("JWT access token expiration is longer than 24 hours")
        
        # Validate HTTPS requirements in production
        if config.is_production:
            if not config.authentication.session_cookie_secure:
                raise ConfigurationError("Secure cookies must be enabled in production")
    
    def _validate_production_requirements(self, config: ApplicationConfig) -> None:
        """Validate production-specific requirements."""
        if not config.is_production:
            return
        
        # Database SSL requirement
        if config.database.ssl_mode in ["disable", "allow"]:
            raise ConfigurationError("SSL must be required for database connections in production")
        
        # Logging requirements
        if config.logging.level.value not in ["INFO", "WARNING", "ERROR"]:
            logger.warning("Debug logging enabled in production")
        
        # Documentation endpoints
        if config.api.docs_url is not None or config.api.redoc_url is not None:
            logger.warning("API documentation endpoints are enabled in production")
        
        # File size limits
        if config.file_storage.max_file_size > 500 * 1024 * 1024:  # 500MB
            logger.warning("Large file size limit configured for production")
    
    def _validate_development_settings(self, config: ApplicationConfig) -> None:
        """Validate development-specific settings."""
        if not config.is_development:
            return
        
        # Enable helpful development features
        if not config.server.reload:
            logger.info("Server auto-reload is disabled in development")
        
        if config.logging.level != "DEBUG":
            logger.info("Debug logging is not enabled in development")
    
    def _validate_dependencies(self, config: ApplicationConfig) -> None:
        """Validate configuration dependencies."""
        # AWS dependencies
        if config.file_storage.storage_backend == "s3":
            if not config.aws.access_key_id and not config.aws.secret_access_key:
                logger.warning("S3 storage enabled but AWS credentials not configured")
        
        # Redis dependencies
        if config.is_feature_enabled("caching"):
            # This would check if Redis configuration is valid
            pass
        
        # Clerk dependencies
        if config.authentication.clerk_jwt_verification:
            if not config.authentication.clerk_secret_key.get_secret_value():
                raise ConfigurationError("Clerk secret key required for JWT verification")


class EnvironmentOverrideManager:
    """Manages environment-specific configuration overrides."""
    
    def __init__(self):
        self._overrides: Dict[Environment, Dict[str, Any]] = {}
    
    def add_override(
        self, 
        environment: Environment, 
        path: str, 
        value: Any
    ) -> None:
        """Add a configuration override for a specific environment."""
        if environment not in self._overrides:
            self._overrides[environment] = {}
        self._overrides[environment][path] = value
    
    def apply_overrides(
        self, 
        config_dict: Dict[str, Any], 
        environment: Environment
    ) -> Dict[str, Any]:
        """Apply environment-specific overrides to configuration."""
        if environment not in self._overrides:
            return config_dict
        
        overrides = self._overrides[environment]
        for path, value in overrides.items():
            self._set_nested_value(config_dict, path, value)
        
        return config_dict
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested dictionary value using dot notation."""
        keys = path.split(".")
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value


class ConfigurationFactory:
    """
    Factory for creating and managing application configurations.
    
    Provides environment-specific configurations, secret management,
    and dependency injection support.
    """
    
    def __init__(
        self,
        secret_manager: Optional[SecretManager] = None,
        override_manager: Optional[EnvironmentOverrideManager] = None
    ):
        self.secret_manager = secret_manager or EnvironmentSecretManager()
        self.override_manager = override_manager or EnvironmentOverrideManager()
        self._setup_default_overrides()
    
    def _setup_default_overrides(self) -> None:
        """Setup default environment-specific overrides."""
        # Development overrides
        self.override_manager.add_override(
            Environment.DEVELOPMENT,
            "server.reload",
            True
        )
        self.override_manager.add_override(
            Environment.DEVELOPMENT,
            "logging.level",
            "DEBUG"
        )
        self.override_manager.add_override(
            Environment.DEVELOPMENT,
            "database.echo_queries",
            True
        )
        
        # Testing overrides
        self.override_manager.add_override(
            Environment.TESTING,
            "logging.level",
            "WARNING"
        )
        self.override_manager.add_override(
            Environment.TESTING,
            "database.name",
            "test_database"
        )
        self.override_manager.add_override(
            Environment.TESTING,
            "redis.database",
            1
        )
        
        # Production overrides
        self.override_manager.add_override(
            Environment.PRODUCTION,
            "server.reload",
            False
        )
        self.override_manager.add_override(
            Environment.PRODUCTION,
            "api.docs_url",
            None
        )
        self.override_manager.add_override(
            Environment.PRODUCTION,
            "api.redoc_url",
            None
        )
        self.override_manager.add_override(
            Environment.PRODUCTION,
            "authentication.session_cookie_secure",
            True
        )
        self.override_manager.add_override(
            Environment.PRODUCTION,
            "database.ssl_mode",
            "require"
        )
    
    async def create_configuration(
        self,
        environment: Optional[Environment] = None,
        config_file: Optional[Path] = None,
        **overrides
    ) -> ApplicationConfig:
        """
        Create application configuration with environment-specific settings.
        
        Args:
            environment: Target environment (auto-detected if None)
            config_file: Optional configuration file
            **overrides: Additional configuration overrides
            
        Returns:
            Configured ApplicationConfig instance
        """
        # Detect environment if not provided
        if environment is None:
            environment = self._detect_environment()
        
        # Load base configuration
        config_dict = await self._load_base_configuration(config_file)
        
        # Apply environment overrides
        config_dict = self.override_manager.apply_overrides(config_dict, environment)
        
        # Apply additional overrides
        for key, value in overrides.items():
            self.override_manager._set_nested_value(config_dict, key, value)
        
        # Load secrets
        await self._load_secrets(config_dict)
        
        # Create configuration instance
        try:
            config = ApplicationConfig(**config_dict)
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")
        
        # Validate configuration
        validator = ConfigurationValidator(environment)
        validator.validate_configuration(config)
        
        logger.info(f"Configuration loaded for environment: {environment}")
        return config
    
    def _detect_environment(self) -> Environment:
        """Detect environment from environment variables."""
        env_value = os.getenv("ENVIRONMENT", "development").lower()
        try:
            return Environment(env_value)
        except ValueError:
            logger.warning(f"Invalid environment '{env_value}', defaulting to development")
            return Environment.DEVELOPMENT
    
    async def _load_base_configuration(
        self, 
        config_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Load base configuration from file or environment."""
        config_dict = {}
        
        # Load from file if provided
        if config_file and config_file.exists():
            import json
            import yaml
            
            try:
                if config_file.suffix.lower() == ".json":
                    config_dict = json.loads(config_file.read_text())
                elif config_file.suffix.lower() in [".yml", ".yaml"]:
                    config_dict = yaml.safe_load(config_file.read_text())
                else:
                    logger.warning(f"Unsupported config file format: {config_file.suffix}")
            except Exception as e:
                logger.error(f"Error loading config file {config_file}: {e}")
                raise ConfigurationError(f"Failed to load configuration file: {e}")
        
        return config_dict
    
    async def _load_secrets(self, config_dict: Dict[str, Any]) -> None:
        """Load secrets from secret manager."""
        secret_mappings = {
            "database.password": "database_password",
            "security.secret_key": "app_secret_key",
            "authentication.clerk_secret_key": "clerk_secret_key",
            "authentication.clerk_webhook_secret": "clerk_webhook_secret",
            "aws.access_key_id": "aws_access_key_id",
            "aws.secret_access_key": "aws_secret_access_key",
            "redis.password": "redis_password",
            "logging.sentry_dsn": "sentry_dsn",
        }
        
        for config_path, secret_name in secret_mappings.items():
            try:
                secret_value = await self.secret_manager.get_secret(secret_name)
                self.override_manager._set_nested_value(config_dict, config_path, secret_value)
            except ConfigurationError:
                # Secret not found, use default or environment value
                pass
            except Exception as e:
                logger.warning(f"Error loading secret '{secret_name}': {e}")
    
    @classmethod
    def create_development_factory(cls) -> "ConfigurationFactory":
        """Create factory for development environment."""
        return cls(
            secret_manager=EnvironmentSecretManager(),
            override_manager=EnvironmentOverrideManager()
        )
    
    @classmethod
    def create_production_factory(cls, secrets_backend: str = "aws") -> "ConfigurationFactory":
        """Create factory for production environment."""
        if secrets_backend == "aws":
            secret_manager = AWSSecretsManager()
        elif secrets_backend == "file":
            secret_manager = FileSecretManager()
        else:
            secret_manager = EnvironmentSecretManager()
        
        return cls(
            secret_manager=secret_manager,
            override_manager=EnvironmentOverrideManager()
        )
    
    @classmethod
    def create_testing_factory(cls) -> "ConfigurationFactory":
        """Create factory for testing environment."""
        return cls(
            secret_manager=EnvironmentSecretManager(prefix="TEST_SECRET_"),
            override_manager=EnvironmentOverrideManager()
        )


# Global configuration instance
_config_instance: Optional[ApplicationConfig] = None
_config_factory: Optional[ConfigurationFactory] = None


async def get_configuration(
    force_reload: bool = False,
    **overrides
) -> ApplicationConfig:
    """
    Get the global application configuration instance.
    
    Args:
        force_reload: Force reload configuration
        **overrides: Configuration overrides
        
    Returns:
        ApplicationConfig instance
    """
    global _config_instance, _config_factory
    
    if _config_instance is None or force_reload:
        if _config_factory is None:
            _config_factory = ConfigurationFactory.create_development_factory()
        
        _config_instance = await _config_factory.create_configuration(**overrides)
    
    return _config_instance


def set_configuration_factory(factory: ConfigurationFactory) -> None:
    """Set the global configuration factory."""
    global _config_factory
    _config_factory = factory


@lru_cache(maxsize=1)
def get_configuration_sync() -> ApplicationConfig:
    """
    Get configuration synchronously (for use in non-async contexts).
    
    Note: This should only be used where async is not available.
    The configuration must be loaded asynchronously first.
    """
    global _config_instance
    
    if _config_instance is None:
        raise ConfigurationError(
            "Configuration not loaded. Call get_configuration() first in an async context."
        )
    
    return _config_instance


# Environment-specific factory functions for dependency injection
def create_development_configuration() -> ApplicationConfig:
    """Create development configuration (sync version for DI)."""
    return get_configuration_sync()


def create_production_configuration() -> ApplicationConfig:
    """Create production configuration (sync version for DI)."""
    return get_configuration_sync()


def create_testing_configuration() -> ApplicationConfig:
    """Create testing configuration (sync version for DI)."""
    return get_configuration_sync()

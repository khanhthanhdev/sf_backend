"""
Hierarchical configuration management with Pydantic validation.

This module implements comprehensive configuration management following
enterprise best practices with environment-specific settings,
secret handling, and dependency injection support.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Type, TypeVar
from pathlib import Path
import os
from enum import Enum
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from pydantic.types import SecretStr
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseSettings)


class Environment(str, Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Supported log formats."""
    JSON = "json"
    TEXT = "text"


class VideoQuality(str, Enum):
    """Supported video qualities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


class BaseConfiguration(BaseSettings, ABC):
    """
    Abstract base configuration class with common settings.
    
    Provides shared configuration patterns and validation logic
    that can be inherited by specific configuration classes.
    """
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
        validate_assignment = True
        use_enum_values = True


class SecurityConfig(BaseConfiguration):
    """Security-related configuration."""
    
    # Encryption and signing
    secret_key: SecretStr = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for encryption and signing",
        env="SECRET_KEY"
    )
    
    # JWT settings
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
        env="JWT_ALGORITHM"
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT access token expiration in minutes",
        env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        gt=0,
        le=1440  # Max 24 hours
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="JWT refresh token expiration in days",
        env="JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        gt=0,
        le=30  # Max 30 days
    )
    
    # Password requirements
    password_min_length: int = Field(
        default=8,
        description="Minimum password length",
        env="PASSWORD_MIN_LENGTH",
        ge=6,
        le=128
    )
    password_require_special: bool = Field(
        default=True,
        description="Require special characters in passwords",
        env="PASSWORD_REQUIRE_SPECIAL"
    )
    
    # Security headers
    enable_hsts: bool = Field(
        default=True,
        description="Enable HTTP Strict Transport Security",
        env="ENABLE_HSTS"
    )
    hsts_max_age: int = Field(
        default=31536000,  # 1 year
        description="HSTS max age in seconds",
        env="HSTS_MAX_AGE",
        ge=0
    )
    
    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
        env="RATE_LIMIT_ENABLED"
    )
    rate_limit_requests_per_minute: int = Field(
        default=100,
        description="Requests per minute per IP",
        env="RATE_LIMIT_REQUESTS_PER_MINUTE",
        gt=0
    )
    rate_limit_burst: int = Field(
        default=200,
        description="Burst allowance for rate limiting",
        env="RATE_LIMIT_BURST",
        gt=0
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v):
        """Validate JWT algorithm."""
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in allowed_algorithms:
            raise ValueError(f"JWT algorithm must be one of: {allowed_algorithms}")
        return v


class DatabaseConfig(BaseConfiguration):
    """Database configuration with connection pooling."""
    
    # Connection details
    host: str = Field(
        default="localhost",
        description="Database host",
        env="DB_HOST"
    )
    port: int = Field(
        default=5432,
        description="Database port",
        env="DB_PORT",
        gt=0,
        le=65535
    )
    name: str = Field(
        default="fastapi_app",
        description="Database name",
        env="DB_NAME",
        min_length=1
    )
    username: str = Field(
        default="postgres",
        description="Database username",
        env="DB_USERNAME",
        min_length=1
    )
    password: SecretStr = Field(
        default="password",
        description="Database password",
        env="DB_PASSWORD"
    )
    
    # SSL settings
    ssl_mode: str = Field(
        default="prefer",
        description="SSL connection mode",
        env="DB_SSL_MODE"
    )
    ssl_cert_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL certificate",
        env="DB_SSL_CERT_PATH"
    )
    ssl_key_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL private key",
        env="DB_SSL_KEY_PATH"
    )
    ssl_ca_path: Optional[Path] = Field(
        default=None,
        description="Path to SSL CA certificate",
        env="DB_SSL_CA_PATH"
    )
    
    # Connection pool settings
    pool_min_size: int = Field(
        default=5,
        description="Minimum pool size",
        env="DB_POOL_MIN_SIZE",
        ge=1
    )
    pool_max_size: int = Field(
        default=20,
        description="Maximum pool size",
        env="DB_POOL_MAX_SIZE",
        ge=1
    )
    pool_max_overflow: int = Field(
        default=10,
        description="Maximum pool overflow",
        env="DB_POOL_MAX_OVERFLOW",
        ge=0
    )
    pool_timeout: int = Field(
        default=30,
        description="Pool checkout timeout in seconds",
        env="DB_POOL_TIMEOUT",
        gt=0
    )
    pool_recycle: int = Field(
        default=3600,
        description="Pool connection recycle time in seconds",
        env="DB_POOL_RECYCLE",
        gt=0
    )
    
    # Query settings
    query_timeout: int = Field(
        default=30,
        description="Query timeout in seconds",
        env="DB_QUERY_TIMEOUT",
        gt=0
    )
    echo_queries: bool = Field(
        default=False,
        description="Echo SQL queries to logs",
        env="DB_ECHO_QUERIES"
    )
    
    @field_validator("ssl_mode")
    @classmethod
    def validate_ssl_mode(cls, v):
        """Validate SSL mode."""
        allowed_modes = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        if v not in allowed_modes:
            raise ValueError(f"SSL mode must be one of: {allowed_modes}")
        return v
    
    @model_validator(mode='after')
    def validate_pool_settings(self):
        """Validate pool configuration."""
        if self.pool_min_size > self.pool_max_size:
            raise ValueError("pool_min_size cannot be greater than pool_max_size")
        return self
    
    @property
    def connection_url(self) -> str:
        """Get database connection URL."""
        password = self.password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.username}:{password}@"
            f"{self.host}:{self.port}/{self.name}"
        )
    
    @property
    def sync_connection_url(self) -> str:
        """Get synchronous database connection URL."""
        password = self.password.get_secret_value()
        return (
            f"postgresql://{self.username}:{password}@"
            f"{self.host}:{self.port}/{self.name}"
        )


class AWSConfig(BaseConfiguration):
    """AWS services configuration."""
    
    # Credentials
    access_key_id: Optional[SecretStr] = Field(
        default=None,
        description="AWS access key ID",
        env="AWS_ACCESS_KEY_ID"
    )
    secret_access_key: Optional[SecretStr] = Field(
        default=None,
        description="AWS secret access key",
        env="AWS_SECRET_ACCESS_KEY"
    )
    session_token: Optional[SecretStr] = Field(
        default=None,
        description="AWS session token",
        env="AWS_SESSION_TOKEN"
    )
    region: str = Field(
        default="us-west-2",
        description="AWS region",
        env="AWS_REGION"
    )
    
    # S3 settings
    s3_bucket_name: str = Field(
        default="fastapi-uploads",
        description="S3 bucket for file uploads",
        env="AWS_S3_BUCKET_NAME",
        min_length=3,
        max_length=63
    )
    s3_bucket_region: Optional[str] = Field(
        default=None,
        description="S3 bucket region (defaults to main region)",
        env="AWS_S3_BUCKET_REGION"
    )
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom S3 endpoint URL (for testing)",
        env="AWS_S3_ENDPOINT_URL"
    )
    s3_max_file_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum file size for S3 uploads in bytes",
        env="AWS_S3_MAX_FILE_SIZE",
        gt=0
    )
    
    # SES settings
    ses_sender_email: str = Field(
        default="noreply@example.com",
        description="Default sender email for SES",
        env="AWS_SES_SENDER_EMAIL"
    )
    ses_configuration_set: Optional[str] = Field(
        default=None,
        description="SES configuration set",
        env="AWS_SES_CONFIGURATION_SET"
    )
    
    # SQS settings
    sqs_queue_url: Optional[str] = Field(
        default=None,
        description="SQS queue URL for background jobs",
        env="AWS_SQS_QUEUE_URL"
    )
    sqs_visibility_timeout: int = Field(
        default=300,  # 5 minutes
        description="SQS message visibility timeout in seconds",
        env="AWS_SQS_VISIBILITY_TIMEOUT",
        gt=0
    )
    
    # CloudWatch settings
    cloudwatch_enabled: bool = Field(
        default=False,
        description="Enable CloudWatch logging",
        env="AWS_CLOUDWATCH_ENABLED"
    )
    cloudwatch_log_group: str = Field(
        default="fastapi-application",
        description="CloudWatch log group name",
        env="AWS_CLOUDWATCH_LOG_GROUP"
    )
    cloudwatch_log_stream: Optional[str] = Field(
        default=None,
        description="CloudWatch log stream name",
        env="AWS_CLOUDWATCH_LOG_STREAM"
    )
    
    @field_validator("s3_bucket_name")
    @classmethod
    def validate_s3_bucket_name(cls, v):
        """Validate S3 bucket name."""
        # Basic S3 bucket name validation
        import re
        if not re.match(r'^[a-z0-9.-]{3,63}$', v):
            raise ValueError("S3 bucket name must be 3-63 characters and contain only lowercase letters, numbers, dots, and hyphens")
        return v
    
    @field_validator("ses_sender_email")
    @classmethod
    def validate_ses_sender_email(cls, v):
        """Validate SES sender email."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format for SES sender")
        return v
    
    @property
    def s3_bucket_region_or_default(self) -> str:
        """Get S3 bucket region or default to main region."""
        return self.s3_bucket_region or self.region


class LoggingConfig(BaseConfiguration):
    """Logging configuration."""
    
    # Basic settings
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Log level",
        env="LOG_LEVEL"
    )
    format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log format",
        env="LOG_FORMAT"
    )
    
    # File logging
    file_enabled: bool = Field(
        default=False,
        description="Enable file logging",
        env="LOG_FILE_ENABLED"
    )
    file_path: Optional[Path] = Field(
        default=None,
        description="Log file path",
        env="LOG_FILE_PATH"
    )
    file_max_size: str = Field(
        default="10MB",
        description="Maximum log file size",
        env="LOG_FILE_MAX_SIZE"
    )
    file_backup_count: int = Field(
        default=5,
        description="Number of backup log files",
        env="LOG_FILE_BACKUP_COUNT",
        ge=0
    )
    
    # Console logging
    console_enabled: bool = Field(
        default=True,
        description="Enable console logging",
        env="LOG_CONSOLE_ENABLED"
    )
    console_colors: bool = Field(
        default=True,
        description="Enable colored console output",
        env="LOG_CONSOLE_COLORS"
    )
    
    # Structured logging
    include_timestamp: bool = Field(
        default=True,
        description="Include timestamp in logs",
        env="LOG_INCLUDE_TIMESTAMP"
    )
    include_caller: bool = Field(
        default=False,
        description="Include caller information in logs",
        env="LOG_INCLUDE_CALLER"
    )
    correlation_id_header: str = Field(
        default="X-Correlation-ID",
        description="HTTP header for correlation ID",
        env="LOG_CORRELATION_ID_HEADER"
    )
    
    # External logging
    sentry_dsn: Optional[SecretStr] = Field(
        default=None,
        description="Sentry DSN for error reporting",
        env="SENTRY_DSN"
    )
    sentry_environment: Optional[str] = Field(
        default=None,
        description="Sentry environment",
        env="SENTRY_ENVIRONMENT"
    )
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        description="Sentry traces sample rate",
        env="SENTRY_TRACES_SAMPLE_RATE",
        ge=0.0,
        le=1.0
    )


class CORSConfig(BaseConfiguration):
    """CORS configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable CORS",
        env="CORS_ENABLED"
    )
    
    allow_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed origins",
        env="CORS_ALLOW_ORIGINS"
    )
    allow_origin_regex: Optional[str] = Field(
        default=None,
        description="Allowed origin regex pattern",
        env="CORS_ALLOW_ORIGIN_REGEX"
    )
    allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed HTTP methods",
        env="CORS_ALLOW_METHODS"
    )
    allow_headers: List[str] = Field(
        default=["*"],
        description="Allowed headers",
        env="CORS_ALLOW_HEADERS"
    )
    allow_credentials: bool = Field(
        default=True,
        description="Allow credentials",
        env="CORS_ALLOW_CREDENTIALS"
    )
    expose_headers: List[str] = Field(
        default=[],
        description="Headers to expose to the browser",
        env="CORS_EXPOSE_HEADERS"
    )
    max_age: int = Field(
        default=600,
        description="Preflight cache max age in seconds",
        env="CORS_MAX_AGE",
        ge=0
    )
    
    @field_validator("allow_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Parse origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @field_validator("allow_methods", mode="before")
    @classmethod
    def parse_methods(cls, v):
        """Parse methods from string or list."""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return [method.upper() for method in v]
    
    @field_validator("allow_headers", mode="before")
    @classmethod
    def parse_headers(cls, v):
        """Parse headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v
    
    @field_validator("expose_headers", mode="before")
    @classmethod
    def parse_expose_headers(cls, v):
        """Parse expose headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

"""
Application configuration that combines all configuration modules.

This module provides the main ApplicationConfig class that aggregates
all configuration sections and provides environment-specific settings.
"""

from typing import Dict, List, Optional, Any, Set
from pathlib import Path
import os
from functools import lru_cache
from typing_extensions import Self

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from pydantic.types import SecretStr

from .base import (
    BaseConfiguration,
    Environment,
    VideoQuality,
    SecurityConfig,
    DatabaseConfig,
    AWSConfig,
    LoggingConfig,
    CORSConfig,
)


class ServerConfig(BaseConfiguration):
    """Server configuration."""
    
    host: str = Field(
        default="0.0.0.0",
        description="Server host",
        env="SERVER_HOST"
    )
    port: int = Field(
        default=8000,
        description="Server port",
        env="SERVER_PORT",
        gt=0,
        le=65535
    )
    workers: int = Field(
        default=1,
        description="Number of worker processes",
        env="SERVER_WORKERS",
        gt=0
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload in development",
        env="SERVER_RELOAD"
    )
    access_log: bool = Field(
        default=True,
        description="Enable access logging",
        env="SERVER_ACCESS_LOG"
    )
    keepalive_timeout: int = Field(
        default=5,
        description="Keep-alive timeout in seconds",
        env="SERVER_KEEPALIVE_TIMEOUT",
        gt=0
    )
    max_concurrent_connections: int = Field(
        default=1000,
        description="Maximum concurrent connections",
        env="SERVER_MAX_CONCURRENT_CONNECTIONS",
        gt=0
    )


class APIConfig(BaseConfiguration):
    """API configuration."""
    
    title: str = Field(
        default="FastAPI Video Backend",
        description="API title",
        env="API_TITLE"
    )
    version: str = Field(
        default="0.1.0",
        description="API version",
        env="API_VERSION"
    )
    description: str = Field(
        default="FastAPI backend for video generation and management",
        description="API description",
        env="API_DESCRIPTION"
    )
    
    # URL configuration
    v1_prefix: str = Field(
        default="/api/v1",
        description="API v1 prefix",
        env="API_V1_PREFIX"
    )
    docs_url: Optional[str] = Field(
        default="/docs",
        description="Swagger UI URL (None to disable)",
        env="API_DOCS_URL"
    )
    redoc_url: Optional[str] = Field(
        default="/redoc",
        description="ReDoc URL (None to disable)",
        env="API_REDOC_URL"
    )
    openapi_url: Optional[str] = Field(
        default="/openapi.json",
        description="OpenAPI schema URL (None to disable)",
        env="API_OPENAPI_URL"
    )
    
    # Request/Response settings
    max_request_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum request size in bytes",
        env="API_MAX_REQUEST_SIZE",
        gt=0
    )
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        env="API_REQUEST_TIMEOUT",
        gt=0
    )
    response_compression: bool = Field(
        default=True,
        description="Enable response compression",
        env="API_RESPONSE_COMPRESSION"
    )
    
    # Documentation settings
    include_in_schema: bool = Field(
        default=True,
        description="Include endpoints in OpenAPI schema",
        env="API_INCLUDE_IN_SCHEMA"
    )
    swagger_ui_parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "displayRequestDuration": True,
        },
        description="Swagger UI parameters",
        env="API_SWAGGER_UI_PARAMETERS"
    )


class FileStorageConfig(BaseConfiguration):
    """File storage configuration."""
    
    # Local storage
    local_storage_path: Path = Field(
        default=Path("./storage"),
        description="Local storage directory",
        env="FILE_LOCAL_STORAGE_PATH"
    )
    temp_storage_path: Path = Field(
        default=Path("./temp"),
        description="Temporary storage directory",
        env="FILE_TEMP_STORAGE_PATH"
    )
    
    # File validation
    max_file_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum file size in bytes",
        env="FILE_MAX_SIZE",
        gt=0
    )
    allowed_extensions: Set[str] = Field(
        default={".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi", ".txt", ".pdf"},
        description="Allowed file extensions",
        env="FILE_ALLOWED_EXTENSIONS"
    )
    allowed_mime_types: Set[str] = Field(
        default={
            "image/jpeg", "image/png", "image/gif",
            "video/mp4", "video/quicktime", "video/x-msvideo",
            "text/plain", "application/pdf"
        },
        description="Allowed MIME types",
        env="FILE_ALLOWED_MIME_TYPES"
    )
    
    # Virus scanning
    virus_scan_enabled: bool = Field(
        default=False,
        description="Enable virus scanning",
        env="FILE_VIRUS_SCAN_ENABLED"
    )
    virus_scan_timeout: int = Field(
        default=30,
        description="Virus scan timeout in seconds",
        env="FILE_VIRUS_SCAN_TIMEOUT",
        gt=0
    )
    
    # Storage backend
    storage_backend: str = Field(
        default="local",
        description="Storage backend (local, s3)",
        env="FILE_STORAGE_BACKEND"
    )
    
    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        """Parse extensions from string or set."""
        if isinstance(v, str):
            extensions = {ext.strip().lower() for ext in v.split(",") if ext.strip()}
            # Ensure extensions start with dot
            return {ext if ext.startswith(".") else f".{ext}" for ext in extensions}
        return {ext.lower() for ext in v}
    
    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def parse_mime_types(cls, v):
        """Parse MIME types from string or set."""
        if isinstance(v, str):
            return {mime.strip().lower() for mime in v.split(",") if mime.strip()}
        return {mime.lower() for mime in v}
    
    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, v):
        """Validate storage backend."""
        allowed_backends = ["local", "s3"]
        if v.lower() not in allowed_backends:
            raise ValueError(f"Storage backend must be one of: {allowed_backends}")
        return v.lower()


class VideoConfig(BaseConfiguration):
    """Video processing configuration."""
    
    # Output settings
    output_directory: Path = Field(
        default=Path("./videos"),
        description="Video output directory",
        env="VIDEO_OUTPUT_DIRECTORY"
    )
    temp_directory: Path = Field(
        default=Path("./temp/videos"),
        description="Video temporary directory",
        env="VIDEO_TEMP_DIRECTORY"
    )
    
    # Quality settings
    default_quality: VideoQuality = Field(
        default=VideoQuality.MEDIUM,
        description="Default video quality",
        env="VIDEO_DEFAULT_QUALITY"
    )
    max_duration_seconds: int = Field(
        default=600,  # 10 minutes
        description="Maximum video duration in seconds",
        env="VIDEO_MAX_DURATION_SECONDS",
        gt=0
    )
    max_resolution_width: int = Field(
        default=1920,
        description="Maximum video width",
        env="VIDEO_MAX_RESOLUTION_WIDTH",
        gt=0
    )
    max_resolution_height: int = Field(
        default=1080,
        description="Maximum video height",
        env="VIDEO_MAX_RESOLUTION_HEIGHT",
        gt=0
    )
    
    # Processing settings
    processing_timeout: int = Field(
        default=3600,  # 1 hour
        description="Video processing timeout in seconds",
        env="VIDEO_PROCESSING_TIMEOUT",
        gt=0
    )
    max_concurrent_jobs: int = Field(
        default=5,
        description="Maximum concurrent video processing jobs",
        env="VIDEO_MAX_CONCURRENT_JOBS",
        gt=0
    )
    cleanup_temp_files: bool = Field(
        default=True,
        description="Cleanup temporary files after processing",
        env="VIDEO_CLEANUP_TEMP_FILES"
    )
    
    # Encoding settings
    video_codec: str = Field(
        default="h264",
        description="Video codec",
        env="VIDEO_CODEC"
    )
    audio_codec: str = Field(
        default="aac",
        description="Audio codec",
        env="VIDEO_AUDIO_CODEC"
    )
    bitrate_kbps: int = Field(
        default=2000,
        description="Video bitrate in kbps",
        env="VIDEO_BITRATE_KBPS",
        gt=0
    )
    framerate: int = Field(
        default=30,
        description="Video framerate",
        env="VIDEO_FRAMERATE",
        gt=0,
        le=120
    )
    
    @field_validator("video_codec")
    @classmethod
    def validate_video_codec(cls, v):
        """Validate video codec."""
        allowed_codecs = ["h264", "h265", "vp8", "vp9", "av1"]
        if v.lower() not in allowed_codecs:
            raise ValueError(f"Video codec must be one of: {allowed_codecs}")
        return v.lower()
    
    @field_validator("audio_codec")
    @classmethod
    def validate_audio_codec(cls, v):
        """Validate audio codec."""
        allowed_codecs = ["aac", "mp3", "opus", "vorbis"]
        if v.lower() not in allowed_codecs:
            raise ValueError(f"Audio codec must be one of: {allowed_codecs}")
        return v.lower()


class AuthenticationConfig(BaseConfiguration):
    """Authentication configuration."""
    
    # Clerk settings
    clerk_secret_key: SecretStr = Field(
        default="",
        description="Clerk secret key",
        env="CLERK_SECRET_KEY"
    )
    clerk_publishable_key: str = Field(
        default="",
        description="Clerk publishable key",
        env="CLERK_PUBLISHABLE_KEY"
    )
    clerk_webhook_secret: Optional[SecretStr] = Field(
        default=None,
        description="Clerk webhook secret",
        env="CLERK_WEBHOOK_SECRET"
    )
    clerk_jwt_verification: bool = Field(
        default=True,
        description="Enable Clerk JWT verification",
        env="CLERK_JWT_VERIFICATION"
    )
    
    # Session settings
    session_cookie_name: str = Field(
        default="session",
        description="Session cookie name",
        env="AUTH_SESSION_COOKIE_NAME"
    )
    session_cookie_secure: bool = Field(
        default=False,
        description="Secure session cookies (HTTPS only)",
        env="AUTH_SESSION_COOKIE_SECURE"
    )
    session_cookie_httponly: bool = Field(
        default=True,
        description="HTTP-only session cookies",
        env="AUTH_SESSION_COOKIE_HTTPONLY"
    )
    session_cookie_samesite: str = Field(
        default="lax",
        description="SameSite session cookie policy",
        env="AUTH_SESSION_COOKIE_SAMESITE"
    )
    session_max_age: int = Field(
        default=86400,  # 24 hours
        description="Session maximum age in seconds",
        env="AUTH_SESSION_MAX_AGE",
        gt=0
    )
    
    # API key authentication
    api_key_header: str = Field(
        default="X-API-Key",
        description="API key header name",
        env="AUTH_API_KEY_HEADER"
    )
    api_key_enabled: bool = Field(
        default=False,
        description="Enable API key authentication",
        env="AUTH_API_KEY_ENABLED"
    )
    
    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_samesite(cls, v):
        """Validate SameSite cookie policy."""
        allowed_values = ["strict", "lax", "none"]
        if v.lower() not in allowed_values:
            raise ValueError(f"SameSite must be one of: {allowed_values}")
        return v.lower()


class ApplicationConfig(BaseConfiguration):
    """
    Main application configuration that combines all configuration sections.
    
    This class aggregates all configuration modules and provides
    environment-specific settings and validation.
    """
    
    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment",
        env="ENVIRONMENT"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
        env="DEBUG"
    )
    testing: bool = Field(
        default=False,
        description="Enable testing mode",
        env="TESTING"
    )
    
    # Configuration sections
    server: ServerConfig = Field(default_factory=ServerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    file_storage: FileStorageConfig = Field(default_factory=FileStorageConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    
    # Feature flags
    features_enabled: Set[str] = Field(
        default=set(),
        description="Enabled feature flags",
        env="FEATURES_ENABLED"
    )
    
    # Health check settings
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health check endpoint",
        env="HEALTH_CHECK_ENABLED"
    )
    health_check_path: str = Field(
        default="/health",
        description="Health check endpoint path",
        env="HEALTH_CHECK_PATH"
    )
    
    @field_validator("features_enabled", mode="before")
    @classmethod
    def parse_features(cls, v):
        """Parse features from string or set."""
        if isinstance(v, str):
            return {feature.strip().lower() for feature in v.split(",") if feature.strip()}
        return {feature.lower() for feature in v}
    
    @model_validator(mode='after')
    def validate_environment_settings(self) -> Self:
        """Validate environment-specific settings."""
        # Auto-configure debug mode for development
        if self.environment == Environment.DEVELOPMENT and self.debug is None:
            self.debug = True
        
        # Auto-configure testing mode
        if self.environment == Environment.TESTING:
            self.testing = True
            self.debug = True
        
        # Production safety checks
        if self.environment == Environment.PRODUCTION:
            if self.debug:
                raise ValueError("Debug mode cannot be enabled in production")
            if self.testing:
                raise ValueError("Testing mode cannot be enabled in production")
        
        return self
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.environment == Environment.STAGING
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == Environment.TESTING or self.testing
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return feature_name.lower() in self.features_enabled
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins with environment-specific defaults."""
        if self.is_development:
            # Add common development origins
            default_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ]
            return list(set(self.cors.allow_origins + default_origins))
        return self.cors.allow_origins
    
    def get_log_level(self) -> str:
        """Get log level with environment-specific defaults."""
        if self.is_development or self.debug:
            return "DEBUG"
        elif self.is_testing:
            return "WARNING"  # Reduce noise in tests
        else:
            return self.logging.level.value
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
        validate_assignment = True
        use_enum_values = True
        
        # Allow nested configuration from environment variables
        env_nested_delimiter = "__"
        
        # Configuration validation
        validate_default = True
        arbitrary_types_allowed = True

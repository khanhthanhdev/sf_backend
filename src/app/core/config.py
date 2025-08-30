"""
Application configuration using Pydantic BaseSettings.
Supports environment-based configuration with validation.
"""

import os
from typing import Optional, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="FastAPI Video Backend", env="APP_NAME")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=True, env="RELOAD")
    
    # API settings
    api_v1_prefix: str = Field(default="/api/v1", env="API_V1_PREFIX")
    docs_url: str = Field(default="/docs", env="DOCS_URL")
    redoc_url: str = Field(default="/redoc", env="REDOC_URL")
    openapi_url: str = Field(default="/openapi.json", env="OPENAPI_URL")
    
    # CORS settings
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000",
        env="ALLOWED_ORIGINS"
    )
    # Optional single frontend URL to auto-append (simpler than editing comma list)
    frontend_url: Optional[str] = Field(default=None, env="FRONTEND_URL")
    allowed_methods: str = Field(
        default="GET,POST,PUT,DELETE,OPTIONS",
        env="ALLOWED_METHODS"
    )
    allowed_headers: str = Field(
        default="*",
        env="ALLOWED_HEADERS"
    )
    
    # Redis settings
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    
    # Clerk authentication settings
    clerk_secret_key: str = Field(default="", env="CLERK_SECRET_KEY")
    clerk_publishable_key: str = Field(default="", env="CLERK_PUBLISHABLE_KEY")
    clerk_webhook_secret: Optional[str] = Field(default=None, env="CLERK_WEBHOOK_SECRET")
    clerk_jwt_verification: bool = Field(default=True, env="CLERK_JWT_VERIFICATION")
    
    # Job queue settings
    job_queue_name: str = Field(default="video_generation_queue", env="JOB_QUEUE_NAME")
    job_queue_max_size: int = Field(default=1000, env="JOB_QUEUE_MAX_SIZE")
    job_default_timeout: int = Field(default=3600, env="JOB_DEFAULT_TIMEOUT")  # 1 hour
    job_retry_attempts: int = Field(default=3, env="JOB_RETRY_ATTEMPTS")
    
    # File storage settings
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")
    file_storage_path: str = Field(default="./storage", env="FILE_STORAGE_PATH")
    max_file_size: int = Field(default=100 * 1024 * 1024, env="MAX_FILE_SIZE")  # 100MB
    allowed_file_types: List[str] = Field(
        default=["image/jpeg", "image/png", "image/gif", "video/mp4", "text/plain"],
        env="ALLOWED_FILE_TYPES"
    )
    
    # Rate limiting settings
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    rate_limit_per_user: int = Field(default=50, env="RATE_LIMIT_PER_USER")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or text
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    log_rotation: str = Field(default="1 day", env="LOG_ROTATION")
    log_retention: str = Field(default="30 days", env="LOG_RETENTION")
    
    # Security settings
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Video generation settings
    video_output_dir: str = Field(default="./videos", env="VIDEO_OUTPUT_DIR")
    video_quality_default: str = Field(default="medium", env="VIDEO_QUALITY_DEFAULT")
    video_max_duration: int = Field(default=600, env="VIDEO_MAX_DURATION")  # 10 minutes
    
    # Health check settings
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")  # seconds
    health_check_timeout: int = Field(default=5, env="HEALTH_CHECK_TIMEOUT")  # seconds
    
    def get_allowed_origins(self) -> List[str]:
        """Parse CORS origins from string."""
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        if self.frontend_url:
            fe = self.frontend_url.strip()
            if fe and fe not in origins:
                origins.append(fe)
        return origins
    
    def get_allowed_methods(self) -> List[str]:
        """Parse CORS methods from string."""
        return [method.strip() for method in self.allowed_methods.split(",")]
    
    def get_allowed_headers(self) -> List[str]:
        """Parse CORS headers from string."""
        return [header.strip() for header in self.allowed_headers.split(",")]
    
    def get_allowed_file_types(self) -> List[str]:
        """Get allowed file types list."""
        return self.allowed_file_types
    
    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def parse_file_types(cls, v):
        """Parse allowed file types from string or list."""
        if isinstance(v, str) and not v.startswith('['):
            # Handle comma-separated string format
            return [file_type.strip() for file_type in v.split(",")]
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of: {valid_formats}")
        return v.lower()
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment."""
        valid_environments = ["development", "staging", "production", "testing"]
        if v.lower() not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        return v.lower()
    
    @field_validator("video_quality_default")
    @classmethod
    def validate_video_quality(cls, v):
        """Validate video quality."""
        valid_qualities = ["low", "medium", "high", "ultra"]
        if v.lower() not in valid_qualities:
            raise ValueError(f"Video quality must be one of: {valid_qualities}")
        return v.lower()
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == "testing"
    
    def get_redis_url(self) -> str:
        """Get Redis URL with proper formatting."""
        if self.redis_url:
            return self.redis_url
        
        auth_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra fields from .env
    }


# Global settings instance
# settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
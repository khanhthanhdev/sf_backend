"""
Environment-specific configuration templates and examples.

This module provides configuration templates for different environments
and demonstrates best practices for configuration management.
"""

from typing import Dict, Any
from pathlib import Path

from .base import Environment
from .application import ApplicationConfig


def get_development_template() -> Dict[str, Any]:
    """Get development environment configuration template."""
    return {
        "environment": "development",
        "debug": True,
        "testing": False,
        
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 1,
            "reload": True,
            "access_log": True,
        },
        
        "api": {
            "title": "FastAPI Video Backend (Development)",
            "version": "0.1.0-dev",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        },
        
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "fastapi_dev",
            "username": "postgres",
            "ssl_mode": "prefer",
            "pool_min_size": 2,
            "pool_max_size": 10,
            "echo_queries": True,
        },
        
        "aws": {
            "region": "us-west-2",
            "s3_bucket_name": "fastapi-dev-uploads",
            "cloudwatch_enabled": False,
        },
        
        "logging": {
            "level": "DEBUG",
            "format": "text",
            "console_enabled": True,
            "console_colors": True,
            "file_enabled": False,
            "include_caller": True,
        },
        
        "cors": {
            "enabled": True,
            "allow_origins": [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ],
            "allow_credentials": True,
        },
        
        "file_storage": {
            "storage_backend": "local",
            "local_storage_path": "./storage/dev",
            "max_file_size": 100 * 1024 * 1024,  # 100MB
            "virus_scan_enabled": False,
        },
        
        "video": {
            "output_directory": "./videos/dev",
            "temp_directory": "./temp/dev",
            "default_quality": "medium",
            "max_duration_seconds": 600,
            "max_concurrent_jobs": 2,
            "processing_timeout": 1800,  # 30 minutes
        },
        
        "security": {
            "jwt_access_token_expire_minutes": 60,  # Longer for development
            "rate_limit_enabled": False,  # Disabled for development
        },
        
        "authentication": {
            "clerk_jwt_verification": True,
            "session_cookie_secure": False,  # HTTP allowed in dev
            "session_max_age": 86400,  # 24 hours
        },
        
        "features_enabled": ["debug_toolbar", "sql_profiler"],
    }


def get_testing_template() -> Dict[str, Any]:
    """Get testing environment configuration template."""
    return {
        "environment": "testing",
        "debug": True,
        "testing": True,
        
        "server": {
            "host": "127.0.0.1",
            "port": 8001,
            "workers": 1,
            "reload": False,
            "access_log": False,
        },
        
        "api": {
            "title": "FastAPI Video Backend (Testing)",
            "version": "0.1.0-test",
            "docs_url": None,  # Disabled in testing
            "redoc_url": None,
            "openapi_url": None,
        },
        
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "fastapi_test",
            "username": "postgres",
            "ssl_mode": "prefer",
            "pool_min_size": 1,
            "pool_max_size": 5,
            "echo_queries": False,
        },
        
        "aws": {
            "region": "us-west-2",
            "s3_bucket_name": "fastapi-test-uploads",
            "s3_endpoint_url": "http://localhost:9000",  # MinIO for testing
            "cloudwatch_enabled": False,
        },
        
        "logging": {
            "level": "WARNING",  # Reduce noise in tests
            "format": "json",
            "console_enabled": False,
            "file_enabled": False,
            "include_caller": False,
        },
        
        "cors": {
            "enabled": True,
            "allow_origins": ["http://testserver"],
            "allow_credentials": True,
        },
        
        "file_storage": {
            "storage_backend": "local",
            "local_storage_path": "./storage/test",
            "temp_storage_path": "./temp/test",
            "max_file_size": 10 * 1024 * 1024,  # 10MB for testing
            "virus_scan_enabled": False,
        },
        
        "video": {
            "output_directory": "./videos/test",
            "temp_directory": "./temp/test",
            "default_quality": "low",  # Faster processing
            "max_duration_seconds": 60,  # Short videos
            "max_concurrent_jobs": 1,
            "processing_timeout": 300,  # 5 minutes
        },
        
        "security": {
            "jwt_access_token_expire_minutes": 5,  # Short for testing
            "rate_limit_enabled": False,
        },
        
        "authentication": {
            "clerk_jwt_verification": False,  # Disabled for testing
            "session_cookie_secure": False,
            "session_max_age": 3600,  # 1 hour
        },
        
        "features_enabled": [],
    }


def get_staging_template() -> Dict[str, Any]:
    """Get staging environment configuration template."""
    return {
        "environment": "staging",
        "debug": False,
        "testing": False,
        
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 2,
            "reload": False,
            "access_log": True,
        },
        
        "api": {
            "title": "FastAPI Video Backend (Staging)",
            "version": "0.1.0-staging",
            "docs_url": "/docs",  # Allowed in staging
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        },
        
        "database": {
            "host": "staging-db.example.com",
            "port": 5432,
            "name": "fastapi_staging",
            "username": "app_user",
            "ssl_mode": "require",
            "pool_min_size": 5,
            "pool_max_size": 20,
            "echo_queries": False,
        },
        
        "aws": {
            "region": "us-west-2",
            "s3_bucket_name": "fastapi-staging-uploads",
            "cloudwatch_enabled": True,
            "cloudwatch_log_group": "fastapi-staging",
        },
        
        "logging": {
            "level": "INFO",
            "format": "json",
            "console_enabled": True,
            "file_enabled": True,
            "file_path": "/var/log/fastapi/app.log",
            "include_caller": False,
            "sentry_environment": "staging",
        },
        
        "cors": {
            "enabled": True,
            "allow_origins": [
                "https://staging.example.com",
                "https://staging-admin.example.com",
            ],
            "allow_credentials": True,
        },
        
        "file_storage": {
            "storage_backend": "s3",
            "max_file_size": 200 * 1024 * 1024,  # 200MB
            "virus_scan_enabled": True,
        },
        
        "video": {
            "output_directory": "/var/lib/fastapi/videos",
            "temp_directory": "/tmp/fastapi/videos",
            "default_quality": "high",
            "max_duration_seconds": 900,  # 15 minutes
            "max_concurrent_jobs": 5,
            "processing_timeout": 3600,  # 1 hour
        },
        
        "security": {
            "jwt_access_token_expire_minutes": 30,
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 100,
            "enable_hsts": True,
        },
        
        "authentication": {
            "clerk_jwt_verification": True,
            "session_cookie_secure": True,
            "session_cookie_httponly": True,
            "session_max_age": 28800,  # 8 hours
        },
        
        "features_enabled": ["monitoring", "metrics"],
    }


def get_production_template() -> Dict[str, Any]:
    """Get production environment configuration template."""
    return {
        "environment": "production",
        "debug": False,
        "testing": False,
        
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 4,
            "reload": False,
            "access_log": True,
            "keepalive_timeout": 10,
            "max_concurrent_connections": 2000,
        },
        
        "api": {
            "title": "FastAPI Video Backend",
            "version": "1.0.0",
            "docs_url": None,  # Disabled in production
            "redoc_url": None,
            "openapi_url": None,
            "max_request_size": 200 * 1024 * 1024,  # 200MB
            "request_timeout": 60,
        },
        
        "database": {
            "host": "prod-db.example.com",
            "port": 5432,
            "name": "fastapi_prod",
            "username": "app_user",
            "ssl_mode": "require",
            "pool_min_size": 10,
            "pool_max_size": 50,
            "pool_max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "echo_queries": False,
        },
        
        "aws": {
            "region": "us-west-2",
            "s3_bucket_name": "fastapi-prod-uploads",
            "s3_max_file_size": 500 * 1024 * 1024,  # 500MB
            "ses_sender_email": "noreply@example.com",
            "cloudwatch_enabled": True,
            "cloudwatch_log_group": "fastapi-production",
        },
        
        "logging": {
            "level": "INFO",
            "format": "json",
            "console_enabled": False,
            "file_enabled": True,
            "file_path": "/var/log/fastapi/app.log",
            "file_max_size": "100MB",
            "file_backup_count": 10,
            "include_timestamp": True,
            "include_caller": False,
            "sentry_environment": "production",
            "sentry_traces_sample_rate": 0.01,  # 1% sampling
        },
        
        "cors": {
            "enabled": True,
            "allow_origins": [
                "https://app.example.com",
                "https://admin.example.com",
            ],
            "allow_credentials": True,
            "max_age": 86400,  # 24 hours
        },
        
        "file_storage": {
            "storage_backend": "s3",
            "max_file_size": 500 * 1024 * 1024,  # 500MB
            "virus_scan_enabled": True,
            "virus_scan_timeout": 60,
        },
        
        "video": {
            "output_directory": "/var/lib/fastapi/videos",
            "temp_directory": "/tmp/fastapi/videos",
            "default_quality": "high",
            "max_duration_seconds": 1800,  # 30 minutes
            "max_resolution_width": 3840,  # 4K
            "max_resolution_height": 2160,
            "max_concurrent_jobs": 10,
            "processing_timeout": 7200,  # 2 hours
            "cleanup_temp_files": True,
        },
        
        "security": {
            "jwt_access_token_expire_minutes": 15,
            "jwt_refresh_token_expire_days": 7,
            "password_min_length": 12,
            "password_require_special": True,
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 60,
            "rate_limit_burst": 120,
            "enable_hsts": True,
            "hsts_max_age": 31536000,  # 1 year
        },
        
        "authentication": {
            "clerk_jwt_verification": True,
            "session_cookie_secure": True,
            "session_cookie_httponly": True,
            "session_cookie_samesite": "strict",
            "session_max_age": 14400,  # 4 hours
            "api_key_enabled": True,
        },
        
        "health_check_enabled": True,
        "health_check_path": "/health",
        
        "features_enabled": [
            "monitoring",
            "metrics", 
            "audit_logging",
            "advanced_security",
        ],
    }


def create_environment_config_file(
    environment: Environment,
    output_path: Path,
    include_secrets_template: bool = False
) -> None:
    """
    Create environment-specific configuration file.
    
    Args:
        environment: Target environment
        output_path: Path to write configuration file
        include_secrets_template: Include secrets template in comments
    """
    import json
    import yaml
    
    # Get template based on environment
    template_functions = {
        Environment.DEVELOPMENT: get_development_template,
        Environment.TESTING: get_testing_template,
        Environment.STAGING: get_staging_template,
        Environment.PRODUCTION: get_production_template,
    }
    
    template = template_functions[environment]()
    
    # Determine format based on file extension
    file_format = output_path.suffix.lower()
    
    # Add comments for secrets if requested
    if include_secrets_template:
        secrets_template = _get_secrets_template(environment)
        template["_secrets_template"] = secrets_template
    
    # Write configuration file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if file_format == ".json":
        with open(output_path, "w") as f:
            json.dump(template, f, indent=2, default=str)
    elif file_format in [".yml", ".yaml"]:
        with open(output_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")


def _get_secrets_template(environment: Environment) -> Dict[str, str]:
    """Get secrets template for environment."""
    base_secrets = {
        "database_password": "Database password",
        "app_secret_key": "Application secret key",
        "clerk_secret_key": "Clerk secret key",
        "clerk_webhook_secret": "Clerk webhook secret",
    }
    
    if environment in [Environment.STAGING, Environment.PRODUCTION]:
        base_secrets.update({
            "aws_access_key_id": "AWS access key ID",
            "aws_secret_access_key": "AWS secret access key",
            "sentry_dsn": "Sentry DSN for error reporting",
        })
    
    return base_secrets


# Export template functions for programmatic access
ENVIRONMENT_TEMPLATES = {
    Environment.DEVELOPMENT: get_development_template,
    Environment.TESTING: get_testing_template,
    Environment.STAGING: get_staging_template,
    Environment.PRODUCTION: get_production_template,
}

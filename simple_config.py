#!/usr/bin/env python3

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""
    
    # Application settings
    app_name: str = Field(default="FastAPI Video Backend", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # CORS settings as strings
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        env="ALLOWED_ORIGINS"
    )
    allowed_methods: str = Field(
        default="GET,POST,PUT,DELETE,OPTIONS",
        env="ALLOWED_METHODS"
    )
    
    # Redis settings
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    
    # Clerk settings
    clerk_secret_key: str = Field(default="", env="CLERK_SECRET_KEY")
    clerk_publishable_key: str = Field(default="", env="CLERK_PUBLISHABLE_KEY")
    
    def get_allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    def get_allowed_methods(self) -> List[str]:
        return [method.strip() for method in self.allowed_methods.split(",")]


if __name__ == "__main__":
    settings = SimpleSettings()
    print("✅ Simple config loaded successfully!")
    print(f"App: {settings.app_name}")
    print(f"Origins: {settings.get_allowed_origins()}")
    print(f"Methods: {settings.get_allowed_methods()}")
    print(f"Clerk Secret: {settings.clerk_secret_key[:20]}..." if settings.clerk_secret_key else "No Clerk secret")
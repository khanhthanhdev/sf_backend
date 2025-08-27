"""
CORS middleware for cross-origin requests.
Enhanced CORS configuration with security considerations.
"""

from typing import List, Optional, Union
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EnhancedCORSMiddleware:
    """
    Enhanced CORS middleware with additional security features.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = True,
        expose_headers: List[str] = None,
        max_age: int = 600,
        allow_origin_regex: Optional[str] = None,
    ):
        self.app = app
        self.allow_origins = allow_origins or settings.get_allowed_origins()
        self.allow_methods = allow_methods or settings.get_allowed_methods()
        self.allow_headers = allow_headers or settings.get_allowed_headers()
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers or [
            "X-Process-Time",
            "X-Request-ID",
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset"
        ]
        self.max_age = max_age
        self.allow_origin_regex = allow_origin_regex
        
        # Initialize FastAPI CORS middleware
        self.cors_middleware = FastAPICORSMiddleware(
            app=app,
            allow_origins=self.allow_origins,
            allow_credentials=self.allow_credentials,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            expose_headers=self.expose_headers,
            max_age=self.max_age,
            allow_origin_regex=self.allow_origin_regex,
        )
    
    async def __call__(self, scope, receive, send):
        """Process CORS requests with enhanced logging."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request information
        request = Request(scope, receive)
        origin = request.headers.get("origin")
        method = request.method
        
        # Log CORS requests for monitoring
        if origin and method == "OPTIONS":
            logger.debug(
                "CORS preflight request",
                origin=origin,
                method=method,
                path=request.url.path,
                allowed_origins=self.allow_origins,
            )
        elif origin:
            logger.debug(
                "CORS request",
                origin=origin,
                method=method,
                path=request.url.path,
            )
        
        # Delegate to FastAPI CORS middleware
        await self.cors_middleware(scope, receive, send)


def setup_cors_middleware(app, **kwargs) -> None:
    """
    Setup CORS middleware with default configuration.
    
    Args:
        app: FastAPI application instance
        **kwargs: Additional CORS configuration options
    """
    cors_config = {
        "allow_origins": settings.get_allowed_origins(),
        "allow_credentials": True,
        "allow_methods": settings.get_allowed_methods(),
        "allow_headers": settings.allowed_headers,
        "expose_headers": [
            "X-Process-Time",
            "X-Request-ID", 
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset"
        ],
        "max_age": 600,
    }
    
    # Override with any provided kwargs
    cors_config.update(kwargs)
    
    logger.info(
        "Setting up CORS middleware",
        allowed_origins=cors_config["allow_origins"],
        allowed_methods=cors_config["allow_methods"],
        allow_credentials=cors_config["allow_credentials"],
    )
    
    app.add_middleware(
        EnhancedCORSMiddleware,
        **cors_config
    )
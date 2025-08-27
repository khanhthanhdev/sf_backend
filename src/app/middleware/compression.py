"""
Response compression middleware.
Implements gzip compression for responses to reduce bandwidth usage.
"""

import gzip
from typing import List, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EnhancedCompressionMiddleware(BaseHTTPMiddleware):
    """
    Enhanced compression middleware with configurable options.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compressible_types: Optional[List[str]] = None,
        compression_level: int = 6,
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/favicon.ico",
        ]
        
        # Default compressible content types
        self.compressible_types = compressible_types or [
            "application/json",
            "application/javascript",
            "application/xml",
            "text/html",
            "text/css",
            "text/javascript",
            "text/plain",
            "text/xml",
            "text/csv",
            "image/svg+xml",
        ]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply compression to eligible responses.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: Potentially compressed HTTP response
        """
        # Skip compression for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        # Process the request
        response = await call_next(request)
        
        # Check if response should be compressed
        if not self._should_compress(response):
            return response
        
        # Apply compression
        return await self._compress_response(response)
    
    def _should_compress(self, response: Response) -> bool:
        """
        Determine if response should be compressed.
        
        Args:
            response: HTTP response
            
        Returns:
            bool: True if response should be compressed
        """
        # Skip if already compressed
        if response.headers.get("content-encoding"):
            return False
        
        # Check content type
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in self.compressible_types:
            return False
        
        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.minimum_size:
            return False
        
        # Skip for certain status codes
        if response.status_code < 200 or response.status_code >= 300:
            if response.status_code not in [404, 410]:  # Compress common error pages
                return False
        
        return True
    
    async def _compress_response(self, response: Response) -> Response:
        """
        Compress response body using gzip.
        
        Args:
            response: HTTP response to compress
            
        Returns:
            Response: Compressed HTTP response
        """
        try:
            # Get response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Compress the body
            compressed_body = gzip.compress(body, compresslevel=self.compression_level)
            
            # Calculate compression ratio
            original_size = len(body)
            compressed_size = len(compressed_body)
            compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            # Log compression stats for monitoring
            if settings.debug:
                logger.debug(
                    "Response compressed",
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_ratio=f"{compression_ratio:.1f}%",
                    content_type=response.headers.get("content-type"),
                )
            
            # Update response headers
            response.headers["content-encoding"] = "gzip"
            response.headers["content-length"] = str(compressed_size)
            response.headers["vary"] = "Accept-Encoding"
            
            # Add compression info header for debugging
            if settings.debug:
                response.headers["X-Compression-Ratio"] = f"{compression_ratio:.1f}%"
                response.headers["X-Original-Size"] = str(original_size)
            
            # Create new response with compressed body
            return Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to compress response",
                error=str(e),
                content_type=response.headers.get("content-type"),
            )
            # Return original response if compression fails
            return response


def setup_compression_middleware(app: ASGIApp, **kwargs) -> None:
    """
    Setup response compression middleware.
    
    Args:
        app: FastAPI application instance
        **kwargs: Additional compression configuration options
    """
    # Use FastAPI's built-in GZip middleware for simplicity in production
    # or our enhanced version for more control
    use_enhanced = kwargs.pop("use_enhanced", settings.debug)
    
    if use_enhanced:
        compression_config = {
            "minimum_size": 500,
            "compression_level": 6,
            "exclude_paths": [
                "/health",
                "/metrics", 
                "/favicon.ico",
                "/docs",
                "/redoc",
                "/openapi.json",
            ],
            "compressible_types": [
                "application/json",
                "application/javascript", 
                "application/xml",
                "text/html",
                "text/css",
                "text/javascript",
                "text/plain",
                "text/xml",
                "text/csv",
                "image/svg+xml",
            ],
        }
        
        # Override with any provided kwargs
        compression_config.update(kwargs)
        
        logger.info(
            "Setting up enhanced compression middleware",
            minimum_size=compression_config["minimum_size"],
            compression_level=compression_config["compression_level"],
            compressible_types_count=len(compression_config["compressible_types"]),
        )
        
        app.add_middleware(EnhancedCompressionMiddleware, **compression_config)
    else:
        # Use FastAPI's built-in GZip middleware
        minimum_size = kwargs.get("minimum_size", 500)
        
        logger.info(
            "Setting up standard GZip compression middleware",
            minimum_size=minimum_size,
        )
        
        app.add_middleware(GZipMiddleware, minimum_size=minimum_size)
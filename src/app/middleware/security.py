"""
Security headers middleware.
Implements various security headers to protect against common web vulnerabilities.
"""

from typing import Dict, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to HTTP responses.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        force_https: bool = None,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        content_type_nosniff: bool = True,
        x_frame_options: str = "DENY",
        x_content_type_options: str = "nosniff",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: Optional[str] = None,
        csp_policy: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(app)
        self.force_https = force_https if force_https is not None else settings.is_production
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.content_type_nosniff = content_type_nosniff
        self.x_frame_options = x_frame_options
        self.x_content_type_options = x_content_type_options
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy
        self.csp_policy = csp_policy
        self.custom_headers = custom_headers or {}
        
        # Default Content Security Policy for API
        if not self.csp_policy:
            self.csp_policy = self._get_default_csp_policy()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response, request)
        
        return response
    
    def _add_security_headers(self, response: Response, request: Request) -> None:
        """
        Add all configured security headers to the response.
        
        Args:
            response: HTTP response
            request: HTTP request
        """
        # X-Content-Type-Options
        if self.x_content_type_options:
            response.headers["X-Content-Type-Options"] = self.x_content_type_options
        
        # X-Frame-Options
        if self.x_frame_options:
            response.headers["X-Frame-Options"] = self.x_frame_options
        
        # Referrer-Policy
        if self.referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy
        
        # Permissions-Policy (formerly Feature-Policy)
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy
        
        # Content-Security-Policy (different policies for different endpoints)
        csp_policy = self._get_csp_policy_for_path(request.url.path)
        if csp_policy:
            response.headers["Content-Security-Policy"] = csp_policy
        
        # Strict-Transport-Security (HSTS) - only for HTTPS
        if self.force_https and self._is_https_request(request):
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value
        
        # X-XSS-Protection (legacy, but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Remove server information
        if "Server" in response.headers:
            del response.headers["Server"]
        
        # Add custom headers
        for header_name, header_value in self.custom_headers.items():
            response.headers[header_name] = header_value
        
        # Add security-related custom headers
        response.headers["X-API-Version"] = settings.app_version
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        
        # Add cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    
    def _get_default_csp_policy(self) -> str:
        """
        Get default Content Security Policy for API.
        
        Returns:
            str: CSP policy string
        """
        # Restrictive CSP for API endpoints
        csp_directives = [
            "default-src 'none'",
            "script-src 'none'",
            "style-src 'none'",
            "img-src 'none'",
            "font-src 'none'",
            "connect-src 'self'",
            "media-src 'none'",
            "object-src 'none'",
            "child-src 'none'",
            "frame-src 'none'",
            "worker-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'none'",
            "base-uri 'none'",
            "manifest-src 'none'",
        ]
        
        # Allow resources needed for Swagger UI and ReDoc in development
        if not settings.is_production:
            csp_directives = [
                "default-src 'none'",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
                "img-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com",
                "font-src 'self' https://cdn.jsdelivr.net https://unpkg.com",
                "connect-src 'self'",
                "media-src 'none'",
                "object-src 'none'",
                "child-src 'none'",
                "frame-src 'none'",
                "worker-src 'none'",
                "frame-ancestors 'none'",
                "form-action 'none'",
                "base-uri 'none'",
                "manifest-src 'none'",
            ]
        
        return "; ".join(csp_directives)
    
    def _get_csp_policy_for_path(self, path: str) -> str:
        """
        Get CSP policy based on request path.
        
        Args:
            path: Request path
            
        Returns:
            str: CSP policy string
        """
        # Relaxed CSP for documentation endpoints
        if path in ["/docs", "/redoc"] or path.startswith("/docs") or path.startswith("/redoc"):
            return "; ".join([
                "default-src 'none'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
                "img-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com https://fastapi.tiangolo.com",
                "font-src 'self' https://cdn.jsdelivr.net https://unpkg.com",
                "connect-src 'self'",
                "media-src 'none'",
                "object-src 'none'",
                "child-src 'none'",
                "frame-src 'none'",
                "worker-src 'none'",
                "frame-ancestors 'none'",
                "form-action 'none'",
                "base-uri 'none'",
                "manifest-src 'none'",
            ])
        
        # Use default CSP for other endpoints
        return self.csp_policy
    
    def _is_https_request(self, request: Request) -> bool:
        """
        Check if request is using HTTPS.
        
        Args:
            request: HTTP request
            
        Returns:
            bool: True if HTTPS request
        """
        # Check scheme
        if request.url.scheme == "https":
            return True
        
        # Check forwarded headers (behind proxy/load balancer)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto and forwarded_proto.lower() == "https":
            return True
        
        forwarded_ssl = request.headers.get("x-forwarded-ssl")
        if forwarded_ssl and forwarded_ssl.lower() == "on":
            return True
        
        return False
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """
        Check if endpoint contains sensitive data.
        
        Args:
            path: Request path
            
        Returns:
            bool: True if endpoint is sensitive
        """
        sensitive_patterns = [
            "/api/v1/auth/",
            "/api/v1/users/",
            "/api/v1/jobs/",
            "/api/v1/videos/",
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limiting headers.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        default_limit: int = None,
        default_window: int = None,
    ):
        super().__init__(app)
        self.default_limit = default_limit or settings.rate_limit_requests
        self.default_window = default_window or settings.rate_limit_window
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Add rate limiting headers to response.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response: HTTP response with rate limit headers
        """
        response = await call_next(request)
        
        # Add rate limit headers (these would be populated by actual rate limiting logic)
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Window"] = str(self.default_window)
        
        # These would be calculated by actual rate limiting middleware
        # For now, just add placeholder values
        response.headers["X-RateLimit-Remaining"] = str(self.default_limit - 1)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.default_window)
        
        return response


def setup_security_middleware(app: ASGIApp, **kwargs) -> None:
    """
    Setup security headers middleware with default configuration.
    
    Args:
        app: FastAPI application instance
        **kwargs: Additional security configuration options
    """
    security_config = {
        "force_https": settings.is_production,
        "hsts_max_age": 31536000,  # 1 year
        "hsts_include_subdomains": True,
        "hsts_preload": False,
        "x_frame_options": "DENY",
        "x_content_type_options": "nosniff",
        "referrer_policy": "strict-origin-when-cross-origin",
        "permissions_policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        ),
        "custom_headers": {
            "X-API-Name": settings.app_name,
            "X-Environment": settings.environment,
        },
    }
    
    # Override with any provided kwargs
    security_config.update(kwargs)
    
    logger.info(
        "Setting up security headers middleware",
        force_https=security_config["force_https"],
        hsts_max_age=security_config["hsts_max_age"],
        environment=settings.environment,
    )
    
    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware, **security_config)
    
    # Add rate limit headers middleware
    app.add_middleware(RateLimitHeadersMiddleware)


# Import time for rate limit headers
import time
# Middleware Implementation

This directory contains the enhanced middleware implementations for the FastAPI backend, implementing task 8.2 from the specification.

## Implemented Middleware

### 1. CORS Middleware (`cors.py`)
- **Purpose**: Handle cross-origin requests with enhanced security
- **Features**:
  - Configurable allowed origins, methods, and headers
  - Enhanced logging for CORS requests
  - Support for credentials and preflight requests
  - Exposed headers for client access to custom headers

### 2. Request/Response Logging Middleware (`logging.py`)
- **Purpose**: Comprehensive request/response logging with performance metrics
- **Features**:
  - Unique request ID generation for tracing
  - Request and response timing measurements
  - Client IP extraction (supports proxy headers)
  - Configurable request/response body logging
  - Performance warning headers for slow requests
  - Separate performance metrics collection

### 3. Response Compression Middleware (`compression.py`)
- **Purpose**: Reduce bandwidth usage through response compression
- **Features**:
  - Gzip compression with configurable compression levels
  - Content-type based compression filtering
  - Minimum size thresholds
  - Compression ratio reporting (in debug mode)
  - Fallback to standard FastAPI GZip middleware

### 4. Security Headers Middleware (`security.py`)
- **Purpose**: Add comprehensive security headers to protect against web vulnerabilities
- **Features**:
  - Content Security Policy (CSP) with restrictive defaults
  - HTTP Strict Transport Security (HSTS) for HTTPS
  - X-Frame-Options, X-Content-Type-Options, Referrer-Policy
  - Permissions-Policy for feature restrictions
  - Server header removal
  - Rate limiting headers
  - Cache control for sensitive endpoints

## Middleware Order

The middleware is applied in the following order (from outer to inner):

1. **Trusted Host Middleware** (FastAPI built-in, production only)
2. **Security Headers Middleware** (custom)
3. **CORS Middleware** (enhanced custom)
4. **Response Compression Middleware** (custom/built-in)
5. **Request Logging Middleware** (custom)
6. **Clerk Authentication Middleware** (existing)

## Configuration

All middleware can be configured through the application settings in `core/config.py`:

```python
# CORS settings
allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allowed_headers: List[str] = ["*"]

# Rate limiting settings
rate_limit_requests: int = 100
rate_limit_window: int = 60

# Logging settings
log_level: str = "INFO"
debug: bool = False
```

## Usage

The middleware is automatically set up in `main.py` using the setup functions:

```python
from .middleware import (
    setup_cors_middleware,
    setup_logging_middleware,
    setup_compression_middleware,
    setup_security_middleware,
)

# In setup_middleware function:
setup_security_middleware(app)
setup_cors_middleware(app)
setup_compression_middleware(app)
setup_logging_middleware(app)
```

## Headers Added

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: <restrictive-policy>`
- `Permissions-Policy: <feature-restrictions>`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HTTPS only)

### Performance Headers
- `X-Process-Time: <milliseconds>`
- `X-Request-ID: <uuid>`
- `X-Request-Count: <count>`
- `X-Average-Duration: <milliseconds>`
- `X-Performance-Warning: slow|very-slow` (when applicable)

### CORS Headers
- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Methods`
- `Access-Control-Allow-Headers`
- `Access-Control-Expose-Headers`
- `Access-Control-Allow-Credentials`

### Compression Headers
- `Content-Encoding: gzip`
- `Vary: Accept-Encoding`
- `X-Compression-Ratio: <percentage>` (debug mode)

## Requirements Satisfied

This implementation satisfies the following requirements from task 8.2:

✅ **Implement CORS middleware for cross-origin requests**
- Enhanced CORS middleware with logging and security features

✅ **Create request logging middleware with performance metrics**
- Comprehensive logging with timing, request IDs, and performance warnings
- Separate performance metrics collection middleware

✅ **Add response compression middleware**
- Configurable gzip compression with content-type filtering
- Compression ratio reporting and fallback options

✅ **Implement security headers middleware**
- Comprehensive security headers including CSP, HSTS, and frame options
- Rate limiting headers and cache control for sensitive endpoints

All middleware is production-ready with proper error handling, logging, and configuration options.
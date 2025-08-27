# User Management Utilities

This module provides comprehensive user management utilities for Clerk authentication integration in the FastAPI backend.

## Overview

The user management utilities are designed to handle:

1. **User Data Extraction** - Extract and process user data from Clerk
2. **Session Management** - Manage user sessions and authentication context
3. **Permission Checking** - Validate user permissions and access control

## Core Components

### UserDataExtractor

Handles extraction and processing of user data from Clerk API.

```python
from app.utils.user_utils import UserDataExtractor
from app.core.auth import get_clerk_manager

# Initialize extractor
clerk_manager = get_clerk_manager()
extractor = UserDataExtractor(clerk_manager)

# Extract user data
clerk_user = await extractor.extract_user_from_clerk("user_123")
user_profile = extractor.create_user_profile(clerk_user)
metadata = extractor.extract_user_metadata(clerk_user)
```

### UserSessionManager

Manages user sessions and authentication context.

```python
from app.utils.user_utils import UserSessionManager

# Initialize session manager
session_manager = UserSessionManager(clerk_manager)

# Create session from token
session = await session_manager.create_user_session("clerk_token")

# Create complete authentication context
auth_context = await session_manager.create_authentication_context("clerk_token")

# Validate session
is_valid = await session_manager.validate_session(session)
```

### UserPermissionChecker

Handles permission validation and access control.

```python
from app.utils.user_utils import UserPermissionChecker

# Initialize permission checker
permission_checker = UserPermissionChecker(clerk_manager)

# Check user permissions
permissions = await permission_checker.check_user_permissions("user_123")

# Validate specific permission
permissions = await permission_checker.check_user_permissions("user_123", "generate_videos")

# Validate resource access
has_access = await permission_checker.validate_user_access("user_123", "job", "job_456")
```

## Utility Functions

### Quick Access Functions

```python
from app.utils.user_utils import (
    extract_user_from_token,
    create_auth_context,
    validate_user_permission
)

# Extract user from token
user = await extract_user_from_token("clerk_token")

# Create authentication context
context = await create_auth_context("clerk_token")

# Validate permission
has_permission = await validate_user_permission("user_123", "admin_access")
```

### Session Caching

```python
from app.utils.user_utils import get_session_cache

# Get session cache
cache = get_session_cache()

# Cache authentication context
cache.set("session_id", auth_context)

# Retrieve cached context
cached_context = cache.get("session_id")

# Clear expired sessions
cache.clear_expired()
```

## FastAPI Integration

The utilities integrate seamlessly with FastAPI dependency injection:

```python
from fastapi import APIRouter, Depends
from app.utils.auth_integration_example import (
    get_current_user,
    get_verified_user,
    get_admin_user,
    require_permission,
    check_rate_limits
)

router = APIRouter()

@router.get("/profile")
async def get_profile(
    current_user: AuthenticationContext = Depends(get_current_user)
):
    """Get user profile - requires authentication."""
    return {"user": current_user.user}

@router.post("/videos/generate")
async def generate_video(
    request: VideoGenerationRequest,
    current_user: AuthenticationContext = Depends(get_verified_user),
    _rate_check: AuthenticationContext = Depends(check_rate_limits)
):
    """Generate video - requires verified user and rate limit check."""
    # Implementation here
    pass

@router.get("/admin/metrics")
async def get_metrics(
    current_user: AuthenticationContext = Depends(get_admin_user)
):
    """Get system metrics - admin only."""
    # Implementation here
    pass

@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: AuthenticationContext = Depends(require_permission("delete_jobs"))
):
    """Delete job - requires specific permission."""
    # Implementation here
    pass
```

## Error Handling

The utilities provide consistent error handling:

```python
from app.core.auth import ClerkAuthError
from fastapi import HTTPException, status

try:
    auth_context = await create_auth_context(token)
except ClerkAuthError as e:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(e)
    )
```

## Requirements Compliance

This implementation satisfies the following requirements:

- **Requirement 6.1**: Returns 401 unauthorized for invalid/missing tokens
- **Requirement 6.2**: Returns 401 unauthorized for expired tokens  
- **Requirement 6.3**: Extracts user information from valid tokens
- **Requirement 6.4**: Retrieves user information from Clerk's system
- **Requirement 8.1**: Returns appropriate HTTP status codes with consistent error format

## Usage Examples

### Basic Authentication

```python
# In your FastAPI endpoint
@router.get("/protected")
async def protected_endpoint(
    current_user: AuthenticationContext = Depends(get_current_user)
):
    return {
        "message": f"Hello {current_user.user.full_name}",
        "user_id": current_user.user_id,
        "permissions": current_user.permissions.dict()
    }
```

### Permission-Based Access

```python
# Require specific permission
@router.post("/admin/action")
async def admin_action(
    current_user: AuthenticationContext = Depends(require_permission("admin_access"))
):
    return {"message": "Admin action performed"}
```

### Rate Limiting

```python
# Check rate limits before processing
@router.post("/expensive-operation")
async def expensive_operation(
    current_user: AuthenticationContext = Depends(check_rate_limits)
):
    # Rate limits are automatically checked
    return {"message": "Operation completed"}
```

## Testing

The utilities include comprehensive test coverage:

```bash
# Run tests
python -m pytest tests/test_user_utils.py -v
```

## Configuration

The utilities use the existing Clerk configuration from `app.core.config`:

```python
# Required environment variables
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_JWT_VERIFICATION=true  # Set to false for development only
ENVIRONMENT=development  # or production
```

## Security Considerations

1. **Token Validation**: All tokens are validated with Clerk before processing
2. **Session Caching**: Sessions are cached with appropriate TTL
3. **Permission Checking**: Granular permission validation
4. **Rate Limiting**: Built-in rate limiting support
5. **Error Handling**: Secure error messages that don't expose sensitive data

## Future Enhancements

1. **Redis Integration**: Replace in-memory cache with Redis
2. **Advanced Permissions**: Role-based access control (RBAC)
3. **Audit Logging**: Track user actions and permissions
4. **Token Refresh**: Automatic token refresh handling
5. **Multi-tenant Support**: Organization-based access control
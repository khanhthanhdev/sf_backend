# Utility functions

from .user_utils import (
    UserDataExtractor,
    UserSessionManager,
    UserPermissionChecker,
    extract_user_from_token,
    create_auth_context,
    validate_user_permission,
    require_permission,
    SessionCache,
    get_session_cache
)

from .file_utils import (
    FileManager,
    FileMetadata,
    FileValidationResult,
    validate_upload_file,
    store_upload_file,
    delete_stored_file,
    cleanup_old_files,
    generate_file_url,
    file_manager
)

from .file_serving import (
    FileServingManager,
    file_serving_manager,
    serve_file_secure,
    generate_secure_file_url,
    generate_thumbnail_url,
    generate_streaming_url
)

from .file_cache import (
    FileCacheManager,
    file_cache_manager,
    cache_file_metadata,
    get_cached_file_metadata,
    track_file_access,
    get_file_access_statistics
)

__all__ = [
    "UserDataExtractor",
    "UserSessionManager", 
    "UserPermissionChecker",
    "extract_user_from_token",
    "create_auth_context",
    "validate_user_permission",
    "require_permission",
    "SessionCache",
    "get_session_cache",
    "FileManager",
    "FileMetadata",
    "FileValidationResult",
    "validate_upload_file",
    "store_upload_file",
    "delete_stored_file",
    "cleanup_old_files",
    "generate_file_url",
    "file_manager",
    "FileServingManager",
    "file_serving_manager",
    "serve_file_secure",
    "generate_secure_file_url",
    "generate_thumbnail_url",
    "generate_streaming_url",
    "FileCacheManager",
    "file_cache_manager",
    "cache_file_metadata",
    "get_cached_file_metadata",
    "track_file_access",
    "get_file_access_statistics"
]

# FastAPI integration utilities are available in auth_integration_example.py
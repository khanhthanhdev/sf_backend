"""
Infrastructure layer for the video generation system.

This package contains the infrastructure concerns such as:
- Repository implementations
- Database adapters
- External service integrations
- Configuration and dependency injection
"""

from .repositories import (
    # Repository interfaces
    IVideoRepository,
    IUserRepository,
    IJobRepository,
    IFileRepository,
    
    # Concrete implementations
    VideoRepository,
    UserRepository,
    JobRepository,
    FileRepository,
    
    # Base repository
    BaseRepository,
    PaginationParams,
    PaginatedResult,
    
    # Session management
    RepositoryManager,
    UnitOfWork,
)

# Import session management functions
from .repositories.session_manager import (
    get_repository_manager,
    get_unit_of_work,
    get_video_repository,
    get_user_repository,
    get_job_repository,
    get_file_repository,
    repository_session,
    unit_of_work_session,
    RepositoryFactory,
)

__all__ = [
    # Repository interfaces
    "IVideoRepository",
    "IUserRepository", 
    "IJobRepository",
    "IFileRepository",
    
    # Concrete implementations
    "VideoRepository",
    "UserRepository",
    "JobRepository", 
    "FileRepository",
    
    # Base repository and utilities
    "BaseRepository",
    "PaginationParams",
    "PaginatedResult",
    
    # Session management
    "RepositoryManager",
    "UnitOfWork",
    
    # Dependency injection functions
    "get_repository_manager",
    "get_unit_of_work",
    "get_video_repository",
    "get_user_repository",
    "get_job_repository",
    "get_file_repository",
    
    # Manual session management
    "repository_session",
    "unit_of_work_session",
    "RepositoryFactory",
]

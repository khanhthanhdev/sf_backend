"""
Repository layer for data persistence abstraction.

This package provides repository interfaces and their concrete implementations
for managing domain entities in the persistence layer.
"""

from .interfaces import (
    # Base classes
    BaseRepository,
    PaginationParams,
    PaginatedResult,
    
    # Repository interfaces
    IVideoRepository,
    IUserRepository,
    IJobRepository,
    IFileRepository,
)

from .implementations import (
    # Concrete implementations
    VideoRepository,
    UserRepository,
    JobRepository,
    FileRepository,
)

from .session_manager import (
    # Session management
    RepositoryManager,
    UnitOfWork,
    get_repository_manager,
)

from .mappers import (
    # Entity mappers
    UserMapper,
    JobMapper,
    FileMapper,
    VideoMapper,
)

__all__ = [
    # Base classes
    "BaseRepository",
    "PaginationParams", 
    "PaginatedResult",
    
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
    
    # Session management
    "RepositoryManager",
    "UnitOfWork",
    "get_repository_manager",
    
    # Entity mappers
    "UserMapper",
    "JobMapper",
    "FileMapper", 
    "VideoMapper",
]

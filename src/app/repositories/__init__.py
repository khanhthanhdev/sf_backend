"""
Repository layer for data access abstraction.

This package provides repository pattern implementation with abstract base
repositories and concrete implementations for domain entities.
"""

from .base_repository import (
    IRepository,
    BaseRepository,
    PaginatedResult,
    IUserRepository,
    IJobRepository,
    IVideoRepository,
    IFileRepository,
    RepositoryFactory
)

from .concrete_repositories import (
    UserRepository,
    JobRepository,
    VideoRepository,
    FileRepository
)

__all__ = [
    'IRepository',
    'BaseRepository',
    'PaginatedResult',
    'IUserRepository',
    'IJobRepository',
    'IVideoRepository',
    'IFileRepository',
    'RepositoryFactory',
    'UserRepository',
    'JobRepository',
    'VideoRepository',
    'FileRepository'
]

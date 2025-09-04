"""
Database session management and repository dependency injection.

This module provides session management and dependency injection
for repository instances, integrating with the existing database
connection manager.
"""

import logging
from typing import AsyncGenerator, Optional, Type, TypeVar
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from ...app.database.connection import get_db_session
from .interfaces import (
    IVideoRepository, IUserRepository, IJobRepository, IFileRepository
)
from .implementations import (
    VideoRepository, UserRepository, JobRepository, FileRepository
)

logger = logging.getLogger(__name__)

# Type variable for repository types
TRepository = TypeVar('TRepository')


class RepositoryManager:
    """
    Repository manager providing dependency injection for repositories.
    
    This class manages the lifecycle of repository instances and ensures
    they are properly initialized with database sessions.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._repositories = {}
    
    def get_repository(self, repository_type: Type[TRepository]) -> TRepository:
        """
        Get a repository instance of the specified type.
        
        Args:
            repository_type: The repository class to instantiate
            
        Returns:
            Repository instance initialized with the session
        """
        if repository_type not in self._repositories:
            self._repositories[repository_type] = repository_type(self.session)
        
        return self._repositories[repository_type]
    
    @property
    def video_repository(self) -> VideoRepository:
        """Get video repository instance."""
        return self.get_repository(VideoRepository)
    
    @property
    def user_repository(self) -> UserRepository:
        """Get user repository instance."""
        return self.get_repository(UserRepository)
    
    @property
    def job_repository(self) -> JobRepository:
        """Get job repository instance."""
        return self.get_repository(JobRepository)
    
    @property
    def file_repository(self) -> FileRepository:
        """Get file repository instance."""
        return self.get_repository(FileRepository)


class UnitOfWork:
    """
    Unit of Work pattern implementation for managing transactions.
    
    Provides a way to group multiple repository operations into a single
    transaction that can be committed or rolled back atomically.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository_manager = RepositoryManager(session)
        self._committed = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, rollback
            await self.rollback()
        elif not self._committed:
            # No exception and not committed, rollback
            await self.rollback()
    
    async def commit(self):
        """Commit the current transaction."""
        try:
            await self.session.commit()
            self._committed = True
            logger.debug("Transaction committed successfully")
        except Exception as e:
            await self.rollback()
            logger.error(f"Failed to commit transaction: {e}")
            raise
    
    async def rollback(self):
        """Rollback the current transaction."""
        try:
            await self.session.rollback()
            logger.debug("Transaction rolled back")
        except Exception as e:
            logger.error(f"Failed to rollback transaction: {e}")
            raise
    
    @property
    def videos(self) -> VideoRepository:
        """Get video repository."""
        return self.repository_manager.video_repository
    
    @property
    def users(self) -> UserRepository:
        """Get user repository."""
        return self.repository_manager.user_repository
    
    @property
    def jobs(self) -> JobRepository:
        """Get job repository."""
        return self.repository_manager.job_repository
    
    @property
    def files(self) -> FileRepository:
        """Get file repository."""
        return self.repository_manager.file_repository


# Dependency injection functions for FastAPI

async def get_repository_manager(
    session: AsyncSession = Depends(get_db_session)
) -> RepositoryManager:
    """
    FastAPI dependency to get repository manager.
    
    Args:
        session: Database session from dependency injection
        
    Returns:
        Repository manager instance
    """
    return RepositoryManager(session)


async def get_unit_of_work(
    session: AsyncSession = Depends(get_db_session)
) -> AsyncGenerator[UnitOfWork, None]:
    """
    FastAPI dependency to get unit of work.
    
    Args:
        session: Database session from dependency injection
        
    Yields:
        Unit of work instance
    """
    uow = UnitOfWork(session)
    try:
        yield uow
    finally:
        # Session cleanup is handled by the session dependency
        pass


# Individual repository dependencies

async def get_video_repository(
    manager: RepositoryManager = Depends(get_repository_manager)
) -> IVideoRepository:
    """FastAPI dependency to get video repository."""
    return manager.video_repository


async def get_user_repository(
    manager: RepositoryManager = Depends(get_repository_manager)
) -> IUserRepository:
    """FastAPI dependency to get user repository."""
    return manager.user_repository


async def get_job_repository(
    manager: RepositoryManager = Depends(get_repository_manager)
) -> IJobRepository:
    """FastAPI dependency to get job repository."""
    return manager.job_repository


async def get_file_repository(
    manager: RepositoryManager = Depends(get_repository_manager)
) -> IFileRepository:
    """FastAPI dependency to get file repository."""
    return manager.file_repository


# Context manager for manual session management

@asynccontextmanager
async def repository_session() -> AsyncGenerator[RepositoryManager, None]:
    """
    Context manager for manual repository session management.
    
    Use this when you need to manage repository sessions outside of FastAPI
    dependency injection (e.g., in background tasks, CLI scripts).
    
    Example:
        async with repository_session() as repos:
            user = await repos.user_repository.get_by_id(user_id)
    """
    from ...app.database.connection import get_connection_manager
    
    manager = get_connection_manager()
    async with manager.get_session() as session:
        yield RepositoryManager(session)


@asynccontextmanager
async def unit_of_work_session() -> AsyncGenerator[UnitOfWork, None]:
    """
    Context manager for manual unit of work session management.
    
    Use this when you need to manage transactions outside of FastAPI
    dependency injection.
    
    Example:
        async with unit_of_work_session() as uow:
            await uow.users.create(user)
            await uow.jobs.create(job)
            await uow.commit()
    """
    from ...app.database.connection import get_connection_manager
    
    manager = get_connection_manager()
    async with manager.get_session() as session:
        uow = UnitOfWork(session)
        try:
            yield uow
        finally:
            # UnitOfWork will handle cleanup in its __aexit__
            pass


# Repository factory for testing

class RepositoryFactory:
    """
    Factory for creating repository instances for testing.
    
    This allows tests to easily create mock repositories or repositories
    with test database sessions.
    """
    
    @staticmethod
    def create_video_repository(session: AsyncSession) -> VideoRepository:
        """Create video repository with custom session."""
        return VideoRepository(session)
    
    @staticmethod
    def create_user_repository(session: AsyncSession) -> UserRepository:
        """Create user repository with custom session."""
        return UserRepository(session)
    
    @staticmethod
    def create_job_repository(session: AsyncSession) -> JobRepository:
        """Create job repository with custom session."""
        return JobRepository(session)
    
    @staticmethod
    def create_file_repository(session: AsyncSession) -> FileRepository:
        """Create file repository with custom session."""
        return FileRepository(session)
    
    @staticmethod
    def create_repository_manager(session: AsyncSession) -> RepositoryManager:
        """Create repository manager with custom session."""
        return RepositoryManager(session)
    
    @staticmethod
    def create_unit_of_work(session: AsyncSession) -> UnitOfWork:
        """Create unit of work with custom session."""
        return UnitOfWork(session)

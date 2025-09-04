"""
Test configuration for repository tests.

This module provides test fixtures, database setup, and common utilities
for testing repository implementations.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.app.database.models import Base
from src.domain.entities import User, Job, File
from src.domain.value_objects import (
    UserId, JobId, FileId, EmailAddress, JobType, JobPriority, 
    JobStatus, JobConfiguration, JobProgress, FileType, FileSize,
    S3Location
)
from src.infrastructure.repositories import (
    UserRepository, JobRepository, FileRepository, VideoRepository,
    RepositoryManager, UnitOfWork
)


# Test database URL (SQLite in-memory for fast testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        # Begin a transaction
        await session.begin()
        
        try:
            yield session
        finally:
            # Rollback the transaction to clean up
            await session.rollback()


@pytest.fixture
async def repository_manager(test_session: AsyncSession) -> RepositoryManager:
    """Create repository manager for testing."""
    return RepositoryManager(test_session)


@pytest.fixture
async def unit_of_work(test_session: AsyncSession) -> UnitOfWork:
    """Create unit of work for testing."""
    return UnitOfWork(test_session)


@pytest.fixture
async def user_repository(test_session: AsyncSession) -> UserRepository:
    """Create user repository for testing."""
    return UserRepository(test_session)


@pytest.fixture
async def job_repository(test_session: AsyncSession) -> JobRepository:
    """Create job repository for testing."""
    return JobRepository(test_session)


@pytest.fixture
async def file_repository(test_session: AsyncSession) -> FileRepository:
    """Create file repository for testing."""
    return FileRepository(test_session)


@pytest.fixture
async def video_repository(test_session: AsyncSession) -> VideoRepository:
    """Create video repository for testing."""
    return VideoRepository(test_session)


# Test data factories

class UserFactory:
    """Factory for creating test user entities."""
    
    @staticmethod
    def create_user(
        user_id: str = None,
        clerk_user_id: str = None,
        email: str = None,
        **kwargs
    ) -> User:
        """Create a test user entity."""
        user_id = user_id or str(uuid4())
        clerk_user_id = clerk_user_id or f"clerk_{uuid4().hex[:8]}"
        email = email or f"test_{uuid4().hex[:8]}@example.com"
        
        email_address = EmailAddress.create(email).value
        
        return User(
            user_id=UserId(user_id),
            clerk_user_id=clerk_user_id,
            username=f"user_{uuid4().hex[:8]}",
            first_name="Test",
            last_name="User",
            email_addresses=[email_address],
            primary_email=email_address,
            role="user",
            status="active",
            **kwargs
        )


class JobFactory:
    """Factory for creating test job entities."""
    
    @staticmethod
    def create_job(
        job_id: str = None,
        user_id: str = None,
        job_type: str = "video_generation",
        **kwargs
    ) -> Job:
        """Create a test job entity."""
        job_id = job_id or str(uuid4())
        user_id = user_id or str(uuid4())
        
        config = JobConfiguration.create({
            "video_config": {
                "title": "Test Video",
                "topic": "technology",
                "context": "Test context",
                "quality": "high",
                "format": "mp4",
                "resolution": "1080p"
            }
        }).value
        
        return Job(
            job_id=JobId(job_id),
            user_id=UserId(user_id),
            job_type=JobType(job_type),
            priority=JobPriority("normal"),
            configuration=config,
            status=JobStatus("queued"),
            progress=JobProgress(0),
            **kwargs
        )


class FileFactory:
    """Factory for creating test file entities."""
    
    @staticmethod
    def create_file(
        file_id: str = None,
        user_id: str = None,
        job_id: str = None,
        **kwargs
    ) -> File:
        """Create a test file entity."""
        file_id = file_id or str(uuid4())
        user_id = user_id or str(uuid4())
        
        file_type = FileType.create("video").value
        file_size = FileSize.create(1024 * 1024).value  # 1MB
        s3_location = S3Location(
            bucket="test-bucket",
            key=f"files/{file_id}.mp4",
            version_id=None
        )
        
        return File(
            file_id=FileId(file_id),
            user_id=UserId(user_id),
            job_id=JobId(job_id) if job_id else None,
            file_type=file_type,
            original_filename="test_video.mp4",
            stored_filename=f"{file_id}.mp4",
            s3_location=s3_location,
            file_size=file_size,
            content_type="video/mp4",
            checksum="abc123def456",
            file_metadata={"duration": 60},
            description="Test file",
            tags=["test"],
            **kwargs
        )


@pytest.fixture
def user_factory() -> UserFactory:
    """Provide user factory."""
    return UserFactory()


@pytest.fixture 
def job_factory() -> JobFactory:
    """Provide job factory."""
    return JobFactory()


@pytest.fixture
def file_factory() -> FileFactory:
    """Provide file factory."""
    return FileFactory()


# Utility functions for tests

async def create_test_user(repository: UserRepository, **kwargs) -> User:
    """Create and save a test user."""
    user = UserFactory.create_user(**kwargs)
    result = await repository.create(user)
    assert result.success
    return result.value


async def create_test_job(repository: JobRepository, **kwargs) -> Job:
    """Create and save a test job."""
    job = JobFactory.create_job(**kwargs)
    result = await repository.create(job)
    assert result.success
    return result.value


async def create_test_file(repository: FileRepository, **kwargs) -> File:
    """Create and save a test file."""
    file_entity = FileFactory.create_file(**kwargs)
    result = await repository.create(file_entity)
    assert result.success
    return result.value

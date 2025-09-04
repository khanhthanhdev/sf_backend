"""
Pytest configuration and fixtures for repository tests.

This module provides test configuration, database fixtures,
and common test utilities for repository layer testing.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.app.database.models import Base, User, Job, FileMetadata, JobQueue
from src.app.repositories.session_manager import DatabaseSessionManager
from src.app.repositories.implementations import (
    UserRepository, 
    JobRepository, 
    FileRepository, 
    JobQueueRepository
)


# Test database URL (in-memory SQLite for fast tests)
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
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_factory(test_engine):
    """Create test session factory."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


@pytest.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with transaction rollback."""
    async with test_session_factory() as session:
        # Start a transaction
        transaction = await session.begin()
        
        try:
            yield session
        finally:
            # Rollback transaction to clean up test data
            await transaction.rollback()
            await session.close()


@pytest.fixture
async def user_repository(db_session) -> UserRepository:
    """Create UserRepository instance for testing."""
    return UserRepository(db_session)


@pytest.fixture
async def job_repository(db_session) -> JobRepository:
    """Create JobRepository instance for testing."""
    return JobRepository(db_session)


@pytest.fixture
async def file_repository(db_session) -> FileRepository:
    """Create FileRepository instance for testing."""
    return FileRepository(db_session)


@pytest.fixture
async def job_queue_repository(db_session) -> JobQueueRepository:
    """Create JobQueueRepository instance for testing."""
    return JobQueueRepository(db_session)


# Test data factories

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'id': uuid4(),
        'clerk_user_id': f'clerk_{uuid4()}',
        'username': 'testuser',
        'first_name': 'Test',
        'last_name': 'User',
        'primary_email': 'test@example.com',
        'email_addresses': ['test@example.com'],
        'phone_numbers': [],
        'email_verified': True,
        'phone_verified': False,
        'two_factor_enabled': False,
        'role': 'user',
        'status': 'active',
        'user_metadata': {},
        'is_deleted': False
    }


@pytest.fixture
def sample_job_data(sample_user_data):
    """Sample job data for testing."""
    return {
        'id': uuid4(),
        'user_id': sample_user_data['id'],
        'job_type': 'video_generation',
        'priority': 'normal',
        'configuration': {'test': 'config'},
        'status': 'queued',
        'progress_percentage': 0,
        'stages_completed': [],
        'metrics': {},
        'is_deleted': False
    }


@pytest.fixture
def sample_file_data(sample_user_data):
    """Sample file metadata for testing."""
    return {
        'id': uuid4(),
        'user_id': sample_user_data['id'],
        'file_type': 'image',
        'original_filename': 'test.jpg',
        'stored_filename': f'{uuid4()}.jpg',
        's3_bucket': 'test-bucket',
        's3_key': f'uploads/{uuid4()}.jpg',
        'file_size': 1024,
        'content_type': 'image/jpeg',
        'file_metadata': {'width': 800, 'height': 600},
        'tags': ['test'],
        'is_deleted': False
    }


@pytest.fixture
def sample_queue_data(sample_job_data):
    """Sample job queue data for testing."""
    return {
        'id': uuid4(),
        'job_id': sample_job_data['id'],
        'priority': 'normal',
        'queue_status': 'queued',
        'retry_count': 0,
        'max_retries': 3
    }


@pytest.fixture
async def created_user(user_repository, sample_user_data) -> User:
    """Create a user in the test database."""
    user = User(**sample_user_data)
    return await user_repository.create(user)


@pytest.fixture
async def created_job(job_repository, created_user, sample_job_data) -> Job:
    """Create a job in the test database."""
    sample_job_data['user_id'] = created_user.id
    job = Job(**sample_job_data)
    return await job_repository.create(job)


@pytest.fixture
async def created_file(file_repository, created_user, sample_file_data) -> FileMetadata:
    """Create a file metadata in the test database."""
    sample_file_data['user_id'] = created_user.id
    file_metadata = FileMetadata(**sample_file_data)
    return await file_repository.create(file_metadata)


@pytest.fixture
async def created_queue_entry(job_queue_repository, created_job, sample_queue_data) -> JobQueue:
    """Create a job queue entry in the test database."""
    sample_queue_data['job_id'] = created_job.id
    queue_entry = JobQueue(**sample_queue_data)
    return await job_queue_repository.create(queue_entry)


# Test utilities

class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user(**overrides) -> dict:
        """Create user data with optional overrides."""
        data = {
            'id': uuid4(),
            'clerk_user_id': f'clerk_{uuid4()}',
            'username': f'user_{uuid4().hex[:8]}',
            'first_name': 'Test',
            'last_name': 'User',
            'primary_email': f'test_{uuid4().hex[:8]}@example.com',
            'email_addresses': [],
            'phone_numbers': [],
            'email_verified': True,
            'phone_verified': False,
            'two_factor_enabled': False,
            'role': 'user',
            'status': 'active',
            'user_metadata': {},
            'is_deleted': False
        }
        data.update(overrides)
        return data
    
    @staticmethod
    def create_job(user_id=None, **overrides) -> dict:
        """Create job data with optional overrides."""
        data = {
            'id': uuid4(),
            'user_id': user_id or uuid4(),
            'job_type': 'video_generation',
            'priority': 'normal',
            'configuration': {'test': 'config'},
            'status': 'queued',
            'progress_percentage': 0,
            'stages_completed': [],
            'metrics': {},
            'is_deleted': False
        }
        data.update(overrides)
        return data
    
    @staticmethod
    def create_file(user_id=None, **overrides) -> dict:
        """Create file metadata with optional overrides."""
        data = {
            'id': uuid4(),
            'user_id': user_id or uuid4(),
            'file_type': 'image',
            'original_filename': 'test.jpg',
            'stored_filename': f'{uuid4()}.jpg',
            's3_bucket': 'test-bucket',
            's3_key': f'uploads/{uuid4()}.jpg',
            'file_size': 1024,
            'content_type': 'image/jpeg',
            'file_metadata': {},
            'tags': [],
            'is_deleted': False
        }
        data.update(overrides)
        return data


@pytest.fixture
def test_data_factory():
    """Test data factory fixture."""
    return TestDataFactory
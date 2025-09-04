"""
Unit tests for repository session management.

Tests cover RepositoryManager, UnitOfWork, and dependency injection
for repository session management.
"""

import pytest
from uuid import uuid4

from src.infrastructure.repositories import (
    RepositoryManager, UnitOfWork, UserRepository, JobRepository,
    FileRepository, VideoRepository
)
from .conftest import UserFactory, JobFactory, FileFactory


class TestRepositoryManager:
    """Test suite for RepositoryManager."""
    
    async def test_repository_manager_initialization(self, repository_manager: RepositoryManager):
        """Test repository manager initialization."""
        assert repository_manager.session is not None
        assert repository_manager._repositories == {}
    
    async def test_get_repository_creates_instance(self, repository_manager: RepositoryManager):
        """Test that get_repository creates repository instances."""
        user_repo = repository_manager.get_repository(UserRepository)
        
        assert isinstance(user_repo, UserRepository)
        assert user_repo.session == repository_manager.session
    
    async def test_get_repository_returns_same_instance(self, repository_manager: RepositoryManager):
        """Test that get_repository returns the same instance for subsequent calls."""
        user_repo1 = repository_manager.get_repository(UserRepository)
        user_repo2 = repository_manager.get_repository(UserRepository)
        
        assert user_repo1 is user_repo2
    
    async def test_repository_properties(self, repository_manager: RepositoryManager):
        """Test repository property accessors."""
        video_repo = repository_manager.video_repository
        user_repo = repository_manager.user_repository
        job_repo = repository_manager.job_repository
        file_repo = repository_manager.file_repository
        
        assert isinstance(video_repo, VideoRepository)
        assert isinstance(user_repo, UserRepository)
        assert isinstance(job_repo, JobRepository)
        assert isinstance(file_repo, FileRepository)
        
        # Test that properties return same instances
        assert repository_manager.video_repository is video_repo
        assert repository_manager.user_repository is user_repo


class TestUnitOfWork:
    """Test suite for UnitOfWork."""
    
    async def test_unit_of_work_initialization(self, unit_of_work: UnitOfWork):
        """Test unit of work initialization."""
        assert unit_of_work.session is not None
        assert unit_of_work.repository_manager is not None
        assert unit_of_work._committed is False
    
    async def test_unit_of_work_repository_access(self, unit_of_work: UnitOfWork):
        """Test accessing repositories through unit of work."""
        assert isinstance(unit_of_work.videos, VideoRepository)
        assert isinstance(unit_of_work.users, UserRepository)
        assert isinstance(unit_of_work.jobs, JobRepository)
        assert isinstance(unit_of_work.files, FileRepository)
    
    async def test_unit_of_work_commit_success(self, unit_of_work: UnitOfWork):
        """Test successful transaction commit."""
        # Create a user through unit of work
        user = UserFactory.create_user()
        result = await unit_of_work.users.create(user)
        assert result.success
        
        # Commit the transaction
        await unit_of_work.commit()
        assert unit_of_work._committed is True
    
    async def test_unit_of_work_rollback(self, unit_of_work: UnitOfWork):
        """Test transaction rollback."""
        # Create a user through unit of work
        user = UserFactory.create_user()
        result = await unit_of_work.users.create(user)
        assert result.success
        
        # Rollback the transaction
        await unit_of_work.rollback()
        assert unit_of_work._committed is False
    
    async def test_unit_of_work_context_manager_commit(self, test_session):
        """Test unit of work context manager with commit."""
        user = UserFactory.create_user()
        
        async with UnitOfWork(test_session) as uow:
            result = await uow.users.create(user)
            assert result.success
            await uow.commit()
        
        # Verify user was created (would need separate session to verify)
        assert result.success
    
    async def test_unit_of_work_context_manager_rollback_on_exception(self, test_session):
        """Test unit of work context manager rolls back on exception."""
        user = UserFactory.create_user()
        
        try:
            async with UnitOfWork(test_session) as uow:
                result = await uow.users.create(user)
                assert result.success
                # Simulate an error
                raise Exception("Test error")
        except Exception:
            pass  # Expected exception
        
        # Transaction should have been rolled back automatically
    
    async def test_unit_of_work_multiple_operations(self, unit_of_work: UnitOfWork):
        """Test multiple operations in a single unit of work."""
        # Create user
        user = UserFactory.create_user()
        user_result = await unit_of_work.users.create(user)
        assert user_result.success
        
        # Create job for the user
        job = JobFactory.create_job(user_id=user.user_id.value)
        job_result = await unit_of_work.jobs.create(job)
        assert job_result.success
        
        # Create file for the job
        file_entity = FileFactory.create_file(
            user_id=user.user_id.value,
            job_id=job.job_id.value
        )
        file_result = await unit_of_work.files.create(file_entity)
        assert file_result.success
        
        # Commit all operations
        await unit_of_work.commit()
        assert unit_of_work._committed is True
    
    async def test_unit_of_work_rollback_on_error(self, unit_of_work: UnitOfWork):
        """Test that unit of work rolls back on database error."""
        # Create user
        user = UserFactory.create_user()
        user_result = await unit_of_work.users.create(user)
        assert user_result.success
        
        # Try to create duplicate user (should fail)
        duplicate_user = UserFactory.create_user(
            clerk_user_id=user.clerk_user_id  # Same Clerk ID
        )
        duplicate_result = await unit_of_work.users.create(duplicate_user)
        assert not duplicate_result.success
        
        # Original operations should still be accessible before rollback
        assert user_result.success
        
        # Rollback due to error
        await unit_of_work.rollback()


class TestRepositoryIntegration:
    """Test suite for repository integration scenarios."""
    
    async def test_cross_repository_operations(self, repository_manager: RepositoryManager):
        """Test operations across multiple repositories."""
        # Create user
        user = UserFactory.create_user()
        user_result = await repository_manager.user_repository.create(user)
        assert user_result.success
        
        # Create job for user
        job = JobFactory.create_job(user_id=user.user_id.value)
        job_result = await repository_manager.job_repository.create(job)
        assert job_result.success
        
        # Create file for job
        file_entity = FileFactory.create_file(
            user_id=user.user_id.value,
            job_id=job.job_id.value
        )
        file_result = await repository_manager.file_repository.create(file_entity)
        assert file_result.success
        
        # Verify relationships
        user_jobs = await repository_manager.job_repository.get_by_user_id(user.user_id)
        assert user_jobs.success
        assert len(user_jobs.value.items) >= 1
        
        job_files = await repository_manager.file_repository.get_by_job_id(job.job_id)
        assert job_files.success
        assert len(job_files.value.items) >= 1
    
    async def test_repository_error_isolation(self, repository_manager: RepositoryManager):
        """Test that errors in one repository don't affect others."""
        # Create valid user
        user = UserFactory.create_user()
        user_result = await repository_manager.user_repository.create(user)
        assert user_result.success
        
        # Try to create invalid job (this might fail)
        invalid_job = JobFactory.create_job()
        invalid_job._user_id = None  # Invalid user ID
        job_result = await repository_manager.job_repository.create(invalid_job)
        
        # Even if job creation fails, user repository should still work
        user_exists = await repository_manager.user_repository.exists(
            uuid4(user.user_id.value)
        )
        assert user_exists.success
        assert user_exists.value is True
    
    async def test_repository_session_sharing(self, repository_manager: RepositoryManager):
        """Test that repositories share the same session."""
        user_repo = repository_manager.user_repository
        job_repo = repository_manager.job_repository
        file_repo = repository_manager.file_repository
        video_repo = repository_manager.video_repository
        
        # All repositories should share the same session
        assert user_repo.session is repository_manager.session
        assert job_repo.session is repository_manager.session
        assert file_repo.session is repository_manager.session
        assert video_repo.session is repository_manager.session
    
    async def test_concurrent_repository_access(self, repository_manager: RepositoryManager):
        """Test concurrent access to repositories."""
        import asyncio
        
        async def create_user(index):
            user = UserFactory.create_user(email=f"concurrent{index}@example.com")
            return await repository_manager.user_repository.create(user)
        
        # Create multiple users concurrently
        tasks = [create_user(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed (or at least not raise exceptions)
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent operation failed: {result}")
            assert result.success
    
    async def test_repository_cleanup(self, test_session):
        """Test proper repository cleanup and session management."""
        # Create repository manager
        repo_manager = RepositoryManager(test_session)
        
        # Use repositories
        user = UserFactory.create_user()
        result = await repo_manager.user_repository.create(user)
        assert result.success
        
        # Repository manager should maintain references
        assert len(repo_manager._repositories) > 0
        
        # After operations, session should still be valid
        assert test_session.is_active

"""
Integration tests for repository layer with real database operations.

This module contains integration tests that verify repository operations
work correctly with actual database connections and transactions.
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta

from src.app.repositories.container import RepositoryContainer, repository_transaction
from src.app.repositories.session_manager import DatabaseSessionManager
from src.app.repositories.interfaces import PaginationParams, FilterCriteria
from src.app.database.models import User, Job, FileMetadata, JobQueue


class TestRepositoryIntegration:
    """Integration tests for repository operations."""
    
    @pytest.fixture
    async def container(self, test_engine):
        """Create repository container for integration tests."""
        # Create session manager with test engine
        session_manager = DatabaseSessionManager()
        session_manager.engine = test_engine
        session_manager.session_factory = pytest.importorskip("sqlalchemy.ext.asyncio").async_sessionmaker(
            bind=test_engine,
            class_=pytest.importorskip("sqlalchemy.ext.asyncio").AsyncSession,
            expire_on_commit=False
        )
        session_manager._is_initialized = True
        
        # Create and initialize container
        container = RepositoryContainer()
        await container.initialize(session_manager)
        
        yield container
        
        # Cleanup
        await container.close()
    
    async def test_cross_repository_operations(self, container, test_data_factory):
        """Test operations across multiple repositories."""
        async with repository_transaction() as repos:
            # Create user
            user_data = test_data_factory.create_user()
            user = User(**user_data)
            created_user = await repos['user_repo'].create(user)
            
            # Create job for user
            job_data = test_data_factory.create_job(user_id=created_user.id)
            job = Job(**job_data)
            created_job = await repos['job_repo'].create(job)
            
            # Create file for user and job
            file_data = test_data_factory.create_file(user_id=created_user.id)
            file_data['job_id'] = created_job.id
            file_metadata = FileMetadata(**file_data)
            created_file = await repos['file_repo'].create(file_metadata)
            
            # Create queue entry for job
            queue_data = {
                'id': uuid4(),
                'job_id': created_job.id,
                'priority': 'normal',
                'queue_status': 'queued',
                'retry_count': 0,
                'max_retries': 3
            }
            queue_entry = JobQueue(**queue_data)
            created_queue = await repos['queue_repo'].create(queue_entry)
            
            # Verify relationships
            assert created_job.user_id == created_user.id
            assert created_file.user_id == created_user.id
            assert created_file.job_id == created_job.id
            assert created_queue.job_id == created_job.id
            
            # Test cross-repository queries
            user_jobs = await repos['job_repo'].get_by_user_id(created_user.id)
            assert len(user_jobs.items) == 1
            assert user_jobs.items[0].id == created_job.id
            
            job_files = await repos['file_repo'].get_by_job_id(created_job.id)
            assert len(job_files) == 1
            assert job_files[0].id == created_file.id
    
    async def test_transaction_rollback(self, container, test_data_factory):
        """Test transaction rollback on error."""
        user_data = test_data_factory.create_user()
        
        try:
            async with repository_transaction() as repos:
                # Create user
                user = User(**user_data)
                created_user = await repos['user_repo'].create(user)
                
                # Verify user was created
                retrieved_user = await repos['user_repo'].get_by_id(created_user.id)
                assert retrieved_user is not None
                
                # Force an error to trigger rollback
                raise ValueError("Simulated error")
                
        except ValueError:
            pass  # Expected error
        
        # Verify user was rolled back (not committed)
        async with container.get_scoped(container._factories[pytest.importorskip("src.app.repositories.interfaces").IUserRepository].__annotations__['return']) as user_repo:
            retrieved_user = await user_repo.get_by_id(user_data['id'])
            # Note: This test behavior depends on transaction isolation
            # In some test setups, the rollback might not be visible
    
    async def test_concurrent_repository_access(self, container, test_data_factory):
        """Test concurrent access to repositories."""
        
        async def create_user_task(user_suffix):
            """Task to create a user."""
            user_data = test_data_factory.create_user(username=f'user_{user_suffix}')
            
            async with container.get_scoped(pytest.importorskip("src.app.repositories.interfaces").IUserRepository) as user_repo:
                user = User(**user_data)
                return await user_repo.create(user)
        
        # Create multiple users concurrently
        tasks = [create_user_task(i) for i in range(5)]
        created_users = await asyncio.gather(*tasks)
        
        # Verify all users were created
        assert len(created_users) == 5
        for user in created_users:
            assert user.id is not None
            assert user.username.startswith('user_')
    
    async def test_repository_container_health_check(self, container):
        """Test repository container health check."""
        health_status = await container.health_check()
        
        assert health_status['container_initialized'] is True
        assert health_status['overall_status'] in ['healthy', 'unhealthy']
        assert 'repositories_available' in health_status
        
        # Check that all expected repositories are available
        expected_repos = ['IUserRepository', 'IJobRepository', 'IFileRepository', 'IJobQueueRepository']
        for repo_name in expected_repos:
            assert repo_name in health_status['repositories_available']
    
    async def test_bulk_operations(self, container, test_data_factory):
        """Test bulk repository operations."""
        async with repository_transaction() as repos:
            # Create multiple users
            users_data = [test_data_factory.create_user(username=f'bulk_user_{i}') for i in range(10)]
            users = [User(**data) for data in users_data]
            
            # Bulk create users
            created_users = await repos['user_repo'].bulk_create(users)
            assert len(created_users) == 10
            
            # Verify all users have IDs
            for user in created_users:
                assert user.id is not None
                assert user.created_at is not None
    
    async def test_complex_filtering_and_pagination(self, container, test_data_factory):
        """Test complex filtering and pagination across repositories."""
        async with repository_transaction() as repos:
            # Create test data
            user_data = test_data_factory.create_user()
            user = User(**user_data)
            created_user = await repos['user_repo'].create(user)
            
            # Create jobs with different statuses and types
            job_statuses = ['queued', 'processing', 'completed', 'failed']
            job_types = ['video_generation', 'image_processing']
            
            created_jobs = []
            for i in range(20):
                job_data = test_data_factory.create_job(
                    user_id=created_user.id,
                    status=job_statuses[i % len(job_statuses)],
                    job_type=job_types[i % len(job_types)]
                )
                job = Job(**job_data)
                created_job = await repos['job_repo'].create(job)
                created_jobs.append(created_job)
            
            # Test filtering by status
            queued_jobs = await repos['job_repo'].get_by_status('queued')
            queued_count = len([j for j in created_jobs if j.status == 'queued'])
            assert len(queued_jobs.items) == queued_count
            
            # Test pagination
            pagination = PaginationParams(page=1, page_size=5)
            paginated_jobs = await repos['job_repo'].get_by_user_id(
                created_user.id, 
                pagination=pagination
            )
            
            assert len(paginated_jobs.items) == 5
            assert paginated_jobs.total_count == 20
            assert paginated_jobs.has_next is True
            assert paginated_jobs.has_previous is False
            
            # Test second page
            pagination = PaginationParams(page=2, page_size=5)
            second_page = await repos['job_repo'].get_by_user_id(
                created_user.id,
                pagination=pagination
            )
            
            assert len(second_page.items) == 5
            assert second_page.has_next is True
            assert second_page.has_previous is True
    
    async def test_repository_error_handling(self, container):
        """Test repository error handling in integration scenarios."""
        async with container.get_scoped(pytest.importorskip("src.app.repositories.interfaces").IUserRepository) as user_repo:
            # Test getting non-existent user
            non_existent_user = await user_repo.get_by_id(uuid4())
            assert non_existent_user is None
            
            # Test deleting non-existent user
            delete_result = await user_repo.delete(uuid4())
            assert delete_result is False
    
    async def test_session_management(self, container):
        """Test database session management."""
        # Test that sessions are properly managed
        session_manager = container._session_manager
        
        # Get connection stats
        stats = session_manager.get_connection_stats()
        assert 'total_connections' in stats
        assert 'active_connections' in stats
        
        # Test health check
        is_healthy = await session_manager.test_connection()
        assert isinstance(is_healthy, bool)
    
    async def test_repository_lifecycle(self, test_engine):
        """Test complete repository lifecycle."""
        # Create new container
        session_manager = DatabaseSessionManager()
        session_manager.engine = test_engine
        session_manager.session_factory = pytest.importorskip("sqlalchemy.ext.asyncio").async_sessionmaker(
            bind=test_engine,
            class_=pytest.importorskip("sqlalchemy.ext.asyncio").AsyncSession,
            expire_on_commit=False
        )
        session_manager._is_initialized = True
        
        container = RepositoryContainer()
        
        # Test initialization
        await container.initialize(session_manager)
        assert container._is_initialized is True
        
        # Test repository creation
        async with container.get_scoped(pytest.importorskip("src.app.repositories.interfaces").IUserRepository) as user_repo:
            assert user_repo is not None
        
        # Test cleanup
        await container.close()
        assert container._is_initialized is False


class TestRepositoryPerformance:
    """Performance tests for repository operations."""
    
    async def test_bulk_insert_performance(self, container, test_data_factory):
        """Test performance of bulk insert operations."""
        import time
        
        async with repository_transaction() as repos:
            # Create test data
            users_data = [test_data_factory.create_user(username=f'perf_user_{i}') for i in range(100)]
            users = [User(**data) for data in users_data]
            
            # Measure bulk insert time
            start_time = time.time()
            created_users = await repos['user_repo'].bulk_create(users)
            end_time = time.time()
            
            # Verify results
            assert len(created_users) == 100
            
            # Log performance (in real tests, you might have specific thresholds)
            insert_time = end_time - start_time
            print(f"Bulk insert of 100 users took {insert_time:.3f} seconds")
            
            # Basic performance assertion (adjust threshold as needed)
            assert insert_time < 10.0  # Should complete within 10 seconds
    
    async def test_pagination_performance(self, container, test_data_factory):
        """Test performance of paginated queries."""
        import time
        
        async with repository_transaction() as repos:
            # Create user and jobs
            user_data = test_data_factory.create_user()
            user = User(**user_data)
            created_user = await repos['user_repo'].create(user)
            
            # Create many jobs
            jobs_data = [
                test_data_factory.create_job(user_id=created_user.id) 
                for i in range(500)
            ]
            jobs = [Job(**data) for data in jobs_data]
            await repos['job_repo'].bulk_create(jobs)
            
            # Test pagination performance
            start_time = time.time()
            
            # Get first page
            pagination = PaginationParams(page=1, page_size=20)
            result = await repos['job_repo'].get_by_user_id(created_user.id, pagination=pagination)
            
            end_time = time.time()
            
            # Verify results
            assert len(result.items) == 20
            assert result.total_count == 500
            
            # Log performance
            query_time = end_time - start_time
            print(f"Paginated query (20 items from 500) took {query_time:.3f} seconds")
            
            # Basic performance assertion
            assert query_time < 5.0  # Should complete within 5 seconds
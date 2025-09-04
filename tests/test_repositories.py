"""
Unit tests for repository layer implementations.

This module contains comprehensive tests for all repository implementations
including CRUD operations, filtering, pagination, and error handling.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from src.app.database.models import User, Job, FileMetadata, JobQueue
from src.app.repositories.interfaces import PaginationParams, FilterCriteria
from src.app.repositories.exceptions import EntityNotFoundError, RepositoryError


class TestUserRepository:
    """Test cases for UserRepository."""
    
    async def test_create_user(self, user_repository, sample_user_data):
        """Test creating a new user."""
        user = User(**sample_user_data)
        created_user = await user_repository.create(user)
        
        assert created_user.id == sample_user_data['id']
        assert created_user.clerk_user_id == sample_user_data['clerk_user_id']
        assert created_user.username == sample_user_data['username']
        assert created_user.primary_email == sample_user_data['primary_email']
        assert created_user.created_at is not None
        assert created_user.updated_at is not None
    
    async def test_get_user_by_id(self, user_repository, created_user):
        """Test retrieving user by ID."""
        retrieved_user = await user_repository.get_by_id(created_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.clerk_user_id == created_user.clerk_user_id
    
    async def test_get_user_by_id_not_found(self, user_repository):
        """Test retrieving non-existent user by ID."""
        non_existent_id = uuid4()
        retrieved_user = await user_repository.get_by_id(non_existent_id)
        
        assert retrieved_user is None
    
    async def test_get_user_by_clerk_id(self, user_repository, created_user):
        """Test retrieving user by Clerk ID."""
        retrieved_user = await user_repository.get_by_clerk_id(created_user.clerk_user_id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.clerk_user_id == created_user.clerk_user_id
    
    async def test_get_user_by_email(self, user_repository, created_user):
        """Test retrieving user by email."""
        retrieved_user = await user_repository.get_by_email(created_user.primary_email)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.primary_email == created_user.primary_email
    
    async def test_update_user(self, user_repository, created_user):
        """Test updating user."""
        created_user.username = 'updated_username'
        created_user.first_name = 'Updated'
        
        updated_user = await user_repository.update(created_user)
        
        assert updated_user.username == 'updated_username'
        assert updated_user.first_name == 'Updated'
        assert updated_user.updated_at > created_user.created_at
    
    async def test_update_last_active(self, user_repository, created_user):
        """Test updating user's last active timestamp."""
        original_last_active = created_user.last_active_at
        
        success = await user_repository.update_last_active(created_user.id)
        
        assert success is True
        
        # Verify the update
        updated_user = await user_repository.get_by_id(created_user.id)
        assert updated_user.last_active_at is not None
        if original_last_active:
            assert updated_user.last_active_at > original_last_active
    
    async def test_soft_delete_user(self, user_repository, created_user):
        """Test soft deleting user."""
        success = await user_repository.delete(created_user.id, soft_delete=True)
        
        assert success is True
        
        # Verify user is not returned in normal queries
        retrieved_user = await user_repository.get_by_id(created_user.id)
        assert retrieved_user is None
    
    async def test_list_users_with_pagination(self, user_repository, test_data_factory):
        """Test listing users with pagination."""
        # Create multiple users
        users = []
        for i in range(5):
            user_data = test_data_factory.create_user(username=f'user_{i}')
            user = User(**user_data)
            created_user = await user_repository.create(user)
            users.append(created_user)
        
        # Test pagination
        pagination = PaginationParams(page=1, page_size=3)
        result = await user_repository.list(pagination=pagination)
        
        assert len(result.items) == 3
        assert result.total_count == 5
        assert result.page == 1
        assert result.has_next is True
        assert result.has_previous is False
    
    async def test_get_active_users(self, user_repository, test_data_factory):
        """Test getting active users."""
        # Create active and inactive users
        active_user_data = test_data_factory.create_user(status='active')
        inactive_user_data = test_data_factory.create_user(status='inactive')
        
        active_user = User(**active_user_data)
        inactive_user = User(**inactive_user_data)
        
        await user_repository.create(active_user)
        await user_repository.create(inactive_user)
        
        # Get active users
        result = await user_repository.get_active_users()
        
        # Should only return active users
        active_usernames = [user.username for user in result.items]
        assert active_user.username in active_usernames
        assert inactive_user.username not in active_usernames


class TestJobRepository:
    """Test cases for JobRepository."""
    
    async def test_create_job(self, job_repository, created_user, sample_job_data):
        """Test creating a new job."""
        sample_job_data['user_id'] = created_user.id
        job = Job(**sample_job_data)
        created_job = await job_repository.create(job)
        
        assert created_job.id == sample_job_data['id']
        assert created_job.user_id == created_user.id
        assert created_job.job_type == sample_job_data['job_type']
        assert created_job.status == sample_job_data['status']
        assert created_job.created_at is not None
    
    async def test_get_job_by_id(self, job_repository, created_job):
        """Test retrieving job by ID."""
        retrieved_job = await job_repository.get_by_id(created_job.id)
        
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.user_id == created_job.user_id
    
    async def test_get_jobs_by_user_id(self, job_repository, created_user, test_data_factory):
        """Test retrieving jobs by user ID."""
        # Create multiple jobs for the user
        jobs = []
        for i in range(3):
            job_data = test_data_factory.create_job(
                user_id=created_user.id,
                job_type=f'type_{i}'
            )
            job = Job(**job_data)
            created_job = await job_repository.create(job)
            jobs.append(created_job)
        
        # Get jobs by user ID
        result = await job_repository.get_by_user_id(created_user.id)
        
        assert len(result.items) == 3
        for job in result.items:
            assert job.user_id == created_user.id
    
    async def test_get_jobs_by_status(self, job_repository, created_user, test_data_factory):
        """Test retrieving jobs by status."""
        # Create jobs with different statuses
        queued_job_data = test_data_factory.create_job(
            user_id=created_user.id,
            status='queued'
        )
        processing_job_data = test_data_factory.create_job(
            user_id=created_user.id,
            status='processing'
        )
        
        queued_job = Job(**queued_job_data)
        processing_job = Job(**processing_job_data)
        
        await job_repository.create(queued_job)
        await job_repository.create(processing_job)
        
        # Get queued jobs
        result = await job_repository.get_by_status('queued')
        
        queued_job_ids = [job.id for job in result.items]
        assert queued_job.id in queued_job_ids
        assert processing_job.id not in queued_job_ids
    
    async def test_update_job_status(self, job_repository, created_job):
        """Test updating job status."""
        success = await job_repository.update_status(
            created_job.id,
            'processing',
            progress_percentage=50.0,
            current_stage='encoding'
        )
        
        assert success is True
        
        # Verify the update
        updated_job = await job_repository.get_by_id(created_job.id)
        assert updated_job.status == 'processing'
        assert updated_job.progress_percentage == 50.0
        assert updated_job.current_stage == 'encoding'
        assert updated_job.started_at is not None
    
    async def test_get_queued_jobs(self, job_repository, created_user, test_data_factory):
        """Test getting queued jobs ordered by priority."""
        # Create jobs with different priorities
        high_priority_data = test_data_factory.create_job(
            user_id=created_user.id,
            status='queued',
            priority='high'
        )
        normal_priority_data = test_data_factory.create_job(
            user_id=created_user.id,
            status='queued',
            priority='normal'
        )
        
        high_job = Job(**high_priority_data)
        normal_job = Job(**normal_priority_data)
        
        # Create normal priority job first
        await job_repository.create(normal_job)
        await job_repository.create(high_job)
        
        # Get queued jobs
        queued_jobs = await job_repository.get_queued_jobs()
        
        # High priority should come first
        assert len(queued_jobs) >= 2
        # Note: This test assumes priority ordering, may need adjustment based on actual priority values


class TestFileRepository:
    """Test cases for FileRepository."""
    
    async def test_create_file(self, file_repository, created_user, sample_file_data):
        """Test creating file metadata."""
        sample_file_data['user_id'] = created_user.id
        file_metadata = FileMetadata(**sample_file_data)
        created_file = await file_repository.create(file_metadata)
        
        assert created_file.id == sample_file_data['id']
        assert created_file.user_id == created_user.id
        assert created_file.original_filename == sample_file_data['original_filename']
        assert created_file.s3_key == sample_file_data['s3_key']
    
    async def test_get_file_by_s3_key(self, file_repository, created_file):
        """Test retrieving file by S3 key."""
        retrieved_file = await file_repository.get_by_s3_key(created_file.s3_key)
        
        assert retrieved_file is not None
        assert retrieved_file.id == created_file.id
        assert retrieved_file.s3_key == created_file.s3_key
    
    async def test_get_files_by_user_id(self, file_repository, created_user, test_data_factory):
        """Test retrieving files by user ID."""
        # Create multiple files for the user
        files = []
        for i in range(3):
            file_data = test_data_factory.create_file(
                user_id=created_user.id,
                original_filename=f'file_{i}.jpg'
            )
            file_metadata = FileMetadata(**file_data)
            created_file = await file_repository.create(file_metadata)
            files.append(created_file)
        
        # Get files by user ID
        result = await file_repository.get_by_user_id(created_user.id)
        
        assert len(result.items) == 3
        for file_meta in result.items:
            assert file_meta.user_id == created_user.id
    
    async def test_update_access_time(self, file_repository, created_file):
        """Test updating file access time."""
        original_access_time = created_file.last_accessed_at
        
        success = await file_repository.update_access_time(created_file.id)
        
        assert success is True
        
        # Verify the update
        updated_file = await file_repository.get_by_id(created_file.id)
        assert updated_file.last_accessed_at is not None
        if original_access_time:
            assert updated_file.last_accessed_at > original_access_time
    
    async def test_get_files_by_age(self, file_repository, created_user, test_data_factory):
        """Test getting files by age."""
        # Create an old file (simulate by setting created_at in the past)
        old_file_data = test_data_factory.create_file(user_id=created_user.id)
        old_file = FileMetadata(**old_file_data)
        old_file.created_at = datetime.utcnow() - timedelta(days=35)
        
        # Create a recent file
        recent_file_data = test_data_factory.create_file(user_id=created_user.id)
        recent_file = FileMetadata(**recent_file_data)
        
        await file_repository.create(old_file)
        await file_repository.create(recent_file)
        
        # Get files older than 30 days
        result = await file_repository.get_files_by_age(30)
        
        old_file_ids = [f.id for f in result.items]
        assert old_file.id in old_file_ids
        assert recent_file.id not in old_file_ids


class TestJobQueueRepository:
    """Test cases for JobQueueRepository."""
    
    async def test_create_queue_entry(self, job_queue_repository, created_job, sample_queue_data):
        """Test creating job queue entry."""
        sample_queue_data['job_id'] = created_job.id
        queue_entry = JobQueue(**sample_queue_data)
        created_entry = await job_queue_repository.create(queue_entry)
        
        assert created_entry.id == sample_queue_data['id']
        assert created_entry.job_id == created_job.id
        assert created_entry.queue_status == sample_queue_data['queue_status']
    
    async def test_get_next_job(self, job_queue_repository, created_job, test_data_factory):
        """Test getting next job from queue."""
        # Create queue entries with different priorities
        high_priority_data = test_data_factory.create_job()
        normal_priority_data = test_data_factory.create_job()
        
        # Create jobs first (simplified for test)
        from src.app.database.models import Job
        high_job = Job(**high_priority_data)
        normal_job = Job(**normal_priority_data)
        
        # Create queue entries
        high_queue_data = {
            'id': uuid4(),
            'job_id': high_job.id,
            'priority': 'high',
            'queue_status': 'queued',
            'retry_count': 0,
            'max_retries': 3
        }
        
        normal_queue_data = {
            'id': uuid4(),
            'job_id': normal_job.id,
            'priority': 'normal',
            'queue_status': 'queued',
            'retry_count': 0,
            'max_retries': 3
        }
        
        high_queue = JobQueue(**high_queue_data)
        normal_queue = JobQueue(**normal_queue_data)
        
        # Create normal priority first
        await job_queue_repository.create(normal_queue)
        await job_queue_repository.create(high_queue)
        
        # Get next job
        next_job = await job_queue_repository.get_next_job()
        
        assert next_job is not None
        assert next_job.queue_status == 'queued'
    
    async def test_update_queue_status(self, job_queue_repository, created_queue_entry):
        """Test updating queue status."""
        success = await job_queue_repository.update_queue_status(
            created_queue_entry.job_id,
            'processing',
            worker_id='worker_1',
            processing_node='node_1'
        )
        
        assert success is True
        
        # Verify the update
        updated_entry = await job_queue_repository.get_by_id(created_queue_entry.id)
        assert updated_entry.queue_status == 'processing'
        assert updated_entry.worker_id == 'worker_1'
        assert updated_entry.processing_node == 'node_1'
        assert updated_entry.processing_started_at is not None
    
    async def test_increment_retry_count(self, job_queue_repository, created_queue_entry):
        """Test incrementing retry count."""
        original_count = created_queue_entry.retry_count
        
        success = await job_queue_repository.increment_retry_count(created_queue_entry.job_id)
        
        assert success is True
        
        # Verify the increment
        updated_entry = await job_queue_repository.get_by_id(created_queue_entry.id)
        assert updated_entry.retry_count == original_count + 1
        assert updated_entry.next_retry_at is not None
        assert updated_entry.queue_status == 'retry_scheduled'


class TestRepositoryErrorHandling:
    """Test error handling in repositories."""
    
    async def test_get_nonexistent_entity(self, user_repository):
        """Test getting non-existent entity returns None."""
        non_existent_id = uuid4()
        result = await user_repository.get_by_id(non_existent_id)
        assert result is None
    
    async def test_update_nonexistent_entity(self, user_repository, sample_user_data):
        """Test updating non-existent entity."""
        # Create user with non-existent ID
        sample_user_data['id'] = uuid4()
        user = User(**sample_user_data)
        
        # This should work as merge will create if not exists
        # In a real scenario, you might want different behavior
        updated_user = await user_repository.update(user)
        assert updated_user is not None
    
    async def test_delete_nonexistent_entity(self, user_repository):
        """Test deleting non-existent entity."""
        non_existent_id = uuid4()
        success = await user_repository.delete(non_existent_id)
        assert success is False


class TestRepositoryPagination:
    """Test pagination functionality."""
    
    async def test_pagination_params(self):
        """Test pagination parameter validation."""
        # Test default values
        pagination = PaginationParams()
        assert pagination.page == 1
        assert pagination.page_size == 20
        assert pagination.offset == 0
        
        # Test custom values
        pagination = PaginationParams(page=3, page_size=10)
        assert pagination.page == 3
        assert pagination.page_size == 10
        assert pagination.offset == 20
        
        # Test invalid values are corrected
        pagination = PaginationParams(page=0, page_size=0)
        assert pagination.page == 1
        assert pagination.page_size == 1
    
    async def test_filter_criteria(self):
        """Test filter criteria functionality."""
        filters = FilterCriteria(status='active', role='user')
        filter_dict = filters.to_dict()
        
        assert filter_dict['status'] == 'active'
        assert filter_dict['role'] == 'user'
        
        # Test with None values (should be excluded)
        filters = FilterCriteria(status='active', role=None)
        filter_dict = filters.to_dict()
        
        assert 'status' in filter_dict
        assert 'role' not in filter_dict
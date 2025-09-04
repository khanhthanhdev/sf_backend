"""
Unit tests for job repository implementation.

Tests cover CRUD operations, business logic, error handling,
and edge cases for the JobRepository.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from src.domain.value_objects import JobId, UserId, JobStatus, JobPriority
from src.infrastructure.repositories import JobRepository, PaginationParams
from .conftest import JobFactory, UserFactory, create_test_job, create_test_user


class TestJobRepository:
    """Test suite for JobRepository."""
    
    async def test_create_job_success(self, job_repository: JobRepository):
        """Test successful job creation."""
        job = JobFactory.create_job()
        
        result = await job_repository.create(job)
        
        assert result.success
        assert result.value.job_id == job.job_id
        assert result.value.user_id == job.user_id
        assert result.value.job_type == job.job_type
        assert result.value.status == job.status
    
    async def test_get_by_id_existing_job(self, job_repository: JobRepository):
        """Test getting existing job by ID."""
        job = await create_test_job(job_repository)
        
        result = await job_repository.get_by_id(uuid4(job.job_id.value))
        
        assert result.success
        assert result.value is not None
        assert result.value.job_id == job.job_id
    
    async def test_get_by_id_non_existing_job(self, job_repository: JobRepository):
        """Test getting non-existing job by ID."""
        non_existing_id = uuid4()
        
        result = await job_repository.get_by_id(non_existing_id)
        
        assert result.success
        assert result.value is None
    
    async def test_update_job_success(self, job_repository: JobRepository):
        """Test successful job update."""
        job = await create_test_job(job_repository)
        
        # Update job properties
        from src.domain.value_objects import JobStatus
        job._status = JobStatus("processing")
        job._updated_at = datetime.utcnow()
        
        result = await job_repository.update(job)
        
        assert result.success
        assert result.value.status.value == "processing"
    
    async def test_delete_job_success(self, job_repository: JobRepository):
        """Test successful job deletion (soft delete)."""
        job = await create_test_job(job_repository)
        
        result = await job_repository.delete(uuid4(job.job_id.value))
        
        assert result.success
        assert result.value is True
        
        # Verify job is soft deleted
        get_result = await job_repository.get_by_id(uuid4(job.job_id.value))
        assert get_result.success
        assert get_result.value is None  # Should not find deleted job
    
    async def test_list_jobs_no_filters(self, job_repository: JobRepository):
        """Test listing jobs without filters."""
        # Create test jobs
        for i in range(3):
            await create_test_job(job_repository)
        
        result = await job_repository.list()
        
        assert result.success
        assert len(result.value.items) >= 3
        assert result.value.total_count >= 3
    
    async def test_list_jobs_with_pagination(self, job_repository: JobRepository):
        """Test listing jobs with pagination."""
        # Create test jobs
        for i in range(5):
            await create_test_job(job_repository)
        
        pagination = PaginationParams(page=1, size=2)
        result = await job_repository.list(pagination=pagination)
        
        assert result.success
        assert len(result.value.items) <= 2
        assert result.value.page == 1
        assert result.value.size == 2
    
    async def test_list_jobs_with_user_filter(self, job_repository: JobRepository):
        """Test listing jobs filtered by user."""
        user_id = str(uuid4())
        
        # Create jobs for specific user
        await create_test_job(job_repository, user_id=user_id)
        await create_test_job(job_repository, user_id=user_id)
        await create_test_job(job_repository)  # Different user
        
        result = await job_repository.list(filters={"user_id": user_id})
        
        assert result.success
        assert len(result.value.items) >= 2
        assert all(job.user_id.value == user_id for job in result.value.items)
    
    async def test_list_jobs_with_status_filter(self, job_repository: JobRepository):
        """Test listing jobs filtered by status."""
        # Create job with specific status
        job = JobFactory.create_job()
        from src.domain.value_objects import JobStatus
        job._status = JobStatus("processing")
        
        created_job = await create_test_job(job_repository)
        # Update to processing status
        created_job._status = JobStatus("processing")
        await job_repository.update(created_job)
        
        result = await job_repository.list(filters={"status": "processing"})
        
        assert result.success
        assert all(job.status.value == "processing" for job in result.value.items)
    
    async def test_get_by_user_id(self, job_repository: JobRepository):
        """Test getting jobs by user ID."""
        user_id = UserId(str(uuid4()))
        
        # Create jobs for user
        await create_test_job(job_repository, user_id=user_id.value)
        await create_test_job(job_repository, user_id=user_id.value)
        
        result = await job_repository.get_by_user_id(user_id)
        
        assert result.success
        assert len(result.value.items) >= 2
        assert all(job.user_id == user_id for job in result.value.items)
    
    async def test_get_by_status(self, job_repository: JobRepository):
        """Test getting jobs by status."""
        status = JobStatus("queued")
        
        # Create jobs with specific status
        await create_test_job(job_repository)  # Default is queued
        await create_test_job(job_repository)
        
        result = await job_repository.get_by_status(status)
        
        assert result.success
        assert len(result.value.items) >= 2
        assert all(job.status == status for job in result.value.items)
    
    async def test_get_by_priority(self, job_repository: JobRepository):
        """Test getting jobs by priority."""
        priority = JobPriority("high")
        
        # Create job with high priority
        job = JobFactory.create_job()
        job._priority = priority
        await job_repository.create(job)
        
        result = await job_repository.get_by_priority(priority)
        
        assert result.success
        assert any(job.priority == priority for job in result.value.items)
    
    async def test_get_pending_jobs(self, job_repository: JobRepository):
        """Test getting pending jobs."""
        # Create pending jobs
        job1 = JobFactory.create_job()
        job1._status = JobStatus("queued")
        await job_repository.create(job1)
        
        job2 = JobFactory.create_job()
        job2._status = JobStatus("pending")
        await job_repository.create(job2)
        
        # Create non-pending job
        job3 = JobFactory.create_job()
        job3._status = JobStatus("completed")
        await job_repository.create(job3)
        
        result = await job_repository.get_pending_jobs(limit=10)
        
        assert result.success
        pending_statuses = {"queued", "pending"}
        assert all(job.status.value in pending_statuses for job in result.value)
    
    async def test_get_pending_jobs_with_limit(self, job_repository: JobRepository):
        """Test getting pending jobs with limit."""
        # Create multiple pending jobs
        for i in range(5):
            job = JobFactory.create_job()
            job._status = JobStatus("queued")
            await job_repository.create(job)
        
        result = await job_repository.get_pending_jobs(limit=2)
        
        assert result.success
        assert len(result.value) <= 2
    
    async def test_get_jobs_by_video_id(self, job_repository: JobRepository):
        """Test getting jobs by video ID (using job ID as video ID)."""
        job = await create_test_job(job_repository)
        
        from src.domain.value_objects import VideoId
        video_id = VideoId(job.job_id.value)
        
        result = await job_repository.get_jobs_by_video_id(video_id)
        
        assert result.success
        assert len(result.value.items) == 1
        assert result.value.items[0].job_id == job.job_id
    
    async def test_exists_existing_job(self, job_repository: JobRepository):
        """Test checking existence of existing job."""
        job = await create_test_job(job_repository)
        
        result = await job_repository.exists(uuid4(job.job_id.value))
        
        assert result.success
        assert result.value is True
    
    async def test_exists_non_existing_job(self, job_repository: JobRepository):
        """Test checking existence of non-existing job."""
        non_existing_id = uuid4()
        
        result = await job_repository.exists(non_existing_id)
        
        assert result.success
        assert result.value is False
    
    async def test_count_jobs_no_filters(self, job_repository: JobRepository):
        """Test counting jobs without filters."""
        initial_count_result = await job_repository.count()
        initial_count = initial_count_result.value if initial_count_result.success else 0
        
        # Create test jobs
        for i in range(3):
            await create_test_job(job_repository)
        
        result = await job_repository.count()
        
        assert result.success
        assert result.value == initial_count + 3
    
    async def test_count_jobs_with_filters(self, job_repository: JobRepository):
        """Test counting jobs with filters."""
        user_id = str(uuid4())
        
        # Create jobs for specific user
        for i in range(2):
            await create_test_job(job_repository, user_id=user_id)
        
        result = await job_repository.count(filters={"user_id": user_id})
        
        assert result.success
        assert result.value >= 2
    
    async def test_job_priority_ordering(self, job_repository: JobRepository):
        """Test that pending jobs are ordered by priority."""
        # Create jobs with different priorities
        low_job = JobFactory.create_job()
        low_job._priority = JobPriority("low")
        low_job._status = JobStatus("queued")
        await job_repository.create(low_job)
        
        high_job = JobFactory.create_job()
        high_job._priority = JobPriority("high")
        high_job._status = JobStatus("queued")
        await job_repository.create(high_job)
        
        result = await job_repository.get_pending_jobs(limit=10)
        
        assert result.success
        # High priority jobs should come first in pending queue
        job_priorities = [job.priority.value for job in result.value]
        if "high" in job_priorities and "low" in job_priorities:
            high_index = job_priorities.index("high")
            low_index = job_priorities.index("low")
            assert high_index < low_index
    
    async def test_job_configuration_persistence(self, job_repository: JobRepository):
        """Test that job configuration is properly persisted."""
        # Create job with complex configuration
        from src.domain.value_objects import JobConfiguration
        config_data = {
            "video_config": {
                "title": "Complex Video",
                "topic": "technology",
                "context": "Advanced testing",
                "quality": "4k",
                "format": "mp4",
                "resolution": "2160p",
                "include_subtitles": True,
                "include_thumbnail": True,
                "custom_settings": {
                    "bitrate": "10000",
                    "fps": 60
                }
            }
        }
        config = JobConfiguration.create(config_data).value
        
        job = JobFactory.create_job()
        job._configuration = config
        
        result = await job_repository.create(job)
        assert result.success
        
        # Retrieve and verify configuration
        retrieved_result = await job_repository.get_by_id(uuid4(result.value.job_id.value))
        assert retrieved_result.success
        
        retrieved_config = retrieved_result.value.configuration.to_dict()
        assert retrieved_config["video_config"]["title"] == "Complex Video"
        assert retrieved_config["video_config"]["custom_settings"]["fps"] == 60
    
    async def test_job_progress_updates(self, job_repository: JobRepository):
        """Test job progress updates."""
        job = await create_test_job(job_repository)
        
        # Update progress
        from src.domain.value_objects import JobProgress
        new_progress = JobProgress(
            percentage=50.0,
            current_stage="processing",
            stages_completed=["validation", "preparation"],
            processing_time_seconds=120.5
        )
        job._progress = new_progress
        
        result = await job_repository.update(job)
        assert result.success
        assert result.value.progress.percentage == 50.0
        assert result.value.progress.current_stage == "processing"
        assert "validation" in result.value.progress.stages_completed

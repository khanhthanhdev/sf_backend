"""
AWS RDS-based Job Service for video generation system.

This service provides job management operations using AWS RDS PostgreSQL
instead of Redis, with full Pydantic model integration and async operations.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from uuid import UUID, uuid4

from ..models.job import (
    Job, JobStatus, JobType, JobPriority, JobConfiguration,
    JobProgress, JobError, JobMetrics, JobCreateRequest,
    BatchJobCreateRequest, JobResponse, JobStatusResponse,
    JobListResponse, BatchJobResponse
)
from ..database.connection import RDSConnectionManager
from ..database.pydantic_models import JobDB, JobQueueDB
from ..core.exceptions import JobNotFoundError, JobValidationError, DatabaseError

logger = logging.getLogger(__name__)


class AWSJobService:
    """
    RDS-based job service for managing video generation jobs.
    
    Provides comprehensive job lifecycle management with database persistence,
    queue management, metrics tracking, and batch processing capabilities.
    """
    
    def __init__(self, db_manager: RDSConnectionManager, redis_client=None):
        """
        Initialize the AWS Job Service.
        
        Args:
            db_manager: RDS connection manager for database operations
            redis_client: Optional Redis client for caching (can be None)
        """
        self.db_manager = db_manager
        self.redis_client = redis_client
        self._cache_ttl = 300  # 5 minutes cache TTL
        
        logger.info("Initialized AWS Job Service with RDS backend")
    
    async def create_job(self, user_id: str, job_request: JobCreateRequest) -> JobResponse:
        """
        Create a new job and add it to the queue.
        
        Args:
            user_id: User ID creating the job
            job_request: Job creation request with configuration
            
        Returns:
            JobResponse with created job information
            
        Raises:
            JobValidationError: If job configuration is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Create Job model from request
            job = Job(
                user_id=user_id,
                job_type=JobType.VIDEO_GENERATION,
                priority=job_request.priority,
                configuration=job_request.configuration,
                status=JobStatus.QUEUED
            )
            
            # Convert to database model
            job_db = JobDB.from_job_model(job, UUID(user_id))
            
            # Save job to database
            saved_job_data = await self.db_manager.save_pydantic_model(
                job_db, 
                "jobs",
                conflict_columns=["id"]
            )
            
            # Add to job queue
            queue_entry = JobQueueDB(
                job_id=job_db.id,
                priority=job_request.priority,
                queue_status="queued"
            )
            
            await self.db_manager.save_pydantic_model(
                queue_entry,
                "job_queue",
                conflict_columns=["job_id"]
            )
            
            # Update queue position
            await self._update_queue_positions()
            
            # Cache job status if Redis is available
            if self.redis_client:
                await self._cache_job_status(str(job_db.id), JobStatus.QUEUED)
            
            logger.info(f"Created job {job_db.id} for user {user_id}")
            
            return JobResponse(
                job_id=str(job_db.id),
                status=JobStatus.QUEUED,
                progress=JobProgress(),
                created_at=job_db.created_at,
                estimated_completion=self._estimate_completion_time(job_request.priority)
            )
            
        except Exception as e:
            logger.error(f"Failed to create job for user {user_id}: {e}")
            raise DatabaseError(f"Job creation failed: {str(e)}")
    
    async def get_job(self, job_id: str, user_id: Optional[str] = None) -> Job:
        """
        Get a job by ID with optional user validation.
        
        Args:
            job_id: Job ID to retrieve
            user_id: Optional user ID for ownership validation
            
        Returns:
            Job model instance
            
        Raises:
            JobNotFoundError: If job doesn't exist or user doesn't have access
        """
        try:
            # Try cache first if Redis is available
            if self.redis_client:
                cached_job = await self._get_cached_job(job_id)
                if cached_job:
                    if user_id and cached_job.user_id != user_id:
                        raise JobNotFoundError(f"Job {job_id} not found for user {user_id}")
                    return cached_job
            
            # Query database
            where_clause = "id = $1 AND is_deleted = FALSE"
            params = [UUID(job_id)]
            
            if user_id:
                where_clause += " AND user_id = $2"
                params.append(UUID(user_id))
            
            job_db = await self.db_manager.get_pydantic_model(
                JobDB, "jobs", where_clause, params
            )
            
            if not job_db:
                raise JobNotFoundError(f"Job {job_id} not found")
            
            job = job_db.to_job_model()
            
            # Cache the job if Redis is available
            if self.redis_client:
                await self._cache_job(job)
            
            return job
            
        except JobNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise DatabaseError(f"Failed to retrieve job: {str(e)}")
    
    async def update_job_status(self, job_id: str, status: JobStatus, 
                               progress: Optional[float] = None,
                               stage: Optional[str] = None,
                               error_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update job status and progress.
        
        Args:
            job_id: Job ID to update
            status: New job status
            progress: Progress percentage (0-100)
            stage: Current processing stage
            error_info: Error information if status is FAILED
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current job
            job_db = await self.db_manager.get_pydantic_model(
                JobDB, "jobs", "id = $1 AND is_deleted = FALSE", [UUID(job_id)]
            )
            
            if not job_db:
                logger.warning(f"Job {job_id} not found for status update")
                return False
            
            # Update job fields
            job_db.status = status
            job_db.updated_at = datetime.utcnow()
            
            # Update progress if provided
            if progress is not None:
                job_db.progress_percentage = min(100.0, max(0.0, progress))
            
            if stage:
                job_db.current_stage = stage
                if stage not in job_db.stages_completed:
                    job_db.stages_completed.append(stage)
            
            # Set timestamps based on status
            if status == JobStatus.PROCESSING and not job_db.started_at:
                job_db.started_at = datetime.utcnow()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if not job_db.completed_at:
                    job_db.completed_at = datetime.utcnow()
                if status == JobStatus.COMPLETED:
                    job_db.progress_percentage = 100.0
            
            # Handle error information
            if error_info and status == JobStatus.FAILED:
                job_db.error_info = error_info
            
            # Update in database
            success = await self.db_manager.update_pydantic_model(
                job_db, "jobs", "id = $1", [UUID(job_id)]
            )
            
            if success:
                # Update queue status if needed
                await self._update_queue_status(UUID(job_id), status)
                
                # Update cache if Redis is available
                if self.redis_client:
                    await self._cache_job_status(job_id, status)
                    await self._invalidate_job_cache(job_id)
                
                logger.info(f"Updated job {job_id} status to {status.value}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False
    
    async def get_jobs_paginated(self, user_id: str, limit: int = 10, offset: int = 0,
                                filters: Optional[Dict[str, Any]] = None) -> JobListResponse:
        """
        Get paginated list of jobs for a user with optional filtering.
        
        Args:
            user_id: User ID to get jobs for
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            filters: Optional filters (status, job_type, priority, dates)
            
        Returns:
            JobListResponse with jobs and pagination info
        """
        try:
            # Build where clause with filters
            where_clause = "user_id = $1 AND is_deleted = FALSE"
            params = [UUID(user_id)]
            param_index = 2
            
            if filters:
                if filters.get("status"):
                    where_clause += f" AND status = ${param_index}"
                    params.append(filters["status"])
                    param_index += 1
                
                if filters.get("job_type"):
                    where_clause += f" AND job_type = ${param_index}"
                    params.append(filters["job_type"])
                    param_index += 1
                
                if filters.get("priority"):
                    where_clause += f" AND priority = ${param_index}"
                    params.append(filters["priority"])
                    param_index += 1
                
                if filters.get("created_after"):
                    where_clause += f" AND created_at >= ${param_index}"
                    params.append(filters["created_after"])
                    param_index += 1
                
                if filters.get("created_before"):
                    where_clause += f" AND created_at <= ${param_index}"
                    params.append(filters["created_before"])
                    param_index += 1
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM jobs WHERE {where_clause}"
            count_result = await self.db_manager.execute_query(count_query, dict(zip(
                [f"${i+1}" for i in range(len(params))], params
            )))
            total_count = count_result[0]["count"] if count_result else 0
            
            # Get jobs with pagination
            jobs_db = await self.db_manager.get_pydantic_models(
                JobDB, "jobs", where_clause, params,
                order_by="created_at DESC", limit=limit, offset=offset
            )
            
            # Convert to response models
            job_responses = []
            for job_db in jobs_db:
                job_responses.append(JobResponse(
                    job_id=str(job_db.id),
                    status=job_db.status,
                    progress=JobProgress(
                        percentage=job_db.progress_percentage,
                        current_stage=job_db.current_stage,
                        stages_completed=job_db.stages_completed,
                        estimated_completion=job_db.estimated_completion,
                        processing_time_seconds=job_db.processing_time_seconds
                    ),
                    created_at=job_db.created_at,
                    estimated_completion=job_db.estimated_completion
                ))
            
            # Calculate pagination info
            page = (offset // limit) + 1
            has_next = (offset + limit) < total_count
            has_previous = offset > 0
            
            return JobListResponse(
                jobs=job_responses,
                total_count=total_count,
                page=page,
                items_per_page=limit,
                has_next=has_next,
                has_previous=has_previous
            )
            
        except Exception as e:
            logger.error(f"Failed to get paginated jobs for user {user_id}: {e}")
            return JobListResponse(
                jobs=[],
                total_count=0,
                page=1,
                items_per_page=limit,
                has_next=False,
                has_previous=False
            )
    
    async def cancel_job(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """
        Cancel a job if it's in a cancellable state.
        
        Args:
            job_id: Job ID to cancel
            user_id: Optional user ID for ownership validation
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            # Get job with user validation
            job = await self.get_job(job_id, user_id)
            
            # Check if job can be cancelled
            if not job.can_be_cancelled:
                logger.warning(f"Job {job_id} cannot be cancelled. Current status: {job.status}")
                return False
            
            # Update job status to cancelled
            return await self.update_job_status(
                job_id, JobStatus.CANCELLED,
                stage="cancelled"
            )
            
        except JobNotFoundError:
            logger.warning(f"Job {job_id} not found for cancellation")
            return False
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    async def soft_delete_job(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """
        Perform soft delete on a job.
        
        Args:
            job_id: Job ID to delete
            user_id: Optional user ID for ownership validation
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Validate job exists and user has access
            await self.get_job(job_id, user_id)
            
            # Perform soft delete
            success = await self.db_manager.delete_pydantic_model(
                "jobs", "id = $1", [UUID(job_id)], soft_delete=True
            )
            
            if success:
                # Also soft delete queue entry
                await self.db_manager.delete_pydantic_model(
                    "job_queue", "job_id = $1", [UUID(job_id)], soft_delete=True
                )
                
                # Clear cache if Redis is available
                if self.redis_client:
                    await self._invalidate_job_cache(job_id)
                
                logger.info(f"Soft deleted job {job_id}")
                return True
            
            return False
            
        except JobNotFoundError:
            logger.warning(f"Job {job_id} not found for deletion")
            return False
        except Exception as e:
            logger.error(f"Failed to soft delete job {job_id}: {e}")
            return False
    
    async def update_job_metrics(self, job_id: str, cpu_usage: Optional[float] = None,
                                memory_usage: Optional[float] = None,
                                disk_usage: Optional[float] = None,
                                network_usage: Optional[float] = None) -> bool:
        """
        Update performance metrics for a job.
        
        Args:
            job_id: Job ID to update metrics for
            cpu_usage: CPU usage percentage
            memory_usage: Memory usage in MB
            disk_usage: Disk usage in MB
            network_usage: Network usage in MB
            
        Returns:
            True if metrics updated successfully, False otherwise
        """
        try:
            # Get current job
            job_db = await self.db_manager.get_pydantic_model(
                JobDB, "jobs", "id = $1 AND is_deleted = FALSE", [UUID(job_id)]
            )
            
            if not job_db:
                return False
            
            # Initialize or update metrics
            if not job_db.metrics:
                job_db.metrics = {}
            
            # Update metrics
            if cpu_usage is not None:
                job_db.metrics["cpu_usage_percent"] = cpu_usage
            if memory_usage is not None:
                job_db.metrics["memory_usage_mb"] = memory_usage
            if disk_usage is not None:
                job_db.metrics["disk_usage_mb"] = disk_usage
            if network_usage is not None:
                job_db.metrics["network_usage_mb"] = network_usage
            
            # Calculate processing time if job is active
            if job_db.started_at:
                if job_db.completed_at:
                    job_db.metrics["processing_time_seconds"] = (
                        job_db.completed_at - job_db.started_at
                    ).total_seconds()
                else:
                    job_db.metrics["processing_time_seconds"] = (
                        datetime.utcnow() - job_db.started_at
                    ).total_seconds()
            
            # Calculate queue time
            if job_db.started_at:
                job_db.metrics["queue_time_seconds"] = (
                    job_db.started_at - job_db.created_at
                ).total_seconds()
            
            # Update in database
            success = await self.db_manager.update_pydantic_model(
                job_db, "jobs", "id = $1", [UUID(job_id)]
            )
            
            if success:
                logger.info(f"Updated metrics for job {job_id}")
                
                # Clear cache to force refresh
                if self.redis_client:
                    await self._invalidate_job_cache(job_id)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update metrics for job {job_id}: {e}")
            return False
    
    async def get_job_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get job statistics for a user.
        
        Args:
            user_id: User ID to get statistics for
            
        Returns:
            Dict containing job statistics
        """
        try:
            # Get user's jobs
            where_clause = "user_id = $1 AND is_deleted = FALSE"
            params = [UUID(user_id)]
            
            jobs_db = await self.db_manager.get_pydantic_models(
                JobDB, "jobs", where_clause, params
            )
            
            if not jobs_db:
                return {
                    "total_jobs": 0,
                    "by_status": {},
                    "by_type": {},
                    "by_priority": {},
                    "recent_activity": []
                }
            
            # Initialize counters
            stats = {
                "total_jobs": len(jobs_db),
                "by_status": {},
                "by_type": {},
                "by_priority": {},
                "recent_activity": []
            }
            
            recent_jobs = []
            
            # Process each job
            for job_db in jobs_db:
                # Count by status
                status = job_db.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Count by type
                job_type = job_db.job_type.value
                stats["by_type"][job_type] = stats["by_type"].get(job_type, 0) + 1
                
                # Count by priority
                priority = job_db.priority.value
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
                
                # Collect recent jobs (last 7 days)
                if job_db.created_at >= datetime.utcnow() - timedelta(days=7):
                    # Get topic from configuration
                    topic = "Unknown"
                    if job_db.configuration and "topic" in job_db.configuration:
                        topic = job_db.configuration["topic"]
                        if len(topic) > 50:
                            topic = topic[:50] + "..."
                    
                    recent_jobs.append({
                        "job_id": str(job_db.id),
                        "status": job_db.status.value,
                        "created_at": job_db.created_at.isoformat(),
                        "topic": topic
                    })
            
            # Sort recent jobs by creation date
            recent_jobs.sort(key=lambda x: x["created_at"], reverse=True)
            stats["recent_activity"] = recent_jobs[:10]  # Last 10 recent jobs
            
            logger.info(f"Generated job statistics for user {user_id}, total jobs: {stats['total_jobs']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get job statistics for user {user_id}: {e}")
            return {
                "total_jobs": 0,
                "by_status": {},
                "by_type": {},
                "by_priority": {},
                "recent_activity": []
            }
    
    async def cleanup_old_jobs(self, retention_days: int = 30) -> int:
        """
        Clean up old completed jobs based on retention policy.
        
        Args:
            retention_days: Number of days to retain completed jobs
            
        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find old completed jobs
            where_clause = """
                completed_at < $1 AND 
                status IN ('completed', 'failed', 'cancelled') AND 
                is_deleted = FALSE
            """
            params = [cutoff_date]
            
            old_jobs = await self.db_manager.get_pydantic_models(
                JobDB, "jobs", where_clause, params
            )
            
            cleaned_count = 0
            
            # Soft delete old jobs
            for job_db in old_jobs:
                try:
                    success = await self.db_manager.delete_pydantic_model(
                        "jobs", "id = $1", [job_db.id], soft_delete=True
                    )
                    
                    if success:
                        # Also clean up queue entry
                        await self.db_manager.delete_pydantic_model(
                            "job_queue", "job_id = $1", [job_db.id], soft_delete=True
                        )
                        
                        # Clear cache if Redis is available
                        if self.redis_client:
                            await self._invalidate_job_cache(str(job_db.id))
                        
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to cleanup job {job_db.id}: {e}")
                    continue
            
            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
    
    async def get_next_queued_job(self, worker_id: Optional[str] = None) -> Optional[Job]:
        """
        Get the next job from the queue for processing.
        
        Args:
            worker_id: Optional worker ID for tracking
            
        Returns:
            Next job to process or None if queue is empty
        """
        try:
            # Get next queued job ordered by priority and creation time
            where_clause = """
                queue_status = 'queued' AND 
                job_id IN (
                    SELECT id FROM jobs 
                    WHERE status = 'queued' AND is_deleted = FALSE
                )
            """
            
            queue_entries = await self.db_manager.get_pydantic_models(
                JobQueueDB, "job_queue", where_clause,
                order_by="priority DESC, queued_at ASC", limit=1
            )
            
            if not queue_entries:
                return None
            
            queue_entry = queue_entries[0]
            
            # Get the job details
            job_db = await self.db_manager.get_pydantic_model(
                JobDB, "jobs", "id = $1", [queue_entry.job_id]
            )
            
            if not job_db:
                # Clean up orphaned queue entry
                await self.db_manager.delete_pydantic_model(
                    "job_queue", "id = $1", [queue_entry.id]
                )
                return None
            
            # Update queue entry to processing
            queue_entry.queue_status = "processing"
            queue_entry.processing_started_at = datetime.utcnow()
            if worker_id:
                queue_entry.worker_id = worker_id
            
            await self.db_manager.update_pydantic_model(
                queue_entry, "job_queue", "id = $1", [queue_entry.id]
            )
            
            # Update job status to processing
            await self.update_job_status(str(job_db.id), JobStatus.PROCESSING)
            
            job = job_db.to_job_model()
            logger.info(f"Dequeued job {job.id} for processing")
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to get next queued job: {e}")
            return None
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and statistics.
        
        Returns:
            Dict containing queue statistics
        """
        try:
            # Get queue counts by status
            queue_stats_query = """
                SELECT queue_status, COUNT(*) as count
                FROM job_queue
                GROUP BY queue_status
            """
            
            queue_results = await self.db_manager.execute_query(queue_stats_query)
            queue_counts = {row["queue_status"]: row["count"] for row in queue_results}
            
            # Get job status distribution
            job_stats_query = """
                SELECT status, COUNT(*) as count
                FROM jobs
                WHERE is_deleted = FALSE
                GROUP BY status
            """
            
            job_results = await self.db_manager.execute_query(job_stats_query)
            job_counts = {row["status"]: row["count"] for row in job_results}
            
            # Get average processing time for completed jobs (last 24 hours)
            avg_time_query = """
                SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds
                FROM jobs
                WHERE status = 'completed' 
                AND completed_at > NOW() - INTERVAL '24 hours'
                AND started_at IS NOT NULL
                AND is_deleted = FALSE
            """
            
            avg_time_result = await self.db_manager.execute_query(avg_time_query)
            avg_processing_time = 0
            if avg_time_result and avg_time_result[0]["avg_seconds"]:
                avg_processing_time = float(avg_time_result[0]["avg_seconds"])
            
            # Get oldest queued job
            oldest_job_query = """
                SELECT MIN(created_at) as oldest_queued
                FROM jobs
                WHERE status = 'queued' AND is_deleted = FALSE
            """
            
            oldest_result = await self.db_manager.execute_query(oldest_job_query)
            oldest_queued = None
            if oldest_result and oldest_result[0]["oldest_queued"]:
                oldest_queued = oldest_result[0]["oldest_queued"]
            
            return {
                "queue_counts": queue_counts,
                "job_status_counts": job_counts,
                "total_queued": queue_counts.get("queued", 0),
                "total_processing": queue_counts.get("processing", 0),
                "total_completed_today": job_counts.get("completed", 0),
                "total_failed_today": job_counts.get("failed", 0),
                "avg_processing_time_seconds": avg_processing_time,
                "oldest_queued_job": oldest_queued.isoformat() if oldest_queued else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {
                "queue_counts": {},
                "job_status_counts": {},
                "total_queued": 0,
                "total_processing": 0,
                "total_completed_today": 0,
                "total_failed_today": 0,
                "avg_processing_time_seconds": 0,
                "oldest_queued_job": None,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # Private helper methods
    
    async def _update_queue_positions(self):
        """Update queue positions for all queued jobs."""
        try:
            # Get all queued jobs ordered by priority and creation time
            where_clause = "queue_status = 'queued'"
            queue_entries = await self.db_manager.get_pydantic_models(
                JobQueueDB, "job_queue", where_clause,
                order_by="priority DESC, queued_at ASC"
            )
            
            # Update positions
            for position, entry in enumerate(queue_entries, 1):
                entry.queue_position = position
                await self.db_manager.update_pydantic_model(
                    entry, "job_queue", "id = $1", [entry.id]
                )
                
        except Exception as e:
            logger.error(f"Failed to update queue positions: {e}")
    
    async def _update_queue_status(self, job_id: UUID, job_status: JobStatus):
        """Update queue status based on job status."""
        try:
            queue_entry = await self.db_manager.get_pydantic_model(
                JobQueueDB, "job_queue", "job_id = $1", [job_id]
            )
            
            if queue_entry:
                if job_status == JobStatus.PROCESSING:
                    queue_entry.queue_status = "processing"
                    queue_entry.processing_started_at = datetime.utcnow()
                elif job_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    queue_entry.queue_status = "completed"
                    queue_entry.completed_at = datetime.utcnow()
                
                await self.db_manager.update_pydantic_model(
                    queue_entry, "job_queue", "id = $1", [queue_entry.id]
                )
                
        except Exception as e:
            logger.error(f"Failed to update queue status for job {job_id}: {e}")
    
    def _estimate_completion_time(self, priority: JobPriority) -> datetime:
        """Estimate job completion time based on priority and queue."""
        base_minutes = {
            JobPriority.URGENT: 2,
            JobPriority.HIGH: 5,
            JobPriority.NORMAL: 10,
            JobPriority.LOW: 20
        }
        
        estimated_minutes = base_minutes.get(priority, 10)
        return datetime.utcnow() + timedelta(minutes=estimated_minutes)
    
    # Redis caching methods (optional)
    
    async def _cache_job(self, job: Job):
        """Cache job data in Redis if available."""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"job:{job.id}"
            await self.redis_client.setex(
                cache_key, self._cache_ttl, job.model_dump_json()
            )
        except Exception as e:
            logger.warning(f"Failed to cache job {job.id}: {e}")
    
    async def _cache_job_status(self, job_id: str, status: JobStatus):
        """Cache job status in Redis if available."""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"job_status:{job_id}"
            await self.redis_client.setex(
                cache_key, self._cache_ttl, status.value
            )
        except Exception as e:
            logger.warning(f"Failed to cache job status {job_id}: {e}")
    
    async def _get_cached_job(self, job_id: str) -> Optional[Job]:
        """Get cached job from Redis if available."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"job:{job_id}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return Job.model_validate_json(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached job {job_id}: {e}")
        
        return None
    
    async def _invalidate_job_cache(self, job_id: str):
        """Invalidate job cache in Redis if available."""
        if not self.redis_client:
            return
        
        try:
            cache_keys = [f"job:{job_id}", f"job_status:{job_id}"]
            await self.redis_client.delete(*cache_keys)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for job {job_id}: {e}")
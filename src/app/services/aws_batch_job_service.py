"""
AWS RDS-based Batch Job Service for video generation system.

This service extends the AWSJobService to provide batch job creation,
management, and queue processing capabilities with priority handling
and cleanup policies.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from .aws_job_service import AWSJobService
from ..models.job import (
    Job, JobStatus, JobType, JobPriority, JobConfiguration,
    BatchJobCreateRequest, BatchJobResponse
)
from ..database.connection import RDSConnectionManager
from ..database.pydantic_models import JobDB, JobQueueDB
from ..core.exceptions import JobValidationError, DatabaseError

logger = logging.getLogger(__name__)


class AWSBatchJobService(AWSJobService):
    """
    Extended job service for batch job processing and queue management.
    
    Provides batch job creation, priority handling, queue position tracking,
    and cleanup policies with database-backed storage.
    """
    
    def __init__(self, db_manager: RDSConnectionManager, redis_client=None):
        """
        Initialize the AWS Batch Job Service.
        
        Args:
            db_manager: RDS connection manager for database operations
            redis_client: Optional Redis client for caching
        """
        super().__init__(db_manager, redis_client)
        self._batch_size_limit = 50
        self._cleanup_retention_days = 30
        
        logger.info("Initialized AWS Batch Job Service with RDS backend")
    
    async def create_batch_jobs(self, user_id: str, batch_request: BatchJobCreateRequest) -> BatchJobResponse:
        """
        Create multiple jobs as a batch operation.
        
        Args:
            user_id: User ID creating the batch
            batch_request: Batch job creation request
            
        Returns:
            BatchJobResponse with batch information and job IDs
            
        Raises:
            JobValidationError: If batch configuration is invalid
            DatabaseError: If database operation fails
        """
        try:
            if len(batch_request.jobs) > self._batch_size_limit:
                raise JobValidationError(f"Batch size exceeds limit of {self._batch_size_limit}")
            
            batch_id = str(uuid4())
            created_jobs = []
            failed_jobs = []
            
            logger.info(
                f"Creating batch {batch_id} with {len(batch_request.jobs)} jobs for user {user_id}"
            )
            
            # Use database transaction for batch creation
            async with self.db_manager.transaction() as conn:
                for i, job_config in enumerate(batch_request.jobs):
                    try:
                        # Create job instance
                        job = Job(
                            user_id=user_id,
                            job_type=JobType.BATCH_VIDEO_GENERATION,
                            priority=batch_request.batch_priority,
                            configuration=job_config,
                            batch_id=batch_id,
                            status=JobStatus.QUEUED
                        )
                        
                        # Convert to database model
                        job_db = JobDB.from_job_model(job, UUID(user_id))
                        
                        # Save job to database within transaction
                        job_data = job_db.model_dump(exclude_none=True)
                        
                        # Handle datetime serialization
                        for key, value in job_data.items():
                            if isinstance(value, datetime):
                                job_data[key] = value.isoformat()
                            elif isinstance(value, (dict, list)):
                                import json
                                job_data[key] = json.dumps(value)
                        
                        # Insert job
                        columns = list(job_data.keys())
                        placeholders = [f"${i+1}" for i in range(len(columns))]
                        values = list(job_data.values())
                        
                        job_query = f"""
                            INSERT INTO jobs ({", ".join(columns)})
                            VALUES ({", ".join(placeholders)})
                            RETURNING id
                        """
                        
                        job_result = await conn.fetchrow(job_query, *values)
                        saved_job_id = job_result["id"]
                        
                        # Add to job queue
                        queue_entry = JobQueueDB(
                            job_id=saved_job_id,
                            priority=batch_request.batch_priority,
                            queue_status="queued"
                        )
                        
                        queue_data = queue_entry.model_dump(exclude_none=True)
                        
                        # Handle datetime serialization for queue entry
                        for key, value in queue_data.items():
                            if isinstance(value, datetime):
                                queue_data[key] = value.isoformat()
                        
                        # Insert queue entry
                        queue_columns = list(queue_data.keys())
                        queue_placeholders = [f"${i+1}" for i in range(len(queue_columns))]
                        queue_values = list(queue_data.values())
                        
                        queue_query = f"""
                            INSERT INTO job_queue ({", ".join(queue_columns)})
                            VALUES ({", ".join(queue_placeholders)})
                        """
                        
                        await conn.execute(queue_query, *queue_values)
                        
                        created_jobs.append({
                            "job_id": str(saved_job_id),
                            "position_in_batch": i + 1,
                            "topic": job_config.topic[:50] + "..." if len(job_config.topic) > 50 else job_config.topic
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to create job {i + 1} in batch {batch_id}: {e}")
                        failed_jobs.append({
                            "position_in_batch": i + 1,
                            "error": str(e),
                            "config": job_config.model_dump()
                        })
            
            # Update queue positions after batch creation
            await self._update_queue_positions()
            
            # Store batch metadata
            batch_metadata = {
                "batch_id": batch_id,
                "user_id": user_id,
                "total_jobs": len(batch_request.jobs),
                "created_jobs": len(created_jobs),
                "failed_jobs": len(failed_jobs),
                "batch_priority": batch_request.batch_priority.value,
                "created_at": datetime.utcnow().isoformat(),
                "job_ids": [job["job_id"] for job in created_jobs]
            }
            
            # Store batch metadata in database
            await self._store_batch_metadata(batch_metadata)
            
            # Cache batch info if Redis is available
            if self.redis_client:
                await self._cache_batch_metadata(batch_id, batch_metadata)
            
            logger.info(
                f"Batch {batch_id} created: {len(created_jobs)} successful, {len(failed_jobs)} failed"
            )
            
            return BatchJobResponse(
                batch_id=batch_id,
                job_ids=[job["job_id"] for job in created_jobs],
                total_jobs=len(created_jobs),
                created_at=datetime.utcnow()
            )
            
        except JobValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create batch jobs for user {user_id}: {e}")
            raise DatabaseError(f"Batch job creation failed: {str(e)}")
    
    async def get_batch_status(self, batch_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get status information for a batch of jobs.
        
        Args:
            batch_id: Batch ID to get status for
            user_id: User ID (for ownership validation)
            
        Returns:
            Dict containing batch status and job summaries
        """
        try:
            # Get batch metadata
            batch_metadata = await self._get_batch_metadata(batch_id)
            
            if not batch_metadata:
                return {"error": "Batch not found"}
            
            # Validate ownership
            if batch_metadata["user_id"] != user_id:
                return {"error": "Access denied"}
            
            # Get status for each job in the batch
            job_statuses = []
            status_counts = {}
            total_progress = 0
            
            for job_id in batch_metadata["job_ids"]:
                try:
                    job_db = await self.db_manager.get_pydantic_model(
                        JobDB, "jobs", "id = $1 AND is_deleted = FALSE", [UUID(job_id)]
                    )
                    
                    if job_db:
                        status = job_db.status.value
                        status_counts[status] = status_counts.get(status, 0) + 1
                        total_progress += job_db.progress_percentage
                        
                        # Get topic from configuration
                        topic = "Unknown"
                        if job_db.configuration and "topic" in job_db.configuration:
                            topic = job_db.configuration["topic"]
                            if len(topic) > 50:
                                topic = topic[:50] + "..."
                        
                        job_statuses.append({
                            "job_id": job_id,
                            "status": status,
                            "progress": job_db.progress_percentage,
                            "topic": topic,
                            "created_at": job_db.created_at.isoformat(),
                            "completed_at": job_db.completed_at.isoformat() if job_db.completed_at else None,
                            "error_message": job_db.error_info.get("error_message") if job_db.error_info else None
                        })
                    
                except Exception as e:
                    logger.warning(f"Failed to get status for job {job_id} in batch {batch_id}: {e}")
                    continue
            
            # Calculate overall batch progress
            overall_progress = total_progress / len(batch_metadata["job_ids"]) if batch_metadata["job_ids"] else 0
            
            # Determine batch status
            total_jobs = len(batch_metadata["job_ids"])
            
            if status_counts.get("failed", 0) == total_jobs:
                batch_status = "failed"
            elif status_counts.get("completed", 0) == total_jobs:
                batch_status = "completed"
            elif status_counts.get("cancelled", 0) == total_jobs:
                batch_status = "cancelled"
            else:
                # Check if we have multiple different states (mixed)
                active_statuses = [status for status, count in status_counts.items() if count > 0]
                final_states = ["completed", "failed", "cancelled"]
                final_state_count = sum(1 for status in final_states if status_counts.get(status, 0) > 0)
                
                # Check for multiple final states first (this indicates truly mixed results)
                if final_state_count > 1:
                    batch_status = "mixed"
                elif status_counts.get("processing", 0) > 0:
                    batch_status = "processing"
                elif status_counts.get("queued", 0) > 0:
                    batch_status = "queued"
                else:
                    batch_status = "mixed"
            
            return {
                "batch_id": batch_id,
                "batch_status": batch_status,
                "overall_progress": round(overall_progress, 2),
                "total_jobs": batch_metadata["total_jobs"],
                "status_summary": status_counts,
                "job_details": job_statuses,
                "created_at": batch_metadata["created_at"],
                "batch_priority": batch_metadata["batch_priority"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get batch status for {batch_id}: {e}")
            return {"error": f"Failed to get batch status: {str(e)}"}
    
    async def cancel_batch_jobs(self, batch_id: str, user_id: str) -> Dict[str, Any]:
        """
        Cancel all jobs in a batch.
        
        Args:
            batch_id: Batch ID to cancel
            user_id: User ID (for ownership validation)
            
        Returns:
            Dict containing cancellation results
        """
        try:
            # Get batch metadata
            batch_metadata = await self._get_batch_metadata(batch_id)
            
            if not batch_metadata:
                return {"error": "Batch not found"}
            
            # Validate ownership
            if batch_metadata["user_id"] != user_id:
                return {"error": "Access denied"}
            
            cancelled_jobs = []
            failed_cancellations = []
            
            # Cancel each job in the batch
            for job_id in batch_metadata["job_ids"]:
                try:
                    success = await self.cancel_job(job_id, user_id)
                    if success:
                        cancelled_jobs.append(job_id)
                    else:
                        failed_cancellations.append(job_id)
                        
                except Exception as e:
                    logger.warning(f"Failed to cancel job {job_id} in batch {batch_id}: {e}")
                    failed_cancellations.append(job_id)
            
            logger.info(
                f"Batch {batch_id} cancellation: {len(cancelled_jobs)} cancelled, "
                f"{len(failed_cancellations)} failed"
            )
            
            return {
                "batch_id": batch_id,
                "cancelled_jobs": cancelled_jobs,
                "failed_cancellations": failed_cancellations,
                "total_requested": len(batch_metadata["job_ids"]),
                "success_rate": len(cancelled_jobs) / len(batch_metadata["job_ids"]) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel batch {batch_id}: {e}")
            return {"error": f"Failed to cancel batch: {str(e)}"}
    
    async def get_priority_queue_status(self) -> Dict[str, Any]:
        """
        Get queue status with priority breakdown.
        
        Returns:
            Dict containing priority-based queue statistics
        """
        try:
            # Get queue counts by priority and status
            priority_queue_query = """
                SELECT 
                    jq.priority,
                    jq.queue_status,
                    COUNT(*) as count,
                    AVG(EXTRACT(EPOCH FROM (NOW() - jq.queued_at))) as avg_wait_time_seconds
                FROM job_queue jq
                JOIN jobs j ON jq.job_id = j.id
                WHERE j.is_deleted = FALSE
                GROUP BY jq.priority, jq.queue_status
                ORDER BY jq.priority DESC, jq.queue_status
            """
            
            priority_results = await self.db_manager.execute_query(priority_queue_query)
            
            # Organize results by priority
            priority_stats = {}
            for row in priority_results:
                priority = row["priority"]
                if priority not in priority_stats:
                    priority_stats[priority] = {}
                
                priority_stats[priority][row["queue_status"]] = {
                    "count": row["count"],
                    "avg_wait_time_seconds": float(row["avg_wait_time_seconds"]) if row["avg_wait_time_seconds"] else 0
                }
            
            # Get estimated processing times by priority
            processing_time_query = """
                SELECT 
                    priority,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_processing_seconds
                FROM jobs
                WHERE status = 'completed' 
                AND completed_at > NOW() - INTERVAL '24 hours'
                AND started_at IS NOT NULL
                AND is_deleted = FALSE
                GROUP BY priority
            """
            
            processing_results = await self.db_manager.execute_query(processing_time_query)
            processing_times = {
                row["priority"]: float(row["avg_processing_seconds"]) 
                for row in processing_results
            }
            
            return {
                "priority_breakdown": priority_stats,
                "avg_processing_times": processing_times,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get priority queue status: {e}")
            return {
                "priority_breakdown": {},
                "avg_processing_times": {},
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def requeue_failed_jobs(self, max_retry_count: int = 3) -> Dict[str, Any]:
        """
        Requeue failed jobs that haven't exceeded retry limit.
        
        Args:
            max_retry_count: Maximum number of retry attempts
            
        Returns:
            Dict containing requeue results
        """
        try:
            # Find failed jobs that can be retried
            failed_jobs_query = """
                SELECT j.id, jq.retry_count
                FROM jobs j
                JOIN job_queue jq ON j.id = jq.job_id
                WHERE j.status = 'failed' 
                AND j.is_deleted = FALSE
                AND jq.retry_count < $1
                AND (jq.next_retry_at IS NULL OR jq.next_retry_at <= NOW())
            """
            
            failed_jobs = await self.db_manager.execute_query(
                failed_jobs_query, {"$1": max_retry_count}
            )
            
            requeued_jobs = []
            failed_requeues = []
            
            for job_row in failed_jobs:
                job_id = job_row["id"]
                retry_count = job_row["retry_count"]
                
                try:
                    # Update job status back to queued
                    success = await self.update_job_status(str(job_id), JobStatus.QUEUED)
                    
                    if success:
                        # Update queue entry
                        queue_update_query = """
                            UPDATE job_queue
                            SET queue_status = 'queued',
                                retry_count = retry_count + 1,
                                next_retry_at = NULL,
                                processing_started_at = NULL,
                                completed_at = NULL
                            WHERE job_id = $1
                        """
                        
                        await self.db_manager.execute_command(
                            queue_update_query, {"$1": job_id}
                        )
                        
                        requeued_jobs.append(str(job_id))
                        logger.info(f"Requeued failed job {job_id} (retry {retry_count + 1})")
                    else:
                        failed_requeues.append(str(job_id))
                        
                except Exception as e:
                    logger.warning(f"Failed to requeue job {job_id}: {e}")
                    failed_requeues.append(str(job_id))
            
            # Update queue positions after requeuing
            if requeued_jobs:
                await self._update_queue_positions()
            
            logger.info(f"Requeued {len(requeued_jobs)} failed jobs")
            
            return {
                "requeued_jobs": requeued_jobs,
                "failed_requeues": failed_requeues,
                "total_processed": len(failed_jobs),
                "success_rate": len(requeued_jobs) / len(failed_jobs) * 100 if failed_jobs else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to requeue failed jobs: {e}")
            return {
                "requeued_jobs": [],
                "failed_requeues": [],
                "total_processed": 0,
                "success_rate": 0,
                "error": str(e)
            }
    
    async def cleanup_completed_jobs(self, retention_days: int = None) -> Dict[str, Any]:
        """
        Clean up completed jobs based on retention policy.
        
        Args:
            retention_days: Number of days to retain completed jobs
            
        Returns:
            Dict containing cleanup results
        """
        retention_days = retention_days or self._cleanup_retention_days
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find completed jobs older than retention period
            cleanup_query = """
                SELECT id, batch_id
                FROM jobs
                WHERE completed_at < $1 
                AND status IN ('completed', 'failed', 'cancelled')
                AND is_deleted = FALSE
            """
            
            old_jobs = await self.db_manager.execute_query(
                cleanup_query, {"$1": cutoff_date}
            )
            
            cleaned_jobs = []
            failed_cleanups = []
            batch_ids_to_cleanup = set()
            
            # Clean up individual jobs
            for job_row in old_jobs:
                job_id = job_row["id"]
                batch_id = job_row["batch_id"]
                
                try:
                    # Soft delete job
                    success = await self.db_manager.delete_pydantic_model(
                        "jobs", "id = $1", [job_id], soft_delete=True
                    )
                    
                    if success:
                        # Also clean up queue entry
                        await self.db_manager.delete_pydantic_model(
                            "job_queue", "job_id = $1", [job_id], soft_delete=True
                        )
                        
                        cleaned_jobs.append(str(job_id))
                        
                        if batch_id:
                            batch_ids_to_cleanup.add(batch_id)
                        
                        # Clear cache if Redis is available
                        if self.redis_client:
                            await self._invalidate_job_cache(str(job_id))
                    else:
                        failed_cleanups.append(str(job_id))
                        
                except Exception as e:
                    logger.warning(f"Failed to cleanup job {job_id}: {e}")
                    failed_cleanups.append(str(job_id))
            
            # Clean up batch metadata for completed batches
            cleaned_batches = []
            for batch_id in batch_ids_to_cleanup:
                try:
                    await self._cleanup_batch_metadata(str(batch_id))
                    cleaned_batches.append(str(batch_id))
                except Exception as e:
                    logger.warning(f"Failed to cleanup batch metadata {batch_id}: {e}")
            
            logger.info(
                f"Cleanup completed: {len(cleaned_jobs)} jobs, {len(cleaned_batches)} batches"
            )
            
            return {
                "cleaned_jobs": cleaned_jobs,
                "failed_cleanups": failed_cleanups,
                "cleaned_batches": cleaned_batches,
                "total_processed": len(old_jobs),
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            return {
                "cleaned_jobs": [],
                "failed_cleanups": [],
                "cleaned_batches": [],
                "total_processed": 0,
                "retention_days": retention_days,
                "error": str(e)
            }
    
    async def apply_retention_policy(self, policy_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply comprehensive retention policy with different rules for different job types.
        
        Args:
            policy_config: Configuration for retention policy
            
        Returns:
            Dict containing retention policy results
        """
        try:
            # Default policy configuration
            default_config = {
                "completed_jobs_days": 30,
                "failed_jobs_days": 7,
                "cancelled_jobs_days": 3,
                "batch_metadata_days": 60,
                "enable_archival": False,
                "archive_before_delete": True
            }
            
            # Merge with provided config
            config = {**default_config, **policy_config}
            
            results = {
                "completed_cleanup": {},
                "failed_cleanup": {},
                "cancelled_cleanup": {},
                "batch_cleanup": {},
                "total_cleaned": 0,
                "policy_applied": config
            }
            
            # Clean up completed jobs
            if config["completed_jobs_days"] > 0:
                completed_result = await self._cleanup_jobs_by_status(
                    JobStatus.COMPLETED, config["completed_jobs_days"]
                )
                results["completed_cleanup"] = completed_result
                results["total_cleaned"] += completed_result.get("cleaned_count", 0)
            
            # Clean up failed jobs
            if config["failed_jobs_days"] > 0:
                failed_result = await self._cleanup_jobs_by_status(
                    JobStatus.FAILED, config["failed_jobs_days"]
                )
                results["failed_cleanup"] = failed_result
                results["total_cleaned"] += failed_result.get("cleaned_count", 0)
            
            # Clean up cancelled jobs
            if config["cancelled_jobs_days"] > 0:
                cancelled_result = await self._cleanup_jobs_by_status(
                    JobStatus.CANCELLED, config["cancelled_jobs_days"]
                )
                results["cancelled_cleanup"] = cancelled_result
                results["total_cleaned"] += cancelled_result.get("cleaned_count", 0)
            
            # Clean up old batch metadata
            if config["batch_metadata_days"] > 0:
                batch_result = await self._cleanup_old_batch_metadata(
                    config["batch_metadata_days"]
                )
                results["batch_cleanup"] = batch_result
            
            logger.info(f"Applied retention policy, cleaned {results['total_cleaned']} jobs")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}")
            return {
                "completed_cleanup": {},
                "failed_cleanup": {},
                "cancelled_cleanup": {},
                "batch_cleanup": {},
                "total_cleaned": 0,
                "error": str(e)
            }
    
    async def _cleanup_jobs_by_status(self, status: JobStatus, retention_days: int) -> Dict[str, Any]:
        """Clean up jobs by specific status and retention period."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find jobs to clean up
            cleanup_query = """
                SELECT id, batch_id, user_id
                FROM jobs
                WHERE status = $1 
                AND completed_at < $2
                AND is_deleted = FALSE
            """
            
            jobs_to_cleanup = await self.db_manager.execute_query(
                cleanup_query, {"$1": status.value, "$2": cutoff_date}
            )
            
            cleaned_count = 0
            failed_count = 0
            batch_ids = set()
            
            for job_row in jobs_to_cleanup:
                job_id = job_row["id"]
                batch_id = job_row["batch_id"]
                
                try:
                    # Soft delete job
                    success = await self.db_manager.delete_pydantic_model(
                        "jobs", "id = $1", [job_id], soft_delete=True
                    )
                    
                    if success:
                        # Clean up queue entry
                        await self.db_manager.delete_pydantic_model(
                            "job_queue", "job_id = $1", [job_id], soft_delete=True
                        )
                        
                        cleaned_count += 1
                        
                        if batch_id:
                            batch_ids.add(str(batch_id))
                        
                        # Clear cache if Redis is available
                        if self.redis_client:
                            await self._invalidate_job_cache(str(job_id))
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to cleanup {status.value} job {job_id}: {e}")
                    failed_count += 1
            
            return {
                "status": status.value,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "cleaned_count": cleaned_count,
                "failed_count": failed_count,
                "affected_batches": list(batch_ids),
                "total_processed": len(jobs_to_cleanup)
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup {status.value} jobs: {e}")
            return {
                "status": status.value,
                "retention_days": retention_days,
                "cleaned_count": 0,
                "failed_count": 0,
                "error": str(e)
            }
    
    async def _cleanup_old_batch_metadata(self, retention_days: int) -> Dict[str, Any]:
        """Clean up old batch metadata."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find old batch metadata
            batch_query = """
                SELECT batch_id, created_at
                FROM batch_metadata
                WHERE created_at < $1 AND is_deleted = FALSE
            """
            
            old_batches = await self.db_manager.execute_query(
                batch_query, {"$1": cutoff_date}
            )
            
            cleaned_count = 0
            failed_count = 0
            
            for batch_row in old_batches:
                batch_id = batch_row["batch_id"]
                
                try:
                    await self._cleanup_batch_metadata(batch_id)
                    cleaned_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to cleanup batch metadata {batch_id}: {e}")
                    failed_count += 1
            
            return {
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "cleaned_count": cleaned_count,
                "failed_count": failed_count,
                "total_processed": len(old_batches)
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old batch metadata: {e}")
            return {
                "retention_days": retention_days,
                "cleaned_count": 0,
                "failed_count": 0,
                "error": str(e)
            }
    
    async def get_retention_policy_preview(self, policy_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preview what would be cleaned up by a retention policy without actually doing it.
        
        Args:
            policy_config: Configuration for retention policy
            
        Returns:
            Dict containing preview of what would be cleaned up
        """
        try:
            # Default policy configuration
            default_config = {
                "completed_jobs_days": 30,
                "failed_jobs_days": 7,
                "cancelled_jobs_days": 3,
                "batch_metadata_days": 60
            }
            
            config = {**default_config, **policy_config}
            
            preview = {
                "policy_config": config,
                "preview_date": datetime.utcnow().isoformat(),
                "jobs_to_cleanup": {},
                "batches_to_cleanup": {},
                "total_jobs_affected": 0
            }
            
            # Preview completed jobs cleanup
            if config["completed_jobs_days"] > 0:
                completed_preview = await self._preview_cleanup_by_status(
                    JobStatus.COMPLETED, config["completed_jobs_days"]
                )
                preview["jobs_to_cleanup"]["completed"] = completed_preview
                preview["total_jobs_affected"] += completed_preview.get("count", 0)
            
            # Preview failed jobs cleanup
            if config["failed_jobs_days"] > 0:
                failed_preview = await self._preview_cleanup_by_status(
                    JobStatus.FAILED, config["failed_jobs_days"]
                )
                preview["jobs_to_cleanup"]["failed"] = failed_preview
                preview["total_jobs_affected"] += failed_preview.get("count", 0)
            
            # Preview cancelled jobs cleanup
            if config["cancelled_jobs_days"] > 0:
                cancelled_preview = await self._preview_cleanup_by_status(
                    JobStatus.CANCELLED, config["cancelled_jobs_days"]
                )
                preview["jobs_to_cleanup"]["cancelled"] = cancelled_preview
                preview["total_jobs_affected"] += cancelled_preview.get("count", 0)
            
            # Preview batch metadata cleanup
            if config["batch_metadata_days"] > 0:
                batch_preview = await self._preview_batch_cleanup(
                    config["batch_metadata_days"]
                )
                preview["batches_to_cleanup"] = batch_preview
            
            return preview
            
        except Exception as e:
            logger.error(f"Failed to generate retention policy preview: {e}")
            return {
                "policy_config": policy_config,
                "error": str(e)
            }
    
    async def _preview_cleanup_by_status(self, status: JobStatus, retention_days: int) -> Dict[str, Any]:
        """Preview cleanup for jobs by status."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            preview_query = """
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(DISTINCT user_id) as affected_users,
                    COUNT(DISTINCT batch_id) as affected_batches,
                    MIN(completed_at) as oldest_job,
                    MAX(completed_at) as newest_job
                FROM jobs
                WHERE status = $1 
                AND completed_at < $2
                AND is_deleted = FALSE
            """
            
            result = await self.db_manager.execute_query(
                preview_query, {"$1": status.value, "$2": cutoff_date}
            )
            
            if result:
                row = result[0]
                return {
                    "status": status.value,
                    "retention_days": retention_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "count": row["total_count"],
                    "affected_users": row["affected_users"],
                    "affected_batches": row["affected_batches"],
                    "oldest_job": row["oldest_job"].isoformat() if row["oldest_job"] else None,
                    "newest_job": row["newest_job"].isoformat() if row["newest_job"] else None
                }
            
            return {
                "status": status.value,
                "retention_days": retention_days,
                "count": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to preview cleanup for {status.value} jobs: {e}")
            return {
                "status": status.value,
                "retention_days": retention_days,
                "count": 0,
                "error": str(e)
            }
    
    async def _preview_batch_cleanup(self, retention_days: int) -> Dict[str, Any]:
        """Preview batch metadata cleanup."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            batch_preview_query = """
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(DISTINCT user_id) as affected_users,
                    MIN(created_at) as oldest_batch,
                    MAX(created_at) as newest_batch
                FROM batch_metadata
                WHERE created_at < $1 AND is_deleted = FALSE
            """
            
            result = await self.db_manager.execute_query(
                batch_preview_query, {"$1": cutoff_date}
            )
            
            if result:
                row = result[0]
                return {
                    "retention_days": retention_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "count": row["total_count"],
                    "affected_users": row["affected_users"],
                    "oldest_batch": row["oldest_batch"].isoformat() if row["oldest_batch"] else None,
                    "newest_batch": row["newest_batch"].isoformat() if row["newest_batch"] else None
                }
            
            return {
                "retention_days": retention_days,
                "count": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to preview batch cleanup: {e}")
            return {
                "retention_days": retention_days,
                "count": 0,
                "error": str(e)
            }
    
    # Queue position and priority management methods
    
    async def _update_queue_positions(self):
        """Update queue positions for all queued jobs based on priority and creation time."""
        try:
            # Get all queued jobs ordered by priority (desc) and creation time (asc)
            queue_update_query = """
                WITH ranked_jobs AS (
                    SELECT 
                        jq.id,
                        ROW_NUMBER() OVER (
                            ORDER BY 
                                CASE jq.priority 
                                    WHEN 'urgent' THEN 4
                                    WHEN 'high' THEN 3
                                    WHEN 'normal' THEN 2
                                    WHEN 'low' THEN 1
                                    ELSE 0
                                END DESC,
                                jq.queued_at ASC
                        ) as new_position
                    FROM job_queue jq
                    JOIN jobs j ON jq.job_id = j.id
                    WHERE jq.queue_status = 'queued' 
                    AND j.status = 'queued'
                    AND j.is_deleted = FALSE
                )
                UPDATE job_queue 
                SET queue_position = ranked_jobs.new_position
                FROM ranked_jobs
                WHERE job_queue.id = ranked_jobs.id
            """
            
            await self.db_manager.execute_command(queue_update_query)
            logger.info("Updated queue positions for all queued jobs")
            
        except Exception as e:
            logger.error(f"Failed to update queue positions: {e}")
    
    async def get_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get the current queue position for a specific job.
        
        Args:
            job_id: Job ID to get position for
            
        Returns:
            Queue position (1-based) or None if not in queue
        """
        try:
            position_query = """
                SELECT queue_position
                FROM job_queue jq
                JOIN jobs j ON jq.job_id = j.id
                WHERE jq.job_id = $1 
                AND jq.queue_status = 'queued'
                AND j.status = 'queued'
                AND j.is_deleted = FALSE
            """
            
            result = await self.db_manager.execute_query(
                position_query, {"$1": UUID(job_id)}
            )
            
            if result:
                return result[0]["queue_position"]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get queue position for job {job_id}: {e}")
            return None
    
    async def get_estimated_wait_time(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get estimated wait time for a job based on queue position and processing history.
        
        Args:
            job_id: Job ID to get estimate for
            
        Returns:
            Dict with wait time estimation or None if not available
        """
        try:
            # Get job priority and queue position
            job_info_query = """
                SELECT 
                    jq.priority,
                    jq.queue_position,
                    jq.queued_at
                FROM job_queue jq
                JOIN jobs j ON jq.job_id = j.id
                WHERE jq.job_id = $1 
                AND jq.queue_status = 'queued'
                AND j.status = 'queued'
                AND j.is_deleted = FALSE
            """
            
            job_result = await self.db_manager.execute_query(
                job_info_query, {"$1": UUID(job_id)}
            )
            
            if not job_result:
                return None
            
            job_info = job_result[0]
            queue_position = job_info["queue_position"]
            priority = job_info["priority"]
            queued_at = job_info["queued_at"]
            
            # Get average processing time for similar priority jobs
            avg_time_query = """
                SELECT 
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_processing_seconds,
                    COUNT(*) as sample_size
                FROM jobs
                WHERE priority = $1
                AND status = 'completed'
                AND completed_at > NOW() - INTERVAL '7 days'
                AND started_at IS NOT NULL
                AND is_deleted = FALSE
            """
            
            avg_result = await self.db_manager.execute_query(
                avg_time_query, {"$1": priority}
            )
            
            avg_processing_time = 300  # Default 5 minutes
            sample_size = 0
            
            if avg_result and avg_result[0]["avg_processing_seconds"]:
                avg_processing_time = float(avg_result[0]["avg_processing_seconds"])
                sample_size = avg_result[0]["sample_size"]
            
            # Calculate estimated wait time
            jobs_ahead = max(0, queue_position - 1)
            estimated_wait_seconds = jobs_ahead * avg_processing_time
            
            # Add current time in queue
            time_in_queue = (datetime.utcnow() - queued_at).total_seconds()
            
            return {
                "queue_position": queue_position,
                "jobs_ahead": jobs_ahead,
                "estimated_wait_seconds": estimated_wait_seconds,
                "estimated_wait_minutes": round(estimated_wait_seconds / 60, 1),
                "time_in_queue_seconds": time_in_queue,
                "avg_processing_time_seconds": avg_processing_time,
                "sample_size": sample_size,
                "priority": priority
            }
            
        except Exception as e:
            logger.error(f"Failed to get estimated wait time for job {job_id}: {e}")
            return None
    
    async def update_job_priority(self, job_id: str, new_priority: JobPriority, user_id: str) -> bool:
        """
        Update job priority and recalculate queue positions.
        
        Args:
            job_id: Job ID to update
            new_priority: New priority level
            user_id: User ID for ownership validation
            
        Returns:
            True if priority updated successfully, False otherwise
        """
        try:
            # Validate job ownership and status
            job = await self.get_job(job_id, user_id)
            
            if job.status != JobStatus.QUEUED:
                logger.warning(f"Cannot update priority for job {job_id} with status {job.status}")
                return False
            
            # Update job priority
            job_update_query = """
                UPDATE jobs 
                SET priority = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND status = 'queued' AND is_deleted = FALSE
            """
            
            job_result = await self.db_manager.execute_command(job_update_query, {
                "$1": new_priority.value,
                "$2": UUID(job_id),
                "$3": UUID(user_id)
            })
            
            # Update queue entry priority
            queue_update_query = """
                UPDATE job_queue 
                SET priority = $1
                WHERE job_id = $2 AND queue_status = 'queued'
            """
            
            await self.db_manager.execute_command(queue_update_query, {
                "$1": new_priority.value,
                "$2": UUID(job_id)
            })
            
            # Recalculate queue positions
            await self._update_queue_positions()
            
            # Clear cache if Redis is available
            if self.redis_client:
                await self._invalidate_job_cache(job_id)
            
            logger.info(f"Updated job {job_id} priority to {new_priority.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id} priority: {e}")
            return False
    
    async def get_batch_queue_summary(self, batch_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get queue summary for all jobs in a batch.
        
        Args:
            batch_id: Batch ID to get summary for
            user_id: User ID for ownership validation
            
        Returns:
            Dict containing batch queue summary
        """
        try:
            # Get batch metadata
            batch_metadata = await self._get_batch_metadata(batch_id)
            
            if not batch_metadata or batch_metadata["user_id"] != user_id:
                return {"error": "Batch not found or access denied"}
            
            # Get queue information for all jobs in batch
            queue_summary_query = """
                SELECT 
                    j.id,
                    j.status,
                    jq.priority,
                    jq.queue_position,
                    jq.queued_at,
                    jq.processing_started_at,
                    j.configuration->>'topic' as topic
                FROM jobs j
                LEFT JOIN job_queue jq ON j.id = jq.job_id
                WHERE j.id = ANY($1) AND j.is_deleted = FALSE
                ORDER BY jq.queue_position ASC NULLS LAST
            """
            
            import json
            job_ids = [UUID(job_id) for job_id in batch_metadata["job_ids"]]
            
            results = await self.db_manager.execute_query(
                queue_summary_query, {"$1": job_ids}
            )
            
            # Process results
            queued_jobs = []
            processing_jobs = []
            completed_jobs = []
            
            total_estimated_wait = 0
            
            for row in results:
                job_info = {
                    "job_id": str(row["id"]),
                    "status": row["status"],
                    "priority": row["priority"],
                    "topic": row["topic"][:50] + "..." if row["topic"] and len(row["topic"]) > 50 else row["topic"],
                    "queue_position": row["queue_position"],
                    "queued_at": row["queued_at"].isoformat() if row["queued_at"] else None,
                    "processing_started_at": row["processing_started_at"].isoformat() if row["processing_started_at"] else None
                }
                
                if row["status"] == "queued":
                    # Get estimated wait time
                    wait_info = await self.get_estimated_wait_time(str(row["id"]))
                    if wait_info:
                        job_info["estimated_wait_minutes"] = wait_info["estimated_wait_minutes"]
                        total_estimated_wait += wait_info["estimated_wait_seconds"]
                    
                    queued_jobs.append(job_info)
                elif row["status"] == "processing":
                    processing_jobs.append(job_info)
                else:
                    completed_jobs.append(job_info)
            
            return {
                "batch_id": batch_id,
                "total_jobs": len(batch_metadata["job_ids"]),
                "queued_jobs": queued_jobs,
                "processing_jobs": processing_jobs,
                "completed_jobs": completed_jobs,
                "queue_summary": {
                    "total_queued": len(queued_jobs),
                    "total_processing": len(processing_jobs),
                    "total_completed": len(completed_jobs),
                    "estimated_total_wait_minutes": round(total_estimated_wait / 60, 1) if total_estimated_wait > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get batch queue summary for {batch_id}: {e}")
            return {"error": f"Failed to get batch queue summary: {str(e)}"}
    
    # Private helper methods for batch management
    
    async def _store_batch_metadata(self, batch_metadata: Dict[str, Any]):
        """Store batch metadata in database."""
        try:
            # Create a simple batch metadata table entry
            batch_query = """
                INSERT INTO batch_metadata (
                    batch_id, user_id, total_jobs, created_jobs, failed_jobs,
                    batch_priority, created_at, job_ids, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (batch_id) DO UPDATE SET
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """
            
            import json
            await self.db_manager.execute_command(batch_query, {
                "$1": batch_metadata["batch_id"],
                "$2": UUID(batch_metadata["user_id"]),
                "$3": batch_metadata["total_jobs"],
                "$4": batch_metadata["created_jobs"],
                "$5": batch_metadata["failed_jobs"],
                "$6": batch_metadata["batch_priority"],
                "$7": datetime.fromisoformat(batch_metadata["created_at"]),
                "$8": json.dumps(batch_metadata["job_ids"]),
                "$9": json.dumps(batch_metadata)
            })
            
        except Exception as e:
            logger.error(f"Failed to store batch metadata: {e}")
    
    async def _get_batch_metadata(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch metadata from database or cache."""
        try:
            # Try cache first if Redis is available
            if self.redis_client:
                cached_metadata = await self._get_cached_batch_metadata(batch_id)
                if cached_metadata:
                    return cached_metadata
            
            # Query database
            batch_query = """
                SELECT metadata FROM batch_metadata 
                WHERE batch_id = $1 AND is_deleted = FALSE
            """
            
            result = await self.db_manager.execute_query(
                batch_query, {"$1": batch_id}
            )
            
            if result:
                import json
                metadata = json.loads(result[0]["metadata"])
                
                # Cache if Redis is available
                if self.redis_client:
                    await self._cache_batch_metadata(batch_id, metadata)
                
                return metadata
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get batch metadata for {batch_id}: {e}")
            return None
    
    async def _cleanup_batch_metadata(self, batch_id: str):
        """Clean up batch metadata."""
        try:
            # Soft delete batch metadata
            await self.db_manager.delete_pydantic_model(
                "batch_metadata", "batch_id = $1", [batch_id], soft_delete=True
            )
            
            # Clear cache if Redis is available
            if self.redis_client:
                cache_key = f"batch_metadata:{batch_id}"
                await self.redis_client.delete(cache_key)
                
        except Exception as e:
            logger.error(f"Failed to cleanup batch metadata {batch_id}: {e}")
    
    # Redis caching methods for batch operations
    
    async def _cache_batch_metadata(self, batch_id: str, metadata: Dict[str, Any]):
        """Cache batch metadata in Redis if available."""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"batch_metadata:{batch_id}"
            import json
            await self.redis_client.setex(
                cache_key, self._cache_ttl, json.dumps(metadata)
            )
        except Exception as e:
            logger.warning(f"Failed to cache batch metadata {batch_id}: {e}")
    
    async def _get_cached_batch_metadata(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get cached batch metadata from Redis if available."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"batch_metadata:{batch_id}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached batch metadata {batch_id}: {e}")
        
        return None
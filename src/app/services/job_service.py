"""
Job management service for handling job lifecycle and operations.

This service provides business logic for job management operations,
including job retrieval, cancellation, deletion, and cleanup.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from redis.asyncio import Redis

from ..models.job import Job, JobStatus, JobType, JobPriority, JobConfiguration
from ..core.redis import RedisKeyManager, redis_json_get, redis_json_set

logger = logging.getLogger(__name__)


class JobService:
    """
    Service class for job management operations.
    
    Handles job lifecycle management, status updates, cleanup,
    and data retrieval operations.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
    
    async def get_jobs_paginated(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of jobs for a user with optional filtering.
        
        Args:
            user_id: User ID to get jobs for
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            filters: Optional filters (status, job_type, priority, dates)
            
        Returns:
            Dict containing jobs list and pagination info
        """
        try:
            # Get user's job IDs
            user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
            job_ids = await self.redis_client.smembers(user_jobs_key)
            
            if not job_ids:
                return {
                    "jobs": [],
                    "total_count": 0
                }
            
            # Get all jobs and apply filters
            jobs = []
            for job_id in job_ids:
                job = await self._get_job_by_id(job_id)
                if job and not job.is_deleted:
                    # Apply filters
                    if self._job_matches_filters(job, filters):
                        jobs.append(job)
            
            # Sort jobs by creation date (newest first)
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            # Apply pagination
            total_count = len(jobs)
            paginated_jobs = jobs[offset:offset + limit]
            
            logger.info(
                "Retrieved paginated jobs",
                user_id=user_id,
                total_count=total_count,
                returned_count=len(paginated_jobs),
                offset=offset,
                limit=limit
            )
            
            return {
                "jobs": paginated_jobs,
                "total_count": total_count
            }
            
        except Exception as e:
            logger.error(
                "Failed to get paginated jobs",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return {
                "jobs": [],
                "total_count": 0
            }
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job if it's in a cancellable state.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for cancellation")
                return False
            
            # Check if job can be cancelled
            if not job.can_be_cancelled:
                logger.warning(
                    f"Job {job_id} cannot be cancelled. Current status: {job.status}"
                )
                return False
            
            # Update job status
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            job.progress.current_stage = "cancelled"
            
            # Save updated job
            await self._save_job(job)
            
            # Remove from processing queue if still queued
            await self.redis_client.lrem(RedisKeyManager.JOB_QUEUE, 0, job_id)
            
            # Update status cache
            status_key = RedisKeyManager.job_status_key(job_id)
            await self.redis_client.set(status_key, JobStatus.CANCELLED.value, ex=300)
            
            logger.info(f"Job {job_id} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cancel job",
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def soft_delete_job(self, job_id: str) -> bool:
        """
        Perform soft delete on a job.
        
        Args:
            job_id: Job ID to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for deletion")
                return False
            
            # Mark as deleted
            job.is_deleted = True
            job.deleted_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            
            # Save updated job
            await self._save_job(job)
            
            logger.info(f"Job {job_id} soft deleted successfully")
            return True
            
        except Exception as e:
            logger.error(
                "Failed to soft delete job",
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def cleanup_job_data(self, job_id: str) -> bool:
        """
        Clean up related data for a deleted job.
        
        Args:
            job_id: Job ID to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            # Clean up video metadata
            video_key = RedisKeyManager.video_key(f"job_{job_id}")
            await self.redis_client.delete(video_key)
            
            # Clean up job status cache
            status_key = RedisKeyManager.job_status_key(job_id)
            await self.redis_client.delete(status_key)
            
            # Clean up job logs
            logs_key = f"job_logs:{job_id}"
            await self.redis_client.delete(logs_key)
            
            # Clean up any cached data
            cache_pattern = f"cache:job:{job_id}:*"
            cache_keys = await self.redis_client.keys(cache_pattern)
            if cache_keys:
                await self.redis_client.delete(*cache_keys)
            
            logger.info(f"Cleaned up data for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(
                "Failed to cleanup job data",
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
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
            # Get user's job IDs
            user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
            job_ids = await self.redis_client.smembers(user_jobs_key)
            
            if not job_ids:
                return {
                    "total_jobs": 0,
                    "by_status": {},
                    "by_type": {},
                    "by_priority": {},
                    "recent_activity": []
                }
            
            # Initialize counters
            stats = {
                "total_jobs": 0,
                "by_status": {},
                "by_type": {},
                "by_priority": {},
                "recent_activity": []
            }
            
            recent_jobs = []
            
            # Process each job
            for job_id in job_ids:
                job = await self._get_job_by_id(job_id)
                if job and not job.is_deleted:
                    stats["total_jobs"] += 1
                    
                    # Count by status
                    status = job.status.value
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                    
                    # Count by type
                    job_type = job.job_type.value
                    stats["by_type"][job_type] = stats["by_type"].get(job_type, 0) + 1
                    
                    # Count by priority
                    priority = job.priority.value
                    stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
                    
                    # Collect recent jobs (last 7 days)
                    if job.created_at >= datetime.utcnow() - timedelta(days=7):
                        recent_jobs.append({
                            "job_id": job.id,
                            "status": job.status.value,
                            "created_at": job.created_at.isoformat(),
                            "topic": job.configuration.topic[:50] + "..." if len(job.configuration.topic) > 50 else job.configuration.topic
                        })
            
            # Sort recent jobs by creation date
            recent_jobs.sort(key=lambda x: x["created_at"], reverse=True)
            stats["recent_activity"] = recent_jobs[:10]  # Last 10 recent jobs
            
            logger.info(
                "Generated job statistics",
                user_id=user_id,
                total_jobs=stats["total_jobs"]
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "Failed to get job statistics",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
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
            cleaned_count = 0
            
            # Get all job keys
            job_pattern = f"{RedisKeyManager.JOB_PREFIX}:*"
            job_keys = await self.redis_client.keys(job_pattern)
            
            for job_key in job_keys:
                try:
                    job_data = await redis_json_get(self.redis_client, job_key)
                    if job_data:
                        job = Job(**job_data)
                        
                        # Check if job is old and completed
                        if (job.completed_at and 
                            job.completed_at < cutoff_date and
                            job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]):
                            
                            # Perform cleanup
                            job_id = job.id
                            await self.cleanup_job_data(job_id)
                            await self.redis_client.delete(job_key)
                            
                            # Remove from user's job index
                            user_jobs_key = RedisKeyManager.user_jobs_key(job.user_id)
                            await self.redis_client.srem(user_jobs_key, job_id)
                            
                            cleaned_count += 1
                            
                except Exception as e:
                    logger.warning(f"Failed to process job key {job_key}: {e}")
                    continue
            
            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(
                "Failed to cleanup old jobs",
                retention_days=retention_days,
                error=str(e),
                exc_info=True
            )
            return 0
    
    async def collect_job_metrics(self, job_id: str) -> Dict[str, Any]:
        """
        Collect comprehensive metrics for a job.
        
        Args:
            job_id: Job ID to collect metrics for
            
        Returns:
            Dict containing job metrics
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                return {}
            
            metrics = {
                "job_id": job_id,
                "status": job.status.value,
                "duration_seconds": job.duration_seconds,
                "queue_time_seconds": None,
                "processing_time_seconds": None,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "progress_percentage": job.progress.percentage,
                "stages_completed": job.progress.stages_completed,
                "error_info": job.error.dict() if job.error else None
            }
            
            # Calculate queue time
            if job.started_at:
                queue_time = (job.started_at - job.created_at).total_seconds()
                metrics["queue_time_seconds"] = queue_time
            
            # Calculate processing time
            if job.started_at and job.completed_at:
                processing_time = (job.completed_at - job.started_at).total_seconds()
                metrics["processing_time_seconds"] = processing_time
            
            # Add performance metrics if available
            if job.metrics:
                metrics.update({
                    "cpu_usage_percent": job.metrics.cpu_usage_percent,
                    "memory_usage_mb": job.metrics.memory_usage_mb,
                    "disk_usage_mb": job.metrics.disk_usage_mb,
                    "network_usage_mb": job.metrics.network_usage_mb
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics for job {job_id}: {e}")
            return {}
    
    async def update_job_metrics(
        self, 
        job_id: str, 
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        disk_usage: Optional[float] = None,
        network_usage: Optional[float] = None
    ) -> bool:
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
            job = await self._get_job_by_id(job_id)
            if not job:
                return False
            
            # Initialize metrics if not present
            if not job.metrics:
                from ..models.job import JobMetrics
                job.metrics = JobMetrics()
            
            # Update metrics
            if cpu_usage is not None:
                job.metrics.cpu_usage_percent = cpu_usage
            if memory_usage is not None:
                job.metrics.memory_usage_mb = memory_usage
            if disk_usage is not None:
                job.metrics.disk_usage_mb = disk_usage
            if network_usage is not None:
                job.metrics.network_usage_mb = network_usage
            
            # Calculate processing time if job is active
            if job.started_at:
                if job.completed_at:
                    job.metrics.processing_time_seconds = (job.completed_at - job.started_at).total_seconds()
                else:
                    job.metrics.processing_time_seconds = (datetime.utcnow() - job.started_at).total_seconds()
            
            # Calculate queue time
            if job.started_at:
                job.metrics.queue_time_seconds = (job.started_at - job.created_at).total_seconds()
            
            # Save updated job
            await self._save_job(job)
            
            logger.info(f"Updated metrics for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update metrics for job {job_id}: {e}")
            return False
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-wide job metrics and statistics.
        
        Returns:
            Dict containing system metrics
        """
        try:
            # Get queue statistics
            queue_length = await self.redis_client.llen(RedisKeyManager.JOB_QUEUE)
            processing_jobs = await self.redis_client.scard("queue:processing")
            
            # Get completion statistics for today
            today = datetime.utcnow().date()
            completed_today = int(await self.redis_client.get(f"queue:completed:{today}") or 0)
            failed_today = int(await self.redis_client.get(f"queue:failed:{today}") or 0)
            
            # Get average processing times
            processing_times_key = "queue:processing_times"
            recent_times = await self.redis_client.lrange(processing_times_key, 0, 99)
            
            avg_processing_time = 0
            if recent_times:
                total_time = sum(float(time) for time in recent_times)
                avg_processing_time = total_time / len(recent_times)
            
            # Get job status distribution
            status_distribution = await self._get_job_status_distribution()
            
            # Get user activity metrics
            active_users = await self._get_active_users_count()
            
            return {
                "queue_metrics": {
                    "queue_length": queue_length,
                    "processing_jobs": processing_jobs,
                    "completed_today": completed_today,
                    "failed_today": failed_today,
                    "success_rate": (completed_today / max(completed_today + failed_today, 1)) * 100
                },
                "performance_metrics": {
                    "average_processing_time_minutes": avg_processing_time,
                    "total_jobs_processed_today": completed_today + failed_today
                },
                "job_distribution": status_distribution,
                "user_metrics": {
                    "active_users_today": active_users
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    async def _get_job_status_distribution(self) -> Dict[str, int]:
        """Get distribution of jobs by status."""
        try:
            distribution = {}
            
            # Get all job keys
            job_pattern = f"{RedisKeyManager.JOB_PREFIX}:*"
            job_keys = await self.redis_client.keys(job_pattern)
            
            for job_key in job_keys[:1000]:  # Limit to prevent performance issues
                try:
                    job_data = await redis_json_get(self.redis_client, job_key)
                    if job_data and not job_data.get("is_deleted", False):
                        status = job_data.get("status", "unknown")
                        distribution[status] = distribution.get(status, 0) + 1
                except Exception:
                    continue
            
            return distribution
            
        except Exception as e:
            logger.error(f"Failed to get job status distribution: {e}")
            return {}
    
    async def _get_active_users_count(self) -> int:
        """Get count of users who created jobs today."""
        try:
            today = datetime.utcnow().date()
            active_users_key = f"active_users:{today}"
            
            # This would be populated when jobs are created
            return await self.redis_client.scard(active_users_key)
            
        except Exception as e:
            logger.error(f"Failed to get active users count: {e}")
            return 0
    
    async def create_batch_jobs(
        self,
        user_id: str,
        job_configurations: List[Dict[str, Any]],
        batch_priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Create multiple jobs as a batch operation.
        
        Args:
            user_id: User ID creating the batch
            job_configurations: List of job configurations
            batch_priority: Priority for the entire batch
            
        Returns:
            Dict containing batch information and job IDs
        """
        try:
            import uuid
            from ..models.job import JobConfiguration, JobPriority, JobType
            
            batch_id = str(uuid.uuid4())
            created_jobs = []
            failed_jobs = []
            
            logger.info(
                "Creating batch jobs",
                user_id=user_id,
                batch_id=batch_id,
                job_count=len(job_configurations),
                batch_priority=batch_priority
            )
            
            # Process each job configuration
            for i, config_data in enumerate(job_configurations):
                try:
                    # Create job configuration
                    job_config = JobConfiguration(**config_data)
                    
                    # Create job instance
                    job = Job(
                        user_id=user_id,
                        job_type=JobType.VIDEO_GENERATION,
                        priority=JobPriority(batch_priority),
                        configuration=job_config,
                        batch_id=batch_id
                    )
                    
                    # Save job to Redis
                    job_key = RedisKeyManager.job_key(job.id)
                    await redis_json_set(self.redis_client, job_key, job.dict())
                    
                    # Add to user's job index
                    user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
                    await self.redis_client.sadd(user_jobs_key, job.id)
                    
                    # Add to job queue
                    await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job.id)
                    
                    created_jobs.append({
                        "job_id": job.id,
                        "position_in_batch": i + 1,
                        "topic": job_config.topic[:50] + "..." if len(job_config.topic) > 50 else job_config.topic
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to create job {i + 1} in batch {batch_id}: {e}")
                    failed_jobs.append({
                        "position_in_batch": i + 1,
                        "error": str(e),
                        "config": config_data
                    })
            
            # Store batch metadata
            batch_metadata = {
                "batch_id": batch_id,
                "user_id": user_id,
                "total_jobs": len(job_configurations),
                "created_jobs": len(created_jobs),
                "failed_jobs": len(failed_jobs),
                "batch_priority": batch_priority,
                "created_at": datetime.utcnow().isoformat(),
                "job_ids": [job["job_id"] for job in created_jobs]
            }
            
            batch_key = f"batch:{batch_id}"
            await redis_json_set(self.redis_client, batch_key, batch_metadata, ex=86400 * 7)  # 7 days TTL
            
            # Add to user's batch index
            user_batches_key = f"user_batches:{user_id}"
            await self.redis_client.sadd(user_batches_key, batch_id)
            
            logger.info(
                "Batch jobs created",
                batch_id=batch_id,
                user_id=user_id,
                created_count=len(created_jobs),
                failed_count=len(failed_jobs)
            )
            
            return {
                "batch_id": batch_id,
                "total_requested": len(job_configurations),
                "created_jobs": created_jobs,
                "failed_jobs": failed_jobs,
                "success_rate": len(created_jobs) / len(job_configurations) * 100,
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Failed to create batch jobs",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return {
                "batch_id": None,
                "total_requested": len(job_configurations),
                "created_jobs": [],
                "failed_jobs": [{"error": str(e), "config": config} for config in job_configurations],
                "success_rate": 0,
                "created_at": datetime.utcnow().isoformat()
            }
    
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
            batch_key = f"batch:{batch_id}"
            batch_data = await redis_json_get(self.redis_client, batch_key)
            
            if not batch_data:
                return {"error": "Batch not found"}
            
            # Validate ownership
            if batch_data["user_id"] != user_id:
                return {"error": "Access denied"}
            
            # Get status for each job in the batch
            job_statuses = []
            status_counts = {}
            total_progress = 0
            
            for job_id in batch_data["job_ids"]:
                job = await self._get_job_by_id(job_id)
                if job:
                    status = job.status.value
                    status_counts[status] = status_counts.get(status, 0) + 1
                    total_progress += job.progress.percentage
                    
                    job_statuses.append({
                        "job_id": job_id,
                        "status": status,
                        "progress": job.progress.percentage,
                        "topic": job.configuration.topic[:50] + "..." if len(job.configuration.topic) > 50 else job.configuration.topic,
                        "created_at": job.created_at.isoformat(),
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "error_message": job.error.error_message if job.error else None
                    })
            
            # Calculate overall batch progress
            overall_progress = total_progress / len(batch_data["job_ids"]) if batch_data["job_ids"] else 0
            
            # Determine batch status
            if status_counts.get("failed", 0) == len(batch_data["job_ids"]):
                batch_status = "failed"
            elif status_counts.get("completed", 0) == len(batch_data["job_ids"]):
                batch_status = "completed"
            elif status_counts.get("cancelled", 0) == len(batch_data["job_ids"]):
                batch_status = "cancelled"
            elif any(status in ["processing"] for status in status_counts.keys()):
                batch_status = "processing"
            elif any(status in ["queued"] for status in status_counts.keys()):
                batch_status = "queued"
            else:
                batch_status = "mixed"
            
            return {
                "batch_id": batch_id,
                "batch_status": batch_status,
                "overall_progress": round(overall_progress, 2),
                "total_jobs": batch_data["total_jobs"],
                "status_summary": status_counts,
                "created_at": batch_data["created_at"],
                "batch_priority": batch_data["batch_priority"],
                "jobs": job_statuses
            }
            
        except Exception as e:
            logger.error(f"Failed to get batch status for {batch_id}: {e}")
            return {"error": str(e)}
    
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
            batch_key = f"batch:{batch_id}"
            batch_data = await redis_json_get(self.redis_client, batch_key)
            
            if not batch_data:
                return {"error": "Batch not found"}
            
            # Validate ownership
            if batch_data["user_id"] != user_id:
                return {"error": "Access denied"}
            
            cancelled_jobs = []
            failed_cancellations = []
            
            # Cancel each job in the batch
            for job_id in batch_data["job_ids"]:
                try:
                    success = await self.cancel_job(job_id)
                    if success:
                        cancelled_jobs.append(job_id)
                    else:
                        failed_cancellations.append(job_id)
                except Exception as e:
                    logger.error(f"Failed to cancel job {job_id} in batch {batch_id}: {e}")
                    failed_cancellations.append(job_id)
            
            logger.info(
                "Batch cancellation completed",
                batch_id=batch_id,
                cancelled_count=len(cancelled_jobs),
                failed_count=len(failed_cancellations)
            )
            
            return {
                "batch_id": batch_id,
                "cancelled_jobs": cancelled_jobs,
                "failed_cancellations": failed_cancellations,
                "success_rate": len(cancelled_jobs) / len(batch_data["job_ids"]) * 100,
                "cancelled_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel batch {batch_id}: {e}")
            return {"error": str(e)}
    
    async def get_user_batches(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get list of batches for a user.
        
        Args:
            user_id: User ID to get batches for
            limit: Maximum number of batches to return
            offset: Number of batches to skip
            
        Returns:
            Dict containing batch list and pagination info
        """
        try:
            # Get user's batch IDs
            user_batches_key = f"user_batches:{user_id}"
            batch_ids = await self.redis_client.smembers(user_batches_key)
            
            if not batch_ids:
                return {
                    "batches": [],
                    "total_count": 0
                }
            
            # Get batch summaries
            batches = []
            for batch_id in batch_ids:
                batch_key = f"batch:{batch_id}"
                batch_data = await redis_json_get(self.redis_client, batch_key)
                
                if batch_data:
                    # Get quick status summary
                    status_counts = {}
                    for job_id in batch_data["job_ids"]:
                        status_key = RedisKeyManager.job_status_key(job_id)
                        status = await self.redis_client.get(status_key)
                        if status:
                            status_counts[status] = status_counts.get(status, 0) + 1
                    
                    batches.append({
                        "batch_id": batch_id,
                        "total_jobs": batch_data["total_jobs"],
                        "created_jobs": batch_data["created_jobs"],
                        "batch_priority": batch_data["batch_priority"],
                        "created_at": batch_data["created_at"],
                        "status_summary": status_counts
                    })
            
            # Sort by creation date (newest first)
            batches.sort(key=lambda x: x["created_at"], reverse=True)
            
            # Apply pagination
            total_count = len(batches)
            paginated_batches = batches[offset:offset + limit]
            
            return {
                "batches": paginated_batches,
                "total_count": total_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get user batches for {user_id}: {e}")
            return {
                "batches": [],
                "total_count": 0
            }
    
    async def cleanup_batch_data(self, batch_id: str) -> bool:
        """
        Clean up batch-related data.
        
        Args:
            batch_id: Batch ID to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            # Get batch metadata
            batch_key = f"batch:{batch_id}"
            batch_data = await redis_json_get(self.redis_client, batch_key)
            
            if batch_data:
                # Clean up individual jobs
                for job_id in batch_data["job_ids"]:
                    await self.cleanup_job_data(job_id)
                
                # Remove from user's batch index
                user_batches_key = f"user_batches:{batch_data['user_id']}"
                await self.redis_client.srem(user_batches_key, batch_id)
            
            # Remove batch metadata
            await self.redis_client.delete(batch_key)
            
            logger.info(f"Cleaned up batch data for {batch_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup batch data for {batch_id}: {e}")
            return False
    
    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress_percentage: Optional[float] = None,
        current_stage: Optional[str] = None,
        error_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update job status and progress information.
        
        Args:
            job_id: Job ID to update
            status: New job status
            progress_percentage: Progress percentage (0-100)
            current_stage: Current processing stage
            error_info: Error information if job failed
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for status update")
                return False
            
            # Update status
            job.status = status
            job.updated_at = datetime.utcnow()
            
            # Update progress if provided
            if progress_percentage is not None:
                job.progress.percentage = max(0, min(100, progress_percentage))
            
            if current_stage:
                job.progress.current_stage = current_stage
                if current_stage not in job.progress.stages_completed:
                    job.progress.stages_completed.append(current_stage)
            
            # Set timestamps based on status
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if not job.completed_at:
                    job.completed_at = datetime.utcnow()
                if status == JobStatus.COMPLETED:
                    job.progress.percentage = 100.0
            
            # Handle error information
            if error_info and status == JobStatus.FAILED:
                from ..models.job import JobError
                job.error = JobError(
                    error_code=error_info.get("error_code", "UNKNOWN_ERROR"),
                    error_message=error_info.get("error_message", "An unknown error occurred"),
                    error_details=error_info.get("error_details"),
                    stack_trace=error_info.get("stack_trace")
                )
            
            # Save updated job
            await self._save_job(job)
            
            # Update status cache
            status_key = RedisKeyManager.job_status_key(job_id)
            await self.redis_client.set(status_key, status.value, ex=300)
            
            # Update daily completion counters
            if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                today = datetime.utcnow().date()
                if status == JobStatus.COMPLETED:
                    await self.redis_client.incr(f"queue:completed:{today}")
                else:
                    await self.redis_client.incr(f"queue:failed:{today}")
                
                # Track processing time for metrics
                if job.started_at and job.completed_at:
                    processing_time = (job.completed_at - job.started_at).total_seconds() / 60  # minutes
                    processing_times_key = "queue:processing_times"
                    await self.redis_client.lpush(processing_times_key, str(processing_time))
                    await self.redis_client.ltrim(processing_times_key, 0, 99)  # Keep last 100
            
            logger.info(
                "Job status updated",
                job_id=job_id,
                old_status=job.status if job else "unknown",
                new_status=status.value,
                progress=progress_percentage
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update job status",
                job_id=job_id,
                status=status.value,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def retry_failed_job(self, job_id: str) -> bool:
        """
        Retry a failed job if it's eligible for retry.
        
        Args:
            job_id: Job ID to retry
            
        Returns:
            True if retry initiated, False otherwise
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for retry")
                return False
            
            # Check if job can be retried
            if job.status != JobStatus.FAILED:
                logger.warning(f"Job {job_id} is not in failed state, cannot retry")
                return False
            
            if job.error and not job.error.can_retry:
                logger.warning(f"Job {job_id} has exceeded maximum retry attempts")
                return False
            
            # Reset job for retry
            job.status = JobStatus.QUEUED
            job.progress.percentage = 0.0
            job.progress.current_stage = None
            job.progress.stages_completed = []
            job.started_at = None
            job.completed_at = None
            job.updated_at = datetime.utcnow()
            
            # Increment retry count
            if job.error:
                job.error.retry_count += 1
            
            # Save updated job
            await self._save_job(job)
            
            # Add back to queue
            await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job_id)
            
            # Update status cache
            status_key = RedisKeyManager.job_status_key(job_id)
            await self.redis_client.set(status_key, JobStatus.QUEUED.value, ex=300)
            
            logger.info(f"Job {job_id} queued for retry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry job {job_id}: {e}")
            return False
    
    async def get_job_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get the position of a job in the processing queue.
        
        Args:
            job_id: Job ID to check position for
            
        Returns:
            Queue position (0-based) or None if not in queue
        """
        try:
            # Get all jobs in queue
            queue_jobs = await self.redis_client.lrange(RedisKeyManager.JOB_QUEUE, 0, -1)
            
            # Find position
            for i, queued_job_id in enumerate(queue_jobs):
                if queued_job_id == job_id:
                    return i
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get queue position for job {job_id}: {e}")
            return None
    
    async def get_estimated_completion_time(self, job_id: str) -> Optional[datetime]:
        """
        Estimate completion time for a job based on queue position and average processing time.
        
        Args:
            job_id: Job ID to estimate completion for
            
        Returns:
            Estimated completion datetime or None if cannot estimate
        """
        try:
            job = await self._get_job_by_id(job_id)
            if not job:
                return None
            
            # If job is already completed or processing, use different logic
            if job.status == JobStatus.COMPLETED:
                return job.completed_at
            elif job.status == JobStatus.PROCESSING:
                # Estimate based on current progress and average processing time
                if job.progress.percentage > 0:
                    elapsed = (datetime.utcnow() - job.started_at).total_seconds() / 60  # minutes
                    estimated_total = elapsed / (job.progress.percentage / 100)
                    remaining = estimated_total - elapsed
                    return datetime.utcnow() + timedelta(minutes=remaining)
            elif job.status == JobStatus.QUEUED:
                # Estimate based on queue position and average processing time
                queue_position = await self.get_job_queue_position(job_id)
                if queue_position is not None:
                    # Get average processing time
                    processing_times_key = "queue:processing_times"
                    recent_times = await self.redis_client.lrange(processing_times_key, 0, 19)  # Last 20
                    
                    if recent_times:
                        avg_time = sum(float(time) for time in recent_times) / len(recent_times)
                        estimated_wait = queue_position * avg_time  # minutes
                        return datetime.utcnow() + timedelta(minutes=estimated_wait)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to estimate completion time for job {job_id}: {e}")
            return None
    
    async def _get_job_by_id(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID from Redis.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance or None if not found
        """
        try:
            job_key = RedisKeyManager.job_key(job_id)
            job_data = await redis_json_get(self.redis_client, job_key)
            
            if job_data:
                return Job(**job_data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    async def _save_job(self, job: Job) -> bool:
        """
        Save job to Redis.
        
        Args:
            job: Job instance to save
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            job_key = RedisKeyManager.job_key(job.id)
            await redis_json_set(self.redis_client, job_key, job.dict())
            return True
            
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {e}")
            return False
    
    def _job_matches_filters(self, job: Job, filters: Optional[Dict[str, Any]]) -> bool:
        """
        Check if job matches the provided filters.
        
        Args:
            job: Job instance to check
            filters: Filter criteria
            
        Returns:
            True if job matches filters, False otherwise
        """
        if not filters:
            return True
        
        try:
            # Filter by status
            if filters.get("status") and job.status.value != filters["status"]:
                return False
            
            # Filter by job type
            if filters.get("job_type") and job.job_type.value != filters["job_type"]:
                return False
            
            # Filter by priority
            if filters.get("priority") and job.priority.value != filters["priority"]:
                return False
            
            # Filter by creation date
            if filters.get("created_after"):
                try:
                    created_after = datetime.fromisoformat(filters["created_after"].replace("Z", "+00:00"))
                    if job.created_at < created_after:
                        return False
                except ValueError:
                    logger.warning(f"Invalid created_after date format: {filters['created_after']}")
            
            if filters.get("created_before"):
                try:
                    created_before = datetime.fromisoformat(filters["created_before"].replace("Z", "+00:00"))
                    if job.created_at > created_before:
                        return False
                except ValueError:
                    logger.warning(f"Invalid created_before date format: {filters['created_before']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying filters to job {job.id}: {e}")
            return True  # Include job if filter check fails
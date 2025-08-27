"""
Queue management service for handling job queues and processing.

This service provides business logic for job queue operations,
including queue management, job processing coordination, and monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from redis.asyncio import Redis

from ..models.job import Job, JobStatus
from ..core.redis import RedisKeyManager, redis_json_get, redis_json_set

logger = logging.getLogger(__name__)


class QueueService:
    """
    Service class for job queue management operations.
    
    Handles job queue operations, processing coordination,
    and queue monitoring functionality.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
    
    async def enqueue_job(self, job_id: str, priority: str = "normal") -> bool:
        """
        Add a job to the processing queue.
        
        Args:
            job_id: Job ID to enqueue
            priority: Job priority (affects queue position)
            
        Returns:
            True if job was enqueued successfully, False otherwise
        """
        try:
            # Add job to appropriate queue based on priority
            if priority == "urgent":
                # Add to front of queue for urgent jobs
                await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job_id)
            elif priority == "high":
                # Add near front for high priority jobs
                queue_length = await self.redis_client.llen(RedisKeyManager.JOB_QUEUE)
                insert_position = min(queue_length // 4, 10)  # Insert in first quarter or top 10
                if insert_position == 0:
                    await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job_id)
                else:
                    # This is a simplified approach - in production you might use a priority queue
                    await self.redis_client.rpush(RedisKeyManager.JOB_QUEUE, job_id)
            else:
                # Normal and low priority jobs go to the end
                await self.redis_client.rpush(RedisKeyManager.JOB_QUEUE, job_id)
            
            logger.info(f"Job {job_id} enqueued with priority {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}", exc_info=True)
            return False
    
    async def dequeue_job(self) -> Optional[str]:
        """
        Remove and return the next job from the queue.
        
        Returns:
            Job ID if available, None if queue is empty
        """
        try:
            # Use blocking pop with timeout to get next job
            result = await self.redis_client.blpop(RedisKeyManager.JOB_QUEUE, timeout=1)
            
            if result:
                queue_name, job_id = result
                logger.info(f"Dequeued job {job_id}")
                return job_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}", exc_info=True)
            return None
    
    async def peek_next_job(self) -> Optional[str]:
        """
        Get the next job ID without removing it from the queue.
        
        Returns:
            Next job ID if available, None if queue is empty
        """
        try:
            job_id = await self.redis_client.lindex(RedisKeyManager.JOB_QUEUE, 0)
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to peek next job: {e}", exc_info=True)
            return None
    
    async def get_queue_length(self) -> int:
        """
        Get current queue length.
        
        Returns:
            Number of jobs in queue
        """
        try:
            return await self.redis_client.llen(RedisKeyManager.JOB_QUEUE)
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0
    
    async def get_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get the position of a job in the queue.
        
        Args:
            job_id: Job ID to find
            
        Returns:
            Queue position (0-based) or None if not found
        """
        try:
            # Get all jobs in queue
            queue_jobs = await self.redis_client.lrange(RedisKeyManager.JOB_QUEUE, 0, -1)
            
            try:
                position = queue_jobs.index(job_id)
                return position
            except ValueError:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get queue position for job {job_id}: {e}")
            return None
    
    async def remove_job_from_queue(self, job_id: str) -> bool:
        """
        Remove a specific job from the queue.
        
        Args:
            job_id: Job ID to remove
            
        Returns:
            True if job was removed, False otherwise
        """
        try:
            # Remove all occurrences of the job ID from the queue
            removed_count = await self.redis_client.lrem(RedisKeyManager.JOB_QUEUE, 0, job_id)
            
            if removed_count > 0:
                logger.info(f"Removed job {job_id} from queue")
                return True
            else:
                logger.warning(f"Job {job_id} not found in queue")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove job {job_id} from queue: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics.
        
        Returns:
            Dictionary containing queue statistics
        """
        try:
            queue_length = await self.get_queue_length()
            
            # Get processing statistics from Redis
            processing_key = "queue:processing"
            processing_jobs = await self.redis_client.scard(processing_key)
            
            # Get completion statistics for today
            today = datetime.utcnow().date()
            completed_today_key = f"queue:completed:{today}"
            failed_today_key = f"queue:failed:{today}"
            
            completed_today = await self.redis_client.get(completed_today_key) or 0
            failed_today = await self.redis_client.get(failed_today_key) or 0
            
            # Calculate average processing time (simplified)
            avg_processing_time = await self._get_average_processing_time()
            
            return {
                "queue_length": queue_length,
                "processing_jobs": processing_jobs,
                "completed_today": int(completed_today),
                "failed_today": int(failed_today),
                "average_processing_time_minutes": avg_processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            return {
                "queue_length": 0,
                "processing_jobs": 0,
                "completed_today": 0,
                "failed_today": 0,
                "average_processing_time_minutes": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def mark_job_processing(self, job_id: str) -> bool:
        """
        Mark a job as currently processing.
        
        Args:
            job_id: Job ID to mark as processing
            
        Returns:
            True if marked successfully, False otherwise
        """
        try:
            processing_key = "queue:processing"
            await self.redis_client.sadd(processing_key, job_id)
            
            # Set processing timestamp
            processing_time_key = f"queue:processing_time:{job_id}"
            await self.redis_client.set(
                processing_time_key, 
                datetime.utcnow().isoformat(),
                ex=3600  # Expire after 1 hour
            )
            
            logger.info(f"Marked job {job_id} as processing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as processing: {e}")
            return False
    
    async def mark_job_completed(self, job_id: str, success: bool = True) -> bool:
        """
        Mark a job as completed and update statistics.
        
        Args:
            job_id: Job ID to mark as completed
            success: Whether job completed successfully
            
        Returns:
            True if marked successfully, False otherwise
        """
        try:
            # Remove from processing set
            processing_key = "queue:processing"
            await self.redis_client.srem(processing_key, job_id)
            
            # Update completion statistics
            today = datetime.utcnow().date()
            if success:
                completed_key = f"queue:completed:{today}"
                await self.redis_client.incr(completed_key)
                await self.redis_client.expire(completed_key, 86400 * 7)  # Keep for 7 days
            else:
                failed_key = f"queue:failed:{today}"
                await self.redis_client.incr(failed_key)
                await self.redis_client.expire(failed_key, 86400 * 7)  # Keep for 7 days
            
            # Calculate and store processing time
            processing_time_key = f"queue:processing_time:{job_id}"
            start_time_str = await self.redis_client.get(processing_time_key)
            
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                processing_duration = (datetime.utcnow() - start_time).total_seconds() / 60  # minutes
                
                # Store processing time for statistics
                processing_times_key = "queue:processing_times"
                await self.redis_client.lpush(processing_times_key, processing_duration)
                await self.redis_client.ltrim(processing_times_key, 0, 999)  # Keep last 1000 times
                
                # Clean up processing time key
                await self.redis_client.delete(processing_time_key)
            
            logger.info(f"Marked job {job_id} as completed (success: {success})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed: {e}")
            return False
    
    async def get_estimated_wait_time(self, position: int) -> float:
        """
        Calculate estimated wait time for a job at given queue position.
        
        Args:
            position: Position in queue (0-based)
            
        Returns:
            Estimated wait time in minutes
        """
        try:
            avg_processing_time = await self._get_average_processing_time()
            
            # Simple calculation: position * average processing time
            # In reality, this would be more sophisticated
            estimated_minutes = position * avg_processing_time
            
            return estimated_minutes
            
        except Exception as e:
            logger.error(f"Failed to calculate estimated wait time: {e}")
            return 0.0
    
    async def cleanup_stale_processing_jobs(self, timeout_minutes: int = 60) -> int:
        """
        Clean up jobs that have been processing for too long.
        
        Args:
            timeout_minutes: Timeout for processing jobs
            
        Returns:
            Number of stale jobs cleaned up
        """
        try:
            processing_key = "queue:processing"
            processing_jobs = await self.redis_client.smembers(processing_key)
            
            cleaned_count = 0
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            for job_id in processing_jobs:
                processing_time_key = f"queue:processing_time:{job_id}"
                start_time_str = await self.redis_client.get(processing_time_key)
                
                if start_time_str:
                    start_time = datetime.fromisoformat(start_time_str)
                    if start_time < cutoff_time:
                        # Job has been processing too long, clean it up
                        await self.redis_client.srem(processing_key, job_id)
                        await self.redis_client.delete(processing_time_key)
                        
                        # Mark job as failed due to timeout
                        await self.mark_job_completed(job_id, success=False)
                        
                        cleaned_count += 1
                        logger.warning(f"Cleaned up stale processing job {job_id}")
                else:
                    # No start time recorded, assume stale
                    await self.redis_client.srem(processing_key, job_id)
                    cleaned_count += 1
                    logger.warning(f"Cleaned up processing job {job_id} with no start time")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale processing jobs")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup stale processing jobs: {e}")
            return 0
    
    async def _get_average_processing_time(self) -> float:
        """
        Get average processing time from recent jobs.
        
        Returns:
            Average processing time in minutes
        """
        try:
            processing_times_key = "queue:processing_times"
            times = await self.redis_client.lrange(processing_times_key, 0, 99)  # Last 100 times
            
            if times:
                total_time = sum(float(time) for time in times)
                avg_time = total_time / len(times)
                return avg_time
            else:
                # Default estimate if no data available
                return 5.0  # 5 minutes default
                
        except Exception as e:
            logger.error(f"Failed to get average processing time: {e}")
            return 5.0  # Default fallback
    
    async def perform_queue_maintenance(self) -> Dict[str, int]:
        """
        Perform comprehensive queue maintenance operations.
        
        Returns:
            Dict containing maintenance operation results
        """
        try:
            results = {
                "stale_jobs_cleaned": 0,
                "orphaned_jobs_removed": 0,
                "expired_keys_cleaned": 0,
                "queue_optimized": False
            }
            
            # Clean up stale processing jobs
            results["stale_jobs_cleaned"] = await self.cleanup_stale_processing_jobs()
            
            # Remove orphaned jobs from queue
            results["orphaned_jobs_removed"] = await self._cleanup_orphaned_queue_jobs()
            
            # Clean up expired keys
            results["expired_keys_cleaned"] = await self._cleanup_expired_keys()
            
            # Optimize queue structure
            results["queue_optimized"] = await self._optimize_queue_structure()
            
            logger.info(f"Queue maintenance completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to perform queue maintenance: {e}")
            return {
                "stale_jobs_cleaned": 0,
                "orphaned_jobs_removed": 0,
                "expired_keys_cleaned": 0,
                "queue_optimized": False
            }
    
    async def _cleanup_orphaned_queue_jobs(self) -> int:
        """
        Remove jobs from queue that no longer exist in Redis.
        
        Returns:
            Number of orphaned jobs removed
        """
        try:
            # Get all jobs in queue
            queue_jobs = await self.redis_client.lrange(RedisKeyManager.JOB_QUEUE, 0, -1)
            
            orphaned_count = 0
            for job_id in queue_jobs:
                # Check if job still exists
                job_key = RedisKeyManager.job_key(job_id)
                exists = await self.redis_client.exists(job_key)
                
                if not exists:
                    # Remove orphaned job from queue
                    await self.redis_client.lrem(RedisKeyManager.JOB_QUEUE, 0, job_id)
                    orphaned_count += 1
                    logger.warning(f"Removed orphaned job {job_id} from queue")
            
            return orphaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned queue jobs: {e}")
            return 0
    
    async def _cleanup_expired_keys(self) -> int:
        """
        Clean up expired processing time keys and other temporary data.
        
        Returns:
            Number of expired keys cleaned
        """
        try:
            cleaned_count = 0
            
            # Clean up old processing time keys
            processing_time_pattern = "queue:processing_time:*"
            processing_time_keys = await self.redis_client.keys(processing_time_pattern)
            
            cutoff_time = datetime.utcnow() - timedelta(hours=2)
            
            for key in processing_time_keys:
                try:
                    start_time_str = await self.redis_client.get(key)
                    if start_time_str:
                        start_time = datetime.fromisoformat(start_time_str)
                        if start_time < cutoff_time:
                            await self.redis_client.delete(key)
                            cleaned_count += 1
                except Exception:
                    # If we can't parse the time, delete the key
                    await self.redis_client.delete(key)
                    cleaned_count += 1
            
            # Clean up old daily statistics (keep last 30 days)
            cutoff_date = datetime.utcnow().date() - timedelta(days=30)
            
            # Clean up old completed/failed counters
            for days_back in range(31, 365):  # Clean up very old data
                old_date = datetime.utcnow().date() - timedelta(days=days_back)
                
                old_completed_key = f"queue:completed:{old_date}"
                old_failed_key = f"queue:failed:{old_date}"
                old_users_key = f"active_users:{old_date}"
                
                deleted = await self.redis_client.delete(old_completed_key, old_failed_key, old_users_key)
                cleaned_count += deleted
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired keys: {e}")
            return 0
    
    async def _optimize_queue_structure(self) -> bool:
        """
        Optimize queue structure by removing duplicates and reordering if needed.
        
        Returns:
            True if optimization was performed, False otherwise
        """
        try:
            # Get current queue
            queue_jobs = await self.redis_client.lrange(RedisKeyManager.JOB_QUEUE, 0, -1)
            
            if not queue_jobs:
                return True
            
            # Remove duplicates while preserving order
            seen = set()
            unique_jobs = []
            duplicates_found = False
            
            for job_id in queue_jobs:
                if job_id not in seen:
                    seen.add(job_id)
                    unique_jobs.append(job_id)
                else:
                    duplicates_found = True
            
            # If duplicates were found, rebuild the queue
            if duplicates_found:
                # Clear current queue
                await self.redis_client.delete(RedisKeyManager.JOB_QUEUE)
                
                # Rebuild with unique jobs
                if unique_jobs:
                    await self.redis_client.rpush(RedisKeyManager.JOB_QUEUE, *unique_jobs)
                
                logger.info(f"Optimized queue: removed {len(queue_jobs) - len(unique_jobs)} duplicates")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to optimize queue structure: {e}")
            return False
    
    async def get_queue_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive queue health status.
        
        Returns:
            Dict containing queue health information
        """
        try:
            # Basic queue metrics
            queue_length = await self.get_queue_length()
            processing_jobs = await self.redis_client.scard("queue:processing")
            
            # Check for stale processing jobs
            stale_jobs = await self._count_stale_processing_jobs()
            
            # Check queue growth rate
            queue_growth_rate = await self._calculate_queue_growth_rate()
            
            # Determine health status
            health_status = "healthy"
            issues = []
            
            if queue_length > 100:
                health_status = "warning"
                issues.append("High queue length")
            
            if stale_jobs > 0:
                health_status = "warning"
                issues.append(f"{stale_jobs} stale processing jobs")
            
            if queue_growth_rate > 10:  # More than 10 jobs per minute
                health_status = "warning"
                issues.append("High queue growth rate")
            
            if queue_length > 500:
                health_status = "critical"
                issues.append("Critical queue length")
            
            return {
                "status": health_status,
                "queue_length": queue_length,
                "processing_jobs": processing_jobs,
                "stale_processing_jobs": stale_jobs,
                "queue_growth_rate_per_minute": queue_growth_rate,
                "issues": issues,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue health status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _count_stale_processing_jobs(self, timeout_minutes: int = 60) -> int:
        """
        Count jobs that have been processing for too long.
        
        Args:
            timeout_minutes: Timeout threshold in minutes
            
        Returns:
            Number of stale processing jobs
        """
        try:
            processing_key = "queue:processing"
            processing_jobs = await self.redis_client.smembers(processing_key)
            
            stale_count = 0
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            for job_id in processing_jobs:
                processing_time_key = f"queue:processing_time:{job_id}"
                start_time_str = await self.redis_client.get(processing_time_key)
                
                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str)
                        if start_time < cutoff_time:
                            stale_count += 1
                    except ValueError:
                        stale_count += 1  # Invalid timestamp counts as stale
                else:
                    stale_count += 1  # No timestamp counts as stale
            
            return stale_count
            
        except Exception as e:
            logger.error(f"Failed to count stale processing jobs: {e}")
            return 0
    
    async def _calculate_queue_growth_rate(self) -> float:
        """
        Calculate queue growth rate in jobs per minute.
        
        Returns:
            Queue growth rate
        """
        try:
            # This is a simplified implementation
            # In production, you'd track queue length over time
            
            # Get current queue length
            current_length = await self.get_queue_length()
            
            # Get queue length from 5 minutes ago (if tracked)
            growth_key = "queue:length_history"
            history = await self.redis_client.lrange(growth_key, 0, 4)  # Last 5 entries
            
            if len(history) >= 2:
                try:
                    # Calculate average growth over the tracked period
                    recent_length = float(history[0])
                    older_length = float(history[-1])
                    time_diff_minutes = len(history)  # Assuming 1 minute intervals
                    
                    growth_rate = (recent_length - older_length) / time_diff_minutes
                    return max(0, growth_rate)  # Don't return negative growth
                except (ValueError, ZeroDivisionError):
                    pass
            
            # Fallback: assume moderate growth if we can't calculate
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate queue growth rate: {e}")
            return 0.0
    
    async def track_queue_metrics(self) -> None:
        """
        Track queue metrics over time for analysis.
        This should be called periodically (e.g., every minute).
        """
        try:
            current_length = await self.get_queue_length()
            processing_count = await self.redis_client.scard("queue:processing")
            
            # Store queue length history
            length_history_key = "queue:length_history"
            await self.redis_client.lpush(length_history_key, current_length)
            await self.redis_client.ltrim(length_history_key, 0, 59)  # Keep last hour
            
            # Store processing count history
            processing_history_key = "queue:processing_history"
            await self.redis_client.lpush(processing_history_key, processing_count)
            await self.redis_client.ltrim(processing_history_key, 0, 59)  # Keep last hour
            
            # Store timestamp
            timestamp_key = "queue:metrics_timestamp"
            await self.redis_client.set(timestamp_key, datetime.utcnow().isoformat(), ex=3600)
            
        except Exception as e:
            logger.error(f"Failed to track queue metrics: {e}")
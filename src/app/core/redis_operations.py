"""
Redis data access patterns for job storage, queue management, and user indexing.

This module implements the specific Redis operations needed for the video
generation API, including hash operations for job storage, list operations
for job queues, and set operations for user job indexing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .redis import RedisKeyManager, RedisErrorHandler, safe_redis_operation

logger = logging.getLogger(__name__)


class JobStorage:
    """
    Redis hash operations for job storage and management.
    
    Handles storing, retrieving, and updating job data using Redis hashes
    for efficient field-level operations.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def create_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Create a new job in Redis storage.
        
        Args:
            job_id: Unique job identifier
            job_data: Job data dictionary
            
        Returns:
            True if job was created successfully
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            
            # Prepare job data with timestamps
            job_data_with_meta = {
                **job_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Convert all values to strings for Redis hash
            hash_data = {k: json.dumps(v) if not isinstance(v, str) else v 
                        for k, v in job_data_with_meta.items()}
            
            result = await safe_redis_operation(
                self.redis.hset, key, mapping=hash_data
            )
            
            logger.info(f"Created job {job_id} in Redis storage")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to create job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("create_job", e)
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job data from Redis storage.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data dictionary or None if not found
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            hash_data = await safe_redis_operation(self.redis.hgetall, key)
            
            if not hash_data:
                return None
            
            # Convert JSON strings back to objects
            job_data = {}
            for k, v in hash_data.items():
                try:
                    job_data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    job_data[k] = v
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("get_job", e)
    
    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of a job.
        
        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if job was updated successfully
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            
            # Add updated timestamp
            updates_with_meta = {
                **updates,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Convert values to strings for Redis hash
            hash_updates = {k: json.dumps(v) if not isinstance(v, str) else v 
                           for k, v in updates_with_meta.items()}
            
            result = await safe_redis_operation(
                self.redis.hset, key, mapping=hash_updates
            )
            
            logger.debug(f"Updated job {job_id} with fields: {list(updates.keys())}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("update_job", e)
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from Redis storage.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was deleted successfully
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            result = await safe_redis_operation(self.redis.delete, key)
            
            logger.info(f"Deleted job {job_id} from Redis storage")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("delete_job", e)
    
    async def job_exists(self, job_id: str) -> bool:
        """
        Check if a job exists in Redis storage.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job exists
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            result = await safe_redis_operation(self.redis.exists, key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to check job existence {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("job_exists", e)
    
    async def get_job_field(self, job_id: str, field: str) -> Optional[Any]:
        """
        Get a specific field from a job.
        
        Args:
            job_id: Job identifier
            field: Field name to retrieve
            
        Returns:
            Field value or None if not found
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            value = await safe_redis_operation(self.redis.hget, key, field)
            
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error(f"Failed to get job field {job_id}.{field}: {e}")
            raise RedisErrorHandler.handle_redis_error("get_job_field", e)


class JobQueue:
    """
    Redis list operations for job queue management.
    
    Implements a FIFO job queue using Redis lists with support for
    priority queuing and queue monitoring.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.queue_key = RedisKeyManager.JOB_QUEUE
        self.processing_key = f"{self.queue_key}:processing"
    
    async def enqueue_job(self, job_id: str, priority: bool = False) -> int:
        """
        Add a job to the queue.
        
        Args:
            job_id: Job identifier
            priority: If True, add to front of queue (high priority)
            
        Returns:
            New queue length
        """
        try:
            if priority:
                result = await safe_redis_operation(
                    self.redis.lpush, self.queue_key, job_id
                )
            else:
                result = await safe_redis_operation(
                    self.redis.rpush, self.queue_key, job_id
                )
            
            logger.info(f"Enqueued job {job_id} ({'priority' if priority else 'normal'})")
            return result
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("enqueue_job", e)
    
    async def dequeue_job(self, timeout: int = 0) -> Optional[str]:
        """
        Remove and return the next job from the queue.
        
        Args:
            timeout: Blocking timeout in seconds (0 for non-blocking)
            
        Returns:
            Job ID or None if queue is empty
        """
        try:
            if timeout > 0:
                # Blocking pop with timeout
                result = await safe_redis_operation(
                    self.redis.blpop, self.queue_key, timeout=timeout
                )
                if result:
                    _, job_id = result
                    # Move to processing queue
                    await safe_redis_operation(
                        self.redis.lpush, self.processing_key, job_id
                    )
                    logger.info(f"Dequeued job {job_id} for processing")
                    return job_id
            else:
                # Non-blocking pop
                job_id = await safe_redis_operation(self.redis.lpop, self.queue_key)
                if job_id:
                    # Move to processing queue
                    await safe_redis_operation(
                        self.redis.lpush, self.processing_key, job_id
                    )
                    logger.info(f"Dequeued job {job_id} for processing")
                    return job_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            raise RedisErrorHandler.handle_redis_error("dequeue_job", e)
    
    async def complete_job(self, job_id: str) -> bool:
        """
        Mark a job as completed and remove from processing queue.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was removed from processing queue
        """
        try:
            result = await safe_redis_operation(
                self.redis.lrem, self.processing_key, 1, job_id
            )
            
            if result:
                logger.info(f"Completed job {job_id}")
            else:
                logger.warning(f"Job {job_id} not found in processing queue")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("complete_job", e)
    
    async def requeue_job(self, job_id: str, priority: bool = True) -> bool:
        """
        Move a job from processing back to the main queue.
        
        Args:
            job_id: Job identifier
            priority: If True, add to front of queue
            
        Returns:
            True if job was requeued successfully
        """
        try:
            # Remove from processing queue
            removed = await safe_redis_operation(
                self.redis.lrem, self.processing_key, 1, job_id
            )
            
            if removed:
                # Add back to main queue
                await self.enqueue_job(job_id, priority=priority)
                logger.info(f"Requeued job {job_id}")
                return True
            else:
                logger.warning(f"Job {job_id} not found in processing queue")
                return False
                
        except Exception as e:
            logger.error(f"Failed to requeue job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("requeue_job", e)
    
    async def get_queue_length(self) -> int:
        """
        Get the current queue length.
        
        Returns:
            Number of jobs in queue
        """
        try:
            return await safe_redis_operation(self.redis.llen, self.queue_key)
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            raise RedisErrorHandler.handle_redis_error("get_queue_length", e)
    
    async def get_processing_length(self) -> int:
        """
        Get the number of jobs currently being processed.
        
        Returns:
            Number of jobs in processing
        """
        try:
            return await safe_redis_operation(self.redis.llen, self.processing_key)
        except Exception as e:
            logger.error(f"Failed to get processing length: {e}")
            raise RedisErrorHandler.handle_redis_error("get_processing_length", e)
    
    async def peek_queue(self, count: int = 10) -> List[str]:
        """
        Peek at jobs in the queue without removing them.
        
        Args:
            count: Number of jobs to peek at
            
        Returns:
            List of job IDs
        """
        try:
            return await safe_redis_operation(
                self.redis.lrange, self.queue_key, 0, count - 1
            )
        except Exception as e:
            logger.error(f"Failed to peek queue: {e}")
            raise RedisErrorHandler.handle_redis_error("peek_queue", e)
    
    async def clear_queue(self) -> bool:
        """
        Clear all jobs from the queue.
        
        Returns:
            True if queue was cleared
        """
        try:
            result = await safe_redis_operation(self.redis.delete, self.queue_key)
            logger.warning("Cleared job queue")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            raise RedisErrorHandler.handle_redis_error("clear_queue", e)


class UserJobIndex:
    """
    Redis set operations for user job indexing.
    
    Maintains indexes of jobs per user using Redis sets for efficient
    lookups and user-specific job management.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def add_user_job(self, user_id: str, job_id: str) -> bool:
        """
        Add a job to a user's job index.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            
        Returns:
            True if job was added to user's index
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            result = await safe_redis_operation(self.redis.sadd, key, job_id)
            
            logger.debug(f"Added job {job_id} to user {user_id} index")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id} to user {user_id} index: {e}")
            raise RedisErrorHandler.handle_redis_error("add_user_job", e)
    
    async def remove_user_job(self, user_id: str, job_id: str) -> bool:
        """
        Remove a job from a user's job index.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            
        Returns:
            True if job was removed from user's index
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            result = await safe_redis_operation(self.redis.srem, key, job_id)
            
            logger.debug(f"Removed job {job_id} from user {user_id} index")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to remove job {job_id} from user {user_id} index: {e}")
            raise RedisErrorHandler.handle_redis_error("remove_user_job", e)
    
    async def get_user_jobs(self, user_id: str) -> Set[str]:
        """
        Get all job IDs for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of job IDs
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            result = await safe_redis_operation(self.redis.smembers, key)
            return set(result) if result else set()
            
        except Exception as e:
            logger.error(f"Failed to get jobs for user {user_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("get_user_jobs", e)
    
    async def get_user_job_count(self, user_id: str) -> int:
        """
        Get the number of jobs for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of jobs
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            return await safe_redis_operation(self.redis.scard, key)
            
        except Exception as e:
            logger.error(f"Failed to get job count for user {user_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("get_user_job_count", e)
    
    async def user_has_job(self, user_id: str, job_id: str) -> bool:
        """
        Check if a user has a specific job.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            
        Returns:
            True if user has the job
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            result = await safe_redis_operation(self.redis.sismember, key, job_id)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to check if user {user_id} has job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("user_has_job", e)
    
    async def clear_user_jobs(self, user_id: str) -> bool:
        """
        Clear all jobs for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user's jobs were cleared
        """
        try:
            key = RedisKeyManager.user_jobs_key(user_id)
            result = await safe_redis_operation(self.redis.delete, key)
            
            logger.info(f"Cleared all jobs for user {user_id}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to clear jobs for user {user_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("clear_user_jobs", e)


class RedisCleanup:
    """
    Redis key expiration and cleanup utilities.
    
    Handles automatic cleanup of expired data and maintenance
    of Redis storage to prevent memory bloat.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def set_job_expiration(self, job_id: str, ttl_seconds: int) -> bool:
        """
        Set expiration time for a job.
        
        Args:
            job_id: Job identifier
            ttl_seconds: Time to live in seconds
            
        Returns:
            True if expiration was set
        """
        try:
            key = RedisKeyManager.job_key(job_id)
            result = await safe_redis_operation(self.redis.expire, key, ttl_seconds)
            
            logger.debug(f"Set expiration for job {job_id}: {ttl_seconds}s")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to set expiration for job {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("set_job_expiration", e)
    
    async def cleanup_completed_jobs(self, retention_days: int = 7) -> int:
        """
        Clean up completed jobs older than retention period.
        
        Args:
            retention_days: Number of days to retain completed jobs
            
        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
            cutoff_iso = cutoff_time.isoformat()
            
            # Scan for job keys
            job_pattern = f"{RedisKeyManager.JOB_PREFIX}:*"
            cleaned_count = 0
            
            async for key in self.redis.scan_iter(match=job_pattern):
                # Get job completion time
                completed_at = await safe_redis_operation(
                    self.redis.hget, key, "completed_at"
                )
                
                if completed_at and completed_at < cutoff_iso:
                    # Get job status to ensure it's completed
                    status = await safe_redis_operation(
                        self.redis.hget, key, "status"
                    )
                    
                    if status in ["completed", "failed", "cancelled"]:
                        await safe_redis_operation(self.redis.delete, key)
                        cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            raise RedisErrorHandler.handle_redis_error("cleanup_completed_jobs", e)
    
    async def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of cache entries cleaned up
        """
        try:
            cache_pattern = f"{RedisKeyManager.CACHE_PREFIX}:*"
            cleaned_count = 0
            
            async for key in self.redis.scan_iter(match=cache_pattern):
                ttl = await safe_redis_operation(self.redis.ttl, key)
                if ttl == -1:  # No expiration set
                    # Set default expiration for cache entries
                    await safe_redis_operation(self.redis.expire, key, 3600)  # 1 hour
                elif ttl == -2:  # Key doesn't exist (expired)
                    cleaned_count += 1
            
            logger.info(f"Processed cache cleanup, {cleaned_count} expired entries")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            raise RedisErrorHandler.handle_redis_error("cleanup_expired_cache", e)
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get Redis memory usage statistics.
        
        Returns:
            Dictionary with memory usage information
        """
        try:
            info = await safe_redis_operation(self.redis.info, "memory")
            
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "used_memory_peak": info.get("used_memory_peak", 0),
                "used_memory_peak_human": info.get("used_memory_peak_human", "0B"),
                "memory_fragmentation_ratio": info.get("mem_fragmentation_ratio", 0),
                "total_system_memory": info.get("total_system_memory", 0),
                "total_system_memory_human": info.get("total_system_memory_human", "0B")
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            raise RedisErrorHandler.handle_redis_error("get_memory_usage", e)


# Convenience class that combines all Redis operations
class RedisOperations:
    """
    Combined Redis operations class providing access to all data patterns.
    
    This class provides a single interface to all Redis operations
    for job storage, queue management, user indexing, and cleanup.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.jobs = JobStorage(redis_client)
        self.queue = JobQueue(redis_client)
        self.user_index = UserJobIndex(redis_client)
        self.cleanup = RedisCleanup(redis_client)
    
    async def create_job_with_queue(
        self, 
        job_id: str, 
        user_id: str, 
        job_data: Dict[str, Any],
        priority: bool = False
    ) -> bool:
        """
        Create a job and add it to the queue and user index atomically.
        
        Args:
            job_id: Job identifier
            user_id: User identifier
            job_data: Job data dictionary
            priority: If True, add to front of queue
            
        Returns:
            True if all operations succeeded
        """
        try:
            # Use Redis transaction for atomicity
            async with self.redis.pipeline(transaction=True) as pipe:
                # Create job
                job_key = RedisKeyManager.job_key(job_id)
                job_data_with_meta = {
                    **job_data,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                hash_data = {k: json.dumps(v) if not isinstance(v, str) else v 
                            for k, v in job_data_with_meta.items()}
                pipe.hset(job_key, mapping=hash_data)
                
                # Add to queue
                if priority:
                    pipe.lpush(RedisKeyManager.JOB_QUEUE, job_id)
                else:
                    pipe.rpush(RedisKeyManager.JOB_QUEUE, job_id)
                
                # Add to user index
                user_key = RedisKeyManager.user_jobs_key(user_id)
                pipe.sadd(user_key, job_id)
                
                # Execute transaction
                await pipe.execute()
            
            logger.info(f"Created job {job_id} with queue and user index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create job with queue {job_id}: {e}")
            raise RedisErrorHandler.handle_redis_error("create_job_with_queue", e)
"""
Queue service implementations for job processing.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import uuid

from ...models.job import Job
from ..interfaces.infrastructure import IQueueService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class InMemoryQueueService(IQueueService):
    """In-memory queue service implementation for development/testing."""
    
    def __init__(self):
        self._queues: Dict[str, List[Dict[str, Any]]] = {}
        self._default_queue = "default"
    
    @property
    def service_name(self) -> str:
        return "InMemoryQueueService"
    
    async def enqueue_job(
        self, 
        job: Job, 
        priority: Optional[int] = None
    ) -> ServiceResult[str]:
        """Enqueue job for processing."""
        try:
            queue_name = self._get_queue_name(job)
            
            if queue_name not in self._queues:
                self._queues[queue_name] = []
            
            queue_item = {
                "id": str(uuid.uuid4()),
                "job": job.dict(),
                "priority": priority or 0,
                "enqueued_at": datetime.utcnow().isoformat(),
                "attempts": 0
            }
            
            # Insert based on priority (higher priority first)
            inserted = False
            for i, item in enumerate(self._queues[queue_name]):
                if (priority or 0) > item.get("priority", 0):
                    self._queues[queue_name].insert(i, queue_item)
                    inserted = True
                    break
            
            if not inserted:
                self._queues[queue_name].append(queue_item)
            
            logger.info(f"Job {job.id} enqueued to {queue_name}")
            
            return ServiceResult.success(
                queue_item["id"],
                metadata={
                    "queue_name": queue_name,
                    "position": len(self._queues[queue_name]),
                    "priority": priority
                }
            )
            
        except Exception as e:
            logger.error(f"Error enqueuing job: {e}")
            return ServiceResult.error(
                error="Failed to enqueue job",
                error_code="ENQUEUE_ERROR"
            )
    
    async def dequeue_job(
        self, 
        queue_name: str
    ) -> ServiceResult[Optional[Job]]:
        """Dequeue next job from queue."""
        try:
            if queue_name not in self._queues or not self._queues[queue_name]:
                return ServiceResult.success(None)
            
            queue_item = self._queues[queue_name].pop(0)
            job_data = queue_item["job"]
            job = Job(**job_data)
            
            logger.info(f"Job {job.id} dequeued from {queue_name}")
            
            return ServiceResult.success(
                job,
                metadata={
                    "queue_name": queue_name,
                    "queue_item_id": queue_item["id"],
                    "attempts": queue_item["attempts"]
                }
            )
            
        except Exception as e:
            logger.error(f"Error dequeuing job: {e}")
            return ServiceResult.error(
                error="Failed to dequeue job",
                error_code="DEQUEUE_ERROR"
            )
    
    async def get_queue_size(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Get number of jobs in queue."""
        try:
            size = len(self._queues.get(queue_name, []))
            return ServiceResult.success(size)
            
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return ServiceResult.error(
                error="Failed to get queue size",
                error_code="QUEUE_SIZE_ERROR"
            )
    
    async def clear_queue(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Clear all jobs from queue."""
        try:
            if queue_name in self._queues:
                count = len(self._queues[queue_name])
                self._queues[queue_name].clear()
                logger.info(f"Cleared {count} jobs from queue {queue_name}")
                return ServiceResult.success(count)
            else:
                return ServiceResult.success(0)
                
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return ServiceResult.error(
                error="Failed to clear queue",
                error_code="QUEUE_CLEAR_ERROR"
            )
    
    def _get_queue_name(self, job: Job) -> str:
        """Determine queue name based on job properties."""
        # Route jobs to different queues based on type and priority
        base_name = job.job_type.value.replace("_", "-")
        
        if job.priority.value in ["high", "urgent"]:
            return f"{base_name}-priority"
        else:
            return f"{base_name}-normal"
    
    async def get_all_queue_stats(self) -> Dict[str, int]:
        """Get statistics for all queues."""
        return {queue_name: len(jobs) for queue_name, jobs in self._queues.items()}


class RedisQueueService(IQueueService):
    """Redis-based queue service implementation for production."""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client  # Would be injected
        self._queue_prefix = "job_queue:"
    
    @property
    def service_name(self) -> str:
        return "RedisQueueService"
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        # Would initialize Redis connection here
        logger.info("RedisQueueService initialized")
    
    async def cleanup(self) -> None:
        """Cleanup Redis connection."""
        # Would cleanup Redis connection here
        logger.info("RedisQueueService cleaned up")
    
    async def enqueue_job(
        self, 
        job: Job, 
        priority: Optional[int] = None
    ) -> ServiceResult[str]:
        """Enqueue job for processing using Redis."""
        try:
            # In real implementation, would use Redis operations
            # For now, return placeholder result
            queue_name = self._get_queue_name(job)
            job_id = str(uuid.uuid4())
            
            # Placeholder - would use Redis ZADD for priority queue
            logger.info(f"Job {job.id} enqueued to Redis queue {queue_name}")
            
            return ServiceResult.success(
                job_id,
                metadata={
                    "queue_name": queue_name,
                    "priority": priority,
                    "backend": "redis"
                }
            )
            
        except Exception as e:
            logger.error(f"Error enqueuing job to Redis: {e}")
            return ServiceResult.error(
                error="Failed to enqueue job to Redis",
                error_code="REDIS_ENQUEUE_ERROR"
            )
    
    async def dequeue_job(
        self, 
        queue_name: str
    ) -> ServiceResult[Optional[Job]]:
        """Dequeue next job from Redis queue."""
        try:
            # Placeholder - would use Redis ZPOPMIN for priority queue
            logger.info(f"Attempting to dequeue from Redis queue {queue_name}")
            
            # For placeholder, return None (no jobs)
            return ServiceResult.success(None)
            
        except Exception as e:
            logger.error(f"Error dequeuing job from Redis: {e}")
            return ServiceResult.error(
                error="Failed to dequeue job from Redis",
                error_code="REDIS_DEQUEUE_ERROR"
            )
    
    async def get_queue_size(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Get number of jobs in Redis queue."""
        try:
            # Placeholder - would use Redis ZCARD
            return ServiceResult.success(0)
            
        except Exception as e:
            logger.error(f"Error getting Redis queue size: {e}")
            return ServiceResult.error(
                error="Failed to get Redis queue size",
                error_code="REDIS_QUEUE_SIZE_ERROR"
            )
    
    async def clear_queue(
        self, 
        queue_name: str
    ) -> ServiceResult[int]:
        """Clear all jobs from Redis queue."""
        try:
            # Placeholder - would use Redis DEL
            logger.info(f"Clearing Redis queue {queue_name}")
            return ServiceResult.success(0)
            
        except Exception as e:
            logger.error(f"Error clearing Redis queue: {e}")
            return ServiceResult.error(
                error="Failed to clear Redis queue",
                error_code="REDIS_QUEUE_CLEAR_ERROR"
            )
    
    def _get_queue_name(self, job: Job) -> str:
        """Determine Redis queue name based on job properties."""
        base_name = job.job_type.value.replace("_", "-")
        
        if job.priority.value in ["high", "urgent"]:
            return f"{self._queue_prefix}{base_name}-priority"
        else:
            return f"{self._queue_prefix}{base_name}-normal"

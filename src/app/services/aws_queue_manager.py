"""
AWS RDS-based Queue Manager for job processing.

This service provides advanced queue management capabilities including
priority handling, position tracking, worker assignment, and queue optimization.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from enum import Enum

from ..database.connection import RDSConnectionManager
from ..database.pydantic_models import JobDB, JobQueueDB
from ..models.job import JobStatus, JobPriority
from ..core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class QueueStatus(str, Enum):
    """Queue entry status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerStatus(str, Enum):
    """Worker status enumeration."""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class AWSQueueManager:
    """
    Advanced queue manager for RDS-based job processing.
    
    Provides priority-based queuing, worker assignment, position tracking,
    and queue optimization with database persistence.
    """
    
    def __init__(self, db_manager: RDSConnectionManager, redis_client=None):
        """
        Initialize the AWS Queue Manager.
        
        Args:
            db_manager: RDS connection manager for database operations
            redis_client: Optional Redis client for caching and real-time updates
        """
        self.db_manager = db_manager
        self.redis_client = redis_client
        self._priority_weights = {
            JobPriority.URGENT: 1000,
            JobPriority.HIGH: 100,
            JobPriority.NORMAL: 10,
            JobPriority.LOW: 1
        }
        self._max_retries = 3
        self._retry_delay_base = 60  # Base retry delay in seconds
        
        logger.info("Initialized AWS Queue Manager with RDS backend")
    
    async def enqueue_job(self, job_id: UUID, priority: JobPriority = JobPriority.NORMAL,
                         estimated_duration: Optional[int] = None) -> bool:
        """
        Add a job to the processing queue.
        
        Args:
            job_id: Job ID to enqueue
            priority: Job priority level
            estimated_duration: Estimated processing duration in seconds
            
        Returns:
            True if job was successfully enqueued, False otherwise
        """
        try:
            # Check if job exists and is in correct state
            job_db = await self.db_manager.get_pydantic_model(
                JobDB, "jobs", "id = $1 AND is_deleted = FALSE", [job_id]
            )
            
            if not job_db:
                logger.warning(f"Cannot enqueue non-existent job {job_id}")
                return False
            
            if job_db.status != JobStatus.QUEUED:
                logger.warning(f"Cannot enqueue job {job_id} with status {job_db.status}")
                return False
            
            # Create queue entry
            queue_entry = JobQueueDB(
                job_id=job_id,
                priority=priority,
                queue_status=QueueStatus.QUEUED.value,
                queued_at=datetime.utcnow()
            )
            
            # Save queue entry
            await self.db_manager.save_pydantic_model(
                queue_entry, "job_queue", conflict_columns=["job_id"]
            )
            
            # Update queue positions
            await self._recalculate_queue_positions()
            
            # Notify workers if Redis is available
            if self.redis_client:
                await self._notify_workers_new_job(priority)
            
            logger.info(f"Enqueued job {job_id} with priority {priority.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            return False
    
    async def dequeue_next_job(self, worker_id: str, worker_capabilities: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Get the next job from the queue for processing.
        
        Args:
            worker_id: Unique identifier for the worker
            worker_capabilities: Optional list of worker capabilities
            
        Returns:
            Dict with job information or None if no jobs available
        """
        try:
            # Register/update worker status
            await self._update_worker_status(worker_id, W
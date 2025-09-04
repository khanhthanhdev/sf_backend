"""
In-memory queue management service for handling job queues and processing.

This service provides business logic for job queue operations,
including queue management, job processing coordination, and monitoring.
Uses in-memory storage for queue operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import deque
import threading

logger = logging.getLogger(__name__)


class QueueService:
    """
    Service class for job queue management operations using in-memory storage.
    
    Handles job queue operations, processing coordination,
    and queue monitoring functionality.
    """
    
    def __init__(self):
        self._job_queue = deque()
        self._queue_lock = threading.Lock()
        self._processing_jobs = set()
        self._completed_today = 0
        self._failed_today = 0
        self._queue_stats = {
            "total_enqueued": 0,
            "total_processed": 0
        }
    
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
            with self._queue_lock:
                # Add job to appropriate position based on priority
                if priority == "urgent":
                    # Add to front of queue for urgent jobs
                    self._job_queue.appendleft(job_id)
                elif priority == "high":
                    # Add near front for high priority jobs
                    if len(self._job_queue) <= 3:
                        self._job_queue.appendleft(job_id)
                    else:
                        # Insert at position 3 for high priority
                        temp_queue = deque()
                        for _ in range(min(3, len(self._job_queue))):
                            temp_queue.append(self._job_queue.popleft())
                        self._job_queue.appendleft(job_id)
                        while temp_queue:
                            self._job_queue.appendleft(temp_queue.pop())
                else:
                    # Normal and low priority jobs go to the end
                    self._job_queue.append(job_id)
                
                self._queue_stats["total_enqueued"] += 1
            
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
            with self._queue_lock:
                if self._job_queue:
                    job_id = self._job_queue.popleft()
                    self._processing_jobs.add(job_id)
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
            with self._queue_lock:
                if self._job_queue:
                    return self._job_queue[0]
            return None
            
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
            with self._queue_lock:
                return len(self._job_queue)
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
            with self._queue_lock:
                try:
                    position = list(self._job_queue).index(job_id)
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
            with self._queue_lock:
                # Convert to list to find and remove
                queue_list = list(self._job_queue)
                if job_id in queue_list:
                    queue_list.remove(job_id)
                    self._job_queue.clear()
                    self._job_queue.extend(queue_list)
                    logger.info(f"Removed job {job_id} from queue")
                    return True
                else:
                    logger.warning(f"Job {job_id} not found in queue")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to remove job {job_id} from queue: {e}")
            return False
    
    async def mark_job_completed(self, job_id: str, success: bool = True) -> None:
        """
        Mark a job as completed and remove from processing set.
        
        Args:
            job_id: Job ID that completed
            success: Whether the job completed successfully
        """
        try:
            with self._queue_lock:
                self._processing_jobs.discard(job_id)
                self._queue_stats["total_processed"] += 1
                
                if success:
                    self._completed_today += 1
                else:
                    self._failed_today += 1
            
            logger.info(f"Job {job_id} marked as completed (success: {success})")
            
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed: {e}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics.
        
        Returns:
            Dictionary containing queue statistics
        """
        try:
            with self._queue_lock:
                queue_length = len(self._job_queue)
                processing_jobs = len(self._processing_jobs)
                
                return {
                    "queue_length": queue_length,
                    "processing_jobs": processing_jobs,
                    "completed_today": self._completed_today,
                    "failed_today": self._failed_today,
                    "total_enqueued": self._queue_stats["total_enqueued"],
                    "total_processed": self._queue_stats["total_processed"],
                    "average_processing_time_minutes": 0,  # Could be calculated if needed
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            return {
                "queue_length": 0,
                "processing_jobs": 0,
                "completed_today": 0,
                "failed_today": 0,
                "total_enqueued": 0,
                "total_processed": 0,
                "average_processing_time_minutes": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_processing_jobs(self) -> List[str]:
        """
        Get list of currently processing job IDs.
        
        Returns:
            List of job IDs currently being processed
        """
        try:
            with self._queue_lock:
                return list(self._processing_jobs)
        except Exception as e:
            logger.error(f"Failed to get processing jobs: {e}")
            return []
    
    async def reset_daily_stats(self) -> None:
        """
        Reset daily statistics (typically called at midnight).
        """
        try:
            with self._queue_lock:
                self._completed_today = 0
                self._failed_today = 0
            
            logger.info("Daily queue statistics reset")
            
        except Exception as e:
            logger.error(f"Failed to reset daily stats: {e}")
    
    async def clear_queue(self) -> int:
        """
        Clear all jobs from the queue.
        
        Returns:
            Number of jobs that were removed
        """
        try:
            with self._queue_lock:
                count = len(self._job_queue)
                self._job_queue.clear()
                logger.info(f"Cleared {count} jobs from queue")
                return count
                
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0
    
    def get_queue_snapshot(self) -> Dict[str, Any]:
        """
        Get a snapshot of the current queue state (synchronous).
        
        Returns:
            Dictionary containing queue snapshot
        """
        try:
            with self._queue_lock:
                return {
                    "queue_jobs": list(self._job_queue),
                    "processing_jobs": list(self._processing_jobs),
                    "queue_length": len(self._job_queue),
                    "processing_count": len(self._processing_jobs),
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Failed to get queue snapshot: {e}")
            return {
                "queue_jobs": [],
                "processing_jobs": [],
                "queue_length": 0,
                "processing_count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
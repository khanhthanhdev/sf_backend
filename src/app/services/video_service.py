"""
Video generation service for managing video creation jobs and operations.

This service handles the business logic for video generation requests,
job queue management, progress tracking, and integration with the
multi-agent video generation pipeline.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from redis.asyncio import Redis

from ..models.job import (
    Job, JobCreateRequest, JobStatus, JobType, JobProgress,
    JobConfiguration, JobError, JobMetrics, BatchJobCreateRequest
)
from ..models.video import VideoMetadata, VideoStatus
from ..core.redis import RedisKeyManager, redis_json_get, redis_json_set

logger = logging.getLogger(__name__)


class VideoService:
    """
    Service class for video generation operations.
    
    Handles job creation, status management, progress tracking,
    and integration with the video generation pipeline.
    """
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
    
    async def create_video_job(
        self,
        request: JobCreateRequest,
        user_id: str
    ) -> Job:
        """
        Create a new video generation job.
        
        Args:
            request: Job creation request with configuration
            user_id: ID of the user creating the job
            
        Returns:
            Created Job instance
            
        Raises:
            Exception: If job creation fails
        """
        try:
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # Calculate estimated completion time based on quality and complexity
            estimated_completion = self._calculate_estimated_completion(
                request.configuration
            )
            
            # Create job progress with initial values
            progress = JobProgress(
                percentage=0.0,
                current_stage="queued",
                estimated_completion=estimated_completion
            )
            
            # Create job instance
            job = Job(
                id=job_id,
                user_id=user_id,
                job_type=JobType.VIDEO_GENERATION,
                priority=request.priority,
                configuration=request.configuration,
                status=JobStatus.QUEUED,
                progress=progress,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Store job in Redis
            await self._store_job_in_redis(job)
            
            # Add job to processing queue
            await self._enqueue_job_for_processing(job_id, request.priority.value)
            
            logger.info(
                "Created video generation job",
                job_id=job_id,
                user_id=user_id,
                topic=request.configuration.topic,
                quality=request.configuration.quality,
                estimated_completion=estimated_completion
            )
            
            return job
            
        except Exception as e:
            logger.error(
                "Failed to create video generation job",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def create_batch_jobs(
        self,
        request: BatchJobCreateRequest,
        user_id: str
    ) -> List[Job]:
        """
        Create multiple video generation jobs as a batch.
        
        Args:
            request: Batch job creation request
            user_id: ID of the user creating the jobs
            
        Returns:
            List of created Job instances
            
        Raises:
            Exception: If batch job creation fails
        """
        try:
            batch_id = str(uuid.uuid4())
            jobs = []
            
            for job_config in request.jobs:
                # Create individual job request
                job_request = JobCreateRequest(
                    configuration=job_config,
                    priority=request.batch_priority
                )
                
                # Create job
                job = await self.create_video_job(job_request, user_id)
                
                # Set batch information
                job.batch_id = batch_id
                job.job_type = JobType.BATCH_VIDEO_GENERATION
                
                jobs.append(job)
            
            logger.info(
                "Created batch video generation jobs",
                batch_id=batch_id,
                job_count=len(jobs),
                user_id=user_id
            )
            
            return jobs
            
        except Exception as e:
            logger.error(
                "Failed to create batch video generation jobs",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """
        Get current job status and information.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Job instance or None if not found
        """
        try:
            job_key = RedisKeyManager.job_key(job_id)
            job_data = await redis_json_get(self.redis_client, job_key)
            
            if not job_data:
                return None
            
            return Job(**job_data)
            
        except Exception as e:
            logger.error(
                "Failed to get job status",
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress_percentage: Optional[float] = None,
        current_stage: Optional[str] = None,
        error_info: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update job status and progress information.
        
        Args:
            job_id: Unique job identifier
            status: New job status
            progress_percentage: Progress percentage (0-100)
            current_stage: Current processing stage
            error_info: Error information if job failed
            metrics: Performance metrics
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current job
            job = await self.get_job_status(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for status update")
                return False
            
            # Update job status
            job.status = status
            job.updated_at = datetime.utcnow()
            
            # Update progress if provided
            if progress_percentage is not None:
                job.progress.percentage = progress_percentage
            
            if current_stage:
                job.progress.current_stage = current_stage
                if current_stage not in job.progress.stages_completed:
                    job.progress.stages_completed.append(current_stage)
            
            # Handle completion
            if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.utcnow()
                if status == JobStatus.COMPLETED:
                    job.progress.percentage = 100.0
            
            # Handle processing start
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.utcnow()
            
            # Update error information
            if error_info and status == JobStatus.FAILED:
                job.error = JobError(
                    error_code=error_info.get("error_code", "UNKNOWN_ERROR"),
                    error_message=error_info.get("error_message", "Unknown error occurred"),
                    error_details=error_info.get("error_details"),
                    stack_trace=error_info.get("stack_trace")
                )
            
            # Update metrics
            if metrics:
                if not job.metrics:
                    job.metrics = JobMetrics()
                
                for key, value in metrics.items():
                    if hasattr(job.metrics, key):
                        setattr(job.metrics, key, value)
            
            # Save updated job to Redis
            job_key = RedisKeyManager.job_key(job_id)
            await redis_json_set(self.redis_client, job_key, job.dict())
            
            # Update status cache
            status_key = RedisKeyManager.job_status_key(job_id)
            await self.redis_client.set(status_key, status.value, ex=300)
            
            logger.info(
                "Updated job status",
                job_id=job_id,
                status=status,
                progress=job.progress.percentage,
                stage=current_stage
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update job status",
                job_id=job_id,
                status=status,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a video generation job.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            job = await self.get_job_status(job_id)
            if not job:
                return False
            
            # Check if job can be cancelled
            if not job.can_be_cancelled:
                logger.warning(
                    f"Job {job_id} cannot be cancelled. Current status: {job.status}"
                )
                return False
            
            # Update job status to cancelled
            success = await self.update_job_status(
                job_id=job_id,
                status=JobStatus.CANCELLED,
                current_stage="cancelled"
            )
            
            if success:
                # Remove from processing queue if still queued
                await self.redis_client.lrem(RedisKeyManager.JOB_QUEUE, 0, job_id)
                
                logger.info(f"Job {job_id} cancelled successfully")
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to cancel job",
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def create_video_metadata(
        self,
        job_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        duration_seconds: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        format: str = "mp4"
    ) -> VideoMetadata:
        """
        Create video metadata for a completed job.
        
        Args:
            job_id: Associated job ID
            filename: Video filename
            file_path: Path to video file
            file_size: File size in bytes
            duration_seconds: Video duration
            width: Video width in pixels
            height: Video height in pixels
            format: Video format
            
        Returns:
            VideoMetadata instance
        """
        try:
            # Get job to extract user_id
            job = await self.get_job_status(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Create video metadata
            video_metadata = VideoMetadata(
                id=str(uuid.uuid4()),
                job_id=job_id,
                user_id=job.user_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
                format=format,
                status=VideoStatus.READY,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
            
            # Store video metadata in Redis
            video_key = RedisKeyManager.video_key(f"job_{job_id}")
            await redis_json_set(self.redis_client, video_key, video_metadata.dict())
            
            logger.info(
                "Created video metadata",
                job_id=job_id,
                video_id=video_metadata.id,
                filename=filename,
                file_size=file_size
            )
            
            return video_metadata
            
        except Exception as e:
            logger.error(
                "Failed to create video metadata",
                job_id=job_id,
                filename=filename,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _calculate_estimated_completion(
        self,
        configuration: JobConfiguration
    ) -> datetime:
        """
        Calculate estimated completion time based on job configuration.
        
        Args:
            configuration: Job configuration
            
        Returns:
            Estimated completion datetime
        """
        # Base processing time in minutes
        base_time = 5
        
        # Adjust based on quality
        quality_multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "ultra": 2.0
        }
        
        quality_multiplier = quality_multipliers.get(
            configuration.quality.value, 1.0
        )
        
        # Adjust based on content complexity (rough estimate)
        content_length = len(configuration.topic) + len(configuration.context)
        complexity_multiplier = 1.0 + (content_length / 1000)  # +1 minute per 1000 chars
        
        # Adjust for RAG usage
        rag_multiplier = 1.3 if configuration.use_rag else 1.0
        
        # Calculate total estimated time
        estimated_minutes = base_time * quality_multiplier * complexity_multiplier * rag_multiplier
        
        return datetime.utcnow() + timedelta(minutes=estimated_minutes)
    
    async def get_queue_length(self) -> int:
        """
        Get current job queue length.
        
        Returns:
            Number of jobs in queue
        """
        try:
            return await self.redis_client.llen(RedisKeyManager.JOB_QUEUE)
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0
    
    async def get_user_jobs(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Job]:
        """
        Get jobs for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of Job instances
        """
        try:
            # Get user's job IDs
            user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
            job_ids = await self.redis_client.smembers(user_jobs_key)
            
            if not job_ids:
                return []
            
            # Get job data for each ID
            jobs = []
            for job_id in list(job_ids)[offset:offset + limit]:
                job = await self.get_job_status(job_id)
                if job:
                    jobs.append(job)
            
            # Sort by creation date (newest first)
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            return jobs
            
        except Exception as e:
            logger.error(
                "Failed to get user jobs",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return []
    
    async def _store_job_in_redis(self, job: Job) -> None:
        """
        Store job data in Redis with proper indexing.
        
        Args:
            job: Job instance to store
        """
        # Store job data
        job_key = RedisKeyManager.job_key(job.id)
        await redis_json_set(self.redis_client, job_key, job.dict())
        
        # Add to user's job index
        user_jobs_key = RedisKeyManager.user_jobs_key(job.user_id)
        await self.redis_client.sadd(user_jobs_key, job.id)
        
        # Set status cache
        status_key = RedisKeyManager.job_status_key(job.id)
        await self.redis_client.set(status_key, job.status.value, ex=300)
    
    async def _enqueue_job_for_processing(self, job_id: str, priority: str) -> None:
        """
        Add job to the processing queue based on priority.
        
        Args:
            job_id: Job ID to enqueue
            priority: Job priority level
        """
        if priority == "urgent":
            # Add to front of queue for urgent jobs
            await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job_id)
        elif priority == "high":
            # Add near front for high priority jobs
            queue_length = await self.redis_client.llen(RedisKeyManager.JOB_QUEUE)
            insert_position = min(queue_length // 4, 10)
            if insert_position == 0:
                await self.redis_client.lpush(RedisKeyManager.JOB_QUEUE, job_id)
            else:
                await self.redis_client.rpush(RedisKeyManager.JOB_QUEUE, job_id)
        else:
            # Normal and low priority jobs go to the end
            await self.redis_client.rpush(RedisKeyManager.JOB_QUEUE, job_id)
    
    async def process_job_queue(self, max_concurrent_jobs: int = 5) -> None:
        """
        Process jobs from the queue with concurrency control.
        
        Args:
            max_concurrent_jobs: Maximum number of concurrent jobs to process
        """
        try:
            # Check current processing jobs
            processing_key = "queue:processing"
            current_processing = await self.redis_client.scard(processing_key)
            
            if current_processing >= max_concurrent_jobs:
                logger.info(f"Max concurrent jobs ({max_concurrent_jobs}) reached")
                return
            
            # Get next job from queue
            result = await self.redis_client.blpop(RedisKeyManager.JOB_QUEUE, timeout=1)
            
            if result:
                queue_name, job_id = result
                
                # Mark job as processing
                await self.redis_client.sadd(processing_key, job_id)
                
                # Update job status
                await self.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    current_stage="initializing"
                )
                
                # Trigger video generation pipeline
                await self._trigger_video_generation_pipeline(job_id)
                
                logger.info(f"Started processing job {job_id}")
                
        except Exception as e:
            logger.error(f"Failed to process job queue: {e}", exc_info=True)
    
    async def _trigger_video_generation_pipeline(self, job_id: str) -> None:
        """
        Trigger the multi-agent video generation pipeline for a job.
        
        Args:
            job_id: Job ID to process
        """
        try:
            # Get job details
            job = await self.get_job_status(job_id)
            if not job:
                logger.error(f"Job {job_id} not found for pipeline trigger")
                return
            
            # Create pipeline message
            pipeline_message = {
                "job_id": job_id,
                "user_id": job.user_id,
                "configuration": job.configuration.dict(),
                "priority": job.priority.value,
                "created_at": job.created_at.isoformat()
            }
            
            # Send to pipeline queue (this would integrate with your existing pipeline)
            pipeline_queue_key = "pipeline:video_generation"
            await redis_json_set(
                self.redis_client, 
                f"{pipeline_queue_key}:{job_id}", 
                pipeline_message,
                ex=3600  # Expire after 1 hour if not processed
            )
            
            # Notify pipeline workers (using pub/sub)
            await self.redis_client.publish("pipeline:new_job", job_id)
            
            logger.info(f"Triggered video generation pipeline for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger pipeline for job {job_id}: {e}", exc_info=True)
            
            # Mark job as failed
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_info={
                    "error_code": "PIPELINE_TRIGGER_FAILED",
                    "error_message": f"Failed to trigger video generation pipeline: {str(e)}"
                }
            )
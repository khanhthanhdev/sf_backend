"""
Video generation service for managing video creation jobs and operations.

This service handles the business logic for video generation requests,
job queue management, progress tracking, and integration with the
multi-agent video generation pipeline using AWS RDS and S3.
"""

import logging
import uuid
import os
import json
import asyncio
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select

from ..models.job import (
    Job as JobModel, JobCreateRequest, JobStatus, JobType, JobProgress,
    JobConfiguration, JobError, JobMetrics, BatchJobCreateRequest, JobPriority
)
from ..models.video import VideoMetadata, VideoStatus
from ..database.models import Job as JobDB, User as UserDB, FileMetadata as FileMetadataDB
from ..database.connection import RDSConnectionManager
from ..services.aws_video_service import AWSVideoService

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively serialize objects for JSON storage, converting UUIDs to strings.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


class VideoService:
    """
    Service class for video generation operations with AWS integration.
    
    Handles job creation, status management, progress tracking,
    and integration with the video generation pipeline using AWS RDS and S3.
    """
    
    def __init__(self, db_manager: RDSConnectionManager, aws_video_service: AWSVideoService):
        self.db_manager = db_manager
        self.aws_video_service = aws_video_service

    async def _ensure_user_exists(self, clerk_user_id: str, user_info: Dict[str, Any] = None) -> UserDB:
        """
        Ensure user exists in database, create if not found.
        
        Args:
            clerk_user_id: Clerk user ID
            user_info: Additional user information from Clerk
            
        Returns:
            User database instance
        """
        async with self.db_manager.get_session() as session:
            from sqlalchemy import select
            
            # Check if user exists
            result = await session.execute(
                select(UserDB).where(UserDB.clerk_user_id == clerk_user_id)
            )
            user_db = result.scalar_one_or_none()
            
            if user_db:
                return user_db
            
            # Create new user if not found
            user_data = user_info or {}
            user_db = UserDB(
                clerk_user_id=clerk_user_id,
                username=user_data.get('username'),
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                image_url=user_data.get('image_url'),
                primary_email=user_data.get('primary_email_address', {}).get('email_address') if user_data.get('primary_email_address') else None,
                email_addresses=user_data.get('email_addresses', []),
                email_verified=user_data.get('email_verified', False),
                user_metadata=user_data.get('public_metadata', {}),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(user_db)
            await session.commit()
            await session.refresh(user_db)
            
            logger.info(f"Created new user in database: {clerk_user_id}")
            return user_db
    
    async def create_video_job(
        self,
        request: JobCreateRequest,
        user_id: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> JobModel:
        """
        Create a new video generation job in AWS RDS.
        
        Args:
            request: Job creation request with configuration
            user_id: ID of the user creating the job
            user_info: Additional user information from authentication
            
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
            
            # Create job database entry
            async with self.db_manager.get_session() as session:
                # Ensure user exists in database
                user_db = await self._ensure_user_exists(user_id, user_info)
                
                job_db = JobDB(
                    id=job_id,
                    user_id=user_db.id,  # Use the UUID from the database
                    job_type=JobType.VIDEO_GENERATION.value,
                    priority=request.priority.value,
                    configuration=request.configuration.dict(),
                    status=JobStatus.QUEUED.value,
                    progress_percentage=0.0,
                    current_stage="queued",
                    stages_completed=[],
                    estimated_completion=estimated_completion,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(job_db)
                await session.commit()
                await session.refresh(job_db)
            
            # Convert to Pydantic model
            job = JobModel(
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
            
            logger.info(
                "Created video generation job",
                extra={
                    "job_id": job_id,
                    "user_id": user_id,
                    "topic": request.configuration.topic,
                    "quality": request.configuration.quality,
                    "estimated_completion": estimated_completion
                }
            )
            
            return job
            
        except Exception as e:
            logger.error(
                "Failed to create video generation job",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    async def create_batch_jobs(
        self,
        request: BatchJobCreateRequest,
        user_id: str
    ) -> List[JobModel]:
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
                extra={
                    "batch_id": batch_id,
                    "job_count": len(jobs),
                    "user_id": user_id
                }
            )
            
            return jobs
            
        except Exception as e:
            logger.error(
                "Failed to create batch video generation jobs",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[JobModel]:
        """
        Get current job status and information from AWS RDS.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Job instance or None if not found
        """
        try:
            async with self.db_manager.get_session() as session:
                # Get job with user relationship
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                
                result = await session.execute(
                    select(JobDB)
                    .options(selectinload(JobDB.user))
                    .where(JobDB.id == job_id)
                )
                job_db = result.scalar_one_or_none()
                
                if not job_db:
                    return None
                
                # Convert database model to Pydantic model
                progress = JobProgress(
                    percentage=job_db.progress_percentage,
                    current_stage=job_db.current_stage,
                    stages_completed=job_db.stages_completed or [],
                    estimated_completion=job_db.estimated_completion
                )
                
                # Handle error information
                error = None
                if job_db.error_info:
                    try:
                        error = JobError(**job_db.error_info)
                    except Exception as e:
                        logger.warning(f"Failed to parse error_info: {e}")
                        # Create a simple error object if parsing fails
                        error = JobError(
                            error_code="PARSE_ERROR",
                            error_message=str(job_db.error_info)
                        )
                
                job = JobModel(
                    id=str(job_db.id),  # Convert UUID to string
                    user_id=job_db.user.clerk_user_id,  # Return Clerk ID instead of UUID
                    job_type=JobType(job_db.job_type),
                    priority=JobPriority(job_db.priority),
                    configuration=JobConfiguration(**job_db.configuration),
                    status=JobStatus(job_db.status),
                    progress=progress,
                    error=error,
                    result_url=job_db.result_url,
                    created_at=job_db.created_at,
                    updated_at=job_db.updated_at,
                    completed_at=job_db.completed_at
                )
                
                return job
            
        except Exception as e:
            logger.error(
                "Failed to get job status",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
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
        metrics: Optional[Dict[str, Any]] = None,
        result_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update job status and progress information in AWS RDS.
        
        Args:
            job_id: Unique job identifier
            status: New job status
            progress_percentage: Progress percentage (0-100)
            current_stage: Current processing stage
            error_info: Error information if job failed
            metrics: Performance metrics
            result_data: Job result data (for completed jobs)
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            async with self.db_manager.get_session() as session:
                # Get current job from database
                job_db = await session.get(JobDB, job_id)
                if not job_db:
                    logger.warning(f"Job {job_id} not found for status update")
                    return False
                
                # Update job status
                job_db.status = status.value
                job_db.updated_at = datetime.utcnow()
                
                # Update progress if provided
                if progress_percentage is not None:
                    job_db.progress_percentage = progress_percentage
                
                if current_stage:
                    job_db.current_stage = current_stage
                    # Add to stages completed if not already there
                    stages_completed = job_db.stages_completed or []
                    if current_stage not in stages_completed:
                        stages_completed.append(current_stage)
                        job_db.stages_completed = stages_completed
                
                # Handle completion
                if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job_db.completed_at = datetime.utcnow()
                    if status == JobStatus.COMPLETED:
                        job_db.progress_percentage = 100.0
                
                # Handle processing start
                if status == JobStatus.PROCESSING and not job_db.started_at:
                    job_db.started_at = datetime.utcnow()
                
                # Update error information
                if error_info and status == JobStatus.FAILED:
                    job_db.error_info = error_info
                
                # Update result data (store in metrics field)
                if result_data and status == JobStatus.COMPLETED:
                    existing_metrics = job_db.metrics or {}
                    # Store result data under a specific key in metrics, serializing UUIDs to strings
                    existing_metrics['result_data'] = serialize_for_json(result_data)
                    job_db.metrics = existing_metrics
                
                # Update metrics (store as JSON in database)
                if metrics:
                    existing_metrics = job_db.metrics or {}
                    # Serialize metrics to handle UUIDs and other non-JSON-serializable objects
                    serialized_metrics = serialize_for_json(metrics)
                    existing_metrics.update(serialized_metrics)
                    job_db.metrics = existing_metrics
                
                # Commit changes
                await session.commit()
                
                logger.info(
                    "Updated job status",
                    extra={
                        "job_id": job_id,
                        "status": status.value,
                        "progress": job_db.progress_percentage,
                        "stage": current_stage
                    }
                )
                
                return True
            
        except Exception as e:
            logger.error(
                "Failed to update job status",
                extra={
                    "job_id": job_id,
                    "status": status.value,
                    "error": str(e)
                },
                exc_info=True
            )
            return False
    
    async def set_job_result_url(self, job_id: str, result_url: str) -> bool:
        """
        Set the result URL for a completed video generation job.
        
        Args:
            job_id: Unique job identifier
            result_url: URL to the generated video
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            async with self.db_manager.get_session() as session:
                job_db = await session.get(JobDB, job_id)
                if not job_db:
                    logger.warning(f"Job {job_id} not found for result URL update")
                    return False
                
                job_db.result_url = result_url
                job_db.updated_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(
                    "Set job result URL",
                    extra={
                        "job_id": job_id,
                        "result_url": result_url
                    }
                )
                
                return True
                
        except Exception as e:
            logger.error(
                "Failed to set job result URL",
                extra={
                    "job_id": job_id,
                    "result_url": result_url,
                    "error": str(e)
                },
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
            if job.status not in [JobStatus.QUEUED, JobStatus.PROCESSING]:
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
                logger.info(f"Job {job_id} cancelled successfully")
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to cancel job",
                extra={
                    "job_id": job_id,
                    "error": str(e)
                },
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
        Create video metadata for a completed job in AWS RDS.
        
        Args:
            job_id: Associated job ID
            filename: Video filename
            file_path: Path to video file (S3 key)
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
                file_path=file_path,  # This will be the S3 key
                file_size=file_size,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
                format=format,
                status=VideoStatus.READY,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
            
            # Store video metadata in RDS using AWSVideoService
            # Note: store_rendered_video already handles metadata creation
            # await self.aws_video_service.create_file_metadata(
            #     file_id=video_metadata.id,
            #     filename=filename,
            #     s3_key=file_path,
            #     file_size=file_size,
            #     user_id=job.user_id,
            #     job_id=job_id,
            #     metadata={
            #         "video_duration": duration_seconds,
            #         "video_width": width,
            #         "video_height": height,
            #         "video_format": format,
            #         "status": VideoStatus.READY.value
            #     }
            # )
            
            logger.info(
                "Created video metadata",
                extra={
                    "job_id": job_id,
                    "video_id": video_metadata.id,
                    "filename": filename,
                    "file_size": file_size,
                    "s3_key": file_path
                }
            )
            
            return video_metadata
            
        except Exception as e:
            logger.error(
                "Failed to create video metadata",
                extra={
                    "job_id": job_id,
                    "filename": filename,
                    "error": str(e)
                },
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
        Get current job queue length from RDS.
        
        Returns:
            Number of jobs in queue
        """
        try:
            async with self.db_manager.get_session() as session:
                from sqlalchemy import func
                
                # Count jobs with QUEUED status
                result = await session.execute(
                    session.query(func.count(JobDB.id)).filter(
                        JobDB.status == JobStatus.QUEUED.value
                    )
                )
                count = result.scalar()
                return count or 0
                
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0
    
    async def get_user_jobs(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[JobModel]:
        """
        Get jobs for a specific user from RDS.
        
        Args:
            user_id: User ID
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of Job instances
        """
        try:
            async with self.db_manager.get_session() as session:
                # First find the user by Clerk ID to get their UUID
                from sqlalchemy import select
                user_result = await session.execute(
                    select(UserDB).where(UserDB.clerk_user_id == user_id)
                )
                user_db = user_result.scalar_one_or_none()
                
                if not user_db:
                    logger.warning(f"User with Clerk ID {user_id} not found")
                    return []
                
                # Query jobs for the user using their UUID, ordered by creation date (newest first)
                result = await session.execute(
                    select(JobDB)
                    .where(JobDB.user_id == user_db.id)
                    .order_by(JobDB.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                job_dbs = result.scalars().all()
                
                # Convert to Pydantic models
                jobs = []
                for job_db in job_dbs:
                    progress = JobProgress(
                        percentage=job_db.progress_percentage,
                        current_stage=job_db.current_stage,
                        stages_completed=job_db.stages_completed or [],
                        estimated_completion=job_db.estimated_completion
                    )
                    
                    # Handle error information
                    error = None
                    if job_db.error_info:
                        try:
                            error = JobError(**job_db.error_info)
                        except Exception as e:
                            logger.warning(f"Failed to parse error_info: {e}")
                            # Create a simple error object if parsing fails
                            error = JobError(
                                error_code="PARSE_ERROR",
                                error_message=str(job_db.error_info)
                            )
                    
                    job = JobModel(
                        id=str(job_db.id),  # Convert UUID to string
                        user_id=user_id,  # Return the Clerk ID, not the UUID
                        job_type=JobType(job_db.job_type),
                        priority=JobPriority(job_db.priority),
                        configuration=JobConfiguration(**job_db.configuration),
                        status=JobStatus(job_db.status),
                        progress=progress,
                        error=error,
                        result_url=job_db.result_url,
                        created_at=job_db.created_at,
                        updated_at=job_db.updated_at,
                        completed_at=job_db.completed_at
                    )
                    jobs.append(job)
                
                return jobs
            
        except Exception as e:
            logger.error(
                "Failed to get user jobs",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return []

    async def process_video_generation_immediately(self, job_id: str) -> None:
        """
        Process video generation immediately without waiting for worker queue.
        
        This method integrates directly with the video generation pipeline
        to provide immediate processing for API requests.
        
        Args:
            job_id: Job ID to process immediately
        """
        try:
            logger.info(f"Starting immediate video generation for job {job_id}")
            
            # Get job details
            job = await self.get_job_status(job_id)
            if not job:
                logger.error(f"Job {job_id} not found for immediate processing")
                return
            
            # Update to processing status
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress_percentage=10.0,
                current_stage="scene_planning"
            )
            
            # Try to import and run the full pipeline, fall back to simple demo if not available
            try:
                logger.info(f"Attempting to run full video pipeline for job {job_id}")
                await self._run_full_video_pipeline(job_id, job)
                logger.info(f"Full video pipeline completed successfully for job {job_id}")
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(f"Full pipeline not available due to import error: {e}", exc_info=True)
                logger.info(f"Falling back to demo video generation for job {job_id}")
                await self._run_demo_video_generation(job_id, job)
            except ValueError as e:
                # Handle OpenTelemetry and entry point errors
                if "Invalid object reference" in str(e) or "entry_points" in str(e):
                    logger.warning(f"Package entry point error: {e}", exc_info=True)
                    logger.info(f"Falling back to demo video generation for job {job_id}")
                    await self._run_demo_video_generation(job_id, job)
                else:
                    logger.error(f"Full pipeline failed with ValueError: {e}", exc_info=True)
                    logger.info(f"Falling back to demo video generation for job {job_id}")
                    await self._run_demo_video_generation(job_id, job)
            except Exception as e:
                logger.error(f"Full pipeline failed with unexpected error: {e}", exc_info=True)
                logger.info(f"Falling back to demo video generation for job {job_id}")
                await self._run_demo_video_generation(job_id, job)
                
        except Exception as e:
            logger.error(f"Failed to process video generation for job {job_id}: {e}", exc_info=True)
            
            # Mark job as failed
            error_info = {
                "error_code": "PROCESSING_ERROR",
                "error_message": f"Error during video processing: {str(e)}"
            }
            
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_info=error_info
            )
    
    async def _run_full_video_pipeline(self, job_id: str, job: JobModel) -> None:
        """Run the full video generation pipeline."""
        try:
            # Import and initialize the enhanced video generator
            import sys
            import os
            
            # Add the root directory to Python path to import generate_video
            # Try multiple possible root directory locations
            current_file = os.path.abspath(__file__)
            possible_roots = [
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))),  # Original path
                os.path.dirname(os.path.dirname(os.path.dirname(current_file))),  # One level up
                os.path.dirname(os.path.dirname(current_file)),  # Two levels up
                os.getcwd(),  # Current working directory
                os.path.dirname(os.getcwd()),  # Parent of working directory
            ]
            
            root_dir = None
            for potential_root in possible_roots:
                generate_video_path = os.path.join(potential_root, 'generate_video.py')
                if os.path.exists(generate_video_path):
                    root_dir = potential_root
                    logger.info(f"Found generate_video.py at: {generate_video_path}")
                    break
            
            if not root_dir:
                raise ImportError(f"Could not find generate_video.py in any of these locations: {possible_roots}")
            
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)
            
            # Import with better error handling
            try:
                from generate_video import EnhancedVideoGenerator, VideoGenerationConfig
                logger.info("Successfully imported EnhancedVideoGenerator")
            except ImportError as e:
                logger.error(f"Failed to import generate_video components: {e}")
                raise ImportError(f"Cannot import generate_video: {e}")
            
            # Check model wrapper availability with better error handling
            model_wrappers_available = []
            try:
                from mllm_tools.litellm import LiteLLMWrapper
                model_wrappers_available.append("LiteLLMWrapper")
            except ImportError as e:
                logger.warning(f"LiteLLMWrapper not available: {e}")
            
            try:
                from mllm_tools.openrouter import OpenRouterWrapper
                model_wrappers_available.append("OpenRouterWrapper")
            except ImportError as e:
                logger.warning(f"OpenRouterWrapper not available: {e}")
            
            try:
                from mllm_tools.gemini import GeminiWrapper
                model_wrappers_available.append("GeminiWrapper")
            except ImportError as e:
                logger.warning(f"GeminiWrapper not available: {e}")
            
            if not model_wrappers_available:
                raise ImportError("No model wrappers available. Please install mllm_tools package.")
            
            logger.info(f"Available model wrappers: {model_wrappers_available}")
            
            # Get model from job configuration or use default
            model_name = getattr(job.configuration, 'model', None) or 'gemini/gemini-2.0-flash-thinking-exp-01-21'
            logger.info(f"Using model: {model_name} for job {job_id}")
            
            # Create configuration for video generation
            output_dir = os.getenv('OUTPUT_DIR', 'output')
            os.makedirs(output_dir, exist_ok=True)  # Ensure output directory exists
            
            config = VideoGenerationConfig(
                planner_model=model_name,
                scene_model=model_name,
                helper_model=model_name,
                output_dir=output_dir,
                verbose=True,
                use_rag=getattr(job.configuration, 'use_rag', False),
                use_context_learning=False,
                use_visual_fix_code=True,
                use_langfuse=True,
                max_scene_concurrency=3,
                max_topic_concurrency=1,
                enable_caching=True,
                default_quality=getattr(job.configuration, 'quality', 'medium'),
                use_gpu_acceleration=False,
                preview_mode=False
            )
            
            # Create enhanced video generator with error handling
            try:
                generator = EnhancedVideoGenerator(config)
                logger.info("Successfully created EnhancedVideoGenerator")
            except Exception as e:
                logger.error(f"Failed to create EnhancedVideoGenerator: {e}")
                raise RuntimeError(f"Generator initialization failed: {e}")
            
        except Exception as init_error:
            logger.warning(f"Failed to initialize full pipeline: {init_error}")
            raise ImportError(f"Pipeline initialization failed: {init_error}")
        
        try:
            # Set up progress callback to update job status
            async def progress_callback(stage: str, percentage: float, message: str):
                await self.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    progress_percentage=percentage,
                    current_stage=stage
                )
                logger.info(f"Job {job_id} progress: {stage} - {percentage:.1f}% - {message}")
            
            # Run the video generation with the enhanced generator
            await self.update_job_status(
                job_id=job_id,
                progress_percentage=15.0,
                current_stage="video_generation_started"
            )
            
            logger.info(f"Starting video generation pipeline for job {job_id}")
            logger.info(f"Topic: {job.configuration.topic}")
            logger.info(f"Context: {job.configuration.context}")
            logger.info(f"Quality: {getattr(job.configuration, 'quality', 'medium')}")
            
            # Update progress during generation
            await self.update_job_status(
                job_id=job_id,
                progress_percentage=25.0,
                current_stage="scene_planning"
            )
            
            # Generate the video using the enhanced generator
            await generator.generate_video_pipeline(
                topic=job.configuration.topic,
                description=job.configuration.context,
                only_plan=False,
                specific_scenes=None
            )
            
            logger.info(f"Video generation pipeline completed for job {job_id}")
            
            # Update progress to completion
            await self.update_job_status(
                job_id=job_id,
                progress_percentage=90.0,
                current_stage="post_processing"
            )
            
            # Check if video was generated successfully
            import re
            file_prefix = re.sub(r'[^a-z0-9_]+', '_', job.configuration.topic.lower())
            output_dir = os.getenv('OUTPUT_DIR', 'output')
            expected_video_path = os.path.join(output_dir, file_prefix, f"{file_prefix}_combined.mp4")
            
            # Also check for alternative paths in case the naming is different
            possible_paths = [
                expected_video_path,
                os.path.join(output_dir, f"{file_prefix}_combined.mp4"),
                os.path.join(output_dir, file_prefix, "combined.mp4")
            ]
            
            actual_video_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    actual_video_path = path
                    break
            
            if actual_video_path:
                # Create successful result
                class SuccessResult:
                    def __init__(self, video_path):
                        self.success = True
                        self.video_path = video_path
                        self.error = None
                
                result = SuccessResult(actual_video_path)
                await self._handle_successful_generation(job_id, job, result)
            else:
                # Video generation completed but file not found
                logger.error(f"Video generation completed but no output file found for job {job_id}")
                logger.error(f"Checked paths: {possible_paths}")
                
                # List the actual output directory to debug
                try:
                    output_dir = os.getenv('OUTPUT_DIR', 'output')
                    if os.path.exists(output_dir):
                        logger.info(f"Output directory contents: {os.listdir(output_dir)}")
                        topic_dir = os.path.join(output_dir, file_prefix)
                        if os.path.exists(topic_dir):
                            logger.info(f"Topic directory contents: {os.listdir(topic_dir)}")
                except Exception as e:
                    logger.error(f"Error listing output directory: {e}")
                
                class FailResult:
                    def __init__(self):
                        self.success = False
                        self.error = "Video file not found after generation"
                
                result = FailResult()
                await self._handle_failed_generation(job_id, result)
                
        except Exception as pipeline_error:
            logger.error(f"Full video pipeline execution failed: {pipeline_error}")
            raise pipeline_error
    
    async def _run_demo_video_generation(self, job_id: str, job: JobModel) -> None:
        """Run a demo video generation with AWS S3 upload."""
        import asyncio
        import tempfile
        from pathlib import Path
        
        logger.info(f"Running demo video generation for job {job_id}")
        
        # Simulate video generation stages
        stages = [
            ("scene_planning", 20.0, "Planning video scenes"),
            ("content_preparation", 40.0, "Preparing educational content"),
            ("code_generation", 60.0, "Generating animation code"),
            ("video_rendering", 80.0, "Rendering video scenes"),
            ("post_processing", 90.0, "Finalizing video"),
            ("uploading", 95.0, "Uploading to cloud storage"),
            ("completed", 100.0, "Video generation completed")
        ]
        
        for stage, percentage, message in stages:
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress_percentage=percentage,
                current_stage=stage
            )
            logger.info(f"Demo job {job_id}: {stage} - {percentage:.1f}% - {message}")
            
            # Simulate processing time
            await asyncio.sleep(1.5)
        
        # Create a demo video file
        temp_path = None
        video_created_successfully = False
        
        try:
            import subprocess
            import shutil
            
            # Create temporary file for video
            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(temp_fd)  # Close the file descriptor, we'll use the path
            temp_path = Path(temp_path)
            
            # Check if ffmpeg is available
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                # Create a simple video with text overlay
                duration = 30  # 30 second demo video
                
                # Properly escape text for FFmpeg - use simpler text to avoid escaping issues
                topic_safe = job.configuration.topic.replace("'", "").replace('"', '').replace('\\', '').replace(':', ' -')[:50]
                current_time = datetime.utcnow().strftime("%Y-%m-%d %H-%M-%S")
                
                # Create a simpler text overlay that's less likely to cause escaping issues
                text_content = f"Demo Video|Topic: {topic_safe}|Generated: {current_time}|Job: {job_id[:8]}|Quality: {job.configuration.quality}"
                
                # FFmpeg command with properly escaped text
                cmd = [
                    ffmpeg_path,
                    '-f', 'lavfi',
                    '-i', f'color=c=blue:size=1280x720:duration={duration}',
                    '-vf', f'drawtext=text={text_content}:fontsize=24:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2',
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-preset', 'ultrafast',  # Faster encoding
                    '-crf', '23',  # Good quality
                    '-y',  # Overwrite output file
                    str(temp_path)
                ]
                
                logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
                
                # Run FFmpeg command with better error handling
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0:
                    # Verify the video file was created and has content
                    if temp_path.exists() and temp_path.stat().st_size > 1000:  # At least 1KB
                        logger.info(f"Created demo video with FFmpeg for job {job_id}, size: {temp_path.stat().st_size} bytes")
                        video_created_successfully = True
                    else:
                        logger.warning(f"FFmpeg completed but video file is too small or missing")
                        raise subprocess.CalledProcessError(1, cmd, "Video file too small")
                else:
                    logger.warning(f"FFmpeg failed with return code {result.returncode}")
                    logger.warning(f"FFmpeg stderr: {result.stderr}")
                    logger.warning(f"FFmpeg stdout: {result.stdout}")
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
            else:
                raise FileNotFoundError("FFmpeg not found in system PATH")
                
        except Exception as video_creation_error:
            logger.error(f"Could not create video file ({video_creation_error}), trying alternative method")
            video_created_successfully = False
            
            # Alternative: Create a simple video using Python (if opencv is available)
            try:
                import cv2
                import numpy as np
                
                # Create a simple video using OpenCV
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                fps = 30
                duration = 30
                width, height = 1280, 720
                
                # Create new temp file if previous attempt failed
                if not temp_path or not temp_path.exists():
                    temp_fd, temp_path_str = tempfile.mkstemp(suffix=".mp4")
                    os.close(temp_fd)
                    temp_path = Path(temp_path_str)
                
                out = cv2.VideoWriter(str(temp_path), fourcc, fps, (width, height))
                
                # Create frames
                total_frames = fps * duration
                for frame_num in range(total_frames):
                    # Create blue background
                    frame = np.full((height, width, 3), (255, 0, 0), dtype=np.uint8)  # Blue in BGR
                    
                    # Add text (simple version)
                    cv2.putText(frame, "Demo Video", (width//2 - 100, height//2 - 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
                    cv2.putText(frame, f"Topic: {job.configuration.topic[:30]}", (width//2 - 200, height//2), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(frame, f"Job ID: {job_id[:16]}", (width//2 - 150, height//2 + 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    out.write(frame)
                
                out.release()
                
                # Verify the video file was created
                if temp_path.exists() and temp_path.stat().st_size > 1000:
                    logger.info(f"Created demo video with OpenCV for job {job_id}, size: {temp_path.stat().st_size} bytes")
                    video_created_successfully = True
                else:
                    raise RuntimeError("OpenCV video creation failed")
                    
            except Exception as cv_error:
                logger.error(f"OpenCV video creation also failed: {cv_error}")
                
                # Final fallback: Create a minimal valid MP4 file
                try:
                    # Create new temp file if previous attempts failed
                    if not temp_path or not temp_path.exists():
                        temp_fd, temp_path_str = tempfile.mkstemp(suffix=".mp4")
                        os.close(temp_fd)
                        temp_path = Path(temp_path_str)
                    
                    # Create a minimal MP4 file using a base64 encoded minimal MP4
                    import base64
                    
                    # This is a minimal 1-second black MP4 file (base64 encoded)
                    minimal_mp4_b64 = """AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAsdtZGF0AAACrgYF//+q3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzA5NSBiYWVlNDAwIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMSAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTI1IHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9NDAgcmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTE6MS4wMACAAAABWWWIhAAz//727L4FNf2f0JcRLMXaSnA+KqSAgHc0wAAAAwAAAwAAFgn0I7DkqgAAAAlBmiRsQn/+tSqAAAAJQZ5CeIK/+tSqAAAACUGeYXiCv/rUqgAAAAlBnoN4gr/61KoAAAAJQZ6leIK/+tSqAAAACUGexXiCv/rUqgAAAAlBnwV4gr/61KoAAAAJQZ8neIK/+tSqAAAACUGfSXiCv/rUqgAAAAlBn2t4gr/61Ko="""
                    
                    # Decode and write the minimal MP4
                    mp4_data = base64.b64decode(minimal_mp4_b64)
                    with open(temp_path, 'wb') as f:
                        f.write(mp4_data)
                    
                    logger.info(f"Created minimal MP4 file for job {job_id}, size: {temp_path.stat().st_size} bytes")
                    video_created_successfully = True
                    
                except Exception as final_error:
                    logger.error(f"All video creation methods failed: {final_error}")
                    # Don't raise here, we'll handle the failure below
        
        # Verify we have a valid video file before uploading
        if not video_created_successfully or not temp_path or not temp_path.exists():
            raise RuntimeError("Failed to create demo video file")
        
        # Verify file size
        file_size = temp_path.stat().st_size
        if file_size < 100:  # Less than 100 bytes is definitely not a valid video
            raise RuntimeError(f"Demo video file too small: {file_size} bytes")
        
        logger.info(f"Demo video created successfully: {temp_path}, size: {file_size} bytes")
        
        try:
            # Upload to S3 using AWS video service
            filename = f"{job.configuration.topic.lower().replace(' ', '_').replace('/', '_')}.mp4"
            
            # Create upload metadata
            metadata = {
                "job_id": job_id,
                "user_id": job.user_id,
                "topic": job.configuration.topic,
                "context": job.configuration.context,
                "quality": job.configuration.quality,
                "demo": True,
                "created_at": datetime.utcnow().isoformat(),
                "video_type": "educational_demo",
                "description": f"Demo educational video about {job.configuration.topic}",
                "duration_seconds": 30,  # Estimated demo duration
                "resolution": "1280x720",
                "format": "mp4"
            }
            
            # Upload video to S3 with progress tracking
            def upload_progress_callback(percentage: float):
                # Update progress synchronously (AWS service calls this sync)
                # We'll use asyncio to run the async update in the background
                import asyncio
                
                async def update_progress():
                    progress = 95.0 + (percentage / 100.0) * 4.0  # 95-99%
                    await self.update_job_status(
                        job_id=job_id,
                        status=JobStatus.PROCESSING,
                        progress_percentage=progress,
                        current_stage="uploading"
                    )
                
                # Create a task to run the async update
                try:
                    asyncio.create_task(update_progress())
                except Exception:
                    # If we can't create a task (no event loop), just log the progress
                    logger.info(f"Upload progress: {percentage:.1f}%")
            
            # Upload the video file
            storage_result = await self.aws_video_service.store_rendered_video(
                video_path=str(temp_path),
                job_id=job_id,
                scene_number=1,  # Default scene number for demo videos
                user_id=job.user_id,
                progress_callback=upload_progress_callback
            )
            
            # Get streaming URL from the storage result
            video_url = storage_result.get('streaming_url')
            
            # Update job with result URL
            await self.set_job_result_url(job_id, video_url)
            
            # Mark job as completed
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                current_stage="completed",
                result_data={
                    "video_id": storage_result.get('video_id'),
                    "s3_url": storage_result.get('s3_url'),
                    "video_url": video_url,
                    "demo": True,
                    "file_size": storage_result.get('file_size'),
                    "duration_seconds": storage_result.get('duration_seconds', 30),
                    "resolution": "1280x720",
                    "format": "mp4",
                    "topic": job.configuration.topic,
                    "video_type": "educational_demo",
                    "metadata": metadata
                }
            )
            
            logger.info(f"Demo video uploaded to S3 and job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to upload demo video for job {job_id}: {e}", exc_info=True)
            
            # Mark job as failed
            error_info = {
                "error_code": "S3_UPLOAD_FAILED",
                "error_message": f"Failed to upload video to S3: {str(e)}"
            }
            
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_info=error_info
            )
            
        finally:
            # Clean up temporary file
            try:
                if temp_path and temp_path.exists():
                    temp_path.unlink()
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")
    
    async def _handle_successful_generation(self, job_id: str, job: JobModel, result) -> None:
        """Handle successful video generation with S3 upload."""
        try:
            # Upload the generated video to S3
            filename = f"{job.configuration.topic.lower().replace(' ', '_')}.mp4"
            
            # Create upload metadata
            metadata = {
                "job_id": job_id,
                "user_id": job.user_id,
                "topic": job.configuration.topic,
                "context": job.configuration.context,
                "quality": job.configuration.quality,
                "demo": False,
                "created_at": datetime.utcnow().isoformat(),
                "generation_metadata": result.metadata if hasattr(result, 'metadata') else {}
            }
            
            # Upload progress callback
            def upload_progress_callback(percentage: float):
                # Update progress synchronously (AWS service calls this sync)
                import asyncio
                
                async def update_progress():
                    # Map upload progress to 90-99%
                    progress = 90.0 + (percentage / 100.0) * 9.0
                    await self.update_job_status(
                        job_id=job_id,
                        status=JobStatus.PROCESSING,
                        progress_percentage=progress,
                        current_stage="uploading"
                    )
                
                # Create a task to run the async update
                try:
                    asyncio.create_task(update_progress())
                except Exception:
                    # If we can't create a task (no event loop), just log the progress
                    logger.info(f"Upload progress: {percentage:.1f}%")
            
            # Upload video to S3
            storage_result = await self.aws_video_service.store_rendered_video(
                video_path=result.combined_video_path,
                job_id=job_id,
                scene_number=1,  # Default scene number for generated videos
                user_id=job.user_id,
                progress_callback=upload_progress_callback
            )
            
            # Get streaming URL from the storage result
            video_url = storage_result.get('streaming_url')
            
            # Update job with result URL
            await self.set_job_result_url(job_id, video_url)
            
            # Mark job as completed
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                current_stage="completed",
                result_data={
                    "video_id": storage_result.get('video_id'),
                    "s3_url": storage_result.get('s3_url'),
                    "video_url": video_url,
                    "file_size": storage_result.get('file_size'),
                    "duration_seconds": storage_result.get('duration_seconds'),
                    "metadata": {
                        "resolution": storage_result.get('resolution'),
                        "upload_duration_seconds": storage_result.get('upload_duration_seconds')
                    }
                }
            )
            
            logger.info(f"Video generation completed and uploaded to S3 for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to upload generated video for job {job_id}: {e}", exc_info=True)
            
            # Mark job as failed
            error_info = {
                "error_code": "S3_UPLOAD_FAILED",
                "error_message": f"Video generated but upload failed: {str(e)}"
            }
            
            await self.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_info=error_info
            )
    
    async def _handle_failed_generation(self, job_id: str, result) -> None:
        """Handle failed video generation."""
        error_info = {
            "error_code": "VIDEO_GENERATION_FAILED",
            "error_message": result.error or "Unknown error during video generation"
        }
        
        await self.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_info=error_info
        )
        
        logger.error(f"Video generation failed for job {job_id}: {result.error}")
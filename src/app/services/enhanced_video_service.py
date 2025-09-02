"""
Enhanced video service that integrates FastAPI backend with the core video generation pipeline.

This service bridges the API layer with the sophisticated video generation workflow
from generate_video.py and src/core/ components, providing end-to-end integration.
"""

import logging
import asyncio
import os
import tempfile
import shutil
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

# Import the core video generation components
from ...core.video_orchestrator import VideoGenerationOrchestrator, VideoGenerationResult, VideoGenerationStatus
from ...core.storage_manager import StorageManager
from ..models.job import Job as JobModel, JobCreateRequest, JobStatus, JobConfiguration
from ..services.video_service import VideoService
from ..services.aws_video_service import AWSVideoService

# Import the enhanced video generator
import sys
import importlib.util

# Add the project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from generate_video import (
        VideoGenerationConfig, 
        EnhancedVideoGenerator,
        ComponentFactory
    )
except ImportError as e:
    logging.error(f"Failed to import video generation components: {e}")
    # Fallback - we'll create a minimal config class
    from dataclasses import dataclass
    
    @dataclass
    class VideoGenerationConfig:
        planner_model: str
        scene_model: Optional[str] = None
        helper_model: Optional[str] = None
        output_dir: str = "output"
        use_rag: bool = False
        use_context_learning: bool = False
        max_scene_concurrency: int = 3
        enable_caching: bool = True
        default_quality: str = "medium"
        use_gpu_acceleration: bool = False
        max_concurrent_renders: int = 2
    
    EnhancedVideoGenerator = None

logger = logging.getLogger(__name__)


class PipelineProgressTracker:
    """Tracks progress from the video generation pipeline and updates job status."""
    
    def __init__(self, job_id: str, video_service: VideoService):
        self.job_id = job_id
        self.video_service = video_service
        self.stage_mapping = {
            "initializing": {"percentage": 5, "stage": "initializing"},
            "planning": {"percentage": 15, "stage": "planning"},
            "scenario_creation": {"percentage": 30, "stage": "generating_scenarios"},
            "code_generation": {"percentage": 50, "stage": "generating_code"},
            "rendering": {"percentage": 80, "stage": "rendering_video"},
            "combining": {"percentage": 90, "stage": "combining_scenes"},
            "storage": {"percentage": 95, "stage": "uploading"},
            "completed": {"percentage": 100, "stage": "completed"}
        }
    
    async def update_progress(self, stage: str, percentage: Optional[float] = None, message: str = "") -> None:
        """Update job progress based on pipeline stage."""
        try:
            stage_info = self.stage_mapping.get(stage, {"percentage": percentage or 0, "stage": stage})
            actual_percentage = percentage if percentage is not None else stage_info["percentage"]
            
            await self.video_service.update_job_status(
                job_id=self.job_id,
                status=JobStatus.PROCESSING,
                progress_percentage=actual_percentage,
                current_stage=stage_info["stage"]
            )
            
            logger.info(f"Job {self.job_id}: {stage} - {actual_percentage}% - {message}")
            
        except Exception as e:
            logger.error(f"Failed to update progress for job {self.job_id}: {e}")
    
    def create_callback(self) -> Callable:
        """Create a progress callback function for the pipeline."""
        async def progress_callback(stage: str, percentage: float = None, message: str = ""):
            await self.update_progress(stage, percentage, message)
        
        return progress_callback


class JobConfigurationMapper:
    """Maps API job configurations to video generation pipeline configurations."""
    
    @staticmethod
    def map_job_to_pipeline_config(job: JobModel, temp_output_dir: str) -> VideoGenerationConfig:
        """Convert job configuration to pipeline configuration."""
        config = job.configuration
        
        # Map quality settings
        quality_mapping = {
            "low": "low",
            "medium": "medium", 
            "high": "high",
            "ultra": "production"
        }
        
        quality = quality_mapping.get(config.quality.value if hasattr(config.quality, 'value') else str(config.quality), "medium")
        
        # Map model settings (use environment defaults or job-specific)
        planner_model = os.getenv("PLANNER_MODEL", "gemini/gemini-2.5-pro")
        scene_model = os.getenv("SCENE_MODEL", planner_model)
        helper_model = os.getenv("HELPER_MODEL", planner_model)
        
        return VideoGenerationConfig(
            planner_model=planner_model,
            scene_model=scene_model,
            helper_model=helper_model,
            output_dir=temp_output_dir,
            verbose=True,
            use_rag=getattr(config, 'use_rag', True),
            use_context_learning=getattr(config, 'use_context_learning', False),
            max_scene_concurrency=int(os.getenv("MAX_SCENE_CONCURRENCY", "3")),
            max_concurrent_renders=int(os.getenv("MAX_CONCURRENT_RENDERS", "2")),
            enable_caching=True,
            default_quality=quality,
            use_gpu_acceleration=os.getenv("USE_GPU_ACCELERATION", "false").lower() == "true",
            preview_mode=False,
            max_retries=5
        )


class S3UploadManager:
    """Handles S3 upload operations after video generation."""
    
    def __init__(self, aws_video_service: AWSVideoService, video_service: VideoService):
        self.aws_video_service = aws_video_service
        self.video_service = video_service
    
    async def upload_generated_video(self, job_id: str, video_path: Path, job: JobModel) -> Dict[str, Any]:
        """Upload generated video to S3 and update job with URLs."""
        try:
            logger.info(f"Uploading video for job {job_id}: {video_path}")
            
            if not video_path.exists():
                raise FileNotFoundError(f"Generated video not found: {video_path}")
            
            file_size = video_path.stat().st_size
            if file_size < 1000:  # Less than 1KB is likely invalid
                raise ValueError(f"Generated video file too small: {file_size} bytes")
            
            # Upload to S3
            upload_result = await self.aws_video_service.upload_video_file(
                file_path=str(video_path),
                job_id=job_id,
                user_id=job.user_id,
                filename=f"{job_id}_video.mp4"
            )
            
            if not upload_result.get("success", False):
                raise Exception(f"S3 upload failed: {upload_result}")
            
            # Create video metadata
            metadata = await self.video_service.create_video_metadata(
                job_id=job_id,
                filename=f"{job_id}_video.mp4",
                file_path=upload_result["s3_key"],
                file_size=file_size,
                format="mp4"
            )
            
            # Update job with result URL
            result_url = upload_result.get("download_url") or upload_result.get("s3_url")
            if result_url:
                await self.video_service.set_job_result_url(job_id, result_url)
            
            logger.info(f"Successfully uploaded video for job {job_id}")
            return {
                "success": True,
                "s3_url": upload_result.get("s3_url"),
                "download_url": upload_result.get("download_url"),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to upload video for job {job_id}: {e}")
            raise


class EnhancedVideoService:
    """
    Enhanced video service that integrates FastAPI backend with core video generation pipeline.
    
    This service replaces the simulation in VideoService with the real sophisticated 
    video generation workflow from generate_video.py and src/core/ components.
    """
    
    def __init__(self, video_service: VideoService, aws_video_service: AWSVideoService):
        self.video_service = video_service
        self.aws_video_service = aws_video_service
        self.s3_upload_manager = S3UploadManager(aws_video_service, video_service)
        
        # Ensure output directory exists
        self.base_output_dir = os.getenv("OUTPUT_DIR", "output")
        os.makedirs(self.base_output_dir, exist_ok=True)
    
    async def process_video_with_core_pipeline(self, job_id: str) -> None:
        """
        Process video generation using the core agents pipeline instead of simulation.
        
        This method integrates with the EnhancedVideoGenerator from generate_video.py
        and provides real-time progress tracking and S3 upload.
        """
        temp_output_dir = None
        
        try:
            # Get job details
            job = await self.video_service.get_job_status(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            logger.info(f"Starting core pipeline for job {job_id}: {job.configuration.topic}")
            
            # Create temporary output directory for this job
            temp_output_dir = tempfile.mkdtemp(prefix=f"video_job_{job_id}_")
            logger.info(f"Created temp output dir: {temp_output_dir}")
            
            # Map job configuration to pipeline configuration
            pipeline_config = JobConfigurationMapper.map_job_to_pipeline_config(job, temp_output_dir)
            
            # Set up progress tracking
            progress_tracker = PipelineProgressTracker(job_id, self.video_service)
            
            # Update job status to processing
            await progress_tracker.update_progress("initializing", 5, "Initializing video generation pipeline")
            
            # Check if EnhancedVideoGenerator is available
            if EnhancedVideoGenerator is None:
                logger.warning("EnhancedVideoGenerator not available, falling back to core orchestrator")
                await self._use_core_orchestrator_fallback(job_id, job, pipeline_config, progress_tracker, temp_output_dir)
            else:
                await self._use_enhanced_generator(job_id, job, pipeline_config, progress_tracker, temp_output_dir)
                
        except Exception as e:
            logger.error(f"Core pipeline failed for job {job_id}: {e}")
            
            # Update job status to failed
            error_info = {
                "error_code": "CORE_PIPELINE_FAILED", 
                "error_message": str(e)
            }
            await self.video_service.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_info=error_info
            )
            raise
            
        finally:
            # Clean up temporary directory
            if temp_output_dir and os.path.exists(temp_output_dir):
                try:
                    shutil.rmtree(temp_output_dir)
                    logger.info(f"Cleaned up temp directory: {temp_output_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory {temp_output_dir}: {e}")
    
    async def _use_enhanced_generator(self, job_id: str, job: JobModel, config: VideoGenerationConfig, 
                                    progress_tracker: PipelineProgressTracker, temp_output_dir: str) -> None:
        """Use the EnhancedVideoGenerator from generate_video.py"""
        try:
            # Initialize enhanced video generator
            video_generator = EnhancedVideoGenerator(config)
            
            # Set up progress callbacks (this would need to be added to EnhancedVideoGenerator)
            # For now, we'll track progress manually at key stages
            
            await progress_tracker.update_progress("planning", 15, "Generating scene outline")
            
            # Run the complete video generation pipeline
            await video_generator.generate_video_pipeline(
                topic=job.configuration.topic,
                description=job.configuration.context,
                only_plan=False,
                specific_scenes=None
            )
            
            await progress_tracker.update_progress("rendering", 80, "Video generation completed")
            
            # Find the generated video file
            topic_dir = self._get_topic_output_dir(job.configuration.topic, temp_output_dir)
            video_path = self._find_generated_video(topic_dir)
            
            if not video_path:
                raise FileNotFoundError("Generated video file not found")
            
            # Upload to S3
            await progress_tracker.update_progress("storage", 95, "Uploading to cloud storage")
            upload_result = await self.s3_upload_manager.upload_generated_video(job_id, video_path, job)
            
            # Mark job as completed
            await self.video_service.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                current_stage="completed",
                result_data=upload_result
            )
            
            logger.info(f"Enhanced video generation completed successfully for job {job_id}")
            
        except Exception as e:
            logger.error(f"Enhanced video generation failed for job {job_id}: {e}")
            raise
    
    async def _use_core_orchestrator_fallback(self, job_id: str, job: JobModel, config: VideoGenerationConfig,
                                            progress_tracker: PipelineProgressTracker, temp_output_dir: str) -> None:
        """Fallback to using VideoGenerationOrchestrator directly"""
        try:
            # Create storage manager
            storage_manager = StorageManager.create_from_config()
            
            # Initialize orchestrator
            orchestrator = VideoGenerationOrchestrator(config, storage_manager)
            
            await progress_tracker.update_progress("planning", 15, "Planning video content")
            
            # Run video generation
            result = await orchestrator.generate_video(
                topic=job.configuration.topic,
                description=job.configuration.context
            )
            
            if result.success:
                await progress_tracker.update_progress("storage", 95, "Uploading to cloud storage")
                
                # Upload the result
                if result.combined_video_path and os.path.exists(result.combined_video_path):
                    video_path = Path(result.combined_video_path)
                    upload_result = await self.s3_upload_manager.upload_generated_video(job_id, video_path, job)
                    
                    # Mark as completed
                    await self.video_service.update_job_status(
                        job_id=job_id,
                        status=JobStatus.COMPLETED,
                        progress_percentage=100.0,
                        current_stage="completed",
                        result_data=upload_result
                    )
                else:
                    raise FileNotFoundError("Video generation completed but no output file found")
            else:
                raise Exception(f"Video generation failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Core orchestrator fallback failed for job {job_id}: {e}")
            raise
    
    def _get_topic_output_dir(self, topic: str, base_dir: str) -> Path:
        """Get the output directory for a topic."""
        import re
        file_prefix = re.sub(r'[^a-z0-9_]+', '_', topic.lower())
        return Path(base_dir) / file_prefix
    
    def _find_generated_video(self, topic_dir: Path) -> Optional[Path]:
        """Find the generated video file in the topic directory."""
        if not topic_dir.exists():
            return None
        
        # Look for combined video file
        video_patterns = [
            f"{topic_dir.name}_combined.mp4",
            "combined.mp4",
            "output.mp4",
            "video.mp4"
        ]
        
        for pattern in video_patterns:
            video_path = topic_dir / pattern
            if video_path.exists() and video_path.stat().st_size > 1000:  # At least 1KB
                return video_path
        
        # Look for any mp4 file
        for video_file in topic_dir.glob("*.mp4"):
            if video_file.stat().st_size > 1000:
                return video_file
        
        return None

    # Delegate other methods to the base video service
    async def create_video_job(self, request: JobCreateRequest, user_id: str, user_info: Optional[Dict[str, Any]] = None) -> JobModel:
        """Create video job using base service."""
        return await self.video_service.create_video_job(request, user_id, user_info)
    
    async def get_job_status(self, job_id: str) -> Optional[JobModel]:
        """Get job status using base service."""
        return await self.video_service.get_job_status(job_id)
    
    async def update_job_status(self, *args, **kwargs):
        """Update job status using base service."""
        return await self.video_service.update_job_status(*args, **kwargs)
    
    async def create_video_metadata(self, *args, **kwargs):
        """Create video metadata using base service."""
        return await self.video_service.create_video_metadata(*args, **kwargs)

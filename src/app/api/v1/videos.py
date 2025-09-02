"""
Video generation API endpoints.

This module implements REST API endpoints for video generation operations,
including job creation, status monitoring, file downloads, and metadata retrieval.
"""

import logging
import asyncio
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query, Path as FastAPIPath
from fastapi.responses import StreamingResponse, FileResponse
from redis.asyncio import Redis
import aiofiles
import os
from pathlib import Path

from ...core.redis import get_redis, RedisKeyManager, redis_json_get, redis_json_set
from ...core.auth import verify_clerk_token, AuthenticationError
from ...models.job import (
    JobCreateRequest, JobStatusResponse, 
    Job, JobStatus, JobConfiguration, JobProgress
)
from ...schemas.responses import JobResponse
from ...models.video import VideoResponse, VideoMetadata, VideoMetadataResponse, VideoStatus
from ...services.video_service import VideoService
from ...services.enhanced_video_service import EnhancedVideoService
from ...api.dependencies import get_current_user, get_video_service, get_enhanced_video_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


def is_job_completed(job: Job) -> bool:
    """Check if a job is completed, handling various status formats."""
    if hasattr(job.status, 'value'):
        return job.status.value.lower() == "completed"
    return str(job.status).lower() == "completed"


def check_job_completion(job: Job, job_id: str) -> None:
    """Raise HTTPException if job is not completed."""
    if not is_job_completed(job):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not completed. Current status: {job.status}"
        )


@router.post(
    "/generate", 
    response_model=JobResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Generate Video",
    description="Create a new video generation job from topic and context",
    operation_id="createVideoGenerationJob",
    responses={
        201: {
            "description": "Video generation job created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "queued",
                        "progress": {
                            "percentage": 0.0,
                            "current_stage": None,
                            "stages_completed": [],
                            "estimated_completion": "2024-01-15T10:35:00Z"
                        },
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        422: {
            "description": "Validation error in request data",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "details": [
                                {
                                    "loc": ["body", "configuration", "topic"],
                                    "msg": "field required",
                                    "type": "value_error.missing"
                                }
                            ]
                        }
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "message": "Rate limit exceeded",
                            "error_code": "RATE_LIMIT_EXCEEDED"
                        }
                    }
                }
            }
        }
    }
)
async def generate_video(
    request: JobCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    enhanced_video_service: EnhancedVideoService = Depends(get_enhanced_video_service)
) -> JobResponse:
    """
    Create a new video generation job and immediately start processing.
    
    This endpoint accepts a video generation request with topic, context,
    and optional parameters, creates the job, and immediately triggers
    the end-to-end video generation workflow using the core pipeline.
    
    Args:
        request: Video generation request with configuration
        current_user: Authenticated user information
        enhanced_video_service: Enhanced video service with core pipeline integration
        
    Returns:
        JobResponse with job ID, status, and metadata
        
    Raises:
        HTTPException: If job creation fails
    """
    try:
        logger.info(
            "Creating video generation job with core pipeline",
            extra={
                "user_id": current_user["user_info"]["id"],
                "topic": request.configuration.topic,
                "quality": request.configuration.quality
            }
        )
        
        # Create job using enhanced video service
        job = await enhanced_video_service.create_video_job(
            request=request,
            user_id=current_user["user_info"]["id"],
            user_info=current_user["user_info"]
        )
        
        # Immediately trigger the core video generation pipeline
        asyncio.create_task(
            enhanced_video_service.process_video_with_core_pipeline(job.id)
        )
        
        logger.info(
            "Video generation job created and core pipeline started",
            extra={
                "job_id": job.id,
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            priority=job.priority,
            progress=job.progress if job.progress else JobProgress(
                percentage=5.0,  # Start at 5% to show processing has begun
                current_stage="initializing",
                stages_completed=[],
                estimated_completion=None
            ),
            created_at=job.created_at,
            estimated_completion=job.progress.estimated_completion if job.progress else None
        )
        
    except Exception as e:
        logger.error(
            "Failed to create video generation job",
            extra={
                "user_id": current_user["user_info"]["id"],
                "topic": request.configuration.topic,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create video generation job: {str(e)}"
        )


@router.get(
    "/jobs/{job_id}/video-url",
    summary="Get Video URL",
    description="Get the streaming URL for a completed video job",
    operation_id="getVideoUrl",
    responses={
        200: {
            "description": "Video URL retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "completed",
                        "video_url": "/api/v1/videos/jobs/550e8400-e29b-41d4-a716-446655440000/stream",
                        "download_url": "/api/v1/videos/jobs/550e8400-e29b-41d4-a716-446655440000/download",
                        "thumbnail_url": "/api/v1/videos/jobs/550e8400-e29b-41d4-a716-446655440000/thumbnail",
                        "metadata": {
                            "duration": 30,
                            "file_size": 1024000,
                            "quality": "medium",
                            "format": "mp4"
                        }
                    }
                }
            }
        },
        404: {
            "description": "Job or video not found"
        },
        409: {
            "description": "Job not completed yet"
        }
    }
)
async def get_video_url(
    job_id: str = FastAPIPath(..., description="Unique job identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service)
) -> Dict[str, Any]:
    """
    Get video URL and metadata for a completed job.
    
    This endpoint is designed for frontend integration to easily get
    the video streaming URL and related information.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        video_service: VideoService dependency
        
    Returns:
        Dict with video URLs and metadata
        
    Raises:
        HTTPException: If job not found, not completed, or access denied
    """
    try:
        # Get job from AWS RDS database using VideoService
        job = await video_service.get_job_status(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        # Check if job is completed using the proper helper function
        if not is_job_completed(job):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Job is not completed yet. Current status: {job.status}",
                    "status": str(job.status).lower(),
                    "progress": job.progress.percentage if job.progress else 0,
                    "current_stage": job.progress.current_stage if job.progress else "unknown"
                }
            )
        
        # Get the video URL from the job's result_url field (stored in AWS RDS)
        video_url = job.result_url
        
        if not video_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video URL not found for this job"
            )
        
        # Extract metadata from job metrics if available
        video_metadata = {
            "duration": 0,
            "quality": "medium",
            "format": "mp4",
            "file_size": 0,  # Default file size
            "demo": False,
            "created_at": None
        }
        
        if job.metrics and 'result_data' in job.metrics:
            result_data = job.metrics['result_data']
            video_metadata.update({
                "duration": result_data.get("duration", 0),
                "quality": result_data.get("quality", "medium"),
                "format": "mp4",  # Default format
                "file_size": result_data.get("file_size", 0),
                "demo": result_data.get("demo", False),
                "created_at": result_data.get("created_at")
            })
        
        # Construct response using actual AWS data
        response_data = {
            "job_id": job_id,
            "status": job.status,
            "video_url": video_url,  # Direct streaming URL from AWS S3
            "download_url": video_url,  # Same URL can be used for download
            "thumbnail_url": f"/api/v1/videos/jobs/{job_id}/thumbnail",  # Placeholder for thumbnail
            "metadata": video_metadata
        }
        
        # Add demo flag if it's a demo video
        if video_metadata.get("demo"):
            response_data["is_demo"] = True
        
        logger.info(
            "Retrieved video URL",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "video_url": response_data["video_url"]
            }
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get video URL",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video URL: {str(e)}"
        )


@router.get(
    "/jobs/{job_id}/status", 
    response_model=JobStatusResponse,
    summary="Get Job Status",
    description="Retrieve current status and progress information for a video generation job",
    operation_id="getVideoJobStatus",
    responses={
        200: {
            "description": "Job status retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "queued": {
                            "summary": "Queued Job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "queued",
                                "progress": {
                                    "percentage": 0.0,
                                    "current_stage": None,
                                    "stages_completed": []
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:30:00Z"
                            }
                        },
                        "processing": {
                            "summary": "Processing Job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "processing",
                                "progress": {
                                    "percentage": 45.0,
                                    "current_stage": "video_generation",
                                    "stages_completed": ["validation", "content_preparation"]
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:32:00Z"
                            }
                        },
                        "completed": {
                            "summary": "Completed Job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "completed",
                                "progress": {
                                    "percentage": 100.0,
                                    "current_stage": "completed",
                                    "stages_completed": ["validation", "content_preparation", "video_generation", "post_processing"]
                                },
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:35:00Z",
                                "completed_at": "2024-01-15T10:35:00Z"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "message": "Job 550e8400-e29b-41d4-a716-446655440000 not found",
                            "error_code": "NOT_FOUND"
                        }
                    }
                }
            }
        },
        403: {
            "description": "Access denied - user doesn't own this job",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "message": "Access denied: You don't own this job",
                            "error_code": "FORBIDDEN"
                        }
                    }
                }
            }
        }
    }
)
async def get_job_status(
    job_id: str = FastAPIPath(..., description="Unique job identifier", example="550e8400-e29b-41d4-a716-446655440000"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service)
) -> JobStatusResponse:
    """
    Get the current status of a video generation job.
    
    This endpoint returns detailed status information including progress,
    current processing stage, and any error information.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        video_service: Video service dependency
        
    Returns:
        JobStatusResponse with current job status and progress
        
    Raises:
        HTTPException: If job not found or access denied
    """
    try:
        # Get job from database
        job = await video_service.get_job_status(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job (compare Clerk IDs)
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        logger.info(
            "Retrieved job status",
            extra={
                "job_id": job_id,
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                "progress": job.progress.percentage if job.progress else 0,
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress if job.progress else JobProgress(
                percentage=0.0,
                current_stage="queued",
                stages_completed=[],
                estimated_completion=None
            ),
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get job status",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get(
    "/jobs/{job_id}/download",
    summary="Download Video",
    description="Download the completed video file with streaming support and range requests",
    operation_id="downloadVideoFile",
    responses={
        200: {
            "description": "Video file download",
            "content": {
                "video/mp4": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            },
            "headers": {
                "Content-Length": {
                    "description": "Size of the video file in bytes",
                    "schema": {"type": "integer"}
                },
                "Content-Type": {
                    "description": "MIME type of the video file",
                    "schema": {"type": "string", "example": "video/mp4"}
                },
                "Content-Disposition": {
                    "description": "File disposition header",
                    "schema": {"type": "string", "example": "attachment; filename=\"video.mp4\""}
                },
                "Accept-Ranges": {
                    "description": "Indicates server supports range requests",
                    "schema": {"type": "string", "example": "bytes"}
                }
            }
        },
        206: {
            "description": "Partial content (range request)",
            "content": {
                "video/mp4": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            },
            "headers": {
                "Content-Range": {
                    "description": "Range of bytes being served",
                    "schema": {"type": "string", "example": "bytes 0-1023/2048"}
                }
            }
        },
        404: {
            "description": "Job or video file not found"
        },
        409: {
            "description": "Job not completed yet"
        },
        403: {
            "description": "Access denied"
        }
    }
)
async def download_video(
    request: Request,
    job_id: str = FastAPIPath(..., description="Unique job identifier", example="550e8400-e29b-41d4-a716-446655440000"),
    inline: bool = Query(False, description="Serve file inline instead of attachment"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis)
) -> StreamingResponse:
    """
    Download the completed video file with enhanced streaming capabilities.
    
    This endpoint serves the generated video file as a streaming response
    with proper content headers, range request support, caching, and security checks.
    
    Args:
        job_id: Unique job identifier
        request: FastAPI request object for range requests
        inline: Whether to serve inline or as attachment
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        StreamingResponse with video file content
        
    Raises:
        HTTPException: If job not found, not completed, or access denied
    """
    try:
        # Get job from Redis
        job_key = RedisKeyManager.job_key(job_id)
        job_data = await redis_json_get(redis_client, job_key)
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = Job(**job_data)
        
        # Verify user owns this job
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        # Check if job is completed
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is not completed. Current status: {job.status}"
            )
        
        # Get video metadata
        video_key = RedisKeyManager.video_key(f"job_{job_id}")
        video_data = await redis_json_get(redis_client, video_key)
        
        if not video_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found"
            )
        
        video = VideoMetadata(**video_data)
        
        # Check if file exists
        file_path = Path(video.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found on disk"
            )
        
        # Update download count
        video.increment_download_count()
        await redis_json_set(redis_client, video_key, video.dict())
        
        logger.info(
            "Serving video download",
            extra={
                "job_id": job_id,
                "video_id": video.id,
                "filename": video.filename,
                "user_id": current_user["user_info"]["id"],
                "inline": inline
            }
        )
        
        # Track file access for analytics
        try:
            from ...utils.file_cache import track_file_access
            await track_file_access(
                file_id=f"job_{job_id}",
                user_id=current_user["user_info"]["id"],
                access_type="download"
            )
        except ImportError:
            # File cache utility not available, skip tracking
            logger.debug("File cache utility not available, skipping access tracking")
        
        # Use enhanced file serving with range request support and caching
        try:
            from ...utils.file_serving import serve_file_secure
            
            return await serve_file_secure(
                file_path=str(file_path),
                file_type="video",
                original_filename=video.filename,
                request=request,
                inline=inline,
                enable_caching=True
            )
        except ImportError:
            # Enhanced file serving not available, use basic file response
            logger.debug("Enhanced file serving not available, using basic file response")
            
            # Basic file serving fallback
            disposition = "inline" if inline else "attachment"
            filename = video.filename
            
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"{disposition}; filename=\"{filename}\"",
                    "Accept-Ranges": "bytes"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download video",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download video: {str(e)}"
        )


@router.get("/jobs/{job_id}/stream")
async def stream_video(
    job_id: str,
    request: Request,
    quality: str = Query("auto", description="Stream quality (auto, 720p, 1080p)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis)
) -> StreamingResponse:
    """
    Stream video file with adaptive quality and range request support.
    
    This endpoint provides optimized video streaming with range requests,
    caching headers, and quality selection for better user experience.
    
    Args:
        job_id: Unique job identifier
        request: FastAPI request object for range requests
        quality: Stream quality setting
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        StreamingResponse with video stream
        
    Raises:
        HTTPException: If job not found, not completed, or access denied
    """
    try:
        # Get job from Redis
        job_key = RedisKeyManager.job_key(job_id)
        job_data = await redis_json_get(redis_client, job_key)
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = Job(**job_data)
        
        # Verify user owns this job
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        # Check if job is completed
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is not completed. Current status: {job.status}"
            )
        
        # Get video metadata
        video_key = RedisKeyManager.video_key(f"job_{job_id}")
        video_data = await redis_json_get(redis_client, video_key)
        
        if not video_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found"
            )
        
        video = VideoMetadata(**video_data)
        
        # Check if file exists
        file_path = Path(video.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found on disk"
            )
        
        logger.info(
            "Serving video stream",
            extra={
                "job_id": job_id,
                "video_id": video.id,
                "filename": video.filename,
                "quality": quality,
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        # Track file access for analytics
        try:
            from ...utils.file_cache import track_file_access
            await track_file_access(
                file_id=f"job_{job_id}",
                user_id=current_user["user_info"]["id"],
                access_type="stream"
            )
        except ImportError:
            logger.debug("File cache utility not available, skipping access tracking")
        
        # Use enhanced file serving with inline=True for streaming
        try:
            from ...utils.file_serving import serve_file_secure
            
            return await serve_file_secure(
                file_path=str(file_path),
                file_type="video",
                original_filename=video.filename,
                request=request,
                inline=True,  # Always serve inline for streaming
                enable_caching=True
            )
        except ImportError:
            # Enhanced file serving not available, use basic streaming response
            logger.debug("Enhanced file serving not available, using basic streaming")
            
            async def file_generator():
                async with aiofiles.open(file_path, 'rb') as f:
                    while chunk := await f.read(8192):
                        yield chunk
            
            return StreamingResponse(
                file_generator(),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"inline; filename=\"{video.filename}\"",
                    "Accept-Ranges": "bytes"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to stream video",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream video: {str(e)}"
        )


@router.get("/jobs/{job_id}/thumbnail")
async def get_video_thumbnail(
    job_id: str,
    request: Request,
    size: str = Query("medium", pattern="^(small|medium|large)$", description="Thumbnail size"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis)
) -> StreamingResponse:
    """
    Get thumbnail for a completed video job.
    
    This endpoint serves video thumbnails with caching and size options
    for better frontend integration and performance.
    
    Args:
        job_id: Unique job identifier
        request: FastAPI request object
        size: Thumbnail size (small, medium, large)
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        StreamingResponse with thumbnail image
        
    Raises:
        HTTPException: If job not found, not completed, or thumbnail not available
    """
    try:
        # Get job from Redis
        job_key = RedisKeyManager.job_key(job_id)
        job_data = await redis_json_get(redis_client, job_key)
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = Job(**job_data)
        
        # Verify user owns this job
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        # Check if job is completed
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is not completed. Current status: {job.status}"
            )
        
        # Get video metadata
        video_key = RedisKeyManager.video_key(f"job_{job_id}")
        video_data = await redis_json_get(redis_client, video_key)
        
        if not video_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found"
            )
        
        video = VideoMetadata(**video_data)
        
        # Check for cached thumbnail path
        thumbnail_path = None
        try:
            from ...utils.file_cache import FileCacheManager
            cache_manager = FileCacheManager(redis_client)
            thumbnail_path = await cache_manager.get_cached_thumbnail_path(f"job_{job_id}", size)
        except ImportError:
            logger.debug("File cache utility not available")
        
        if not thumbnail_path:
            # Generate thumbnail path based on video file
            video_path = Path(video.file_path)
            thumbnail_filename = f"{video_path.stem}_thumb_{size}.jpg"
            thumbnail_path = video_path.parent / "thumbnails" / thumbnail_filename
            
            # Cache the thumbnail path if caching is available
            try:
                from ...utils.file_cache import FileCacheManager
                cache_manager = FileCacheManager(redis_client)
                await cache_manager.cache_thumbnail_path(f"job_{job_id}", size, str(thumbnail_path))
            except ImportError:
                pass
        else:
            thumbnail_path = Path(thumbnail_path)
        
        # Check if thumbnail exists
        if not thumbnail_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thumbnail not available for size: {size}"
            )
        
        logger.info(
            "Serving video thumbnail",
            extra={
                "job_id": job_id,
                "size": size,
                "thumbnail_path": str(thumbnail_path),
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        # Track file access
        try:
            from ...utils.file_cache import track_file_access
            await track_file_access(
                file_id=f"job_{job_id}_thumb_{size}",
                user_id=current_user["user_info"]["id"],
                access_type="thumbnail"
            )
        except ImportError:
            pass
        
        # Use enhanced file serving for thumbnail
        try:
            from ...utils.file_serving import serve_file_secure
            
            return await serve_file_secure(
                file_path=str(thumbnail_path),
                file_type="image",
                original_filename=thumbnail_path.name,
                request=request,
                inline=True,  # Always serve thumbnails inline
                enable_caching=True
            )
        except ImportError:
            # Enhanced file serving not available, use basic file response
            return FileResponse(
                path=str(thumbnail_path),
                filename=thumbnail_path.name,
                media_type="image/jpeg",
                headers={
                    "Content-Disposition": f"inline; filename=\"{thumbnail_path.name}\"",
                    "Cache-Control": "public, max-age=3600"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get video thumbnail",
            extra={
                "job_id": job_id,
                "size": size,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video thumbnail: {str(e)}"
        )


@router.get("/jobs/{job_id}/metadata", response_model=VideoMetadataResponse)
async def get_video_metadata(
    job_id: str = FastAPIPath(..., description="Unique job identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service)
) -> VideoMetadataResponse:
    """
    Get comprehensive metadata for a video generation job.
    
    This endpoint returns detailed video metadata including file information,
    processing metrics, thumbnails, and subtitle tracks.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        video_service: VideoService dependency
        
    Returns:
        VideoMetadataResponse with complete video metadata
        
    Raises:
        HTTPException: If job not found or access denied
    """
    try:
        # Get job from AWS RDS database using VideoService
        job = await video_service.get_job_status(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        if job.user_id != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        # Check if job is completed
        if not is_job_completed(job):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is not completed yet. Current status: {job.status}"
            )
        
        # Build metadata response from job data
        file_prefix = job.configuration.topic.replace(' ', '_').lower()
        video_filename = f"{file_prefix}_combined.mp4"
        
        # Extract metadata from job metrics if available
        duration = None  # Set to None initially
        file_size = 1  # Set minimum valid value as default
        quality = getattr(job.configuration, 'quality', 'medium')
        
        if job.metrics and 'result_data' in job.metrics:
            result_data = job.metrics['result_data']
            duration = result_data.get("duration") or None  # Only set if > 0
            file_size = max(result_data.get("file_size", 1), 1)  # Ensure minimum 1
        
        # Create metadata response using the expected structure
        video_metadata = VideoMetadata(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=job.user_id,
            filename=video_filename,
            file_path=job.result_url or "",
            file_size=file_size,
            duration_seconds=duration,
            width=1920,  # Default width
            height=1080,  # Default height
            format=getattr(job.configuration, 'output_format', 'mp4'),
            status=VideoStatus.READY,
            created_at=job.created_at,
            processed_at=job.completed_at
        )
        
        metadata_response = VideoMetadataResponse(
            video=video_metadata,
            download_url=job.result_url,
            thumbnail_urls=[f"/api/v1/videos/jobs/{job_id}/thumbnail"],
            streaming_url=f"/api/v1/videos/jobs/{job_id}/stream"
        )
        
        logger.info(
            "Retrieved video metadata",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "video_title": job.configuration.topic
            }
        )
        
        return metadata_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get video metadata",
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"],
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video metadata: {str(e)}"
        )
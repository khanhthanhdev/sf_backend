"""
Video generation API endpoints.

This module implements REST API endpoints for video generation operations,
including job creation, status monitoring, file downloads, and metadata retrieval.
"""

import logging
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
    JobCreateRequest, JobResponse, JobStatusResponse, 
    Job, JobStatus, JobConfiguration, JobProgress
)
from ...models.video import VideoResponse, VideoMetadata, VideoMetadataResponse
from ...services.video_service import VideoService
from ...services.aws_video_service import AWSVideoService
from ...api.dependencies import get_current_user, get_video_service, get_aws_video_service
from ...utils.aws_error_handler import handle_aws_service_error, log_aws_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


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
    aws_video_service: AWSVideoService = Depends(get_aws_video_service)
) -> JobResponse:
    """
    Create a new video generation job.
    
    This endpoint accepts a video generation request with topic, context,
    and optional parameters, then queues the job for processing.
    
    Args:
        request: Video generation request with configuration
        current_user: Authenticated user information
        video_service: Video service dependency
        redis_client: Redis client dependency
        
    Returns:
        JobResponse with job ID, status, and metadata
        
    Raises:
        HTTPException: If job creation fails
    """
    try:
        logger.info(
            "Creating video generation job",
            user_id=current_user["user_info"]["id"],
            topic=request.configuration.topic,
            quality=request.configuration.quality
        )
        
        # Create job using AWS video service
        job_result = await aws_video_service.create_video_job(
            request=request,
            user_id=current_user["user_info"]["id"]
        )
        
        job_id = job_result.get("job_id")
        job_status = job_result.get("status", "queued")
        
        logger.info(
            "Video generation job created successfully",
            job_id=job.id,
            user_id=current_user["user_info"]["id"]
        )
        
        return JobResponse(
            job_id=job_id,
            status=job_status,
            progress=0,
            created_at=datetime.utcnow(),
            estimated_completion=None
        )
        
    except Exception as e:
        log_aws_error(e, {
            "operation": "create_video_job",
            "user_id": current_user["user_info"]["id"],
            "topic": request.configuration.topic
        })
        raise handle_aws_service_error(e, "rds", "create video generation job")


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
    aws_video_service: AWSVideoService = Depends(get_aws_video_service)
) -> JobStatusResponse:
    """
    Get the current status of a video generation job.
    
    This endpoint returns detailed status information including progress,
    current processing stage, and any error information.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        JobStatusResponse with current job status and progress
        
    Raises:
        HTTPException: If job not found or access denied
    """
    try:
        # Get job from AWS service
        job_data = await aws_video_service.get_job_status(
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        if job_data.get("user_id") != current_user["user_info"]["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You don't own this job"
            )
        
        logger.info(
            "Retrieved job status",
            job_id=job_id,
            status=job_data.get("status"),
            progress=job_data.get("progress_percentage", 0),
            user_id=current_user["user_info"]["id"]
        )
        
        return JobStatusResponse(
            job_id=job_data.get("id"),
            status=job_data.get("status"),
            progress=job_data.get("progress_percentage", 0),
            error=job_data.get("error_info"),
            metrics=job_data.get("metrics"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at"),
            completed_at=job_data.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_aws_error(e, {
            "operation": "get_job_status",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "get job status")


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
            job_id=job_id,
            video_id=video.id,
            filename=video.filename,
            user_id=current_user["user_info"]["id"],
            inline=inline
        )
        
        # Track file access for analytics
        from ...utils.file_cache import track_file_access
        await track_file_access(
            file_id=f"job_{job_id}",
            user_id=current_user["user_info"]["id"],
            access_type="download"
        )
        
        # Use enhanced file serving with range request support and caching
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=str(file_path),
            file_type="video",
            original_filename=video.filename,
            request=request,
            inline=inline,
            enable_caching=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download video",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download video: {str(e)}"
        )


@router.get("/jobs/{job_id}/metadata", response_model=VideoMetadataResponse)
async def get_video_metadata(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis)
) -> VideoMetadataResponse:
    """
    Get comprehensive metadata for a video generation job.
    
    This endpoint returns detailed video metadata including file information,
    processing metrics, thumbnails, and subtitle tracks.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        VideoMetadataResponse with complete video metadata
        
    Raises:
        HTTPException: If job not found or access denied
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
        
        # Get video metadata if job is completed
        video_metadata = None
        download_url = None
        thumbnail_urls = []
        streaming_url = None
        
        if job.status == JobStatus.COMPLETED:
            video_key = RedisKeyManager.video_key(f"job_{job_id}")
            video_data = await redis_json_get(redis_client, video_key)
            
            if video_data:
                video_metadata = VideoMetadata(**video_data)
                
                # Generate download URL
                download_url = f"/api/v1/videos/jobs/{job_id}/download"
                
                # Generate thumbnail URLs
                thumbnail_urls = [
                    f"/api/v1/videos/thumbnails/{thumb.id}"
                    for thumb in video_metadata.thumbnails
                ]
                
                # Generate streaming URL (if supported)
                streaming_url = f"/api/v1/videos/jobs/{job_id}/stream"
                
                # Update view count
                video_metadata.increment_view_count()
                await redis_json_set(redis_client, video_key, video_metadata.dict())
        
        logger.info(
            "Retrieved video metadata",
            job_id=job_id,
            has_video=video_metadata is not None,
            user_id=current_user["user_info"]["id"]
        )
        
        return VideoMetadataResponse(
            video=video_metadata,
            download_url=download_url,
            thumbnail_urls=thumbnail_urls,
            streaming_url=streaming_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get video metadata",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve video metadata: {str(e)}"
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
            job_id=job_id,
            video_id=video.id,
            filename=video.filename,
            quality=quality,
            user_id=current_user["user_info"]["id"]
        )
        
        # Track file access for analytics
        from ...utils.file_cache import track_file_access
        await track_file_access(
            file_id=f"job_{job_id}",
            user_id=current_user["user_info"]["id"],
            access_type="stream"
        )
        
        # Use enhanced file serving with inline=True for streaming
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=str(file_path),
            file_type="video",
            original_filename=video.filename,
            request=request,
            inline=True,  # Always serve inline for streaming
            enable_caching=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to stream video",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
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
        from ...utils.file_cache import FileCacheManager
        cache_manager = FileCacheManager(redis_client)
        thumbnail_path = await cache_manager.get_cached_thumbnail_path(f"job_{job_id}", size)
        
        if not thumbnail_path:
            # Generate thumbnail path based on video file
            video_path = Path(video.file_path)
            thumbnail_filename = f"{video_path.stem}_thumb_{size}.jpg"
            thumbnail_path = video_path.parent / "thumbnails" / thumbnail_filename
            
            # Cache the thumbnail path
            await cache_manager.cache_thumbnail_path(f"job_{job_id}", size, str(thumbnail_path))
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
            job_id=job_id,
            size=size,
            thumbnail_path=str(thumbnail_path),
            user_id=current_user["user_info"]["id"]
        )
        
        # Track file access
        from ...utils.file_cache import track_file_access
        await track_file_access(
            file_id=f"job_{job_id}_thumb_{size}",
            user_id=current_user["user_info"]["id"],
            access_type="thumbnail"
        )
        
        # Use enhanced file serving for thumbnail
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=str(thumbnail_path),
            file_type="image",
            original_filename=thumbnail_path.name,
            request=request,
            inline=True,  # Always serve thumbnails inline
            enable_caching=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get video thumbnail",
            job_id=job_id,
            size=size,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video thumbnail: {str(e)}"
        )
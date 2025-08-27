"""
Job management API endpoints.

This module implements REST API endpoints for job management operations,
including job listing, cancellation, deletion, and log retrieval.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from redis.asyncio import Redis

from ...core.redis import get_redis, RedisKeyManager, redis_json_get, redis_json_set
from ...core.cache import cache_response, CacheConfig
from ...core.performance import performance_monitor
from ...models.job import (
    JobListResponse, JobResponse, JobStatus, Job,
    JobStatusResponse, JobType, JobPriority
)
from ...services.job_service import JobService
from ...api.dependencies import (
    get_current_user, get_job_service, get_pagination_params,
    get_job_filters, PaginationParams, JobFilters, validate_job_ownership
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: JobFilters = Depends(get_job_filters),
    job_service: JobService = Depends(get_job_service)
) -> JobListResponse:
    """
    List jobs for the current user with pagination and filtering.
    
    This endpoint returns a paginated list of jobs belonging to the current user,
    with optional filtering by status, type, priority, and creation date.
    
    Args:
        current_user: Authenticated user information
        pagination: Pagination parameters
        filters: Job filtering parameters
        job_service: Job service dependency
        
    Returns:
        JobListResponse with paginated job list
        
    Raises:
        HTTPException: If job retrieval fails
    """
    try:
        user_id = current_user["user_info"]["id"]
        
        logger.info(
            "Listing jobs for user",
            user_id=user_id,
            page=pagination.page,
            items_per_page=pagination.items_per_page,
            filters=filters.to_dict()
        )
        
        # Get jobs from service
        jobs_result = await job_service.get_jobs_paginated(
            user_id=user_id,
            limit=pagination.limit,
            offset=pagination.offset,
            filters=filters.to_dict()
        )
        
        # Convert jobs to response format
        job_responses = []
        for job in jobs_result["jobs"]:
            job_responses.append(JobResponse(
                job_id=job.id,
                status=job.status,
                progress=job.progress,
                created_at=job.created_at,
                estimated_completion=job.progress.estimated_completion
            ))
        
        # Calculate pagination info
        total_count = jobs_result["total_count"]
        has_next = (pagination.offset + pagination.items_per_page) < total_count
        has_previous = pagination.page > 1
        
        logger.info(
            "Retrieved jobs for user",
            user_id=user_id,
            job_count=len(job_responses),
            total_count=total_count
        )
        
        return JobListResponse(
            jobs=job_responses,
            total_count=total_count,
            page=pagination.page,
            items_per_page=pagination.items_per_page,
            has_next=has_next,
            has_previous=has_previous
        )
        
    except Exception as e:
        logger.error(
            "Failed to list jobs",
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )


@router.post("/{job_id}/cancel", response_model=Dict[str, Any])
async def cancel_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Cancel a specific job.
    
    This endpoint attempts to cancel a job if it's in a cancellable state
    (queued or processing). Completed or already cancelled jobs cannot be cancelled.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        job_service: Job service dependency
        redis_client: Redis client dependency
        
    Returns:
        Dict with cancellation status and message
        
    Raises:
        HTTPException: If job not found, access denied, or cancellation fails
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
        validate_job_ownership(job.user_id, current_user)
        
        # Check if job can be cancelled
        if not job.can_be_cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job cannot be cancelled. Current status: {job.status}"
            )
        
        logger.info(
            "Cancelling job",
            job_id=job_id,
            current_status=job.status,
            user_id=current_user["user_info"]["id"]
        )
        
        # Cancel job using service
        success = await job_service.cancel_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel job"
            )
        
        logger.info(
            "Job cancelled successfully",
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        return {
            "success": True,
            "message": f"Job {job_id} has been cancelled",
            "job_id": job_id,
            "previous_status": job.status,
            "new_status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to cancel job",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}"
        )


@router.delete("/{job_id}", response_model=Dict[str, Any])
async def delete_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Delete a specific job (soft delete).
    
    This endpoint performs a soft delete on a job, marking it as deleted
    but preserving the data for audit purposes. The job will no longer
    appear in normal job listings.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        job_service: Job service dependency
        redis_client: Redis client dependency
        
    Returns:
        Dict with deletion status and message
        
    Raises:
        HTTPException: If job not found, access denied, or deletion fails
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
        validate_job_ownership(job.user_id, current_user)
        
        # Check if job is already deleted
        if job.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job is already deleted"
            )
        
        logger.info(
            "Deleting job",
            job_id=job_id,
            status=job.status,
            user_id=current_user["user_info"]["id"]
        )
        
        # Cancel job if it's still active
        if job.can_be_cancelled:
            await job_service.cancel_job(job_id)
        
        # Perform soft delete
        success = await job_service.soft_delete_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete job"
            )
        
        # Remove from user's job index
        user_jobs_key = RedisKeyManager.user_jobs_key(current_user["user_info"]["id"])
        await redis_client.srem(user_jobs_key, job_id)
        
        # Clean up related data (video metadata, cache entries)
        await job_service.cleanup_job_data(job_id)
        
        logger.info(
            "Job deleted successfully",
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        return {
            "success": True,
            "message": f"Job {job_id} has been deleted",
            "job_id": job_id,
            "deleted_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete job",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}"
        )


@router.get("/{job_id}/logs", response_model=Dict[str, Any])
async def get_job_logs(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    offset: int = Query(0, ge=0, description="Number of log entries to skip"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    redis_client: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get processing logs for a specific job.
    
    This endpoint returns the processing logs for a job, which can be useful
    for debugging failed jobs or monitoring progress in detail.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        limit: Maximum number of log entries to return
        offset: Number of log entries to skip
        level: Filter logs by level
        redis_client: Redis client dependency
        
    Returns:
        Dict with job logs and metadata
        
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
        validate_job_ownership(job.user_id, current_user)
        
        logger.info(
            "Retrieving job logs",
            job_id=job_id,
            limit=limit,
            offset=offset,
            level=level,
            user_id=current_user["user_info"]["id"]
        )
        
        # Get logs from Redis (stored as a list)
        logs_key = f"job_logs:{job_id}"
        
        # Get total log count
        total_logs = await redis_client.llen(logs_key)
        
        # Get log entries with pagination
        log_entries = []
        if total_logs > 0:
            # Redis lists are 0-indexed, get range with offset and limit
            end_index = offset + limit - 1
            if end_index >= total_logs:
                end_index = total_logs - 1
            
            if offset < total_logs:
                raw_logs = await redis_client.lrange(logs_key, offset, end_index)
                
                # Parse and filter logs
                for log_entry in raw_logs:
                    try:
                        import json
                        log_data = json.loads(log_entry)
                        
                        # Filter by level if specified
                        if level and log_data.get("level", "").upper() != level.upper():
                            continue
                        
                        log_entries.append(log_data)
                        
                    except json.JSONDecodeError:
                        # Handle plain text logs
                        log_entries.append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "level": "INFO",
                            "message": log_entry,
                            "source": "system"
                        })
        
        # Calculate pagination info
        has_more = (offset + limit) < total_logs
        
        logger.info(
            "Retrieved job logs",
            job_id=job_id,
            log_count=len(log_entries),
            total_logs=total_logs,
            user_id=current_user["user_info"]["id"]
        )
        
        return {
            "job_id": job_id,
            "logs": log_entries,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total_count": total_logs,
                "returned_count": len(log_entries),
                "has_more": has_more
            },
            "filters": {
                "level": level
            },
            "job_info": {
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "progress": job.progress.percentage
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get job logs",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job logs: {str(e)}"
        )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_details(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis)
) -> JobStatusResponse:
    """
    Get detailed information about a specific job.
    
    This endpoint returns comprehensive job information including status,
    progress, configuration, metrics, and error details if applicable.
    
    Args:
        job_id: Unique job identifier
        current_user: Authenticated user information
        redis_client: Redis client dependency
        
    Returns:
        JobStatusResponse with detailed job information
        
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
        validate_job_ownership(job.user_id, current_user)
        
        logger.info(
            "Retrieved job details",
            job_id=job_id,
            status=job.status,
            user_id=current_user["user_info"]["id"]
        )
        
        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            error=job.error,
            metrics=job.metrics,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get job details",
            job_id=job_id,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job details: {str(e)}"
        )
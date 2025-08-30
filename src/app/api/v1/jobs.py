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
from ...services.aws_job_service import AWSJobService
from ...api.dependencies import (
    get_current_user, get_job_service, get_aws_job_service, get_pagination_params,
    get_job_filters, PaginationParams, JobFilters, validate_job_ownership
)
from ...utils.aws_error_handler import handle_aws_service_error, log_aws_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: JobFilters = Depends(get_job_filters),
    aws_job_service: AWSJobService = Depends(get_aws_job_service)
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
        
        # Get jobs from AWS service
        jobs_result = await aws_job_service.get_user_jobs(
            user_id=user_id,
            limit=pagination.limit,
            offset=pagination.offset,
            filters=filters.to_dict()
        )
        
        # Convert jobs to response format
        job_responses = []
        for job in jobs_result.get("jobs", []):
            job_responses.append(JobResponse(
                job_id=job.get("id"),
                status=job.get("status"),
                progress=job.get("progress_percentage", 0),
                created_at=job.get("created_at"),
                estimated_completion=job.get("estimated_completion")
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
        log_aws_error(e, {
            "operation": "list_jobs",
            "user_id": current_user["user_info"]["id"],
            "page": pagination.page,
            "items_per_page": pagination.items_per_page
        })
        raise handle_aws_service_error(e, "rds", "list jobs")


@router.post("/{job_id}/cancel", response_model=Dict[str, Any])
async def cancel_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    aws_job_service: AWSJobService = Depends(get_aws_job_service)
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
        # Get job from AWS service
        job_data = await aws_job_service.get_job(
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        validate_job_ownership(job_data.get("user_id"), current_user)
        
        # Check if job can be cancelled
        current_status = job_data.get("status")
        if current_status in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job cannot be cancelled. Current status: {current_status}"
            )
        
        logger.info(
            "Cancelling job",
            job_id=job_id,
            current_status=current_status,
            user_id=current_user["user_info"]["id"]
        )
        
        # Cancel job using AWS service
        success = await aws_job_service.cancel_job(job_id)
        
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
            "previous_status": current_status,
            "new_status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_aws_error(e, {
            "operation": "cancel_job",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "cancel job")


@router.delete("/{job_id}", response_model=Dict[str, Any])
async def delete_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    aws_job_service: AWSJobService = Depends(get_aws_job_service)
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
        # Get job from AWS service
        job_data = await aws_job_service.get_job(
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        validate_job_ownership(job_data.get("user_id"), current_user)
        
        current_status = job_data.get("status")
        
        logger.info(
            "Deleting job",
            job_id=job_id,
            status=current_status,
            user_id=current_user["user_info"]["id"]
        )
        
        # Cancel job if it's still active
        if current_status in ["queued", "processing"]:
            await aws_job_service.cancel_job(job_id)
        
        # Perform soft delete
        success = await aws_job_service.delete_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete job"
            )
        
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
        log_aws_error(e, {
            "operation": "delete_job",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "delete job")


@router.get("/{job_id}/logs", response_model=Dict[str, Any])
async def get_job_logs(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    offset: int = Query(0, ge=0, description="Number of log entries to skip"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    aws_job_service: AWSJobService = Depends(get_aws_job_service)
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
        # Get job from AWS service
        job_data = await aws_job_service.get_job(
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        validate_job_ownership(job_data.get("user_id"), current_user)
        
        logger.info(
            "Retrieving job logs",
            job_id=job_id,
            limit=limit,
            offset=offset,
            level=level,
            user_id=current_user["user_info"]["id"]
        )
        
        # Get logs from AWS service
        try:
            logs_result = await aws_job_service.get_job_logs(
                job_id=job_id,
                limit=limit,
                offset=offset,
                level=level
            )
            
            log_entries = logs_result.get("logs", [])
            total_logs = logs_result.get("total_count", 0)
            
        except Exception as e:
            logger.warning(f"Failed to get job logs from AWS service: {e}")
            # Fallback to empty logs
            log_entries = []
            total_logs = 0
        
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
                "status": job_data.get("status"),
                "created_at": job_data.get("created_at"),
                "updated_at": job_data.get("updated_at"),
                "progress": job_data.get("progress_percentage", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_aws_error(e, {
            "operation": "get_job_logs",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "get job logs")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_details(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    aws_job_service: AWSJobService = Depends(get_aws_job_service)
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
        # Get job from AWS service
        job_data = await aws_job_service.get_job(
            job_id=job_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Verify user owns this job
        validate_job_ownership(job_data.get("user_id"), current_user)
        
        logger.info(
            "Retrieved job details",
            job_id=job_id,
            status=job_data.get("status"),
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
            "operation": "get_job_details",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "get job details")
"""
Job management API endpoints.

This module implements REST API endpoints for job management operations,
including job listing, cancellation, deletion, and log retrieval.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from redis.asyncio import Redis

from ...utils.http_cache import compute_etag, set_cache_headers, not_modified
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
from ...core.audit import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=JobListResponse,
    summary="List Jobs",
    description=(
        "List jobs for the current user with pagination, filtering, and sorting.\n\n"
        "Query params: `page`, `items_per_page`, `status`, `type`, `priority`, `created_after`, `created_before`."
    ),
    responses={
        200: {
            "description": "Paginated job list",
            "content": {
                "application/json": {
                    "example": {
                        "jobs": [
                            {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "processing",
                                "progress": {"percentage": 45.5, "current_stage": "rendering"},
                                "created_at": "2024-09-01T10:00:00Z",
                                "estimated_completion": "2024-09-01T10:07:00Z"
                            }
                        ],
                        "total_count": 23,
                        "page": 1,
                        "items_per_page": 10,
                        "has_next": True,
                        "has_previous": False
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized",
            "content": {"application/json": {"example": {"message": "Unauthorized", "error": {"code": "UNAUTHORIZED"}}}}
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {"application/json": {"example": {"message": "Rate limit exceeded", "error": {"code": "RATE_LIMIT_EXCEEDED"}}}}
        },
        500: {
            "description": "Internal error",
            "content": {"application/json": {"example": {"message": "Internal server error", "error": {"code": "INTERNAL_ERROR"}}}}
        }
    }
)
async def list_jobs(
    request: Request,
    response: Response,
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
            extra={
                "user_id": user_id,
                "page": pagination.page,
                "items_per_page": pagination.items_per_page,
                "filters": filters.to_dict()
            }
        )
        
        # Get jobs from AWS service
        jobs_result = await aws_job_service.get_jobs_paginated(
            user_id=user_id,
            limit=pagination.limit,
            offset=pagination.offset,
            filters=filters.to_dict()
        )
        
        logger.info(
            "Retrieved jobs for user",
            extra={
                "user_id": user_id,
                "job_count": len(jobs_result.jobs),
                "total_count": jobs_result.total_count
            }
        )
        # Set HTTP cache headers (ETag/Cache-Control)
        try:
            etag = compute_etag(jobs_result.model_dump())
        except Exception:
            etag = compute_etag(jobs_result)
        if not_modified(request, etag):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        set_cache_headers(response, etag, max_age=60)
        return jobs_result
        
    except Exception as e:
        log_aws_error(e, {
            "operation": "list_jobs",
            "user_id": current_user["user_info"]["id"],
            "page": pagination.page,
            "items_per_page": pagination.items_per_page
        })
        raise handle_aws_service_error(e, "rds", "list jobs")


@router.post(
    "/{job_id}/cancel",
    response_model=Dict[str, Any],
    summary="Cancel Job",
    description="Cancel a queued or processing job. Returns the new status if successful.",
    responses={
        200: {"description": "Cancellation successful", "content": {"application/json": {"example": {"success": True, "job_id": "550e...", "previous_status": "processing", "new_status": "cancelled"}}}},
        401: {"description": "Unauthorized", "content": {"application/json": {"example": {"message": "Unauthorized", "error": {"code": "UNAUTHORIZED"}}}}},
        403: {"description": "Forbidden", "content": {"application/json": {"example": {"message": "Access denied", "error": {"code": "FORBIDDEN"}}}}},
        404: {"description": "Job not found"},
        409: {"description": "Job not cancellable", "content": {"application/json": {"example": {"message": "Job cannot be cancelled. Current status: completed", "error": {"code": "CONFLICT"}}}}},
        500: {"description": "Internal error"}
    }
)
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
            extra={
                "job_id": job_id,
                "current_status": current_status,
                "user_id": current_user["user_info"]["id"]
            }
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
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"]
            }
        )
        # Audit log
        log_audit_event(
            action="job.cancel",
            user_id=current_user["user_info"]["id"],
            resource_type="job",
            resource_id=job_id,
            status="success",
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
        # Audit failure
        log_audit_event(
            action="job.cancel",
            user_id=current_user["user_info"]["id"],
            resource_type="job",
            resource_id=job_id,
            status="failed",
            details={"error": str(e)},
        )
        raise handle_aws_service_error(e, "rds", "cancel job")


@router.delete(
    "/{job_id}",
    response_model=Dict[str, Any],
    summary="Delete Job (Soft)",
    description="Soft delete a job (preserved for audit).",
    responses={
        200: {"description": "Deletion successful", "content": {"application/json": {"example": {"success": True, "job_id": "550e...", "deleted_at": "2024-09-04T09:05:00Z"}}}},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Job not found"},
        500: {"description": "Internal error"}
    }
)
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
            extra={
                "job_id": job_id,
                "status": current_status,
                "user_id": current_user["user_info"]["id"]
            }
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
            extra={
                "job_id": job_id,
                "user_id": current_user["user_info"]["id"]
            }
        )
        # Audit log
        log_audit_event(
            action="job.delete",
            user_id=current_user["user_info"]["id"],
            resource_type="job",
            resource_id=job_id,
            status="success",
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
        # Audit failure
        log_audit_event(
            action="job.delete",
            user_id=current_user["user_info"]["id"],
            resource_type="job",
            resource_id=job_id,
            status="failed",
            details={"error": str(e)},
        )
        raise handle_aws_service_error(e, "rds", "delete job")


@router.get(
    "/{job_id}/logs",
    response_model=Dict[str, Any],
    summary="Get Job Logs",
    description="Retrieve processing logs for a job with pagination and level filters.",
    responses={
        200: {"description": "Logs returned", "content": {"application/json": {"example": {"job_id": "550e...", "logs": [{"timestamp": "2024-09-04T09:00:01Z", "level": "INFO", "message": "Starting render"}], "pagination": {"offset": 0, "limit": 100, "total_count": 250, "returned_count": 100, "has_more": True}}}}},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Job not found"}
    }
)
async def get_job_logs(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    offset: int = Query(0, ge=0, description="Number of log entries to skip"),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    aws_job_service: AWSJobService = Depends(get_aws_job_service),
    request: Request = None,
    response: Response = None,
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
            extra={
                "job_id": job_id,
                "limit": limit,
                "offset": offset,
                "level": level,
                "user_id": current_user["user_info"]["id"]
            }
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
            extra={
                "job_id": job_id,
                "log_count": len(log_entries),
                "total_logs": total_logs,
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        result_payload = {
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
        if request and response:
            etag = compute_etag(result_payload)
            if not_modified(request, etag):
                return Response(status_code=status.HTTP_304_NOT_MODIFIED)
            set_cache_headers(response, etag, max_age=60)
        return result_payload
        
    except HTTPException:
        raise
    except Exception as e:
        log_aws_error(e, {
            "operation": "get_job_logs",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "get job logs")


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get Job Details",
    description="Get comprehensive job details including status, progress, metrics, and errors.",
    responses={
        200: {"description": "Job details returned", "content": {"application/json": {"example": {"job_id": "550e...", "status": "processing", "progress": {"percentage": 72.5, "current_stage": "compositing"}, "metrics": {"processing_time_seconds": 320.5}, "created_at": "2024-09-04T08:50:00Z", "updated_at": "2024-09-04T09:02:00Z"}}}},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Job not found"}
    }
)
async def get_job_details(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    aws_job_service: AWSJobService = Depends(get_aws_job_service),
    request: Request = None,
    response: Response = None
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
            extra={
                "job_id": job_id,
                "status": job_data.get("status"),
                "user_id": current_user["user_info"]["id"]
            }
        )
        
        result_obj = JobStatusResponse(
            job_id=job_data.get("id"),
            status=job_data.get("status"),
            progress=job_data.get("progress_percentage", 0),
            error=job_data.get("error_info"),
            metrics=job_data.get("metrics"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at"),
            completed_at=job_data.get("completed_at")
        )
        if request and response:
            etag = compute_etag(result_obj.model_dump())
            if not_modified(request, etag):
                return Response(status_code=status.HTTP_304_NOT_MODIFIED)
            set_cache_headers(response, etag, max_age=60)
        return result_obj
        
    except HTTPException:
        raise
    except Exception as e:
        log_aws_error(e, {
            "operation": "get_job_details",
            "job_id": job_id,
            "user_id": current_user["user_info"]["id"]
        })
        raise handle_aws_service_error(e, "rds", "get job details")

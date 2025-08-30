"""
API endpoints for user relationship management.

This module provides REST API endpoints for user-file associations,
job history tracking, and data cleanup operations.
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from ..core.auth import get_current_user, require_permission
from ..core.database import get_connection_manager
from ..services.user_relationship_service import get_user_relationship_service, UserRelationshipService
from ..models.user_relationships import (
    UserDataSummary,
    UserJobHistoryModel,
    JobHistoryStats,
    CleanupResult,
    DataRetentionPolicy,
    FileAccessInfo,
    JobTrendData,
    AccessLevel
)
from ..models.user import AuthenticationContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user-relationships", tags=["User Relationships"])


@router.get("/files", response_model=List[FileAccessInfo])
async def get_user_files_with_access(
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of files"),
    offset: int = Query(0, ge=0, description="Number of files to skip"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get user files with access control information.
    
    Returns a list of files the user has access to, along with their
    access levels and permissions.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        files_with_access = await relationship_service.get_user_files_with_access(
            user_id=user_uuid,
            file_type=file_type,
            access_level=access_level,
            limit=limit,
            offset=offset
        )
        
        # Convert to FileAccessInfo models
        file_access_list = []
        for file_data in files_with_access:
            file_access = FileAccessInfo(
                file_id=str(file_data["id"]),
                filename=file_data["original_filename"],
                file_type=file_data["file_type"],
                file_size=file_data["file_size"],
                created_at=file_data["created_at"],
                last_accessed_at=file_data.get("last_accessed"),
                access_level=AccessLevel(file_data["access_level"]),
                can_read=file_data["can_read"],
                can_write=file_data["can_write"],
                can_delete=file_data["can_delete"],
                description=file_data.get("description"),
                tags=file_data.get("tags", []),
                job_id=str(file_data["job_id"]) if file_data.get("job_id") else None
            )
            file_access_list.append(file_access)
        
        logger.info(f"Retrieved {len(file_access_list)} files for user {current_user.user_id}")
        return file_access_list
        
    except Exception as e:
        logger.error(f"Failed to get user files with access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user files"
        )


@router.get("/files/{file_id}/access")
async def check_file_access(
    file_id: str,
    required_access: AccessLevel = Query(AccessLevel.READ, description="Required access level"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Check if user has required access to a specific file.
    
    Returns access information for the specified file.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        file_uuid = UUID(file_id)
        
        has_access = await relationship_service.check_file_access(
            user_id=user_uuid,
            file_id=file_uuid,
            required_access=required_access.value
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have {required_access.value} access to file {file_id}"
            )
        
        # Update access time
        await relationship_service.update_file_access_time(user_uuid, file_uuid)
        
        return JSONResponse(
            content={
                "file_id": file_id,
                "user_id": current_user.user_id,
                "access_level": required_access.value,
                "has_access": True,
                "accessed_at": datetime.utcnow().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check file access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check file access"
        )


@router.get("/job-history", response_model=UserJobHistoryModel)
async def get_user_job_history(
    include_stats: bool = Query(True, description="Include detailed statistics"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get comprehensive user job history and statistics.
    
    Returns detailed job history including statistics, trends, and recent activity.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        job_history = await relationship_service.get_user_job_history(
            user_id=user_uuid,
            include_stats=include_stats
        )
        
        # Convert to response model
        history_model = UserJobHistoryModel(
            user_id=user_uuid,
            stats=job_history.stats if hasattr(job_history, 'stats') else JobHistoryStats(),
            recent_activity=job_history.recent_activity if hasattr(job_history, 'recent_activity') else []
        )
        
        logger.info(f"Retrieved job history for user {current_user.user_id}")
        return history_model
        
    except Exception as e:
        logger.error(f"Failed to get user job history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job history"
        )


@router.get("/job-trends", response_model=JobTrendData)
async def get_user_job_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get user job trends over specified period.
    
    Returns trend analysis including daily counts, success rates, and performance metrics.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        trends = await relationship_service.get_user_job_trends(
            user_id=user_uuid,
            days=days
        )
        
        # Convert to JobTrendData model
        trend_data = JobTrendData(
            user_id=current_user.user_id,
            period_days=days,
            daily_counts=trends.get("daily_counts", {}),
            status_trends=trends.get("status_trends", {}),
            type_trends=trends.get("type_trends", {}),
            performance_trends=trends.get("performance_trends", {}),
            total_jobs_in_period=sum(trends.get("daily_counts", {}).values()),
            avg_jobs_per_day=sum(trends.get("daily_counts", {}).values()) / days if days > 0 else 0
        )
        
        # Find peak day
        if trend_data.daily_counts:
            peak_day = max(trend_data.daily_counts.items(), key=lambda x: x[1])
            trend_data.peak_day = peak_day[0]
            trend_data.peak_day_count = peak_day[1]
        
        logger.info(f"Retrieved job trends for user {current_user.user_id} over {days} days")
        return trend_data
        
    except Exception as e:
        logger.error(f"Failed to get user job trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job trends"
        )


@router.get("/data-summary", response_model=UserDataSummary)
async def get_user_data_summary(
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get comprehensive summary of user's data.
    
    Returns detailed information about user's files, jobs, and storage usage.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        data_summary = await relationship_service.get_user_data_summary(user_uuid)
        
        logger.info(f"Retrieved data summary for user {current_user.user_id}")
        return data_summary
        
    except Exception as e:
        logger.error(f"Failed to get user data summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve data summary"
        )


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup_user_data(
    retention_policy: Optional[DataRetentionPolicy] = None,
    dry_run: bool = Query(True, description="Perform dry run without actual cleanup"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Clean up user data based on retention policies.
    
    Removes old jobs, orphaned files, and logs according to retention settings.
    Use dry_run=true to see what would be cleaned without actually deleting data.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        # Set user_id in retention policy if provided
        if retention_policy:
            retention_policy.user_id = user_uuid
        
        cleanup_result = await relationship_service.cleanup_user_data(
            user_id=user_uuid,
            retention_policy=retention_policy,
            dry_run=dry_run
        )
        
        logger.info(f"Cleanup {'simulation' if dry_run else 'execution'} completed for user {current_user.user_id}")
        return cleanup_result
        
    except Exception as e:
        logger.error(f"Failed to cleanup user data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup user data"
        )


@router.post("/bulk-cleanup", response_model=dict)
@require_permission("admin")
async def bulk_cleanup_inactive_users(
    inactive_days: int = Query(180, ge=30, le=3650, description="Days to consider user inactive"),
    dry_run: bool = Query(True, description="Perform dry run without actual cleanup"),
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Perform bulk cleanup of inactive users' data.
    
    Admin-only endpoint to clean up data for users who haven't been active
    for the specified number of days.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        
        bulk_result = await relationship_service.bulk_cleanup_inactive_users(
            inactive_days=inactive_days,
            dry_run=dry_run
        )
        
        logger.info(f"Bulk cleanup {'simulation' if dry_run else 'execution'} completed by admin {current_user.user_id}")
        return bulk_result
        
    except Exception as e:
        logger.error(f"Failed to perform bulk cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk cleanup"
        )


@router.get("/cleanup-recommendations")
async def get_cleanup_recommendations(
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get cleanup recommendations for the user.
    
    Returns suggestions for data cleanup based on usage patterns and retention policies.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        # Get data summary to generate recommendations
        data_summary = await relationship_service.get_user_data_summary(user_uuid)
        
        recommendations = []
        estimated_savings = 0.0
        
        # Generate recommendations based on data summary
        if data_summary.cleanup_recommended:
            if data_summary.total_jobs > 100:
                recommendations.append("Consider cleaning up old completed jobs to free up database space")
            
            if data_summary.total_files > 50:
                recommendations.append("Review and remove unnecessary files to reduce storage usage")
            
            if data_summary.account_age_days > 90:
                recommendations.append("Regular cleanup is recommended for accounts older than 90 days")
            
            # Estimate potential savings (simplified calculation)
            estimated_savings = data_summary.total_file_size_mb * 0.1  # Assume 10% can be cleaned
        
        return JSONResponse(
            content={
                "user_id": current_user.user_id,
                "cleanup_recommended": data_summary.cleanup_recommended,
                "recommendations": recommendations,
                "estimated_savings_mb": estimated_savings,
                "data_summary": data_summary.model_dump(),
                "retention_policy": DataRetentionPolicy(user_id=user_uuid).model_dump()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get cleanup recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cleanup recommendations"
        )


@router.get("/stats")
async def get_user_relationship_stats(
    current_user: AuthenticationContext = Depends(get_current_user),
    connection_manager = Depends(get_connection_manager)
):
    """
    Get comprehensive user relationship statistics.
    
    Returns combined statistics about user's files, jobs, and data usage.
    """
    try:
        relationship_service = await get_user_relationship_service(connection_manager)
        user_uuid = UUID(current_user.user_id)
        
        # Get various statistics
        data_summary = await relationship_service.get_user_data_summary(user_uuid)
        job_history = await relationship_service.get_user_job_history(user_uuid)
        
        stats = {
            "user_id": current_user.user_id,
            "data_summary": data_summary.model_dump(),
            "job_statistics": {
                "total_jobs": job_history.total_jobs,
                "completed_jobs": job_history.completed_jobs,
                "failed_jobs": job_history.failed_jobs,
                "active_jobs": job_history.active_jobs,
                "success_rate": (job_history.completed_jobs / job_history.total_jobs * 100) if job_history.total_jobs > 0 else 0,
                "avg_processing_time": job_history.avg_processing_time,
                "job_types_distribution": job_history.job_types_count,
                "priority_distribution": job_history.priority_distribution
            },
            "file_statistics": {
                "total_files": data_summary.total_files,
                "total_size_mb": data_summary.total_file_size_mb,
                "file_types_distribution": data_summary.file_types,
                "storage_usage_level": data_summary.storage_usage_level
            },
            "activity_summary": {
                "account_age_days": data_summary.account_age_days,
                "is_active_user": data_summary.is_active_user,
                "last_active": data_summary.last_active,
                "first_job_date": data_summary.first_job_date,
                "last_job_date": data_summary.last_job_date
            }
        }
        
        logger.info(f"Retrieved comprehensive stats for user {current_user.user_id}")
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"Failed to get user relationship stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )
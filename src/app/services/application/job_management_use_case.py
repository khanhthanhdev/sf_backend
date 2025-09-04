"""
Job Management Use Case - Orchestrates comprehensive job management operations.

This application service coordinates multiple domain services to implement
complete job management workflows.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from ...models.job import Job, JobStatus
from ...models.user import ClerkUser
from ...schemas.common import PaginationRequest
from ..interfaces.application import IJobManagementUseCase
from ..interfaces.domain import (
    IJobManagementService, 
    IUserManagementService,
    INotificationService
)
from ..interfaces.infrastructure import IMetricsService, ILoggingService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class JobManagementUseCase(IJobManagementUseCase):
    """Use case for comprehensive job management operations."""
    
    def __init__(
        self,
        job_management_service: IJobManagementService,
        user_management_service: IUserManagementService,
        notification_service: INotificationService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService
    ):
        self.job_management_service = job_management_service
        self.user_management_service = user_management_service
        self.notification_service = notification_service
        self.metrics_service = metrics_service
        self.logging_service = logging_service
    
    @property
    def service_name(self) -> str:
        return "JobManagementUseCase"
    
    async def get_user_jobs(
        self, 
        user: ClerkUser, 
        pagination: PaginationRequest,
        filters: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[List[Job]]:
        """Get paginated list of user jobs with filtering."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the action
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="get_user_jobs",
                metadata={
                    "correlation_id": correlation_id,
                    "pagination": pagination.model_dump(),
                    "filters": filters or {}
                }
            )
            
            # Validate user permissions
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "read_jobs"
            )
            if not permission_result.success:
                return permission_result
            
            # Get jobs from domain service
            jobs_result = await self.job_management_service.get_user_jobs(
                user.clerk_user_id, pagination, filters
            )
            if not jobs_result.success:
                return jobs_result
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "jobs_retrieved",
                tags={
                    "user_tier": user.subscription_tier,
                    "job_count": str(len(jobs_result.data))
                }
            )
            
            return jobs_result
            
        except Exception as e:
            logger.error(f"Error getting user jobs: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("job_retrieval_errors")
            return ServiceResult.error(
                error=f"Failed to retrieve jobs: {str(e)}",
                error_code="JOB_RETRIEVAL_ERROR"
            )
    
    async def update_job_progress(
        self, 
        job_id: str, 
        progress: float, 
        status: Optional[JobStatus] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[Job]:
        """Update job progress and notify stakeholders."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the action
            await self.logging_service.log_system_event(
                event="job_progress_update",
                metadata={
                    "correlation_id": correlation_id,
                    "job_id": job_id,
                    "progress": progress,
                    "status": status.value if status else None
                }
            )
            
            # Update job through domain service
            update_result = await self.job_management_service.update_job_progress(
                job_id, progress, status, metadata
            )
            if not update_result.success:
                return update_result
            
            job = update_result.data
            
            # Send notifications if significant progress or status change
            if progress >= 1.0 or status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                await self.notification_service.send_job_status_notification(job)
            elif progress % 0.25 == 0:  # Every 25% progress
                await self.notification_service.send_job_progress_notification(job)
            
            # Track metrics
            await self.metrics_service.record_gauge(
                "job_progress",
                progress * 100,
                tags={"job_type": job.job_type.value, "status": job.status.value}
            )
            
            return update_result
            
        except Exception as e:
            logger.error(f"Error updating job progress: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("job_update_errors")
            return ServiceResult.error(
                error=f"Failed to update job progress: {str(e)}",
                error_code="JOB_UPDATE_ERROR"
            )
    
    async def handle_job_completion(
        self, 
        job_id: str, 
        result_metadata: Dict[str, Any]
    ) -> ServiceResult[Job]:
        """Handle job completion with notifications and cleanup."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the completion
            await self.logging_service.log_system_event(
                event="job_completion",
                metadata={
                    "correlation_id": correlation_id,
                    "job_id": job_id,
                    "result_metadata": result_metadata
                }
            )
            
            # Update job status to completed
            completion_result = await self.job_management_service.complete_job(
                job_id, result_metadata
            )
            if not completion_result.success:
                return completion_result
            
            job = completion_result.data
            
            # Send completion notification
            await self.notification_service.send_job_completion_notification(job)
            
            # Track completion metrics
            await self.metrics_service.increment_counter(
                "jobs_completed",
                tags={"job_type": job.job_type.value}
            )
            
            # Record completion time
            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                await self.metrics_service.record_histogram(
                    "job_duration_seconds",
                    duration,
                    tags={"job_type": job.job_type.value}
                )
            
            return completion_result
            
        except Exception as e:
            logger.error(f"Error handling job completion: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("job_completion_errors")
            return ServiceResult.error(
                error=f"Failed to handle job completion: {str(e)}",
                error_code="JOB_COMPLETION_ERROR"
            )
    
    async def handle_job_failure(
        self, 
        job_id: str, 
        error: str, 
        retry: bool = False
    ) -> ServiceResult[Job]:
        """Handle job failure with error reporting and retry logic."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the failure
            await self.logging_service.log_system_event(
                event="job_failure",
                metadata={
                    "correlation_id": correlation_id,
                    "job_id": job_id,
                    "error": error,
                    "retry": retry
                }
            )
            
            # Update job status to failed
            failure_result = await self.job_management_service.fail_job(
                job_id, error, retry
            )
            if not failure_result.success:
                return failure_result
            
            job = failure_result.data
            
            # Send failure notification
            await self.notification_service.send_job_failure_notification(job, error)
            
            # Track failure metrics
            await self.metrics_service.increment_counter(
                "jobs_failed",
                tags={"job_type": job.job_type.value, "retry": str(retry)}
            )
            
            return failure_result
            
        except Exception as e:
            logger.error(f"Error handling job failure: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("job_failure_handling_errors")
            return ServiceResult.error(
                error=f"Failed to handle job failure: {str(e)}",
                error_code="JOB_FAILURE_HANDLING_ERROR"
            )
    
    async def cleanup_old_jobs(
        self, 
        retention_days: int = 30
    ) -> ServiceResult[int]:
        """Cleanup old completed jobs."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the cleanup
            await self.logging_service.log_system_event(
                event="job_cleanup_started",
                metadata={
                    "correlation_id": correlation_id,
                    "retention_days": retention_days
                }
            )
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Cleanup through domain service
            cleanup_result = await self.job_management_service.cleanup_old_jobs(cutoff_date)
            if not cleanup_result.success:
                return cleanup_result
            
            cleaned_count = cleanup_result.data
            
            # Log completion
            await self.logging_service.log_system_event(
                event="job_cleanup_completed",
                metadata={
                    "correlation_id": correlation_id,
                    "cleaned_count": cleaned_count
                }
            )
            
            # Track metrics
            await self.metrics_service.record_gauge(
                "jobs_cleaned_up",
                cleaned_count,
                tags={"retention_days": str(retention_days)}
            )
            
            return cleanup_result
            
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("job_cleanup_errors")
            return ServiceResult.error(
                error=f"Failed to cleanup old jobs: {str(e)}",
                error_code="JOB_CLEANUP_ERROR"
            )

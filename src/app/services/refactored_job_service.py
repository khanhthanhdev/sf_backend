"""
Refactored Job Service - SOLID Principles Implementation Example.

This demonstrates how to refactor the monolithic job_service.py to follow
SOLID principles with proper separation of concerns and dependency injection.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..repositories.base_repository import IJobRepository, IUserRepository, PaginatedResult
from ..interfaces.domain import IJobManagementService
from ..interfaces.infrastructure import IMetricsService, ILoggingService
from ..models.job import Job, JobStatus
from ..schemas.common import PaginationRequest
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class RefactoredJobService:
    """
    Refactored job service following SOLID principles.
    
    This service demonstrates how the monolithic job_service.py can be
    refactored to follow SOLID principles:
    
    1. Single Responsibility: This service only coordinates job operations
    2. Open/Closed: Can be extended without modification through interfaces
    3. Liskov Substitution: All dependencies are abstractions
    4. Interface Segregation: Depends only on specific interfaces it needs
    5. Dependency Inversion: Depends on abstractions, not concretions
    """
    
    def __init__(
        self,
        job_repository: IJobRepository,
        user_repository: IUserRepository,
        job_domain_service: IJobManagementService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService
    ):
        """
        Initialize with dependency injection.
        
        All dependencies are interfaces (abstractions), not concrete implementations.
        This enables easy testing and swapping of implementations.
        """
        self.job_repository = job_repository
        self.user_repository = user_repository
        self.job_domain_service = job_domain_service
        self.metrics_service = metrics_service
        self.logging_service = logging_service
    
    async def get_jobs_paginated(
        self,
        user_id: str,
        pagination: PaginationRequest,
        filters: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[PaginatedResult[Job]]:
        """
        Get paginated list of jobs for a user.
        
        Demonstrates separation of concerns:
        - Repository handles data access
        - Domain service handles business rules
        - This service coordinates the operation
        """
        try:
            # Log the operation
            await self.logging_service.log_user_action(
                user_id=user_id,
                action="get_jobs_paginated",
                metadata={
                    "pagination": pagination.model_dump(),
                    "filters": filters or {}
                }
            )
            
            # Validate user exists (using repository abstraction)
            user_result = await self.user_repository.get_by_id(user_id)
            if not user_result.success or user_result.data is None:
                await self.metrics_service.increment_counter("job_query_user_not_found")
                return ServiceResult.error(
                    error="User not found",
                    error_code="USER_NOT_FOUND"
                )
            
            # Apply business rules for filtering (using domain service)
            processed_filters = await self._apply_filter_business_rules(user_result.data, filters)
            
            # Get jobs from repository
            jobs_result = await self.job_repository.get_by_user_id(
                user_id=user_id,
                pagination=pagination,
                status_filter=processed_filters.get('status')
            )
            
            if jobs_result.success:
                # Track metrics
                await self.metrics_service.increment_counter(
                    "jobs_queried",
                    tags={"user_tier": user_result.data.subscription_tier}
                )
                
                await self.metrics_service.record_gauge(
                    "jobs_returned",
                    len(jobs_result.data.items),
                    tags={"user_id": user_id}
                )
            
            return jobs_result
            
        except Exception as e:
            logger.error(f"Error getting paginated jobs for user {user_id}: {e}")
            await self.metrics_service.increment_counter("job_query_errors")
            return ServiceResult.error(
                error=f"Failed to get jobs: {str(e)}",
                error_code="JOB_QUERY_ERROR"
            )
    
    async def cancel_job(
        self,
        job_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> ServiceResult[bool]:
        """
        Cancel a job with business rule validation.
        
        Demonstrates dependency inversion and single responsibility:
        - Domain service handles business rules
        - Repository handles data persistence
        - This service coordinates the workflow
        """
        try:
            # Log the cancellation attempt
            await self.logging_service.log_user_action(
                user_id=user_id,
                action="job_cancellation_attempt",
                metadata={"job_id": job_id, "reason": reason}
            )
            
            # Get job from repository
            job_result = await self.job_repository.get_by_id(job_id)
            if not job_result.success or job_result.data is None:
                return ServiceResult.error(
                    error="Job not found",
                    error_code="JOB_NOT_FOUND"
                )
            
            job = job_result.data
            
            # Get user for business rule validation
            user_result = await self.user_repository.get_by_id(user_id)
            if not user_result.success or user_result.data is None:
                return ServiceResult.error(
                    error="User not found",
                    error_code="USER_NOT_FOUND"
                )
            
            user = user_result.data
            
            # Apply business rules using domain service
            validation_result = await self.job_domain_service.validate_job_cancellation(job, user)
            if not validation_result.success:
                await self.metrics_service.increment_counter("job_cancellation_validation_failed")
                return validation_result
            
            # Update job status using repository
            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.utcnow()
            
            update_result = await self.job_repository.update(job)
            if not update_result.success:
                return update_result
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "jobs_cancelled",
                tags={"user_tier": user.subscription_tier}
            )
            
            # Log successful cancellation
            await self.logging_service.log_user_action(
                user_id=user_id,
                action="job_cancelled",
                metadata={"job_id": job_id, "reason": reason}
            )
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            await self.metrics_service.increment_counter("job_cancellation_errors")
            return ServiceResult.error(
                error=f"Failed to cancel job: {str(e)}",
                error_code="JOB_CANCELLATION_ERROR"
            )
    
    async def cleanup_old_jobs(
        self,
        retention_days: int = 30
    ) -> ServiceResult[int]:
        """
        Clean up old completed jobs.
        
        Demonstrates open/closed principle - can be extended without modification
        by injecting different repository implementations.
        """
        try:
            # Log cleanup operation
            await self.logging_service.log_system_event(
                event="job_cleanup_started",
                metadata={"retention_days": retention_days}
            )
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Get old completed jobs
            filters = {
                "status": {"in": [JobStatus.COMPLETED.value, JobStatus.FAILED.value]},
                "updated_at": {"lt": cutoff_date}
            }
            
            old_jobs_result = await self.job_repository.list(filters=filters)
            if not old_jobs_result.success:
                return old_jobs_result
            
            old_jobs = old_jobs_result.data.items
            cleanup_count = 0
            
            # Delete old jobs
            for job in old_jobs:
                delete_result = await self.job_repository.delete(job.id)
                if delete_result.success:
                    cleanup_count += 1
                else:
                    logger.warning(f"Failed to delete job {job.id}: {delete_result.error}")
            
            # Track metrics
            await self.metrics_service.record_gauge(
                "jobs_cleaned_up",
                cleanup_count,
                tags={"retention_days": str(retention_days)}
            )
            
            # Log completion
            await self.logging_service.log_system_event(
                event="job_cleanup_completed",
                metadata={
                    "retention_days": retention_days,
                    "jobs_cleaned": cleanup_count
                }
            )
            
            return ServiceResult.success(cleanup_count)
            
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            await self.metrics_service.increment_counter("job_cleanup_errors")
            return ServiceResult.error(
                error=f"Failed to cleanup old jobs: {str(e)}",
                error_code="JOB_CLEANUP_ERROR"
            )
    
    async def _apply_filter_business_rules(
        self,
        user: Any,  # User domain model
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply business rules to filters based on user permissions.
        
        Demonstrates single responsibility - this private method has one job:
        apply business rules to filters.
        """
        if not filters:
            filters = {}
        
        # Business rule: Free tier users can only see their own jobs from last 7 days
        if user.subscription_tier == "free":
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            filters["created_at"] = {"gte": seven_days_ago}
        
        # Business rule: Hide internal job types from regular users
        if user.subscription_tier != "enterprise":
            internal_statuses = ["system_maintenance", "internal_processing"]
            if "status" not in filters:
                filters["status"] = {"not_in": internal_statuses}
        
        return filters


# Example of how to configure this refactored service with dependency injection
class RefactoredJobServiceFactory:
    """Factory for creating RefactoredJobService with proper dependencies."""
    
    @staticmethod
    def create(
        job_repository: IJobRepository,
        user_repository: IUserRepository,
        job_domain_service: IJobManagementService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService
    ) -> RefactoredJobService:
        """Create RefactoredJobService with injected dependencies."""
        return RefactoredJobService(
            job_repository=job_repository,
            user_repository=user_repository,
            job_domain_service=job_domain_service,
            metrics_service=metrics_service,
            logging_service=logging_service
        )


"""
COMPARISON: Old vs New Approach

OLD MONOLITHIC APPROACH (job_service.py):
- Single class handling multiple responsibilities:
  * Data access (direct database queries)
  * Business logic (validation, rules)
  * Infrastructure concerns (logging, metrics)
- Tight coupling to specific implementations
- Hard to test (requires real database)
- Difficult to extend or modify

NEW SOLID APPROACH (RefactoredJobService):
- Single Responsibility: Each class has one reason to change
- Open/Closed: Can extend behavior without modifying existing code
- Liskov Substitution: All dependencies are interchangeable abstractions
- Interface Segregation: Depends only on interfaces it actually needs
- Dependency Inversion: Depends on abstractions, not concretions

BENEFITS:
1. Testability: Can inject mock repositories and services for testing
2. Flexibility: Can swap implementations (e.g., different databases)
3. Maintainability: Changes to one concern don't affect others
4. Extensibility: Can add new features without breaking existing code
5. Clarity: Each component has a clear, single purpose
"""

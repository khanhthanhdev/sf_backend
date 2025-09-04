"""
Job Management Domain Service - Pure business logic for job lifecycle management.

This service contains only the core business rules for job management
without any infrastructure concerns.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...models.job import Job, JobCreateRequest, JobStatus, JobType, JobPriority
from ...models.user import ClerkUser
from ..interfaces.domain import IJobManagementService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class JobManagementService(IJobManagementService):
    """Domain service for job lifecycle management business logic."""
    
    @property
    def service_name(self) -> str:
        return "JobManagementService"
    
    # Valid status transitions
    VALID_TRANSITIONS = {
        JobStatus.QUEUED: [JobStatus.PROCESSING, JobStatus.CANCELLED],
        JobStatus.PROCESSING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
        JobStatus.COMPLETED: [],  # Terminal state
        JobStatus.FAILED: [JobStatus.QUEUED],  # Can retry
        JobStatus.CANCELLED: []  # Terminal state
    }
    
    # Job timeout configuration by type and priority
    TIMEOUT_CONFIG = {
        JobType.VIDEO_GENERATION: {
            JobPriority.LOW: timedelta(hours=6),
            JobPriority.NORMAL: timedelta(hours=4),
            JobPriority.HIGH: timedelta(hours=2),
            JobPriority.URGENT: timedelta(hours=1)
        },
        JobType.BATCH_VIDEO_GENERATION: {
            JobPriority.LOW: timedelta(hours=24),
            JobPriority.NORMAL: timedelta(hours=12),
            JobPriority.HIGH: timedelta(hours=6),
            JobPriority.URGENT: timedelta(hours=3)
        },
        JobType.FILE_PROCESSING: {
            JobPriority.LOW: timedelta(hours=2),
            JobPriority.NORMAL: timedelta(hours=1),
            JobPriority.HIGH: timedelta(minutes=30),
            JobPriority.URGENT: timedelta(minutes=15)
        }
    }
    
    async def create_job(
        self, 
        request: JobCreateRequest, 
        user_id: str
    ) -> ServiceResult[Job]:
        """Create a new job with business validation."""
        try:
            # Validate job creation request
            validation_result = await self._validate_job_creation(request, user_id)
            if not validation_result.success:
                return validation_result
            
            # Apply business rules to determine job properties
            job_priority = self._determine_job_priority(request.job_type, user_id)
            
            # Create job with business logic applied
            job = Job(
                id=f"job_{request.job_type.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                user_id=user_id,
                job_type=request.job_type,
                status=JobStatus.QUEUED,
                priority=job_priority,
                topic=request.topic,
                context=request.context,
                configuration=request.configuration or {},
                progress=0.0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(
                f"Created job {job.id} for user {user_id}",
                extra={
                    "job_id": job.id,
                    "user_id": user_id,
                    "job_type": job.job_type.value,
                    "priority": job.priority.value
                }
            )
            
            return ServiceResult.success(
                job,
                metadata={
                    "priority_assigned": job_priority.value,
                    "estimated_timeout": self._calculate_timeout(job).isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            return ServiceResult.error(
                error="Failed to create job",
                error_code="JOB_CREATION_ERROR"
            )
    
    async def validate_job_transition(
        self, 
        job_id: str, 
        from_status: JobStatus, 
        to_status: JobStatus
    ) -> ServiceResult[bool]:
        """Validate if job status transition is allowed."""
        try:
            valid_transitions = self.VALID_TRANSITIONS.get(from_status, [])
            
            if to_status not in valid_transitions:
                return ServiceResult.error(
                    error=f"Invalid transition from {from_status.value} to {to_status.value}",
                    error_code="INVALID_TRANSITION",
                    metadata={
                        "from_status": from_status.value,
                        "to_status": to_status.value,
                        "valid_transitions": [s.value for s in valid_transitions]
                    }
                )
            
            # Additional business rules for specific transitions
            if to_status == JobStatus.PROCESSING:
                # Check if system can handle processing
                processing_limit_result = await self._check_processing_capacity()
                if not processing_limit_result.success:
                    return processing_limit_result
            
            return ServiceResult.success(
                True,
                metadata={
                    "transition": f"{from_status.value} -> {to_status.value}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error validating job transition: {e}")
            return ServiceResult.error(
                error="Failed to validate transition",
                error_code="TRANSITION_VALIDATION_ERROR"
            )
    
    async def apply_job_priority_rules(
        self, 
        job: Job, 
        user: ClerkUser
    ) -> ServiceResult[Job]:
        """Apply priority rules based on user subscription and job type."""
        try:
            # Calculate priority based on multiple factors
            base_priority = self._get_subscription_priority(user.subscription_tier)
            
            # Adjust for job type
            if job.job_type == JobType.BATCH_VIDEO_GENERATION:
                # Batch jobs get lower priority
                base_priority = max(0, base_priority - 1)
            
            # Emergency escalation rules
            if job.created_at and (datetime.utcnow() - job.created_at) > timedelta(hours=2):
                # Escalate jobs that have been waiting too long
                base_priority = min(3, base_priority + 1)
            
            # Map to JobPriority enum
            priority_mapping = [JobPriority.LOW, JobPriority.NORMAL, JobPriority.HIGH, JobPriority.URGENT]
            final_priority = priority_mapping[min(base_priority, 3)]
            
            # Update job if priority changed
            if job.priority != final_priority:
                original_priority = job.priority
                job.priority = final_priority
                job.updated_at = datetime.utcnow()
                
                logger.info(
                    f"Job priority updated: {original_priority.value} -> {final_priority.value}",
                    extra={
                        "job_id": job.id,
                        "user_id": job.user_id,
                        "original_priority": original_priority.value,
                        "new_priority": final_priority.value
                    }
                )
            
            return ServiceResult.success(
                job,
                metadata={
                    "priority_applied": final_priority.value,
                    "base_priority": base_priority,
                    "subscription_tier": user.subscription_tier
                }
            )
            
        except Exception as e:
            logger.error(f"Error applying job priority rules: {e}")
            return ServiceResult.error(
                error="Failed to apply priority rules",
                error_code="PRIORITY_RULES_ERROR"
            )
    
    async def calculate_job_timeout(
        self, 
        job: Job
    ) -> ServiceResult[datetime]:
        """Calculate when job should timeout."""
        try:
            timeout_delta = self._calculate_timeout(job)
            timeout_time = job.created_at + timeout_delta
            
            return ServiceResult.success(
                timeout_time,
                metadata={
                    "timeout_delta_hours": timeout_delta.total_seconds() / 3600,
                    "job_type": job.job_type.value,
                    "priority": job.priority.value,
                    "created_at": job.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating job timeout: {e}")
            return ServiceResult.error(
                error="Failed to calculate timeout",
                error_code="TIMEOUT_CALCULATION_ERROR"
            )
    
    def _calculate_timeout(self, job: Job) -> timedelta:
        """Calculate timeout delta for a job."""
        timeout_config = self.TIMEOUT_CONFIG.get(
            job.job_type, 
            self.TIMEOUT_CONFIG[JobType.VIDEO_GENERATION]
        )
        return timeout_config.get(job.priority, timedelta(hours=4))
    
    async def _validate_job_creation(
        self, 
        request: JobCreateRequest, 
        user_id: str
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate job creation request."""
        validation_errors = []
        
        # Basic validation
        if not request.topic or len(request.topic.strip()) < 10:
            validation_errors.append("Topic must be at least 10 characters")
        
        if not request.context or len(request.context.strip()) < 20:
            validation_errors.append("Context must be at least 20 characters")
        
        # Business rule validation
        if not self._is_valid_job_type(request.job_type):
            validation_errors.append("Invalid job type")
        
        if validation_errors:
            return ServiceResult.error(
                error="; ".join(validation_errors),
                error_code="JOB_VALIDATION_ERROR",
                metadata={"validation_errors": validation_errors}
            )
        
        return ServiceResult.success({"valid": True})
    
    def _determine_job_priority(self, job_type: JobType, user_id: str) -> JobPriority:
        """Determine initial job priority."""
        # Default priority based on job type
        if job_type == JobType.BATCH_VIDEO_GENERATION:
            return JobPriority.LOW
        else:
            return JobPriority.NORMAL
    
    def _get_subscription_priority(self, subscription_tier: str) -> int:
        """Get base priority score from subscription tier."""
        priority_scores = {
            "free": 0,
            "pro": 1, 
            "enterprise": 2
        }
        return priority_scores.get(subscription_tier, 0)
    
    def _is_valid_job_type(self, job_type: JobType) -> bool:
        """Validate job type against business rules."""
        return job_type in [JobType.VIDEO_GENERATION, JobType.BATCH_VIDEO_GENERATION, JobType.FILE_PROCESSING]
    
    async def _check_processing_capacity(self) -> ServiceResult[bool]:
        """Check if system has capacity for processing new jobs."""
        # This would typically check current processing load
        # For now, assume we have capacity
        return ServiceResult.success(True)

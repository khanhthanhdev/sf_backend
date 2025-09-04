"""
Video Generation Use Case - Orchestrates the complete video generation workflow.

This application service coordinates multiple domain services to implement
the complete video generation use case from request to completion.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from ...models.job import Job, JobCreateRequest, JobType, JobStatus
from ...models.video import VideoMetadata
from ...models.user import ClerkUser
from ...schemas.requests import VideoGenerationRequest
from ..interfaces.application import IVideoGenerationUseCase
from ..interfaces.domain import (
    IVideoGenerationService, 
    IJobManagementService, 
    IUserManagementService,
    INotificationService
)
from ..interfaces.infrastructure import IQueueService, IMetricsService, ILoggingService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class VideoGenerationUseCase(IVideoGenerationUseCase):
    """Use case for complete video generation workflow."""
    
    def __init__(
        self,
        video_generation_service: IVideoGenerationService,
        job_management_service: IJobManagementService,
        user_management_service: IUserManagementService,
        notification_service: INotificationService,
        queue_service: IQueueService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService
    ):
        self.video_generation_service = video_generation_service
        self.job_management_service = job_management_service
        self.user_management_service = user_management_service
        self.notification_service = notification_service
        self.queue_service = queue_service
        self.metrics_service = metrics_service
        self.logging_service = logging_service
    
    @property
    def service_name(self) -> str:
        return "VideoGenerationUseCase"
    
    async def generate_video(
        self, 
        request: VideoGenerationRequest, 
        user: ClerkUser
    ) -> ServiceResult[Job]:
        """
        Complete workflow for video generation including:
        - Request validation
        - User permission checking
        - Cost calculation and credit deduction
        - Job creation
        - Queue submission
        - Notification setup
        """
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the start of the workflow
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="video_generation_started",
                metadata={
                    "correlation_id": correlation_id,
                    "request_summary": {
                        "topic_length": len(request.topic),
                        "quality": request.quality,
                        "use_rag": request.use_rag
                    }
                }
            )
            
            # Step 1: Validate user permissions
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "video_generation"
            )
            if not permission_result.success:
                await self.metrics_service.increment_counter(
                    "video_generation_permission_denied",
                    tags={"subscription_tier": user.subscription_tier}
                )
                return permission_result
            
            # Step 2: Apply rate limiting
            rate_limit_result = await self.user_management_service.apply_rate_limiting_rules(
                user, "video_generation"
            )
            if not rate_limit_result.success:
                await self.metrics_service.increment_counter(
                    "video_generation_rate_limited",
                    tags={"subscription_tier": user.subscription_tier}
                )
                return rate_limit_result
            
            # Step 3: Validate generation request
            validation_result = await self.video_generation_service.validate_generation_request(request)
            if not validation_result.success:
                await self.metrics_service.increment_counter("video_generation_validation_failed")
                return validation_result
            
            # Step 4: Apply business rules and calculate cost
            business_rules_result = await self.video_generation_service.apply_business_rules(user, request)
            if not business_rules_result.success:
                return business_rules_result
            
            # Apply any modifications from business rules
            if business_rules_result.data.get("modifications"):
                request = self._apply_modifications(request, business_rules_result.data["modifications"])
            
            # Step 5: Calculate generation cost
            cost_result = await self.video_generation_service.calculate_generation_cost(request)
            if not cost_result.success:
                return cost_result
            
            # Step 6: Check user credits (placeholder - would integrate with billing service)
            credits_available = await self._check_user_credits(user, cost_result.data)
            if not credits_available:
                return ServiceResult.error(
                    error="Insufficient credits for video generation",
                    error_code="INSUFFICIENT_CREDITS",
                    metadata={"required_credits": cost_result.data, "user_id": user.clerk_user_id}
                )
            
            # Step 7: Create job
            job_request = JobCreateRequest(
                job_type=JobType.VIDEO_GENERATION,
                topic=request.topic,
                context=request.context,
                configuration=request.configuration or {}
            )
            
            job_result = await self.job_management_service.create_job(job_request, user.clerk_user_id)
            if not job_result.success:
                return job_result
            
            job = job_result.data
            
            # Step 8: Apply job priority rules
            priority_result = await self.job_management_service.apply_job_priority_rules(job, user)
            if priority_result.success:
                job = priority_result.data
            
            # Step 9: Deduct credits (placeholder)
            await self._deduct_user_credits(user, cost_result.data)
            
            # Step 10: Submit to queue
            queue_result = await self.queue_service.enqueue_job(job, priority=job.priority.value)
            if not queue_result.success:
                # Rollback credit deduction
                await self._refund_user_credits(user, cost_result.data)
                return ServiceResult.error(
                    error="Failed to submit job to processing queue",
                    error_code="QUEUE_SUBMISSION_FAILED"
                )
            
            # Step 11: Set up notifications
            await self._setup_job_notifications(job, user)
            
            # Step 12: Record metrics
            await self.metrics_service.increment_counter(
                "video_generation_started",
                tags={
                    "subscription_tier": user.subscription_tier,
                    "quality": request.quality,
                    "use_rag": str(request.use_rag)
                }
            )
            
            await self.metrics_service.record_metric(
                "video_generation_cost",
                float(cost_result.data),
                tags={"subscription_tier": user.subscription_tier}
            )
            
            # Log successful workflow completion
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="video_generation_queued",
                resource_id=job.id,
                metadata={
                    "correlation_id": correlation_id,
                    "job_id": job.id,
                    "priority": job.priority.value,
                    "estimated_cost": cost_result.data
                }
            )
            
            return ServiceResult.success(
                job,
                metadata={
                    "correlation_id": correlation_id,
                    "estimated_cost": cost_result.data,
                    "queue_position": queue_result.data
                }
            )
            
        except Exception as e:
            logger.error(f"Error in video generation workflow: {e}", extra={"correlation_id": correlation_id})
            
            await self.logging_service.log_event(
                level="error",
                message=f"Video generation workflow failed: {e}",
                context={"correlation_id": correlation_id, "user_id": user.clerk_user_id}
            )
            
            return ServiceResult.error(
                error="Video generation workflow failed",
                error_code="WORKFLOW_ERROR",
                metadata={"correlation_id": correlation_id}
            )
    
    async def generate_batch_videos(
        self, 
        requests: List[VideoGenerationRequest], 
        user: ClerkUser
    ) -> ServiceResult[List[Job]]:
        """Generate multiple videos in batch."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Validate batch permissions
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "batch_generation"
            )
            if not permission_result.success:
                return permission_result
            
            # Validate batch size
            if len(requests) > self._get_max_batch_size(user):
                return ServiceResult.error(
                    error=f"Batch size exceeds limit for {user.subscription_tier} tier",
                    error_code="BATCH_SIZE_EXCEEDED"
                )
            
            jobs = []
            total_cost = 0
            
            # Validate all requests first
            for i, request in enumerate(requests):
                validation_result = await self.video_generation_service.validate_generation_request(request)
                if not validation_result.success:
                    return ServiceResult.error(
                        error=f"Request {i+1} validation failed: {validation_result.error}",
                        error_code="BATCH_VALIDATION_FAILED"
                    )
                
                cost_result = await self.video_generation_service.calculate_generation_cost(request)
                if cost_result.success:
                    total_cost += cost_result.data
            
            # Check total credits
            if not await self._check_user_credits(user, total_cost):
                return ServiceResult.error(
                    error="Insufficient credits for batch generation",
                    error_code="INSUFFICIENT_CREDITS"
                )
            
            # Create all jobs
            for request in requests:
                job_request = JobCreateRequest(
                    job_type=JobType.BATCH_VIDEO_GENERATION,
                    topic=request.topic,
                    context=request.context,
                    configuration=request.configuration or {}
                )
                
                job_result = await self.job_management_service.create_job(job_request, user.clerk_user_id)
                if job_result.success:
                    job = job_result.data
                    # Batch jobs get lower priority
                    job.priority = job.priority if job.priority.value > 1 else job.priority
                    jobs.append(job)
                    
                    # Submit to queue
                    await self.queue_service.enqueue_job(job, priority=job.priority.value)
            
            # Deduct total credits
            await self._deduct_user_credits(user, total_cost)
            
            # Record metrics
            await self.metrics_service.increment_counter(
                "batch_video_generation_started",
                tags={
                    "subscription_tier": user.subscription_tier,
                    "batch_size": str(len(requests))
                }
            )
            
            return ServiceResult.success(
                jobs,
                metadata={
                    "correlation_id": correlation_id,
                    "total_cost": total_cost,
                    "batch_size": len(requests)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in batch video generation: {e}")
            return ServiceResult.error(
                error="Batch video generation failed",
                error_code="BATCH_WORKFLOW_ERROR"
            )
    
    async def cancel_video_generation(
        self, 
        job_id: str, 
        user: ClerkUser, 
        reason: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Cancel video generation and handle cleanup."""
        try:
            # Validate cancellation permission (user owns job)
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "cancel_job", job_id
            )
            if not permission_result.success:
                return permission_result
            
            # Validate job can be cancelled
            # In real implementation, would fetch job and check status
            cancellation_result = await self._perform_job_cancellation(job_id, reason)
            if not cancellation_result.success:
                return cancellation_result
            
            # Record metrics
            await self.metrics_service.increment_counter(
                "video_generation_cancelled",
                tags={"subscription_tier": user.subscription_tier}
            )
            
            # Log cancellation
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="video_generation_cancelled",
                resource_id=job_id,
                metadata={"reason": reason}
            )
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error cancelling video generation: {e}")
            return ServiceResult.error(
                error="Failed to cancel video generation",
                error_code="CANCELLATION_ERROR"
            )
    
    async def get_video_generation_status(
        self, 
        job_id: str, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Get detailed status of video generation."""
        try:
            # Validate access permission
            permission_result = await self.user_management_service.validate_user_permissions(
                user, "view_job", job_id
            )
            if not permission_result.success:
                return permission_result
            
            # Get job status (placeholder)
            status_data = await self._get_job_status_details(job_id)
            
            return ServiceResult.success(status_data)
            
        except Exception as e:
            logger.error(f"Error getting video generation status: {e}")
            return ServiceResult.error(
                error="Failed to get generation status",
                error_code="STATUS_RETRIEVAL_ERROR"
            )
    
    def _apply_modifications(
        self, 
        request: VideoGenerationRequest, 
        modifications: Dict[str, Any]
    ) -> VideoGenerationRequest:
        """Apply business rule modifications to request."""
        # Create new request with modifications
        request_dict = request.dict()
        request_dict.update(modifications)
        return VideoGenerationRequest(**request_dict)
    
    async def _check_user_credits(self, user: ClerkUser, required_credits: int) -> bool:
        """Check if user has sufficient credits."""
        # Placeholder - would integrate with billing service
        return True
    
    async def _deduct_user_credits(self, user: ClerkUser, credits: int) -> None:
        """Deduct credits from user account."""
        # Placeholder - would integrate with billing service
        pass
    
    async def _refund_user_credits(self, user: ClerkUser, credits: int) -> None:
        """Refund credits to user account."""
        # Placeholder - would integrate with billing service
        pass
    
    async def _setup_job_notifications(self, job: Job, user: ClerkUser) -> None:
        """Set up notifications for job progress."""
        # Setup completion notification
        await self.notification_service.determine_notification_preferences(user, "job_completion")
        # Setup failure notification
        await self.notification_service.determine_notification_preferences(user, "job_failure")
    
    def _get_max_batch_size(self, user: ClerkUser) -> int:
        """Get maximum batch size for user subscription."""
        limits = {"free": 5, "pro": 50, "enterprise": 200}
        return limits.get(user.subscription_tier, 5)
    
    async def _perform_job_cancellation(self, job_id: str, reason: Optional[str]) -> ServiceResult[bool]:
        """Perform the actual job cancellation."""
        # Placeholder - would implement actual cancellation logic
        return ServiceResult.success(True)
    
    async def _get_job_status_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job status information."""
        # Placeholder - would fetch from job service
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": 45.0,
            "estimated_completion": "2025-01-01T12:00:00Z"
        }

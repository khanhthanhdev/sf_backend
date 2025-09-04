"""
Video Generation Domain Service - Pure business logic for video generation.

This service contains only the core business rules and validation logic
for video generation, without any infrastructure concerns.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...models.video import VideoMetadata
from ...models.user import ClerkUser
from ...models.job import JobType, JobPriority, VideoQuality
from ...schemas.requests import VideoGenerationRequest
from ..interfaces.domain import IVideoGenerationService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class VideoGenerationService(IVideoGenerationService):
    """Domain service for video generation business logic."""
    
    @property
    def service_name(self) -> str:
        return "VideoGenerationService"
    
    # Business configuration - could be moved to config service
    MIN_TOPIC_LENGTH = 10
    MAX_TOPIC_LENGTH = 500
    MIN_CONTEXT_LENGTH = 20
    MAX_CONTEXT_LENGTH = 2000
    
    # Credit costs by quality
    CREDIT_COSTS = {
        VideoQuality.LOW: 1,
        VideoQuality.MEDIUM: 3,
        VideoQuality.HIGH: 5,
        VideoQuality.ULTRA: 10
    }
    
    # Estimation times in minutes by quality
    GENERATION_TIMES = {
        VideoQuality.LOW: 2,
        VideoQuality.MEDIUM: 5,
        VideoQuality.HIGH: 10,
        VideoQuality.ULTRA: 20
    }
    
    async def validate_generation_request(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[Dict[str, Any]]:
        """Validate video generation request parameters."""
        try:
            validation_errors = []
            
            # Topic validation
            if not request.topic or len(request.topic.strip()) < self.MIN_TOPIC_LENGTH:
                validation_errors.append(f"Topic must be at least {self.MIN_TOPIC_LENGTH} characters")
            
            if len(request.topic) > self.MAX_TOPIC_LENGTH:
                validation_errors.append(f"Topic must not exceed {self.MAX_TOPIC_LENGTH} characters")
            
            # Context validation
            if not request.context or len(request.context.strip()) < self.MIN_CONTEXT_LENGTH:
                validation_errors.append(f"Context must be at least {self.MIN_CONTEXT_LENGTH} characters")
            
            if len(request.context) > self.MAX_CONTEXT_LENGTH:
                validation_errors.append(f"Context must not exceed {self.MAX_CONTEXT_LENGTH} characters")
            
            # Quality validation
            if request.quality not in [q.value for q in VideoQuality]:
                validation_errors.append("Invalid quality level specified")
            
            # Model validation (basic)
            if request.model and not self._is_valid_model(request.model):
                validation_errors.append("Invalid model specified")
            
            if validation_errors:
                return ServiceResult.error(
                    error="; ".join(validation_errors),
                    error_code="VALIDATION_ERROR",
                    metadata={"validation_errors": validation_errors}
                )
            
            return ServiceResult.success({
                "valid": True,
                "topic_length": len(request.topic),
                "context_length": len(request.context),
                "quality": request.quality
            })
            
        except Exception as e:
            logger.error(f"Error validating generation request: {e}")
            return ServiceResult.error(
                error="Failed to validate request",
                error_code="VALIDATION_SERVICE_ERROR"
            )
    
    async def calculate_generation_cost(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[int]:
        """Calculate cost in credits for video generation."""
        try:
            base_cost = self.CREDIT_COSTS.get(
                VideoQuality(request.quality), 
                self.CREDIT_COSTS[VideoQuality.MEDIUM]
            )
            
            # Apply multipliers based on features
            multiplier = 1.0
            
            if request.use_rag:
                multiplier += 0.5  # RAG adds 50% to cost
            
            if request.configuration:
                # Custom configurations add complexity
                if request.configuration.get("custom_voice"):
                    multiplier += 0.3
                
                if request.configuration.get("advanced_transitions"):
                    multiplier += 0.2
                
                if request.configuration.get("custom_music"):
                    multiplier += 0.4
            
            final_cost = int(base_cost * multiplier)
            
            return ServiceResult.success(
                final_cost,
                metadata={
                    "base_cost": base_cost,
                    "multiplier": multiplier,
                    "features": {
                        "use_rag": request.use_rag,
                        "has_configuration": bool(request.configuration)
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating generation cost: {e}")
            return ServiceResult.error(
                error="Failed to calculate cost",
                error_code="COST_CALCULATION_ERROR"
            )
    
    async def estimate_generation_time(
        self, 
        request: VideoGenerationRequest
    ) -> ServiceResult[int]:
        """Estimate generation time in seconds."""
        try:
            base_time_minutes = self.GENERATION_TIMES.get(
                VideoQuality(request.quality),
                self.GENERATION_TIMES[VideoQuality.MEDIUM]
            )
            
            # Apply time multipliers
            multiplier = 1.0
            
            if request.use_rag:
                multiplier += 0.3  # RAG adds processing time
            
            # Longer content takes more time
            content_length = len(request.topic) + len(request.context)
            if content_length > 1000:
                multiplier += 0.2
            elif content_length > 1500:
                multiplier += 0.4
            
            if request.configuration:
                if request.configuration.get("custom_voice"):
                    multiplier += 0.4
                if request.configuration.get("advanced_transitions"):
                    multiplier += 0.3
            
            final_time_seconds = int(base_time_minutes * multiplier * 60)
            
            return ServiceResult.success(
                final_time_seconds,
                metadata={
                    "base_time_minutes": base_time_minutes,
                    "multiplier": multiplier,
                    "estimated_minutes": round(final_time_seconds / 60, 1)
                }
            )
            
        except Exception as e:
            logger.error(f"Error estimating generation time: {e}")
            return ServiceResult.error(
                error="Failed to estimate time",
                error_code="TIME_ESTIMATION_ERROR"
            )
    
    async def apply_business_rules(
        self, 
        user: ClerkUser, 
        request: VideoGenerationRequest
    ) -> ServiceResult[Dict[str, Any]]:
        """Apply business rules for video generation."""
        try:
            rules_applied = []
            modifications = {}
            
            # Free tier limitations
            if user.subscription_tier == "free":
                # Force lower quality for free users
                if VideoQuality(request.quality) in [VideoQuality.HIGH, VideoQuality.ULTRA]:
                    modifications["quality"] = VideoQuality.MEDIUM.value
                    rules_applied.append("Quality downgraded for free tier")
                
                # Disable premium features
                if request.use_rag:
                    modifications["use_rag"] = False
                    rules_applied.append("RAG disabled for free tier")
                
                if request.configuration:
                    # Remove premium configuration options
                    config = request.configuration.copy()
                    premium_features = ["custom_voice", "advanced_transitions", "custom_music"]
                    for feature in premium_features:
                        if config.get(feature):
                            config.pop(feature)
                            rules_applied.append(f"Premium feature '{feature}' removed for free tier")
                    modifications["configuration"] = config
            
            # Priority assignment based on subscription
            priority = self._determine_job_priority(user)
            modifications["priority"] = priority.value
            
            # Rate limiting check (business rule)
            daily_limit = self._get_daily_generation_limit(user)
            rules_applied.append(f"Daily limit: {daily_limit} generations")
            
            return ServiceResult.success({
                "rules_applied": rules_applied,
                "modifications": modifications,
                "priority": priority.value,
                "daily_limit": daily_limit
            })
            
        except Exception as e:
            logger.error(f"Error applying business rules: {e}")
            return ServiceResult.error(
                error="Failed to apply business rules",
                error_code="BUSINESS_RULES_ERROR"
            )
    
    def _is_valid_model(self, model: str) -> bool:
        """Validate model name against allowed models."""
        allowed_models = [
            "gpt-4", "gpt-3.5-turbo", "claude-3", "gemini-pro"
        ]
        return model in allowed_models
    
    def _determine_job_priority(self, user: ClerkUser) -> JobPriority:
        """Determine job priority based on user subscription."""
        if user.subscription_tier == "enterprise":
            return JobPriority.HIGH
        elif user.subscription_tier == "pro":
            return JobPriority.NORMAL
        else:  # free tier
            return JobPriority.LOW
    
    def _get_daily_generation_limit(self, user: ClerkUser) -> int:
        """Get daily generation limit based on subscription."""
        limits = {
            "free": 3,
            "pro": 50,
            "enterprise": 500
        }
        return limits.get(user.subscription_tier, 3)

"""
Notification Domain Service - Pure business logic for notifications.

This service contains only the core business rules for notification
preferences, content validation, and priority calculation.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...models.user import ClerkUser
from ..interfaces.domain import INotificationService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class NotificationService(INotificationService):
    """Domain service for notification business logic."""
    
    @property
    def service_name(self) -> str:
        return "NotificationService"
    
    # Default notification preferences by subscription tier
    DEFAULT_PREFERENCES = {
        "free": {
            "job_completion": {"email": True, "in_app": True, "push": False},
            "job_failure": {"email": True, "in_app": True, "push": False},
            "account_updates": {"email": True, "in_app": True, "push": False},
            "marketing": {"email": False, "in_app": False, "push": False},
            "security": {"email": True, "in_app": True, "push": True}
        },
        "pro": {
            "job_completion": {"email": True, "in_app": True, "push": True},
            "job_failure": {"email": True, "in_app": True, "push": True},
            "account_updates": {"email": True, "in_app": True, "push": True},
            "marketing": {"email": True, "in_app": True, "push": False},
            "security": {"email": True, "in_app": True, "push": True},
            "quota_warnings": {"email": True, "in_app": True, "push": True}
        },
        "enterprise": {
            "job_completion": {"email": True, "in_app": True, "push": True},
            "job_failure": {"email": True, "in_app": True, "push": True},
            "account_updates": {"email": True, "in_app": True, "push": True},
            "marketing": {"email": True, "in_app": True, "push": False},
            "security": {"email": True, "in_app": True, "push": True},
            "quota_warnings": {"email": True, "in_app": True, "push": True},
            "system_alerts": {"email": True, "in_app": True, "push": True},
            "compliance": {"email": True, "in_app": True, "push": True}
        }
    }
    
    # Notification priority levels
    PRIORITY_LEVELS = {
        "low": 1,
        "normal": 2, 
        "high": 3,
        "critical": 4,
        "emergency": 5
    }
    
    # Content validation rules
    CONTENT_RULES = {
        "job_completion": {
            "required_fields": ["job_id", "job_type", "completion_time"],
            "max_title_length": 100,
            "max_body_length": 500
        },
        "job_failure": {
            "required_fields": ["job_id", "job_type", "error_message"],
            "max_title_length": 100,
            "max_body_length": 1000
        },
        "account_updates": {
            "required_fields": ["update_type", "effective_date"],
            "max_title_length": 150,
            "max_body_length": 2000
        },
        "security": {
            "required_fields": ["event_type", "timestamp", "ip_address"],
            "max_title_length": 100,
            "max_body_length": 1000
        }
    }
    
    async def determine_notification_preferences(
        self, 
        user: ClerkUser, 
        notification_type: str
    ) -> ServiceResult[Dict[str, Any]]:
        """Determine user notification preferences."""
        try:
            # Get default preferences for user's subscription tier
            default_prefs = self.DEFAULT_PREFERENCES.get(
                user.subscription_tier,
                self.DEFAULT_PREFERENCES["free"]
            )
            
            # Get notification type preferences
            type_preferences = default_prefs.get(notification_type, {})
            
            # Apply user-specific overrides (would come from user settings in real implementation)
            user_overrides = await self._get_user_preference_overrides(user, notification_type)
            
            # Merge preferences
            final_preferences = {**type_preferences, **user_overrides}
            
            # Apply business rules
            final_preferences = self._apply_preference_business_rules(
                user, notification_type, final_preferences
            )
            
            return ServiceResult.success(
                final_preferences,
                metadata={
                    "notification_type": notification_type,
                    "subscription_tier": user.subscription_tier,
                    "has_user_overrides": bool(user_overrides)
                }
            )
            
        except Exception as e:
            logger.error(f"Error determining notification preferences: {e}")
            return ServiceResult.error(
                error="Failed to determine notification preferences",
                error_code="NOTIFICATION_PREFERENCES_ERROR"
            )
    
    async def validate_notification_content(
        self, 
        content: Dict[str, Any], 
        notification_type: str
    ) -> ServiceResult[bool]:
        """Validate notification content according to business rules."""
        try:
            validation_errors = []
            
            # Get validation rules for notification type
            rules = self.CONTENT_RULES.get(notification_type, {})
            
            # Check required fields
            required_fields = rules.get("required_fields", [])
            for field in required_fields:
                if field not in content or not content[field]:
                    validation_errors.append(f"Required field '{field}' is missing or empty")
            
            # Validate title length
            title = content.get("title", "")
            max_title_length = rules.get("max_title_length", 200)
            if len(title) > max_title_length:
                validation_errors.append(f"Title exceeds maximum length of {max_title_length} characters")
            
            # Validate body length
            body = content.get("body", "")
            max_body_length = rules.get("max_body_length", 1000)
            if len(body) > max_body_length:
                validation_errors.append(f"Body exceeds maximum length of {max_body_length} characters")
            
            # Content safety checks
            if self._contains_sensitive_information(content):
                validation_errors.append("Content contains sensitive information that should not be included")
            
            # Language and tone validation
            if not self._is_appropriate_tone(content, notification_type):
                validation_errors.append("Content tone is not appropriate for notification type")
            
            if validation_errors:
                return ServiceResult.error(
                    error="; ".join(validation_errors),
                    error_code="CONTENT_VALIDATION_ERROR",
                    metadata={"validation_errors": validation_errors}
                )
            
            return ServiceResult.success(
                True,
                metadata={
                    "notification_type": notification_type,
                    "title_length": len(title),
                    "body_length": len(body)
                }
            )
            
        except Exception as e:
            logger.error(f"Error validating notification content: {e}")
            return ServiceResult.error(
                error="Failed to validate notification content",
                error_code="CONTENT_VALIDATION_SERVICE_ERROR"
            )
    
    async def calculate_notification_priority(
        self, 
        user: ClerkUser, 
        notification_type: str, 
        content: Dict[str, Any]
    ) -> ServiceResult[int]:
        """Calculate notification priority based on business rules."""
        try:
            # Base priority by notification type
            base_priorities = {
                "job_completion": "normal",
                "job_failure": "high",
                "account_updates": "normal",
                "marketing": "low",
                "security": "critical",
                "quota_warnings": "high",
                "system_alerts": "high",
                "compliance": "critical"
            }
            
            base_priority = base_priorities.get(notification_type, "normal")
            priority_score = self.PRIORITY_LEVELS[base_priority]
            
            # Apply user-specific modifiers
            if user.subscription_tier == "enterprise":
                # Enterprise users get higher priority for business notifications
                if notification_type in ["job_failure", "system_alerts", "compliance"]:
                    priority_score = min(5, priority_score + 1)
            
            # Apply content-based modifiers
            priority_score = self._apply_content_priority_modifiers(
                priority_score, notification_type, content
            )
            
            # Apply timing modifiers
            priority_score = self._apply_timing_priority_modifiers(
                priority_score, notification_type
            )
            
            # Ensure priority is within valid range
            final_priority = max(1, min(5, priority_score))
            
            return ServiceResult.success(
                final_priority,
                metadata={
                    "notification_type": notification_type,
                    "base_priority": base_priority,
                    "subscription_tier": user.subscription_tier,
                    "content_modifiers_applied": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating notification priority: {e}")
            return ServiceResult.error(
                error="Failed to calculate notification priority",
                error_code="PRIORITY_CALCULATION_ERROR"
            )
    
    async def _get_user_preference_overrides(
        self, 
        user: ClerkUser, 
        notification_type: str
    ) -> Dict[str, bool]:
        """Get user-specific notification preference overrides."""
        # In real implementation, this would query user settings from database
        # For now, return empty dict (no overrides)
        return {}
    
    def _apply_preference_business_rules(
        self, 
        user: ClerkUser, 
        notification_type: str, 
        preferences: Dict[str, bool]
    ) -> Dict[str, bool]:
        """Apply business rules to notification preferences."""
        # Security notifications are always enabled
        if notification_type == "security":
            preferences["email"] = True
            preferences["in_app"] = True
        
        # Free users don't get marketing notifications via push
        if user.subscription_tier == "free" and notification_type == "marketing":
            preferences["push"] = False
        
        # Critical notifications always enabled for paid users
        if (user.subscription_tier in ["pro", "enterprise"] and 
            notification_type in ["security", "compliance", "quota_warnings"]):
            preferences["email"] = True
            preferences["in_app"] = True
        
        return preferences
    
    def _contains_sensitive_information(self, content: Dict[str, Any]) -> bool:
        """Check if content contains sensitive information."""
        sensitive_patterns = [
            "password", "api_key", "secret", "token", "credit_card", 
            "ssn", "social security", "bank account"
        ]
        
        text_content = " ".join([
            str(content.get("title", "")),
            str(content.get("body", "")),
            str(content.get("details", ""))
        ]).lower()
        
        return any(pattern in text_content for pattern in sensitive_patterns)
    
    def _is_appropriate_tone(self, content: Dict[str, Any], notification_type: str) -> bool:
        """Validate content tone for notification type."""
        # Basic tone validation - in real implementation would use NLP
        title = content.get("title", "").lower()
        body = content.get("body", "").lower()
        
        # Security notifications should be serious
        if notification_type == "security":
            inappropriate_words = ["lol", "haha", "funny", "joke"]
            if any(word in title + body for word in inappropriate_words):
                return False
        
        # Marketing notifications can be more casual
        # Job notifications should be professional
        
        return True  # Placeholder - would implement proper tone analysis
    
    def _apply_content_priority_modifiers(
        self, 
        priority_score: int, 
        notification_type: str, 
        content: Dict[str, Any]
    ) -> int:
        """Apply content-based priority modifiers."""
        
        # Job failure notifications get higher priority if critical error
        if notification_type == "job_failure":
            error_message = content.get("error_message", "").lower()
            critical_errors = ["timeout", "system failure", "data corruption"]
            if any(error in error_message for error in critical_errors):
                priority_score += 1
        
        # Security notifications get higher priority for suspicious activity
        if notification_type == "security":
            event_type = content.get("event_type", "").lower()
            high_risk_events = ["multiple_failed_logins", "unusual_location", "admin_access"]
            if any(event in event_type for event in high_risk_events):
                priority_score += 1
        
        return priority_score
    
    def _apply_timing_priority_modifiers(
        self, 
        priority_score: int, 
        notification_type: str
    ) -> int:
        """Apply timing-based priority modifiers."""
        current_hour = datetime.utcnow().hour
        
        # Lower priority for marketing during night hours
        if notification_type == "marketing" and (current_hour < 8 or current_hour > 20):
            priority_score = max(1, priority_score - 1)
        
        # Higher priority for system alerts during business hours
        if (notification_type == "system_alerts" and 
            8 <= current_hour <= 18):  # Business hours
            priority_score = min(5, priority_score + 1)
        
        return priority_score

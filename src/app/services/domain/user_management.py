"""
User Management Domain Service - Pure business logic for user management.

This service contains only the core business rules for user permissions,
limits, and rate limiting without any infrastructure concerns.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...models.user import ClerkUser
from ..interfaces.domain import IUserManagementService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class UserManagementService(IUserManagementService):
    """Domain service for user management business logic."""
    
    @property
    def service_name(self) -> str:
        return "UserManagementService"
    
    # Permission matrix by subscription tier
    PERMISSIONS = {
        "free": {
            "video_generation": True,
            "batch_generation": False,
            "high_quality": False,
            "custom_models": False,
            "api_access": False,
            "priority_support": False,
            "advanced_features": False
        },
        "pro": {
            "video_generation": True,
            "batch_generation": True,
            "high_quality": True,
            "custom_models": True,
            "api_access": True,
            "priority_support": True,
            "advanced_features": True
        },
        "enterprise": {
            "video_generation": True,
            "batch_generation": True,
            "high_quality": True,
            "custom_models": True,
            "api_access": True,
            "priority_support": True,
            "advanced_features": True,
            "white_label": True,
            "custom_integration": True
        }
    }
    
    # User limits by subscription tier
    USER_LIMITS = {
        "free": {
            "daily_generations": 3,
            "monthly_generations": 30,
            "max_file_size": 50 * 1024 * 1024,      # 50MB
            "storage_quota": 1 * 1024 * 1024 * 1024,  # 1GB
            "concurrent_jobs": 1,
            "api_calls_per_hour": 0  # No API access
        },
        "pro": {
            "daily_generations": 50,
            "monthly_generations": 1000,
            "max_file_size": 500 * 1024 * 1024,     # 500MB
            "storage_quota": 100 * 1024 * 1024 * 1024,  # 100GB
            "concurrent_jobs": 5,
            "api_calls_per_hour": 1000
        },
        "enterprise": {
            "daily_generations": 500,
            "monthly_generations": 10000,
            "max_file_size": 2 * 1024 * 1024 * 1024,  # 2GB
            "storage_quota": 1000 * 1024 * 1024 * 1024,  # 1TB
            "concurrent_jobs": 20,
            "api_calls_per_hour": 10000
        }
    }
    
    # Rate limiting windows
    RATE_LIMIT_WINDOWS = {
        "video_generation": timedelta(minutes=5),
        "file_upload": timedelta(minutes=1),
        "api_call": timedelta(hours=1),
        "batch_operation": timedelta(hours=1)
    }
    
    async def validate_user_permissions(
        self, 
        user: ClerkUser, 
        operation: str, 
        resource_id: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Validate user permissions for operation."""
        try:
            user_permissions = self.PERMISSIONS.get(
                user.subscription_tier, 
                self.PERMISSIONS["free"]
            )
            
            # Check basic permission
            has_permission = user_permissions.get(operation, False)
            
            if not has_permission:
                return ServiceResult.error(
                    error=f"User does not have permission for operation: {operation}",
                    error_code="PERMISSION_DENIED",
                    metadata={
                        "operation": operation,
                        "subscription_tier": user.subscription_tier,
                        "required_permission": operation
                    }
                )
            
            # Additional permission checks based on operation
            additional_checks = await self._perform_additional_permission_checks(
                user, operation, resource_id
            )
            
            if not additional_checks.success:
                return additional_checks
            
            return ServiceResult.success(
                True,
                metadata={
                    "operation": operation,
                    "subscription_tier": user.subscription_tier,
                    "permission_granted": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error validating user permissions: {e}")
            return ServiceResult.error(
                error="Failed to validate permissions",
                error_code="PERMISSION_VALIDATION_ERROR"
            )
    
    async def calculate_user_limits(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, int]]:
        """Calculate user limits based on subscription."""
        try:
            base_limits = self.USER_LIMITS.get(
                user.subscription_tier,
                self.USER_LIMITS["free"]
            ).copy()
            
            # Apply dynamic adjustments
            # Example: New users get bonus limits for first month
            if self._is_new_user(user):
                base_limits["daily_generations"] = int(base_limits["daily_generations"] * 1.5)
                base_limits["monthly_generations"] = int(base_limits["monthly_generations"] * 1.2)
            
            # Apply usage-based adjustments
            if user.subscription_tier != "free":
                # Good users get slight bonuses
                if self._is_good_standing_user(user):
                    for key in ["daily_generations", "monthly_generations"]:
                        base_limits[key] = int(base_limits[key] * 1.1)
            
            return ServiceResult.success(
                base_limits,
                metadata={
                    "subscription_tier": user.subscription_tier,
                    "is_new_user": self._is_new_user(user),
                    "good_standing": self._is_good_standing_user(user)
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating user limits: {e}")
            return ServiceResult.error(
                error="Failed to calculate user limits",
                error_code="LIMITS_CALCULATION_ERROR"
            )
    
    async def apply_rate_limiting_rules(
        self, 
        user: ClerkUser, 
        operation: str
    ) -> ServiceResult[Dict[str, Any]]:
        """Apply rate limiting rules for user operations."""
        try:
            rate_window = self.RATE_LIMIT_WINDOWS.get(operation)
            if not rate_window:
                # No rate limiting for this operation
                return ServiceResult.success({
                    "rate_limited": False,
                    "operation": operation
                })
            
            # Get operation limits
            user_limits = self.USER_LIMITS.get(
                user.subscription_tier,
                self.USER_LIMITS["free"]
            )
            
            # Calculate rate limits based on operation
            rate_limits = self._calculate_operation_rate_limits(operation, user_limits, rate_window)
            
            # Check current usage (would query from cache/database in real implementation)
            current_usage = await self._get_current_usage(user, operation, rate_window)
            
            if current_usage >= rate_limits["max_operations"]:
                return ServiceResult.error(
                    error=f"Rate limit exceeded for operation: {operation}",
                    error_code="RATE_LIMIT_EXCEEDED",
                    metadata={
                        "operation": operation,
                        "current_usage": current_usage,
                        "max_operations": rate_limits["max_operations"],
                        "window_minutes": rate_window.total_seconds() / 60,
                        "reset_time": (datetime.utcnow() + rate_window).isoformat()
                    }
                )
            
            return ServiceResult.success({
                "rate_limited": False,
                "operation": operation,
                "current_usage": current_usage,
                "max_operations": rate_limits["max_operations"],
                "remaining": rate_limits["max_operations"] - current_usage,
                "window_minutes": rate_window.total_seconds() / 60
            })
            
        except Exception as e:
            logger.error(f"Error applying rate limiting rules: {e}")
            return ServiceResult.error(
                error="Failed to apply rate limiting",
                error_code="RATE_LIMITING_ERROR"
            )
    
    async def _perform_additional_permission_checks(
        self, 
        user: ClerkUser, 
        operation: str, 
        resource_id: Optional[str]
    ) -> ServiceResult[bool]:
        """Perform additional permission checks specific to operations."""
        
        # Resource ownership checks
        if resource_id and operation in ["delete_file", "download_file", "cancel_job"]:
            # In real implementation, check if user owns the resource
            if not await self._user_owns_resource(user, resource_id):
                return ServiceResult.error(
                    error="User does not own the requested resource",
                    error_code="RESOURCE_ACCESS_DENIED"
                )
        
        # Account status checks
        if not self._is_account_active(user):
            return ServiceResult.error(
                error="Account is not active",
                error_code="ACCOUNT_INACTIVE"
            )
        
        # Compliance checks
        if operation in ["batch_generation", "api_access"] and not self._is_compliant_user(user):
            return ServiceResult.error(
                error="User does not meet compliance requirements",
                error_code="COMPLIANCE_CHECK_FAILED"
            )
        
        return ServiceResult.success(True)
    
    def _calculate_operation_rate_limits(
        self, 
        operation: str, 
        user_limits: Dict[str, int], 
        window: timedelta
    ) -> Dict[str, int]:
        """Calculate rate limits for specific operations."""
        if operation == "video_generation":
            # For video generation, use daily limit distributed across windows
            daily_limit = user_limits["daily_generations"]
            windows_per_day = 24 * 60 / (window.total_seconds() / 60)  # Number of windows per day
            return {"max_operations": max(1, int(daily_limit / windows_per_day))}
        
        elif operation == "api_call":
            return {"max_operations": user_limits["api_calls_per_hour"]}
        
        elif operation == "file_upload":
            # File uploads: based on subscription tier
            limits = {"free": 5, "pro": 50, "enterprise": 200}
            return {"max_operations": limits.get(user_limits.get("subscription_tier", "free"), 5)}
        
        else:
            # Default rate limit
            return {"max_operations": 10}
    
    def _is_new_user(self, user: ClerkUser) -> bool:
        """Check if user is newly registered."""
        if not user.created_at:
            return False
        return (datetime.utcnow() - user.created_at) < timedelta(days=30)
    
    def _is_good_standing_user(self, user: ClerkUser) -> bool:
        """Check if user is in good standing."""
        # In real implementation, check payment history, compliance, etc.
        return user.subscription_tier in ["pro", "enterprise"]
    
    def _is_account_active(self, user: ClerkUser) -> bool:
        """Check if user account is active."""
        # In real implementation, check account status
        return not getattr(user, "is_suspended", False)
    
    def _is_compliant_user(self, user: ClerkUser) -> bool:
        """Check if user meets compliance requirements."""
        # In real implementation, check various compliance factors
        return user.subscription_tier in ["pro", "enterprise"]
    
    async def _user_owns_resource(self, user: ClerkUser, resource_id: str) -> bool:
        """Check if user owns the specified resource."""
        # In real implementation, query database to verify ownership
        return True  # Placeholder
    
    async def _get_current_usage(
        self, 
        user: ClerkUser, 
        operation: str, 
        window: timedelta
    ) -> int:
        """Get current usage count for operation within time window."""
        # In real implementation, query cache/database for usage metrics
        # For simulation, return some values
        simulation_usage = {
            "video_generation": 1,
            "file_upload": 2,
            "api_call": 50,
            "batch_operation": 0
        }
        return simulation_usage.get(operation, 0)

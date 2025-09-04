"""
User Management Use Case - Orchestrates comprehensive user management operations.

This application service coordinates multiple domain services to implement
complete user management workflows.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from ...models.user import ClerkUser
from ..interfaces.application import IUserManagementUseCase
from ..interfaces.domain import (
    IUserManagementService,
    INotificationService
)
from ..interfaces.infrastructure import IMetricsService, ILoggingService, IExternalAPIService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class UserManagementUseCase(IUserManagementUseCase):
    """Use case for user management operations."""
    
    def __init__(
        self,
        user_management_service: IUserManagementService,
        notification_service: INotificationService,
        metrics_service: IMetricsService,
        logging_service: ILoggingService,
        external_api_service: IExternalAPIService
    ):
        self.user_management_service = user_management_service
        self.notification_service = notification_service
        self.metrics_service = metrics_service
        self.logging_service = logging_service
        self.external_api_service = external_api_service
    
    @property
    def service_name(self) -> str:
        return "UserManagementUseCase"
    
    async def create_user_profile(
        self, 
        clerk_user_data: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Create user profile from Clerk webhook data."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the user creation start
            await self.logging_service.log_system_event(
                event="user_creation_started",
                metadata={
                    "correlation_id": correlation_id,
                    "clerk_user_id": clerk_user_data.get("id"),
                    "email": clerk_user_data.get("email_addresses", [{}])[0].get("email_address")
                }
            )
            
            # Step 1: Validate Clerk user data
            validation_result = await self.user_management_service.validate_clerk_user_data(clerk_user_data)
            if not validation_result.success:
                await self.metrics_service.increment_counter("user_creation_validation_failed")
                return validation_result
            
            # Step 2: Check for existing user
            existing_user_result = await self.user_management_service.get_user_by_clerk_id(
                clerk_user_data["id"]
            )
            if existing_user_result.success:
                # User already exists, return existing user
                await self.metrics_service.increment_counter("user_creation_already_exists")
                return existing_user_result
            
            # Step 3: Create user profile
            user_result = await self.user_management_service.create_user_from_clerk_data(clerk_user_data)
            if not user_result.success:
                return user_result
            
            user = user_result.data
            
            # Step 4: Initialize user resources (storage, default settings, etc.)
            init_result = await self.user_management_service.initialize_user_resources(user)
            if not init_result.success:
                # Rollback user creation if resource initialization fails
                await self.user_management_service.delete_user(user.clerk_user_id)
                return init_result
            
            # Step 5: Send welcome notification
            await self.notification_service.send_welcome_notification(user)
            
            # Step 6: Track metrics
            await self.metrics_service.increment_counter(
                "users_created",
                tags={"subscription_tier": user.subscription_tier}
            )
            
            # Log completion
            await self.logging_service.log_system_event(
                event="user_creation_completed",
                metadata={
                    "correlation_id": correlation_id,
                    "user_id": user.clerk_user_id,
                    "subscription_tier": user.subscription_tier
                }
            )
            
            return ServiceResult.success(user)
            
        except Exception as e:
            logger.error(f"Error creating user profile: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("user_creation_errors")
            return ServiceResult.error(
                error=f"Failed to create user profile: {str(e)}",
                error_code="USER_CREATION_ERROR"
            )
    
    async def update_user_profile(
        self, 
        user_id: str, 
        updates: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Update user profile."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the update start
            await self.logging_service.log_user_action(
                user_id=user_id,
                action="profile_update_started",
                metadata={
                    "correlation_id": correlation_id,
                    "update_fields": list(updates.keys())
                }
            )
            
            # Step 1: Get existing user
            user_result = await self.user_management_service.get_user_by_clerk_id(user_id)
            if not user_result.success:
                return user_result
            
            # Step 2: Validate updates
            validation_result = await self.user_management_service.validate_user_updates(updates)
            if not validation_result.success:
                await self.metrics_service.increment_counter("user_update_validation_failed")
                return validation_result
            
            # Step 3: Apply updates
            update_result = await self.user_management_service.update_user_profile(user_id, updates)
            if not update_result.success:
                return update_result
            
            updated_user = update_result.data
            
            # Step 4: Handle subscription changes if applicable
            if "subscription_tier" in updates:
                await self._handle_subscription_tier_change(
                    updated_user, 
                    user_result.data.subscription_tier,
                    updates["subscription_tier"]
                )
            
            # Step 5: Send update notification if significant changes
            significant_fields = {"email", "subscription_tier", "status"}
            if any(field in updates for field in significant_fields):
                await self.notification_service.send_profile_update_notification(updated_user, updates)
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "user_profiles_updated",
                tags={"subscription_tier": updated_user.subscription_tier}
            )
            
            return ServiceResult.success(updated_user)
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("user_update_errors")
            return ServiceResult.error(
                error=f"Failed to update user profile: {str(e)}",
                error_code="USER_UPDATE_ERROR"
            )
    
    async def get_user_dashboard_data(
        self, 
        user: ClerkUser
    ) -> ServiceResult[Dict[str, Any]]:
        """Get comprehensive user dashboard data."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the dashboard request
            await self.logging_service.log_user_action(
                user_id=user.clerk_user_id,
                action="dashboard_data_requested",
                metadata={"correlation_id": correlation_id}
            )
            
            # Step 1: Get user statistics
            stats_result = await self.user_management_service.get_user_statistics(user)
            if not stats_result.success:
                return stats_result
            
            # Step 2: Get recent activity
            activity_result = await self.user_management_service.get_user_recent_activity(user)
            if not activity_result.success:
                return activity_result
            
            # Step 3: Get usage metrics
            usage_result = await self.user_management_service.get_user_usage_metrics(user)
            if not usage_result.success:
                return usage_result
            
            # Step 4: Get subscription information
            subscription_result = await self.user_management_service.get_user_subscription_info(user)
            if not subscription_result.success:
                return subscription_result
            
            # Compile dashboard data
            dashboard_data = {
                "user_info": {
                    "id": user.clerk_user_id,
                    "email": user.email,
                    "name": user.full_name,
                    "subscription_tier": user.subscription_tier,
                    "created_at": user.created_at,
                    "last_active": user.last_active_at
                },
                "statistics": stats_result.data,
                "recent_activity": activity_result.data,
                "usage_metrics": usage_result.data,
                "subscription": subscription_result.data,
                "generated_at": datetime.utcnow()
            }
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "dashboard_requests",
                tags={"subscription_tier": user.subscription_tier}
            )
            
            return ServiceResult.success(dashboard_data)
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("dashboard_errors")
            return ServiceResult.error(
                error=f"Failed to get dashboard data: {str(e)}",
                error_code="DASHBOARD_ERROR"
            )
    
    async def handle_subscription_change(
        self, 
        user_id: str, 
        subscription_data: Dict[str, Any]
    ) -> ServiceResult[ClerkUser]:
        """Handle user subscription changes."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the subscription change
            await self.logging_service.log_system_event(
                event="subscription_change_started",
                metadata={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "subscription_data": subscription_data
                }
            )
            
            # Step 1: Get user
            user_result = await self.user_management_service.get_user_by_clerk_id(user_id)
            if not user_result.success:
                return user_result
            
            user = user_result.data
            old_tier = user.subscription_tier
            
            # Step 2: Validate subscription data
            validation_result = await self.user_management_service.validate_subscription_data(subscription_data)
            if not validation_result.success:
                return validation_result
            
            # Step 3: Update user subscription
            update_result = await self.user_management_service.update_user_subscription(
                user_id, subscription_data
            )
            if not update_result.success:
                return update_result
            
            updated_user = update_result.data
            
            # Step 4: Handle tier-specific changes
            await self._handle_subscription_tier_change(updated_user, old_tier, updated_user.subscription_tier)
            
            # Step 5: Send notification
            await self.notification_service.send_subscription_change_notification(
                updated_user, old_tier, updated_user.subscription_tier
            )
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "subscription_changes",
                tags={
                    "old_tier": old_tier,
                    "new_tier": updated_user.subscription_tier
                }
            )
            
            return ServiceResult.success(updated_user)
            
        except Exception as e:
            logger.error(f"Error handling subscription change: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("subscription_change_errors")
            return ServiceResult.error(
                error=f"Failed to handle subscription change: {str(e)}",
                error_code="SUBSCRIPTION_CHANGE_ERROR"
            )
    
    async def deactivate_user(
        self, 
        user_id: str, 
        reason: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Deactivate user and cleanup resources."""
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log the deactivation start
            await self.logging_service.log_system_event(
                event="user_deactivation_started",
                metadata={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "reason": reason
                }
            )
            
            # Step 1: Get user
            user_result = await self.user_management_service.get_user_by_clerk_id(user_id)
            if not user_result.success:
                return user_result
            
            user = user_result.data
            
            # Step 2: Cancel active jobs
            cancel_result = await self.user_management_service.cancel_user_active_jobs(user_id)
            if not cancel_result.success:
                logger.warning(f"Failed to cancel user jobs during deactivation: {cancel_result.error}")
            
            # Step 3: Cleanup user resources
            cleanup_result = await self.user_management_service.cleanup_user_resources(user_id)
            if not cleanup_result.success:
                logger.warning(f"Failed to cleanup user resources during deactivation: {cleanup_result.error}")
            
            # Step 4: Deactivate user
            deactivation_result = await self.user_management_service.deactivate_user(user_id, reason)
            if not deactivation_result.success:
                return deactivation_result
            
            # Step 5: Send deactivation notification
            await self.notification_service.send_user_deactivation_notification(user, reason)
            
            # Track metrics
            await self.metrics_service.increment_counter(
                "users_deactivated",
                tags={"subscription_tier": user.subscription_tier}
            )
            
            # Log completion
            await self.logging_service.log_system_event(
                event="user_deactivation_completed",
                metadata={
                    "correlation_id": correlation_id,
                    "user_id": user_id
                }
            )
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error deactivating user: {e}", extra={"correlation_id": correlation_id})
            await self.metrics_service.increment_counter("user_deactivation_errors")
            return ServiceResult.error(
                error=f"Failed to deactivate user: {str(e)}",
                error_code="USER_DEACTIVATION_ERROR"
            )
    
    async def _handle_subscription_tier_change(
        self, 
        user: ClerkUser, 
        old_tier: str, 
        new_tier: str
    ) -> None:
        """Handle subscription tier change side effects."""
        if old_tier == new_tier:
            return
        
        try:
            # Update user quotas and limits
            await self.user_management_service.update_user_quotas_for_tier(user, new_tier)
            
            # If downgrading, check if user exceeds new limits
            if self._is_tier_downgrade(old_tier, new_tier):
                await self.user_management_service.handle_tier_downgrade(user, old_tier, new_tier)
            
            # If upgrading, unlock new features
            if self._is_tier_upgrade(old_tier, new_tier):
                await self.user_management_service.handle_tier_upgrade(user, old_tier, new_tier)
                
        except Exception as e:
            logger.error(f"Error handling subscription tier change: {e}")
            # Don't propagate error - log and continue
    
    def _is_tier_downgrade(self, old_tier: str, new_tier: str) -> bool:
        """Check if the tier change is a downgrade."""
        tier_order = {"free": 0, "basic": 1, "premium": 2, "enterprise": 3}
        return tier_order.get(new_tier, 0) < tier_order.get(old_tier, 0)
    
    def _is_tier_upgrade(self, old_tier: str, new_tier: str) -> bool:
        """Check if the tier change is an upgrade."""
        tier_order = {"free": 0, "basic": 1, "premium": 2, "enterprise": 3}
        return tier_order.get(new_tier, 0) > tier_order.get(old_tier, 0)

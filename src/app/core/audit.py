"""
Audit logging utilities.

Provides helpers to emit structured audit events for important business
operations with correlation IDs and user context.
"""

from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger("audit")


def log_audit_event(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = "success",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit an audit log entry.

    Args:
        action: Business action performed (e.g., "job.cancel", "job.delete")
        user_id: ID of the actor (if any)
        resource_type: Type of resource affected (e.g., "job")
        resource_id: Identifier of the resource
        status: Outcome (e.g., "success", "failed")
        details: Additional context to include
    """
    payload: Dict[str, Any] = {
        "event": "audit",
        "action": action,
        "status": status,
    }
    if user_id:
        payload["user_id"] = user_id
    if resource_type:
        payload["resource_type"] = resource_type
    if resource_id:
        payload["resource_id"] = resource_id
    if details:
        payload.update(details)

    # INFO level for successful actions; WARNING/ERROR can be used by callers if needed
    logger.info("audit_event", **payload)


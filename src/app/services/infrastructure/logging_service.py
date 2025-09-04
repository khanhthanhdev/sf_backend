"""
Logging service implementation for structured logging and audit trails.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from ..interfaces.infrastructure import ILoggingService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class StructuredLoggingService(ILoggingService):
    """Structured logging service implementation."""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self._audit_logs: List[Dict[str, Any]] = []
        
        # Configure structured logger
        self._setup_logger()
    
    @property
    def service_name(self) -> str:
        return "StructuredLoggingService"
    
    def _setup_logger(self):
        """Setup structured logging configuration."""
        # This would typically configure JSON logging, log aggregation, etc.
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    async def log_event(
        self, 
        level: str, 
        message: str, 
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> ServiceResult[bool]:
        """Log structured event."""
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": level.upper(),
                "message": message,
                "context": context or {},
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "service": self.service_name
            }
            
            # Log to standard logger
            log_func = getattr(logger, level.lower(), logger.info)
            log_func(
                message,
                extra={
                    "structured_data": event_data,
                    "correlation_id": correlation_id
                }
            )
            
            # Store for potential querying
            self._audit_logs.append(event_data)
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error logging event: {e}")
            return ServiceResult.error(
                error="Failed to log event",
                error_code="LOG_EVENT_ERROR"
            )
    
    async def log_user_action(
        self, 
        user_id: str, 
        action: str, 
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[bool]:
        """Log user action for audit trail."""
        try:
            audit_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "user_action",
                "user_id": user_id,
                "action": action,
                "resource_id": resource_id,
                "metadata": metadata or {},
                "correlation_id": str(uuid.uuid4())
            }
            
            # Log to audit trail
            logger.info(
                f"User action: {action}",
                extra={
                    "audit_data": audit_data,
                    "user_id": user_id,
                    "action": action
                }
            )
            
            # Store audit log
            self._audit_logs.append(audit_data)
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error logging user action: {e}")
            return ServiceResult.error(
                error="Failed to log user action",
                error_code="LOG_USER_ACTION_ERROR"
            )
    
    async def log_system_event(
        self, 
        event_type: str, 
        component: str, 
        details: Dict[str, Any]
    ) -> ServiceResult[bool]:
        """Log system event."""
        try:
            system_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "system_event",
                "system_event_type": event_type,
                "component": component,
                "details": details,
                "correlation_id": str(uuid.uuid4())
            }
            
            # Determine log level based on event type
            log_level = self._get_system_event_log_level(event_type)
            log_func = getattr(logger, log_level)
            
            log_func(
                f"System event: {event_type} in {component}",
                extra={
                    "system_event": system_event,
                    "component": component
                }
            )
            
            # Store system event
            self._audit_logs.append(system_event)
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error logging system event: {e}")
            return ServiceResult.error(
                error="Failed to log system event",
                error_code="LOG_SYSTEM_EVENT_ERROR"
            )
    
    async def search_logs(
        self, 
        query: str, 
        time_range: Optional[tuple] = None,
        limit: int = 100
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """Search logs with query."""
        try:
            results = []
            
            for log_entry in self._audit_logs:
                # Simple text search in log entries
                if self._matches_query(log_entry, query):
                    # Apply time range filter if specified
                    if time_range:
                        log_time = datetime.fromisoformat(log_entry["timestamp"])
                        start_time, end_time = time_range
                        if not (start_time <= log_time <= end_time):
                            continue
                    
                    results.append(log_entry)
                    
                    if len(results) >= limit:
                        break
            
            return ServiceResult.success(
                results,
                metadata={
                    "query": query,
                    "total_found": len(results),
                    "limit": limit,
                    "time_range": {
                        "start": time_range[0].isoformat() if time_range else None,
                        "end": time_range[1].isoformat() if time_range else None
                    } if time_range else None
                }
            )
            
        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            return ServiceResult.error(
                error="Failed to search logs",
                error_code="LOG_SEARCH_ERROR"
            )
    
    def _get_system_event_log_level(self, event_type: str) -> str:
        """Determine log level for system event type."""
        critical_events = ["service_down", "database_error", "security_breach"]
        warning_events = ["high_memory_usage", "slow_response", "rate_limit_exceeded"]
        
        if event_type in critical_events:
            return "error"
        elif event_type in warning_events:
            return "warning"
        else:
            return "info"
    
    def _matches_query(self, log_entry: Dict[str, Any], query: str) -> bool:
        """Check if log entry matches search query."""
        query_lower = query.lower()
        
        # Search in common fields
        searchable_text = " ".join([
            str(log_entry.get("message", "")),
            str(log_entry.get("action", "")),
            str(log_entry.get("event_type", "")),
            str(log_entry.get("component", "")),
            str(log_entry.get("user_id", "")),
            json.dumps(log_entry.get("metadata", {})),
            json.dumps(log_entry.get("details", {})),
            json.dumps(log_entry.get("context", {}))
        ]).lower()
        
        return query_lower in searchable_text
    
    def get_audit_logs(
        self, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all audit logs."""
        if limit:
            return self._audit_logs[-limit:]
        return self._audit_logs.copy()
    
    def clear_audit_logs(self) -> None:
        """Clear all audit logs."""
        self._audit_logs.clear()
    
    async def initialize(self) -> None:
        """Initialize logging service."""
        logger.info("StructuredLoggingService initialized")
    
    async def cleanup(self) -> None:
        """Cleanup logging service."""
        logger.info("StructuredLoggingService cleaned up")

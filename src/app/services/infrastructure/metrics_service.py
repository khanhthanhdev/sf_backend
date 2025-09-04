"""
Metrics service implementations for monitoring and observability.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from ..interfaces.infrastructure import IMetricsService
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)


class ConsoleMetricsService(IMetricsService):
    """Console-based metrics service for development."""
    
    def __init__(self):
        self._metrics: List[Dict[str, Any]] = []
    
    @property
    def service_name(self) -> str:
        return "ConsoleMetricsService"
    
    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record a metric value."""
        try:
            metric_data = {
                "name": metric_name,
                "value": value,
                "tags": tags or {},
                "timestamp": datetime.utcnow().isoformat(),
                "type": "gauge"
            }
            
            self._metrics.append(metric_data)
            
            logger.info(f"METRIC: {metric_name}={value} {tags or {}}")
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
            return ServiceResult.error(
                error="Failed to record metric",
                error_code="METRIC_RECORD_ERROR"
            )
    
    async def increment_counter(
        self, 
        counter_name: str, 
        increment: int = 1, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Increment a counter metric."""
        try:
            metric_data = {
                "name": counter_name,
                "value": increment,
                "tags": tags or {},
                "timestamp": datetime.utcnow().isoformat(),
                "type": "counter"
            }
            
            self._metrics.append(metric_data)
            
            logger.info(f"COUNTER: {counter_name}+={increment} {tags or {}}")
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error incrementing counter: {e}")
            return ServiceResult.error(
                error="Failed to increment counter",
                error_code="COUNTER_INCREMENT_ERROR"
            )
    
    async def record_duration(
        self, 
        operation_name: str, 
        duration_ms: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record operation duration."""
        try:
            metric_data = {
                "name": f"{operation_name}_duration_ms",
                "value": duration_ms,
                "tags": tags or {},
                "timestamp": datetime.utcnow().isoformat(),
                "type": "histogram"
            }
            
            self._metrics.append(metric_data)
            
            logger.info(f"DURATION: {operation_name}={duration_ms}ms {tags or {}}")
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error recording duration: {e}")
            return ServiceResult.error(
                error="Failed to record duration",
                error_code="DURATION_RECORD_ERROR"
            )
    
    async def get_metrics(
        self, 
        metric_names: List[str], 
        time_range: Optional[tuple] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Get metric values for specified time range."""
        try:
            filtered_metrics = []
            
            for metric in self._metrics:
                if metric["name"] in metric_names:
                    # Apply time range filter if specified
                    if time_range:
                        metric_time = datetime.fromisoformat(metric["timestamp"])
                        start_time, end_time = time_range
                        if start_time <= metric_time <= end_time:
                            filtered_metrics.append(metric)
                    else:
                        filtered_metrics.append(metric)
            
            result = {
                "metrics": filtered_metrics,
                "count": len(filtered_metrics),
                "time_range": {
                    "start": time_range[0].isoformat() if time_range else None,
                    "end": time_range[1].isoformat() if time_range else None
                }
            }
            
            return ServiceResult.success(result)
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return ServiceResult.error(
                error="Failed to get metrics",
                error_code="METRICS_GET_ERROR"
            )
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get all recorded metrics."""
        return self._metrics.copy()
    
    def clear_metrics(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()


class CloudWatchMetricsService(IMetricsService):
    """CloudWatch-based metrics service for production."""
    
    def __init__(self, cloudwatch_client=None):
        self.cloudwatch = cloudwatch_client  # Would be injected
        self.namespace = "VideoGeneration/API"
    
    @property
    def service_name(self) -> str:
        return "CloudWatchMetricsService"
    
    async def initialize(self) -> None:
        """Initialize CloudWatch client."""
        # Would initialize CloudWatch client here
        logger.info("CloudWatchMetricsService initialized")
    
    async def cleanup(self) -> None:
        """Cleanup CloudWatch client."""
        # Would cleanup CloudWatch client here
        logger.info("CloudWatchMetricsService cleaned up")
    
    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record a metric value to CloudWatch."""
        try:
            # In real implementation, would use boto3 CloudWatch client
            # cloudwatch.put_metric_data(
            #     Namespace=self.namespace,
            #     MetricData=[{
            #         'MetricName': metric_name,
            #         'Value': value,
            #         'Dimensions': [{'Name': k, 'Value': v} for k, v in (tags or {}).items()]
            #     }]
            # )
            
            logger.info(f"CloudWatch METRIC: {metric_name}={value} {tags or {}}")
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error recording CloudWatch metric: {e}")
            return ServiceResult.error(
                error="Failed to record CloudWatch metric",
                error_code="CLOUDWATCH_METRIC_ERROR"
            )
    
    async def increment_counter(
        self, 
        counter_name: str, 
        increment: int = 1, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Increment a counter metric in CloudWatch."""
        return await self.record_metric(counter_name, float(increment), tags)
    
    async def record_duration(
        self, 
        operation_name: str, 
        duration_ms: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> ServiceResult[bool]:
        """Record operation duration in CloudWatch."""
        metric_name = f"{operation_name}_duration"
        
        # Record both the duration value and count
        await self.record_metric(metric_name, duration_ms, tags)
        await self.increment_counter(f"{operation_name}_count", 1, tags)
        
        return ServiceResult.success(True)
    
    async def get_metrics(
        self, 
        metric_names: List[str], 
        time_range: Optional[tuple] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Get metric values from CloudWatch."""
        try:
            # In real implementation, would use CloudWatch get_metric_statistics
            logger.info(f"Getting CloudWatch metrics: {metric_names}")
            
            # Placeholder result
            result = {
                "metrics": [],
                "source": "cloudwatch",
                "namespace": self.namespace
            }
            
            return ServiceResult.success(result)
            
        except Exception as e:
            logger.error(f"Error getting CloudWatch metrics: {e}")
            return ServiceResult.error(
                error="Failed to get CloudWatch metrics",
                error_code="CLOUDWATCH_GET_ERROR"
            )

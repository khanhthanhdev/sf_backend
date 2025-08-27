"""
Cache monitoring and metrics collection for Redis caching strategies.

This module provides comprehensive monitoring, alerting, and analytics
for cache performance and usage patterns.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

from .redis import redis_manager, RedisKeyManager
from .cache import cache_manager, CacheConfig
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CacheMetrics:
    """Data class for cache metrics."""
    timestamp: datetime
    hits: int
    misses: int
    sets: int
    deletes: int
    invalidations: int
    hit_rate: float
    memory_usage: int
    key_count: int
    avg_ttl: float
    top_keys: List[str]
    slow_operations: List[Dict[str, Any]]


@dataclass
class CacheAlert:
    """Data class for cache alerts."""
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]
    threshold: Optional[float] = None
    current_value: Optional[float] = None


class CacheMonitor:
    """Advanced cache monitoring with alerting and analytics."""
    
    def __init__(self):
        self._metrics_history = deque(maxlen=1000)  # Keep last 1000 metric snapshots
        self._alerts = deque(maxlen=100)  # Keep last 100 alerts
        self._slow_operations = deque(maxlen=50)  # Track slow operations
        self._key_access_patterns = defaultdict(int)
        self._monitoring_enabled = True
        
        # Alert thresholds
        self._thresholds = {
            "hit_rate_low": 70.0,  # Alert if hit rate below 70%
            "memory_usage_high": 80.0,  # Alert if memory usage above 80%
            "slow_operation_threshold": 1.0,  # Alert if operation takes > 1 second
            "error_rate_high": 5.0,  # Alert if error rate above 5%
            "key_count_high": 10000,  # Alert if key count above 10k
        }
    
    async def collect_metrics(self) -> CacheMetrics:
        """
        Collect comprehensive cache metrics.
        
        Returns:
            CacheMetrics object with current metrics
        """
        try:
            redis_client = redis_manager.redis
            
            # Get basic cache stats
            cache_stats = cache_manager.get_stats()
            
            # Get Redis memory info
            redis_info = await redis_client.info("memory")
            memory_usage = redis_info.get("used_memory", 0)
            
            # Get key count and sample keys
            key_count = await redis_client.dbsize()
            sample_keys = await redis_client.keys("cache:*", count=10)
            
            # Calculate average TTL for sample keys
            avg_ttl = await self._calculate_avg_ttl(sample_keys)
            
            # Get top accessed keys
            top_keys = await self._get_top_keys()
            
            # Get recent slow operations
            slow_operations = list(self._slow_operations)
            
            metrics = CacheMetrics(
                timestamp=datetime.utcnow(),
                hits=cache_stats["hits"],
                misses=cache_stats["misses"],
                sets=cache_stats["sets"],
                deletes=cache_stats["deletes"],
                invalidations=cache_stats["invalidations"],
                hit_rate=cache_stats["hit_rate"],
                memory_usage=memory_usage,
                key_count=key_count,
                avg_ttl=avg_ttl,
                top_keys=top_keys,
                slow_operations=slow_operations
            )
            
            # Store metrics in history
            self._metrics_history.append(metrics)
            
            # Check for alerts
            await self._check_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")
            # Return empty metrics on error
            return CacheMetrics(
                timestamp=datetime.utcnow(),
                hits=0, misses=0, sets=0, deletes=0, invalidations=0,
                hit_rate=0.0, memory_usage=0, key_count=0, avg_ttl=0.0,
                top_keys=[], slow_operations=[]
            )
    
    async def _calculate_avg_ttl(self, keys: List[str]) -> float:
        """Calculate average TTL for a sample of keys."""
        if not keys:
            return 0.0
        
        try:
            redis_client = redis_manager.redis
            ttls = []
            
            for key in keys:
                ttl = await redis_client.ttl(key)
                if ttl > 0:  # Only include keys with positive TTL
                    ttls.append(ttl)
            
            return sum(ttls) / len(ttls) if ttls else 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate average TTL: {e}")
            return 0.0
    
    async def _get_top_keys(self, limit: int = 10) -> List[str]:
        """Get top accessed keys based on access patterns."""
        try:
            # Sort by access count and return top keys
            sorted_keys = sorted(
                self._key_access_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return [key for key, _ in sorted_keys[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to get top keys: {e}")
            return []
    
    async def _check_alerts(self, metrics: CacheMetrics) -> None:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        
        # Check hit rate
        if metrics.hit_rate < self._thresholds["hit_rate_low"]:
            alerts.append(CacheAlert(
                alert_type="low_hit_rate",
                severity="medium",
                message=f"Cache hit rate is low: {metrics.hit_rate}%",
                timestamp=datetime.utcnow(),
                metrics={"hit_rate": metrics.hit_rate},
                threshold=self._thresholds["hit_rate_low"],
                current_value=metrics.hit_rate
            ))
        
        # Check memory usage (if we can get max memory)
        try:
            redis_client = redis_manager.redis
            redis_config = await redis_client.config_get("maxmemory")
            max_memory = int(redis_config.get("maxmemory", 0))
            
            if max_memory > 0:
                memory_usage_percent = (metrics.memory_usage / max_memory) * 100
                if memory_usage_percent > self._thresholds["memory_usage_high"]:
                    alerts.append(CacheAlert(
                        alert_type="high_memory_usage",
                        severity="high",
                        message=f"Cache memory usage is high: {memory_usage_percent:.1f}%",
                        timestamp=datetime.utcnow(),
                        metrics={"memory_usage_percent": memory_usage_percent},
                        threshold=self._thresholds["memory_usage_high"],
                        current_value=memory_usage_percent
                    ))
        except Exception as e:
            logger.debug(f"Could not check memory usage: {e}")
        
        # Check key count
        if metrics.key_count > self._thresholds["key_count_high"]:
            alerts.append(CacheAlert(
                alert_type="high_key_count",
                severity="medium",
                message=f"High number of cache keys: {metrics.key_count}",
                timestamp=datetime.utcnow(),
                metrics={"key_count": metrics.key_count},
                threshold=self._thresholds["key_count_high"],
                current_value=metrics.key_count
            ))
        
        # Check for slow operations
        recent_slow_ops = [
            op for op in metrics.slow_operations
            if datetime.fromisoformat(op["timestamp"]) > datetime.utcnow() - timedelta(minutes=5)
        ]
        
        if len(recent_slow_ops) > 3:  # More than 3 slow operations in 5 minutes
            alerts.append(CacheAlert(
                alert_type="frequent_slow_operations",
                severity="medium",
                message=f"Frequent slow cache operations detected: {len(recent_slow_ops)} in last 5 minutes",
                timestamp=datetime.utcnow(),
                metrics={"slow_operations_count": len(recent_slow_ops)},
                threshold=3,
                current_value=len(recent_slow_ops)
            ))
        
        # Store alerts
        for alert in alerts:
            self._alerts.append(alert)
            logger.warning(f"Cache alert: {alert.message}")
    
    def track_key_access(self, key: str) -> None:
        """Track key access patterns for analytics."""
        if self._monitoring_enabled:
            self._key_access_patterns[key] += 1
    
    def track_slow_operation(
        self,
        operation: str,
        duration: float,
        key: str = None,
        details: Dict[str, Any] = None
    ) -> None:
        """Track slow cache operations."""
        if duration > self._thresholds["slow_operation_threshold"]:
            slow_op = {
                "operation": operation,
                "duration": duration,
                "key": key,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            self._slow_operations.append(slow_op)
            logger.warning(f"Slow cache operation: {operation} took {duration:.2f}s")
    
    def get_metrics_history(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[CacheMetrics]:
        """
        Get historical metrics data.
        
        Args:
            hours: Number of hours of history to return
            limit: Maximum number of data points
            
        Returns:
            List of historical metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_metrics = [
            metrics for metrics in self._metrics_history
            if metrics.timestamp > cutoff_time
        ]
        
        # Return most recent metrics if we have more than limit
        if len(filtered_metrics) > limit:
            return filtered_metrics[-limit:]
        
        return filtered_metrics
    
    def get_alerts(
        self,
        severity: Optional[str] = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[CacheAlert]:
        """
        Get recent alerts.
        
        Args:
            severity: Filter by severity level
            hours: Number of hours of history
            limit: Maximum number of alerts
            
        Returns:
            List of alerts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_alerts = [
            alert for alert in self._alerts
            if alert.timestamp > cutoff_time
        ]
        
        if severity:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert.severity == severity
            ]
        
        # Return most recent alerts
        if len(filtered_alerts) > limit:
            return filtered_alerts[-limit:]
        
        return filtered_alerts
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary and recommendations."""
        if not self._metrics_history:
            return {"error": "No metrics data available"}
        
        recent_metrics = list(self._metrics_history)[-10:]  # Last 10 snapshots
        
        # Calculate averages
        avg_hit_rate = sum(m.hit_rate for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
        avg_keys = sum(m.key_count for m in recent_metrics) / len(recent_metrics)
        
        # Generate recommendations
        recommendations = []
        
        if avg_hit_rate < 80:
            recommendations.append("Consider increasing cache TTL for frequently accessed data")
        
        if avg_keys > 5000:
            recommendations.append("Consider implementing cache key cleanup policies")
        
        if len(self._slow_operations) > 10:
            recommendations.append("Investigate slow cache operations and optimize queries")
        
        # Get top cache patterns
        top_patterns = {}
        for key in self._key_access_patterns:
            pattern = key.split(':')[1] if ':' in key else 'unknown'
            top_patterns[pattern] = top_patterns.get(pattern, 0) + self._key_access_patterns[key]
        
        return {
            "performance_summary": {
                "avg_hit_rate": round(avg_hit_rate, 2),
                "avg_memory_usage": int(avg_memory),
                "avg_key_count": int(avg_keys),
                "total_slow_operations": len(self._slow_operations),
                "active_alerts": len([a for a in self._alerts if a.timestamp > datetime.utcnow() - timedelta(hours=1)])
            },
            "top_cache_patterns": dict(sorted(top_patterns.items(), key=lambda x: x[1], reverse=True)[:5]),
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def set_threshold(self, threshold_name: str, value: float) -> bool:
        """Update alert threshold."""
        if threshold_name in self._thresholds:
            self._thresholds[threshold_name] = value
            logger.info(f"Updated threshold {threshold_name} to {value}")
            return True
        return False
    
    def enable_monitoring(self) -> None:
        """Enable cache monitoring."""
        self._monitoring_enabled = True
        logger.info("Cache monitoring enabled")
    
    def disable_monitoring(self) -> None:
        """Disable cache monitoring."""
        self._monitoring_enabled = False
        logger.info("Cache monitoring disabled")
    
    def reset_metrics(self) -> None:
        """Reset all metrics and history."""
        self._metrics_history.clear()
        self._alerts.clear()
        self._slow_operations.clear()
        self._key_access_patterns.clear()
        cache_manager.reset_stats()
        logger.info("Cache metrics reset")


# Global cache monitor instance
cache_monitor = CacheMonitor()


# Monitoring utilities
async def start_metrics_collection(interval: int = 60) -> None:
    """
    Start periodic metrics collection.
    
    Args:
        interval: Collection interval in seconds
    """
    logger.info(f"Starting cache metrics collection with {interval}s interval")
    
    while True:
        try:
            await cache_monitor.collect_metrics()
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            await asyncio.sleep(interval)


async def generate_cache_report() -> Dict[str, Any]:
    """Generate comprehensive cache performance report."""
    try:
        current_metrics = await cache_monitor.collect_metrics()
        performance_summary = cache_monitor.get_performance_summary()
        recent_alerts = cache_monitor.get_alerts(hours=24)
        
        return {
            "report_timestamp": datetime.utcnow().isoformat(),
            "current_metrics": asdict(current_metrics),
            "performance_summary": performance_summary,
            "recent_alerts": [asdict(alert) for alert in recent_alerts],
            "cache_health": "healthy" if current_metrics.hit_rate > 70 else "needs_attention"
        }
        
    except Exception as e:
        logger.error(f"Failed to generate cache report: {e}")
        return {
            "error": str(e),
            "report_timestamp": datetime.utcnow().isoformat()
        }
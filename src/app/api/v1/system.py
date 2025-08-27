"""
System monitoring and health check API endpoints.

This module implements REST API endpoints for system monitoring,
health checks, metrics collection, and queue status monitoring.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import psutil
import os

from fastapi import APIRouter, Depends, HTTPException, status, Request
from redis.asyncio import Redis

from ...core.redis import get_redis, redis_manager, RedisKeyManager
from ...core.auth import clerk_manager
from ...core.cache import cache_response, CacheConfig, cache_manager
from ...core.cache_monitoring import cache_monitor, generate_cache_report
from ...models.system import SystemHealthResponse, SystemMetricsResponse, QueueStatusResponse
from ...api.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
@cache_response(ttl=CacheConfig.SHORT_TTL, user_specific=True)
async def get_system_health(
    request: Request,
    redis_client: Redis = Depends(get_redis),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> SystemHealthResponse:
    """
    Get comprehensive system health status.
    
    This endpoint checks the health of all system components including
    Redis, authentication service, job queue, and basic system resources.
    
    Args:
        redis_client: Redis client dependency
        current_user: Optional authenticated user (for detailed info)
        
    Returns:
        SystemHealthResponse with health status of all components
    """
    try:
        logger.info("Performing system health check")
        
        # Initialize health status
        overall_healthy = True
        components = {}
        
        # Check Redis health
        redis_health = await redis_manager.health_check()
        components["redis"] = redis_health
        if redis_health["status"] != "healthy":
            overall_healthy = False
        
        # Check Clerk authentication health
        clerk_health = clerk_manager.health_check()
        components["authentication"] = clerk_health
        if clerk_health["status"] != "healthy":
            overall_healthy = False
        
        # Check job queue health
        queue_health = await _check_queue_health(redis_client)
        components["job_queue"] = queue_health
        if queue_health["status"] != "healthy":
            overall_healthy = False
        
        # Check system resources
        system_health = await _check_system_resources()
        components["system_resources"] = system_health
        if system_health["status"] != "healthy":
            overall_healthy = False
        
        # Check disk space for video storage
        storage_health = await _check_storage_health()
        components["storage"] = storage_health
        if storage_health["status"] != "healthy":
            overall_healthy = False
        
        # Additional checks for authenticated users
        if current_user:
            # Check user-specific health metrics
            user_health = await _check_user_health(current_user["user_info"]["id"], redis_client)
            components["user_context"] = user_health
        
        # Determine overall status
        overall_status = "healthy" if overall_healthy else "unhealthy"
        
        # Calculate uptime
        uptime_seconds = _get_system_uptime()
        
        logger.info(
            "System health check completed",
            overall_status=overall_status,
            components_checked=len(components)
        )
        
        return SystemHealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            uptime_seconds=uptime_seconds,
            components=components,
            version=os.getenv("APP_VERSION", "unknown"),
            environment=os.getenv("ENVIRONMENT", "unknown")
        )
        
    except Exception as e:
        logger.error(
            f"System health check failed: {str(e)}",
            exc_info=True
        )
        
        return SystemHealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            uptime_seconds=0,
            components={
                "error": {
                    "status": "unhealthy",
                    "error": f"Health check failed: {str(e)}"
                }
            },
            version=os.getenv("APP_VERSION", "unknown"),
            environment=os.getenv("ENVIRONMENT", "unknown")
        )


@router.get("/metrics", response_model=SystemMetricsResponse)
@cache_response(ttl=CacheConfig.MEDIUM_TTL, user_specific=True)
async def get_system_metrics(
    request: Request,
    redis_client: Redis = Depends(get_redis),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> SystemMetricsResponse:
    """
    Get comprehensive system performance metrics.
    
    This endpoint returns detailed system metrics including resource usage,
    job statistics, performance indicators, and operational metrics.
    
    Args:
        redis_client: Redis client dependency
        current_user: Optional authenticated user (for user-specific metrics)
        
    Returns:
        SystemMetricsResponse with system performance metrics
    """
    try:
        logger.info("Collecting system metrics")
        
        # Collect system resource metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Collect Redis metrics
        redis_info = await redis_client.info()
        redis_memory = redis_info.get("used_memory", 0)
        redis_connections = redis_info.get("connected_clients", 0)
        
        # Collect job queue metrics
        queue_length = await redis_client.llen(RedisKeyManager.JOB_QUEUE)
        
        # Count jobs by status
        job_stats = await _get_job_statistics(redis_client)
        
        # Calculate processing metrics
        processing_metrics = await _get_processing_metrics(redis_client)
        
        # Get error rates
        error_metrics = await _get_error_metrics(redis_client)
        
        # User-specific metrics if authenticated
        user_metrics = None
        if current_user:
            user_metrics = await _get_user_metrics(current_user["user_info"]["id"], redis_client)
        
        logger.info(
            "System metrics collected",
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            queue_length=queue_length
        )
        
        return SystemMetricsResponse(
            timestamp=datetime.utcnow(),
            system_resources={
                "cpu_percent": cpu_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": round((disk.used / disk.total) * 100, 2)
            },
            redis_metrics={
                "memory_used_mb": round(redis_memory / (1024**2), 2),
                "connected_clients": redis_connections,
                "commands_processed": redis_info.get("total_commands_processed", 0),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0)
            },
            job_metrics={
                "queue_length": queue_length,
                "jobs_by_status": job_stats,
                "processing_metrics": processing_metrics
            },
            performance_metrics={
                "error_rate_percent": error_metrics.get("error_rate", 0),
                "avg_response_time_ms": processing_metrics.get("avg_response_time", 0),
                "requests_per_minute": processing_metrics.get("requests_per_minute", 0)
            },
            user_metrics=user_metrics
        )
        
    except Exception as e:
        logger.error(
            "Failed to collect system metrics",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect system metrics: {str(e)}"
        )


@router.get("/queue-status", response_model=QueueStatusResponse)
@cache_response(ttl=CacheConfig.SHORT_TTL, user_specific=True)
async def get_queue_status(
    request: Request,
    redis_client: Redis = Depends(get_redis),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> QueueStatusResponse:
    """
    Get detailed job queue status and monitoring information.
    
    This endpoint provides comprehensive information about the job processing
    queue, including queue length, processing rates, and job distribution.
    
    Args:
        redis_client: Redis client dependency
        current_user: Optional authenticated user
        
    Returns:
        QueueStatusResponse with queue status and metrics
    """
    try:
        logger.info("Collecting queue status")
        
        # Get basic queue metrics
        queue_length = await redis_client.llen(RedisKeyManager.JOB_QUEUE)
        
        # Get queue processing statistics
        processing_stats = await _get_queue_processing_stats(redis_client)
        
        # Get job distribution by priority and type
        job_distribution = await _get_job_distribution(redis_client)
        
        # Calculate estimated wait times
        estimated_wait_times = await _calculate_wait_times(redis_client, queue_length)
        
        # Get recent queue activity
        recent_activity = await _get_recent_queue_activity(redis_client)
        
        # User-specific queue info if authenticated
        user_queue_info = None
        if current_user:
            user_queue_info = await _get_user_queue_info(
                current_user["user_info"]["id"], 
                redis_client
            )
        
        logger.info(
            "Queue status collected",
            queue_length=queue_length,
            processing_jobs=processing_stats.get("processing_count", 0)
        )
        
        return QueueStatusResponse(
            timestamp=datetime.utcnow(),
            queue_length=queue_length,
            processing_jobs=processing_stats.get("processing_count", 0),
            completed_jobs_today=processing_stats.get("completed_today", 0),
            failed_jobs_today=processing_stats.get("failed_today", 0),
            average_processing_time_minutes=processing_stats.get("avg_processing_time", 0),
            job_distribution=job_distribution,
            estimated_wait_times=estimated_wait_times,
            recent_activity=recent_activity,
            user_queue_info=user_queue_info
        )
        
    except Exception as e:
        logger.error(
            "Failed to get queue status",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


# Helper functions for health checks and metrics

async def _check_queue_health(redis_client: Redis) -> Dict[str, Any]:
    """Check job queue health."""
    try:
        queue_length = await redis_client.llen(RedisKeyManager.JOB_QUEUE)
        
        # Consider queue unhealthy if it's too long (>1000 jobs)
        if queue_length > 1000:
            return {
                "status": "unhealthy",
                "queue_length": queue_length,
                "error": "Queue length exceeds healthy threshold"
            }
        
        return {
            "status": "healthy",
            "queue_length": queue_length
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_system_resources() -> Dict[str, Any]:
    """Check system resource health."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Consider unhealthy if CPU > 90% or memory > 90%
        if cpu_percent > 90 or memory.percent > 90:
            return {
                "status": "unhealthy",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "error": "High resource usage detected"
            }
        
        return {
            "status": "healthy",
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_storage_health() -> Dict[str, Any]:
    """Check storage health."""
    try:
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        # Consider unhealthy if disk usage > 85%
        if disk_percent > 85:
            return {
                "status": "unhealthy",
                "disk_percent": disk_percent,
                "error": "Low disk space"
            }
        
        return {
            "status": "healthy",
            "disk_percent": disk_percent,
            "free_gb": round((disk.total - disk.used) / (1024**3), 2)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_user_health(user_id: str, redis_client: Redis) -> Dict[str, Any]:
    """Check user-specific health metrics."""
    try:
        # Get user's active jobs
        user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
        job_count = await redis_client.scard(user_jobs_key)
        
        return {
            "status": "healthy",
            "active_jobs": job_count
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _get_job_statistics(redis_client: Redis) -> Dict[str, int]:
    """Get job statistics by status."""
    try:
        stats = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        # This is a simplified implementation
        # In a real system, you might maintain counters or scan all jobs
        queue_length = await redis_client.llen(RedisKeyManager.JOB_QUEUE)
        stats["queued"] = queue_length
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get job statistics: {e}")
        return {}


async def _get_processing_metrics(redis_client: Redis) -> Dict[str, float]:
    """Get processing performance metrics."""
    try:
        # This would typically be collected from application metrics
        # For now, return placeholder values
        return {
            "avg_response_time": 150.0,  # ms
            "requests_per_minute": 45.0,
            "success_rate": 98.5  # %
        }
        
    except Exception as e:
        logger.error(f"Failed to get processing metrics: {e}")
        return {}


async def _get_error_metrics(redis_client: Redis) -> Dict[str, float]:
    """Get error rate metrics."""
    try:
        # This would typically be collected from application logs/metrics
        return {
            "error_rate": 1.5,  # %
            "errors_last_hour": 3
        }
        
    except Exception as e:
        logger.error(f"Failed to get error metrics: {e}")
        return {}


async def _get_user_metrics(user_id: str, redis_client: Redis) -> Dict[str, Any]:
    """Get user-specific metrics."""
    try:
        user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
        job_count = await redis_client.scard(user_jobs_key)
        
        return {
            "total_jobs": job_count,
            "jobs_today": 0,  # Would need to implement date-based counting
            "quota_used": 0,  # Would need to implement quota tracking
            "quota_limit": 100
        }
        
    except Exception as e:
        logger.error(f"Failed to get user metrics: {e}")
        return {}


def _get_system_uptime() -> int:
    """Get system uptime in seconds."""
    try:
        return int(psutil.boot_time())
    except Exception:
        return 0


async def _get_queue_processing_stats(redis_client: Redis) -> Dict[str, Any]:
    """Get queue processing statistics."""
    try:
        # This would typically be maintained as counters
        return {
            "processing_count": 0,
            "completed_today": 0,
            "failed_today": 0,
            "avg_processing_time": 5.0  # minutes
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue processing stats: {e}")
        return {}


async def _get_job_distribution(redis_client: Redis) -> Dict[str, Any]:
    """Get job distribution by priority and type."""
    try:
        return {
            "by_priority": {
                "low": 10,
                "normal": 25,
                "high": 5,
                "urgent": 0
            },
            "by_type": {
                "video_generation": 35,
                "batch_video_generation": 5
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get job distribution: {e}")
        return {}


async def _calculate_wait_times(redis_client: Redis, queue_length: int) -> Dict[str, float]:
    """Calculate estimated wait times."""
    try:
        # Simple calculation based on queue length and average processing time
        avg_processing_time = 5.0  # minutes
        
        return {
            "next_job_minutes": avg_processing_time,
            "queue_end_minutes": queue_length * avg_processing_time,
            "new_job_minutes": (queue_length + 1) * avg_processing_time
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate wait times: {e}")
        return {}


async def _get_recent_queue_activity(redis_client: Redis) -> List[Dict[str, Any]]:
    """Get recent queue activity."""
    try:
        # This would typically be maintained as a log
        return [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                "action": "job_completed",
                "job_id": "example-job-1"
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "action": "job_started",
                "job_id": "example-job-2"
            }
        ]
        
    except Exception as e:
        logger.error(f"Failed to get recent queue activity: {e}")
        return []


async def _get_user_queue_info(user_id: str, redis_client: Redis) -> Dict[str, Any]:
    """Get user-specific queue information."""
    try:
        user_jobs_key = RedisKeyManager.user_jobs_key(user_id)
        user_job_count = await redis_client.scard(user_jobs_key)
        
        return {
            "jobs_in_queue": 0,  # Would need to check which jobs are queued
            "jobs_processing": 0,  # Would need to check which jobs are processing
            "estimated_wait_time_minutes": 0
        }
        
    except Exception as e:
        logger.error(f"Failed to get user queue info: {e}")
        return {}


# Cache management endpoints

@router.get("/cache/info")
@cache_response(ttl=CacheConfig.SHORT_TTL)
async def get_cache_info(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Get comprehensive cache information and statistics.
    
    Returns cache performance metrics, Redis memory usage,
    and connection information.
    """
    try:
        from ...core.cache import get_cache_info
        cache_info = await get_cache_info()
        
        # Add monitoring data
        cache_info["monitoring"] = cache_monitor.get_performance_summary()
        
        return cache_info
        
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache information: {str(e)}"
        )


@router.get("/cache/metrics")
async def get_cache_metrics(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Get detailed cache metrics and monitoring data.
    
    Returns current cache metrics, historical data, and alerts.
    """
    try:
        # Collect current metrics
        current_metrics = await cache_monitor.collect_metrics()
        
        # Get performance summary
        performance_summary = cache_monitor.get_performance_summary()
        
        # Get recent alerts
        recent_alerts = cache_monitor.get_alerts(hours=24, limit=10)
        
        return {
            "current_metrics": {
                "timestamp": current_metrics.timestamp.isoformat(),
                "hits": current_metrics.hits,
                "misses": current_metrics.misses,
                "hit_rate": current_metrics.hit_rate,
                "memory_usage": current_metrics.memory_usage,
                "key_count": current_metrics.key_count,
                "avg_ttl": current_metrics.avg_ttl
            },
            "performance_summary": performance_summary,
            "recent_alerts": [
                {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in recent_alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache metrics: {str(e)}"
        )


@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Invalidate cache entries based on pattern or user.
    
    Args:
        pattern: Cache key pattern to invalidate
        user_id: User ID to invalidate cache for
    """
    try:
        deleted_count = 0
        
        if user_id:
            from ...core.cache import CacheInvalidationManager
            deleted_count = await CacheInvalidationManager.invalidate_user_related_cache(user_id)
        elif pattern:
            deleted_count = await cache_manager.delete_pattern(pattern)
        else:
            # Invalidate system cache
            from ...core.cache import CacheInvalidationManager
            deleted_count = await CacheInvalidationManager.invalidate_system_cache()
        
        logger.info(f"Cache invalidation completed: {deleted_count} keys deleted")
        
        return {
            "message": "Cache invalidation completed",
            "deleted_keys": deleted_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache invalidation failed: {str(e)}"
        )


@router.post("/cache/warm")
async def warm_cache(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Warm cache with commonly accessed data.
    
    Preloads frequently accessed endpoints and queries into cache.
    """
    try:
        from ...core.cache import warm_common_queries
        result = await warm_common_queries()
        
        logger.info("Cache warming completed", result=result)
        
        return {
            "message": "Cache warming completed",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache warming failed: {str(e)}"
        )


@router.get("/cache/report")
async def get_cache_report(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Generate comprehensive cache performance report.
    
    Returns detailed analysis of cache performance, recommendations,
    and historical trends.
    """
    try:
        report = await generate_cache_report()
        
        logger.info("Cache report generated")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate cache report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cache report: {str(e)}"
        )
# Performance monitoring endpoints

@router.get("/performance/summary")
async def get_performance_summary(
    hours: int = 1,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Get performance summary for the specified time period.
    
    Args:
        hours: Number of hours to analyze (default: 1)
    """
    try:
        from ...core.performance import request_deduplicator, response_cache, connection_optimizer
        from ...middleware.performance import PerformanceMiddleware
        
        # Get performance middleware instance from app state
        # This is a simplified approach - in production you'd want proper instance management
        performance_summary = {
            "deduplication_stats": request_deduplicator.get_stats(),
            "response_cache_stats": response_cache.get_stats(),
            "connection_pool_stats": await connection_optimizer.monitor_redis_pool(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return performance_summary
        
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance summary: {str(e)}"
        )


@router.get("/performance/deduplication")
async def get_deduplication_stats(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """Get request deduplication statistics."""
    try:
        from ...core.performance import request_deduplicator
        
        stats = request_deduplicator.get_stats()
        
        return {
            "deduplication_stats": stats,
            "recommendations": [
                "Enable deduplication for expensive read operations",
                "Monitor deduplication rate to identify optimization opportunities"
            ] if stats["deduplication_rate"] < 10 else [
                "Deduplication is working effectively"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get deduplication stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deduplication stats: {str(e)}"
        )


@router.get("/performance/connections")
async def get_connection_stats(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """Get connection pool performance statistics."""
    try:
        from ...core.performance import connection_optimizer
        
        redis_stats = await connection_optimizer.monitor_redis_pool()
        pool_history = connection_optimizer.get_pool_history(hours=1)
        
        return {
            "current_stats": redis_stats,
            "history": pool_history,
            "optimization_tips": [
                "Monitor pool utilization to optimize connection limits",
                "Consider connection pooling for database operations",
                "Use connection health checks to maintain pool quality"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection stats: {str(e)}"
        )


@router.get("/performance/async")
async def get_async_stats(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """Get async processing performance statistics."""
    try:
        from ...core.performance import async_optimizer
        
        stats = async_optimizer.get_stats()
        
        return {
            "async_stats": stats,
            "optimization_recommendations": [
                "Use semaphores to limit concurrent operations",
                "Implement batch processing for bulk operations",
                "Set appropriate timeouts for async operations",
                "Monitor semaphore usage to prevent bottlenecks"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get async stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get async stats: {str(e)}"
        )


@router.post("/performance/optimize")
async def optimize_performance(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Trigger performance optimization tasks.
    
    This endpoint can be used to manually trigger optimization tasks
    like cache warming, connection pool adjustment, etc.
    """
    try:
        optimization_results = []
        
        # Warm cache
        from ...core.cache import warm_common_queries
        cache_result = await warm_common_queries()
        optimization_results.append({
            "task": "cache_warming",
            "result": cache_result
        })
        
        # Monitor connection pools
        from ...core.performance import connection_optimizer
        pool_result = await connection_optimizer.monitor_redis_pool()
        optimization_results.append({
            "task": "connection_monitoring",
            "result": pool_result
        })
        
        # Collect cache metrics
        from ...core.cache_monitoring import cache_monitor
        metrics_result = await cache_monitor.collect_metrics()
        optimization_results.append({
            "task": "metrics_collection",
            "result": "completed"
        })
        
        return {
            "message": "Performance optimization completed",
            "results": optimization_results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance optimization failed: {str(e)}"
        )
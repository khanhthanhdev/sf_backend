"""
API performance optimization utilities and middleware.

This module provides response caching, request deduplication,
connection pooling optimization, and async processing enhancements.
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from dataclasses import dataclass
import weakref

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .redis import redis_manager, RedisKeyManager
from .cache import cache_manager, CacheConfig, CacheKeyGenerator
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    endpoint: str
    method: str
    response_time: float
    status_code: int
    timestamp: datetime
    cache_hit: bool = False
    deduplication_hit: bool = False
    user_id: Optional[str] = None


class RequestDeduplicator:
    """
    Request deduplication for expensive operations.
    
    Prevents multiple identical requests from being processed simultaneously
    by caching in-flight requests and returning the same result.
    """
    
    def __init__(self):
        self._in_flight_requests: Dict[str, asyncio.Future] = {}
        self._request_counts = defaultdict(int)
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _generate_request_key(
        self,
        method: str,
        path: str,
        query_params: Dict[str, Any],
        body_hash: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Generate unique key for request deduplication."""
        key_parts = [method, path]
        
        if user_id:
            key_parts.append(f"user:{user_id}")
        
        if query_params:
            sorted_params = sorted(query_params.items())
            params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
            key_parts.append(f"params:{params_str}")
        
        if body_hash:
            key_parts.append(f"body:{body_hash}")
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def deduplicate_request(
        self,
        request_key: str,
        request_func: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, bool]:
        """
        Deduplicate request execution.
        
        Args:
            request_key: Unique key for the request
            request_func: Function to execute if not in flight
            *args: Arguments for request_func
            **kwargs: Keyword arguments for request_func
            
        Returns:
            Tuple of (result, was_deduplicated)
        """
        # Cleanup old requests periodically
        await self._cleanup_old_requests()
        
        # Check if request is already in flight
        if request_key in self._in_flight_requests:
            logger.debug(f"Request deduplication hit for key: {request_key}")
            self._request_counts[request_key] += 1
            
            try:
                result = await self._in_flight_requests[request_key]
                return result, True
            except Exception as e:
                # If the in-flight request failed, remove it and retry
                self._in_flight_requests.pop(request_key, None)
                logger.warning(f"In-flight request failed, retrying: {e}")
        
        # Create new future for this request
        future = asyncio.create_task(request_func(*args, **kwargs))
        self._in_flight_requests[request_key] = future
        self._request_counts[request_key] += 1
        
        try:
            result = await future
            return result, False
        except Exception as e:
            logger.error(f"Request execution failed for key {request_key}: {e}")
            raise
        finally:
            # Remove completed request
            self._in_flight_requests.pop(request_key, None)
    
    async def _cleanup_old_requests(self):
        """Clean up completed or stale requests."""
        current_time = time.time()
        
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        # Remove completed futures
        completed_keys = [
            key for key, future in self._in_flight_requests.items()
            if future.done()
        ]
        
        for key in completed_keys:
            self._in_flight_requests.pop(key, None)
        
        # Reset request counts periodically
        self._request_counts.clear()
        self._last_cleanup = current_time
        
        logger.debug(f"Cleaned up {len(completed_keys)} completed requests")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        total_requests = sum(self._request_counts.values())
        unique_requests = len(self._request_counts)
        deduplication_rate = (
            ((total_requests - unique_requests) / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        return {
            "total_requests": total_requests,
            "unique_requests": unique_requests,
            "in_flight_requests": len(self._in_flight_requests),
            "deduplication_rate": round(deduplication_rate, 2),
            "timestamp": datetime.utcnow().isoformat()
        }


class ResponseCache:
    """
    Advanced response caching for static and semi-static data.
    
    Provides intelligent caching with TTL, conditional requests,
    and cache warming capabilities.
    """
    
    def __init__(self):
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0
        }
    
    async def get_cached_response(
        self,
        cache_key: str,
        etag: Optional[str] = None,
        last_modified: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response with conditional request support.
        
        Args:
            cache_key: Cache key for the response
            etag: ETag for conditional requests
            last_modified: Last modified timestamp
            
        Returns:
            Cached response data or None
        """
        try:
            cached_data = await cache_manager.get(cache_key)
            
            if cached_data is None:
                self._cache_stats["misses"] += 1
                return None
            
            # Check conditional request headers
            if etag and cached_data.get("etag") == etag:
                self._cache_stats["hits"] += 1
                return {"status": "not_modified", "etag": etag}
            
            if last_modified and cached_data.get("last_modified"):
                cached_modified = datetime.fromisoformat(cached_data["last_modified"])
                if cached_modified <= last_modified:
                    self._cache_stats["hits"] += 1
                    return {"status": "not_modified", "last_modified": cached_modified}
            
            self._cache_stats["hits"] += 1
            return cached_data
            
        except Exception as e:
            logger.error(f"Failed to get cached response: {e}")
            self._cache_stats["misses"] += 1
            return None
    
    async def cache_response(
        self,
        cache_key: str,
        response_data: Any,
        ttl: int = CacheConfig.DEFAULT_TTL,
        etag: Optional[str] = None,
        last_modified: Optional[datetime] = None,
        vary_headers: Optional[List[str]] = None
    ) -> bool:
        """
        Cache response with metadata.
        
        Args:
            cache_key: Cache key for the response
            response_data: Response data to cache
            ttl: Time to live in seconds
            etag: ETag for the response
            last_modified: Last modified timestamp
            vary_headers: Headers that affect caching
            
        Returns:
            True if successful
        """
        try:
            cache_data = {
                "data": response_data,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl": ttl
            }
            
            if etag:
                cache_data["etag"] = etag
            
            if last_modified:
                cache_data["last_modified"] = last_modified.isoformat()
            
            if vary_headers:
                cache_data["vary_headers"] = vary_headers
            
            success = await cache_manager.set(cache_key, cache_data, ttl)
            if success:
                self._cache_stats["sets"] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
            return False
    
    async def invalidate_response_cache(self, pattern: str) -> int:
        """Invalidate cached responses matching pattern."""
        try:
            deleted = await cache_manager.delete_pattern(pattern)
            self._cache_stats["invalidations"] += 1
            return deleted
        except Exception as e:
            logger.error(f"Failed to invalidate response cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get response cache statistics."""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            (self._cache_stats["hits"] / total_requests * 100)
            if total_requests > 0 else 0
        )
        
        return {
            **self._cache_stats,
            "hit_rate": round(hit_rate, 2),
            "timestamp": datetime.utcnow().isoformat()
        }


class ConnectionPoolOptimizer:
    """
    Connection pool optimization for database and Redis connections.
    
    Monitors connection usage and provides optimization recommendations.
    """
    
    def __init__(self):
        self._connection_metrics = deque(maxlen=1000)
        self._pool_stats = {}
    
    async def monitor_redis_pool(self) -> Dict[str, Any]:
        """Monitor Redis connection pool performance."""
        try:
            pool_info = await redis_manager.get_connection_info()
            
            # Calculate pool utilization
            max_connections = pool_info.get("max_connections", 0)
            in_use = pool_info.get("in_use_connections", 0)
            available = pool_info.get("available_connections", 0)
            
            utilization = (in_use / max_connections * 100) if max_connections > 0 else 0
            
            metrics = {
                "timestamp": datetime.utcnow(),
                "max_connections": max_connections,
                "in_use_connections": in_use,
                "available_connections": available,
                "utilization_percent": round(utilization, 2),
                "pool_type": "redis"
            }
            
            self._connection_metrics.append(metrics)
            
            # Generate recommendations
            recommendations = []
            if utilization > 80:
                recommendations.append("Consider increasing Redis connection pool size")
            elif utilization < 20:
                recommendations.append("Consider reducing Redis connection pool size")
            
            return {
                "current_metrics": metrics,
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Failed to monitor Redis pool: {e}")
            return {"error": str(e)}
    
    def get_pool_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get connection pool history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            {
                "timestamp": metric["timestamp"].isoformat(),
                "utilization_percent": metric["utilization_percent"],
                "in_use_connections": metric["in_use_connections"],
                "pool_type": metric["pool_type"]
            }
            for metric in self._connection_metrics
            if metric["timestamp"] > cutoff_time
        ]


class AsyncProcessingOptimizer:
    """
    Async processing optimization utilities.
    
    Provides utilities for optimizing async operations, batch processing,
    and concurrent request handling.
    """
    
    def __init__(self):
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._batch_processors: Dict[str, List] = defaultdict(list)
        self._processing_stats = defaultdict(int)
    
    def get_semaphore(self, resource: str, limit: int = 10) -> asyncio.Semaphore:
        """Get or create semaphore for resource limiting."""
        if resource not in self._semaphores:
            self._semaphores[resource] = asyncio.Semaphore(limit)
        return self._semaphores[resource]
    
    @asynccontextmanager
    async def limit_concurrency(self, resource: str, limit: int = 10):
        """Context manager for limiting concurrent operations."""
        semaphore = self.get_semaphore(resource, limit)
        async with semaphore:
            self._processing_stats[f"{resource}_concurrent"] += 1
            try:
                yield
            finally:
                self._processing_stats[f"{resource}_concurrent"] -= 1
    
    async def batch_process(
        self,
        items: List[Any],
        processor: Callable,
        batch_size: int = 10,
        max_concurrency: int = 5
    ) -> List[Any]:
        """
        Process items in batches with concurrency control.
        
        Args:
            items: Items to process
            processor: Async function to process each item
            batch_size: Number of items per batch
            max_concurrency: Maximum concurrent batches
            
        Returns:
            List of processed results
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_batch(batch):
            async with semaphore:
                batch_results = await asyncio.gather(
                    *[processor(item) for item in batch],
                    return_exceptions=True
                )
                return batch_results
        
        # Create batches
        batches = [
            items[i:i + batch_size]
            for i in range(0, len(items), batch_size)
        ]
        
        # Process batches concurrently
        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks)
        
        # Flatten results
        for batch_result in batch_results:
            results.extend(batch_result)
        
        self._processing_stats["batch_operations"] += 1
        self._processing_stats["items_processed"] += len(items)
        
        return results
    
    async def timeout_operation(
        self,
        operation: Callable,
        timeout_seconds: float,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with timeout."""
        try:
            return await asyncio.wait_for(
                operation(*args, **kwargs),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            self._processing_stats["timeouts"] += 1
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get async processing statistics."""
        return {
            "processing_stats": dict(self._processing_stats),
            "active_semaphores": {
                resource: semaphore._value
                for resource, semaphore in self._semaphores.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Performance monitoring and optimization middleware.
    
    Tracks request performance, applies optimizations,
    and collects metrics for analysis.
    """
    
    def __init__(self, app, enable_deduplication: bool = True):
        super().__init__(app)
        self.enable_deduplication = enable_deduplication
        self.deduplicator = RequestDeduplicator()
        self.response_cache = ResponseCache()
        self.metrics_history = deque(maxlen=1000)
        
        # Endpoints that benefit from deduplication
        self.deduplication_endpoints = {
            "/api/v1/system/health",
            "/api/v1/system/metrics",
            "/api/v1/system/queue-status",
            "/api/v1/jobs",
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request with performance optimizations."""
        start_time = time.time()
        
        # Extract user ID if available
        user_id = getattr(request.state, "user_id", None)
        
        # Check if endpoint should use deduplication
        should_deduplicate = (
            self.enable_deduplication and
            request.method == "GET" and
            request.url.path in self.deduplication_endpoints
        )
        
        response = None
        cache_hit = False
        deduplication_hit = False
        
        if should_deduplicate:
            # Generate request key for deduplication
            body_hash = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                body_hash = hashlib.md5(body).hexdigest() if body else None
            
            request_key = self.deduplicator._generate_request_key(
                request.method,
                request.url.path,
                dict(request.query_params),
                body_hash,
                user_id
            )
            
            # Try deduplication
            try:
                result, deduplication_hit = await self.deduplicator.deduplicate_request(
                    request_key,
                    call_next,
                    request
                )
                response = result
            except Exception as e:
                logger.error(f"Deduplication failed: {e}")
                response = await call_next(request)
        else:
            response = await call_next(request)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000  # ms
        
        # Record metrics
        metrics = PerformanceMetrics(
            endpoint=request.url.path,
            method=request.method,
            response_time=response_time,
            status_code=response.status_code,
            timestamp=datetime.utcnow(),
            cache_hit=cache_hit,
            deduplication_hit=deduplication_hit,
            user_id=user_id
        )
        
        self.metrics_history.append(metrics)
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
        if deduplication_hit:
            response.headers["X-Deduplication-Hit"] = "true"
        if cache_hit:
            response.headers["X-Cache-Hit"] = "true"
        
        return response
    
    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > cutoff_time
        ]
        
        if not recent_metrics:
            return {"message": "No metrics available for the specified period"}
        
        # Calculate statistics
        response_times = [m.response_time for m in recent_metrics]
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # Count by status code
        status_codes = defaultdict(int)
        for m in recent_metrics:
            status_codes[m.status_code] += 1
        
        # Count cache and deduplication hits
        cache_hits = sum(1 for m in recent_metrics if m.cache_hit)
        deduplication_hits = sum(1 for m in recent_metrics if m.deduplication_hit)
        
        # Top endpoints by request count
        endpoint_counts = defaultdict(int)
        for m in recent_metrics:
            endpoint_counts[f"{m.method} {m.endpoint}"] += 1
        
        top_endpoints = sorted(
            endpoint_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "period_hours": hours,
            "total_requests": len(recent_metrics),
            "avg_response_time_ms": round(avg_response_time, 2),
            "max_response_time_ms": round(max_response_time, 2),
            "min_response_time_ms": round(min_response_time, 2),
            "status_codes": dict(status_codes),
            "cache_hit_rate": round((cache_hits / len(recent_metrics)) * 100, 2),
            "deduplication_hit_rate": round((deduplication_hits / len(recent_metrics)) * 100, 2),
            "top_endpoints": top_endpoints,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global instances
request_deduplicator = RequestDeduplicator()
response_cache = ResponseCache()
connection_optimizer = ConnectionPoolOptimizer()
async_optimizer = AsyncProcessingOptimizer()


# Utility functions
async def optimize_database_query(query_func: Callable, *args, **kwargs):
    """Optimize database query with caching and connection pooling."""
    # This would integrate with your database layer
    # For now, just execute the query
    return await query_func(*args, **kwargs)


async def batch_api_calls(
    api_calls: List[Tuple[Callable, tuple, dict]],
    max_concurrency: int = 10
) -> List[Any]:
    """Execute multiple API calls with concurrency control."""
    return await async_optimizer.batch_process(
        api_calls,
        lambda call: call[0](*call[1], **call[2]),
        max_concurrency=max_concurrency
    )


def performance_monitor(func: Callable) -> Callable:
    """Decorator for monitoring function performance."""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000
            
            logger.debug(
                f"Function {func.__name__} executed in {execution_time:.2f}ms"
            )
            
            return result
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                f"Function {func.__name__} failed after {execution_time:.2f}ms: {e}"
            )
            raise
    
    return wrapper
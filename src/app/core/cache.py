"""
Redis caching strategies and decorators for FastAPI endpoints.

This module provides caching decorators, cache invalidation patterns,
cache warming strategies, and monitoring for the video generation API.
"""

import asyncio
import functools
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union, Tuple
from contextlib import asynccontextmanager

from fastapi import Request, Response
from redis.asyncio import Redis

from .redis import redis_manager, RedisKeyManager, safe_redis_operation
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheConfig:
    """Configuration for caching behavior."""
    
    # Default TTL values (in seconds)
    DEFAULT_TTL = 300  # 5 minutes
    SHORT_TTL = 60     # 1 minute
    MEDIUM_TTL = 900   # 15 minutes
    LONG_TTL = 3600    # 1 hour
    VERY_LONG_TTL = 86400  # 24 hours
    
    # Cache key prefixes
    ENDPOINT_CACHE = "endpoint_cache"
    QUERY_CACHE = "query_cache"
    USER_CACHE = "user_cache"
    SYSTEM_CACHE = "system_cache"
    
    # Cache warming settings
    WARM_CACHE_BATCH_SIZE = 10
    WARM_CACHE_DELAY = 0.1  # seconds between batch operations


class CacheKeyGenerator:
    """Utility class for generating consistent cache keys."""
    
    @staticmethod
    def endpoint_key(
        method: str,
        path: str,
        query_params: Dict[str, Any] = None,
        user_id: str = None,
        additional_params: Dict[str, Any] = None
    ) -> str:
        """
        Generate cache key for API endpoint responses.
        
        Args:
            method: HTTP method
            path: Request path
            query_params: Query parameters
            user_id: User ID for user-specific caching
            additional_params: Additional parameters for key generation
            
        Returns:
            Generated cache key
        """
        key_parts = [method.upper(), path]
        
        if user_id:
            key_parts.append(f"user:{user_id}")
        
        if query_params:
            # Sort params for consistent key generation
            sorted_params = sorted(query_params.items())
            params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
            key_parts.append(f"params:{params_str}")
        
        if additional_params:
            sorted_additional = sorted(additional_params.items())
            additional_str = "&".join(f"{k}={v}" for k, v in sorted_additional)
            key_parts.append(f"extra:{additional_str}")
        
        # Create hash for long keys
        key_string = "|".join(key_parts)
        if len(key_string) > 200:  # Redis key length limit consideration
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return RedisKeyManager.cache_key(CacheConfig.ENDPOINT_CACHE, key_hash)
        
        return RedisKeyManager.cache_key(CacheConfig.ENDPOINT_CACHE, key_string)
    
    @staticmethod
    def query_key(query_name: str, params: Dict[str, Any] = None) -> str:
        """Generate cache key for database queries."""
        key_parts = [query_name]
        
        if params:
            sorted_params = sorted(params.items())
            params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
            key_parts.append(params_str)
        
        key_string = "|".join(key_parts)
        return RedisKeyManager.cache_key(CacheConfig.QUERY_CACHE, key_string)
    
    @staticmethod
    def user_key(user_id: str, data_type: str) -> str:
        """Generate cache key for user-specific data."""
        return RedisKeyManager.cache_key(CacheConfig.USER_CACHE, f"{user_id}:{data_type}")
    
    @staticmethod
    def system_key(component: str, metric: str = None) -> str:
        """Generate cache key for system data."""
        key = component
        if metric:
            key = f"{component}:{metric}"
        return RedisKeyManager.cache_key(CacheConfig.SYSTEM_CACHE, key)


class CacheManager:
    """Advanced cache management with invalidation and warming strategies."""
    
    def __init__(self):
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "invalidations": 0
        }
    
    async def get(
        self,
        key: str,
        default: Any = None,
        deserialize: bool = True
    ) -> Any:
        """
        Get value from cache with statistics tracking.
        
        Args:
            key: Cache key
            default: Default value if key doesn't exist
            deserialize: Whether to deserialize JSON data
            
        Returns:
            Cached value or default
        """
        try:
            redis_client = redis_manager.redis
            value = await redis_client.get(key)
            
            if value is None:
                self._cache_stats["misses"] += 1
                return default
            
            self._cache_stats["hits"] += 1
            
            if deserialize:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to deserialize cached value for key: {key}")
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {e}")
            self._cache_stats["misses"] += 1
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = CacheConfig.DEFAULT_TTL,
        serialize: bool = True
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            serialize: Whether to serialize value as JSON
            
        Returns:
            True if successful
        """
        try:
            redis_client = redis_manager.redis
            
            if serialize:
                value = json.dumps(value, default=str)
            
            result = await redis_client.setex(key, ttl, value)
            self._cache_stats["sets"] += 1
            return result
            
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            redis_client = redis_manager.redis
            result = await redis_client.delete(key)
            self._cache_stats["deletes"] += 1
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Redis key pattern (supports wildcards)
            
        Returns:
            Number of keys deleted
        """
        try:
            redis_client = redis_manager.redis
            keys = await redis_client.keys(pattern)
            
            if not keys:
                return 0
            
            deleted = await redis_client.delete(*keys)
            self._cache_stats["deletes"] += deleted
            return deleted
            
        except Exception as e:
            logger.error(f"Cache pattern delete failed for pattern {pattern}: {e}")
            return 0
    
    async def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate all cache entries for a specific user."""
        pattern = RedisKeyManager.cache_key(CacheConfig.USER_CACHE, f"{user_id}:*")
        deleted = await self.delete_pattern(pattern)
        self._cache_stats["invalidations"] += 1
        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
        return deleted
    
    async def invalidate_endpoint_cache(self, path_pattern: str) -> int:
        """Invalidate cache entries for specific endpoint patterns."""
        pattern = RedisKeyManager.cache_key(CacheConfig.ENDPOINT_CACHE, f"*{path_pattern}*")
        deleted = await self.delete_pattern(pattern)
        self._cache_stats["invalidations"] += 1
        logger.info(f"Invalidated {deleted} cache entries for pattern {path_pattern}")
        return deleted
    
    async def warm_cache(
        self,
        warm_functions: List[Tuple[Callable, Dict[str, Any]]],
        batch_size: int = CacheConfig.WARM_CACHE_BATCH_SIZE
    ) -> Dict[str, Any]:
        """
        Warm cache with predefined data.
        
        Args:
            warm_functions: List of (function, kwargs) tuples to execute
            batch_size: Number of operations per batch
            
        Returns:
            Warming results and statistics
        """
        results = {
            "total_functions": len(warm_functions),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for i in range(0, len(warm_functions), batch_size):
            batch = warm_functions[i:i + batch_size]
            
            for func, kwargs in batch:
                try:
                    await func(**kwargs)
                    results["successful"] += 1
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "function": func.__name__,
                        "error": str(e)
                    })
                    logger.error(f"Cache warming failed for {func.__name__}: {e}")
            
            # Small delay between batches to avoid overwhelming the system
            if i + batch_size < len(warm_functions):
                await asyncio.sleep(CacheConfig.WARM_CACHE_DELAY)
        
        logger.info(f"Cache warming completed: {results}")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_operations = sum(self._cache_stats.values())
        hit_rate = (
            self._cache_stats["hits"] / (self._cache_stats["hits"] + self._cache_stats["misses"])
            if (self._cache_stats["hits"] + self._cache_stats["misses"]) > 0
            else 0
        )
        
        return {
            **self._cache_stats,
            "total_operations": total_operations,
            "hit_rate": round(hit_rate * 100, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "invalidations": 0
        }


# Global cache manager instance
cache_manager = CacheManager()


def cache_response(
    ttl: int = CacheConfig.DEFAULT_TTL,
    key_generator: Optional[Callable] = None,
    user_specific: bool = False,
    skip_cache_header: str = "X-Skip-Cache",
    vary_on: List[str] = None
):
    """
    Decorator for caching FastAPI endpoint responses.
    
    Args:
        ttl: Time to live in seconds
        key_generator: Custom key generation function
        user_specific: Whether to include user ID in cache key
        skip_cache_header: Header name to skip cache
        vary_on: List of headers/params to vary cache on
        
    Usage:
        @router.get("/api/v1/jobs")
        @cache_response(ttl=300, user_specific=True)
        async def get_jobs(request: Request, user_id: str = Depends(get_current_user_id)):
            return await job_service.get_jobs(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request object
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request object, execute function without caching
                return await func(*args, **kwargs)
            
            # Check if cache should be skipped
            if request.headers.get(skip_cache_header):
                return await func(*args, **kwargs)
            
            # Generate cache key
            if key_generator:
                cache_key = await key_generator(request, *args, **kwargs)
            else:
                user_id = None
                if user_specific:
                    # Try to extract user_id from kwargs or dependencies
                    user_id = kwargs.get("user_id") or kwargs.get("current_user_id")
                
                vary_params = {}
                if vary_on:
                    for header in vary_on:
                        if header in request.headers:
                            vary_params[header] = request.headers[header]
                
                cache_key = CacheKeyGenerator.endpoint_key(
                    method=request.method,
                    path=request.url.path,
                    query_params=dict(request.query_params),
                    user_id=user_id,
                    additional_params=vary_params
                )
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


def cache_query(
    ttl: int = CacheConfig.DEFAULT_TTL,
    key_prefix: str = "query"
):
    """
    Decorator for caching database query results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Usage:
        @cache_query(ttl=600, key_prefix="user_jobs")
        async def get_user_jobs(user_id: str, status: str = None):
            # Database query logic
            return results
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and parameters
            cache_key = CacheKeyGenerator.query_key(
                f"{key_prefix}:{func.__name__}",
                {**dict(zip(func.__code__.co_varnames, args)), **kwargs}
            )
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Query cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached query result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


class CacheInvalidationManager:
    """Manages cache invalidation patterns and strategies."""
    
    @staticmethod
    async def invalidate_job_related_cache(job_id: str, user_id: str = None):
        """Invalidate all cache entries related to a specific job."""
        patterns_to_invalidate = [
            f"*jobs*{job_id}*",
            f"*job_status*{job_id}*",
            f"*videos*{job_id}*"
        ]
        
        if user_id:
            patterns_to_invalidate.extend([
                f"*user:{user_id}*jobs*",
                f"*user_jobs*{user_id}*"
            ])
        
        total_deleted = 0
        for pattern in patterns_to_invalidate:
            deleted = await cache_manager.delete_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"Invalidated {total_deleted} cache entries for job {job_id}")
        return total_deleted
    
    @staticmethod
    async def invalidate_user_related_cache(user_id: str):
        """Invalidate all cache entries related to a specific user."""
        return await cache_manager.invalidate_user_cache(user_id)
    
    @staticmethod
    async def invalidate_system_cache():
        """Invalidate system-wide cache entries."""
        patterns = [
            f"*{CacheConfig.SYSTEM_CACHE}*",
            "*health*",
            "*metrics*",
            "*queue*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await cache_manager.delete_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"Invalidated {total_deleted} system cache entries")
        return total_deleted


# Cache warming functions
async def warm_common_queries():
    """Warm cache with commonly accessed data."""
    warming_functions = [
        # Add warming functions here as they're implemented
        # (get_system_health, {}),
        # (get_queue_status, {}),
        # (get_popular_jobs, {"limit": 10}),
    ]
    
    if warming_functions:
        return await cache_manager.warm_cache(warming_functions)
    
    return {"message": "No warming functions configured"}


# Utility functions
async def get_cache_info() -> Dict[str, Any]:
    """Get comprehensive cache information and statistics."""
    try:
        redis_client = redis_manager.redis
        redis_info = await redis_client.info("memory")
        
        return {
            "cache_stats": cache_manager.get_stats(),
            "redis_memory": {
                "used_memory": redis_info.get("used_memory_human", "unknown"),
                "used_memory_peak": redis_info.get("used_memory_peak_human", "unknown"),
                "memory_fragmentation_ratio": redis_info.get("memory_fragmentation_ratio", 0)
            },
            "connection_info": await redis_manager.get_connection_info(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}")
        return {
            "error": str(e),
            "cache_stats": cache_manager.get_stats(),
            "timestamp": datetime.utcnow().isoformat()
        }
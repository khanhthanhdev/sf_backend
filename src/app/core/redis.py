"""
Redis connection management and utilities for the FastAPI backend.

This module provides Redis connection pooling, dependency injection,
health checks, and error handling for the video generation API.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from fastapi import HTTPException, status

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisManager:
    """
    Redis connection manager with connection pooling and error handling.
    
    Provides centralized Redis connection management, health checks,
    and utility methods for the FastAPI application.
    """
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[Redis] = None
        self._is_connected = False
    
    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        try:
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                settings.get_redis_url(),
                max_connections=settings.redis_max_connections,
                retry_on_timeout=True,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                socket_timeout=settings.redis_socket_timeout,
                health_check_interval=30,
                decode_responses=True
            )
            
            # Create Redis client
            self._redis = Redis(connection_pool=self._pool)
            
            # Test connection
            await self._redis.ping()
            self._is_connected = True
            
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self._is_connected = False
            raise
    
    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()
        
        self._is_connected = False
        logger.info("Redis connection closed")
    
    @property
    def redis(self) -> Redis:
        """Get Redis client instance."""
        if not self._redis or not self._is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis connection not available"
            )
        return self._redis
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._is_connected
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform Redis health check.
        
        Returns:
            Dict containing health status and metrics
        """
        try:
            if not self._redis:
                return {
                    "status": "unhealthy",
                    "error": "Redis client not initialized"
                }
            
            # Test basic connectivity
            start_time = asyncio.get_event_loop().time()
            await self._redis.ping()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Get Redis info
            info = await self._redis.info()
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get Redis connection information."""
        if not self._pool:
            return {"error": "Connection pool not initialized"}
        
        return {
            "max_connections": self._pool.max_connections,
            "created_connections": self._pool.created_connections,
            "available_connections": len(self._pool._available_connections),
            "in_use_connections": len(self._pool._in_use_connections)
        }


# Global Redis manager instance
redis_manager = RedisManager()


async def get_redis() -> Redis:
    """
    FastAPI dependency to get Redis client.
    
    Returns:
        Redis client instance
        
    Raises:
        HTTPException: If Redis is not available
    """
    return redis_manager.redis


@asynccontextmanager
async def redis_transaction():
    """
    Context manager for Redis transactions.
    
    Usage:
        async with redis_transaction() as pipe:
            pipe.set("key", "value")
            pipe.incr("counter")
            await pipe.execute()
    """
    redis_client = redis_manager.redis
    pipe = redis_client.pipeline(transaction=True)
    try:
        yield pipe
    except Exception as e:
        logger.error(f"Redis transaction failed: {e}")
        raise
    finally:
        await pipe.reset()


class RedisKeyManager:
    """
    Utility class for managing Redis keys with consistent naming patterns.
    """
    
    # Key prefixes
    JOB_PREFIX = "jobs"
    VIDEO_PREFIX = "videos"
    USER_JOBS_PREFIX = "user_jobs"
    JOB_QUEUE = "job_queue"
    JOB_STATUS_PREFIX = "job_status"
    SYSTEM_PREFIX = "system"
    CACHE_PREFIX = "cache"
    FILE_PREFIX = "files"
    USER_FILES_PREFIX = "user_files"
    
    @staticmethod
    def job_key(job_id: str) -> str:
        """Generate Redis key for job data."""
        return f"{RedisKeyManager.JOB_PREFIX}:{job_id}"
    
    @staticmethod
    def video_key(video_id: str) -> str:
        """Generate Redis key for video metadata."""
        return f"{RedisKeyManager.VIDEO_PREFIX}:{video_id}"
    
    @staticmethod
    def user_jobs_key(user_id: str) -> str:
        """Generate Redis key for user jobs index."""
        return f"{RedisKeyManager.USER_JOBS_PREFIX}:{user_id}"
    
    @staticmethod
    def job_status_key(job_id: str) -> str:
        """Generate Redis key for job status cache."""
        return f"{RedisKeyManager.JOB_STATUS_PREFIX}:{job_id}"
    
    @staticmethod
    def system_health_key() -> str:
        """Generate Redis key for system health data."""
        return f"{RedisKeyManager.SYSTEM_PREFIX}:health"
    
    @staticmethod
    def cache_key(namespace: str, key: str) -> str:
        """Generate Redis key for cached data."""
        return f"{RedisKeyManager.CACHE_PREFIX}:{namespace}:{key}"
    
    @staticmethod
    def file_key(file_id: str) -> str:
        """Generate Redis key for file metadata."""
        return f"{RedisKeyManager.FILE_PREFIX}:{file_id}"
    
    @staticmethod
    def user_files_key(user_id: str) -> str:
        """Generate Redis key for user files index."""
        return f"{RedisKeyManager.USER_FILES_PREFIX}:{user_id}"


class RedisErrorHandler:
    """
    Utility class for handling Redis errors consistently.
    """
    
    @staticmethod
    def handle_redis_error(operation: str, error: Exception) -> HTTPException:
        """
        Convert Redis errors to appropriate HTTP exceptions.
        
        Args:
            operation: Description of the operation that failed
            error: The Redis exception that occurred
            
        Returns:
            HTTPException with appropriate status code and message
        """
        logger.error(f"Redis {operation} failed: {error}")
        
        if isinstance(error, ConnectionError):
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Redis connection failed during {operation}"
            )
        elif isinstance(error, TimeoutError):
            return HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Redis operation timed out during {operation}"
            )
        elif isinstance(error, RedisError):
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Redis error during {operation}"
            )
        else:
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error during {operation}"
            )


# Utility functions for common Redis operations
async def safe_redis_operation(operation_func, *args, **kwargs):
    """
    Safely execute a Redis operation with error handling.
    
    Args:
        operation_func: The Redis operation function to execute
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        Result of the operation or None if failed
        
    Raises:
        HTTPException: If the operation fails
    """
    try:
        return await operation_func(*args, **kwargs)
    except Exception as e:
        operation_name = getattr(operation_func, '__name__', 'unknown')
        raise RedisErrorHandler.handle_redis_error(operation_name, e)


async def redis_json_get(redis_client: Redis, key: str, default: Any = None) -> Any:
    """
    Get and deserialize JSON data from Redis.
    
    Args:
        redis_client: Redis client instance
        key: Redis key
        default: Default value if key doesn't exist
        
    Returns:
        Deserialized JSON data or default value
    """
    try:
        data = await redis_client.get(key)
        if data is None:
            return default
        return json.loads(data)
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON data in Redis key: {key}")
        return default
    except Exception as e:
        raise RedisErrorHandler.handle_redis_error("json_get", e)


async def redis_json_set(
    redis_client: Redis, 
    key: str, 
    value: Any, 
    ex: Optional[int] = None
) -> bool:
    """
    Serialize and store JSON data in Redis.
    
    Args:
        redis_client: Redis client instance
        key: Redis key
        value: Data to serialize and store
        ex: Expiration time in seconds
        
    Returns:
        True if successful
    """
    try:
        json_data = json.dumps(value, default=str)
        return await redis_client.set(key, json_data, ex=ex)
    except Exception as e:
        raise RedisErrorHandler.handle_redis_error("json_set", e)
"""
File caching utilities for improved performance.

This module provides caching strategies for file metadata,
thumbnails, and frequently accessed files.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiofiles

from redis.asyncio import Redis

from ..core.redis import get_redis, redis_json_get, redis_json_set
from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class FileCacheManager:
    """Manager for file caching operations."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis_client = redis_client
        self.cache_ttl = {
            'metadata': 3600,      # 1 hour
            'thumbnail': 86400,    # 1 day
            'file_content': 1800,  # 30 minutes
            'access_stats': 300    # 5 minutes
        }
    
    async def cache_file_metadata(
        self,
        file_id: str,
        metadata: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache file metadata in Redis.
        
        Args:
            file_id: File identifier
            metadata: Metadata to cache
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully
        """
        try:
            if not self.redis_client:
                return False
            
            cache_key = f"file_cache:metadata:{file_id}"
            cache_ttl = ttl or self.cache_ttl['metadata']
            
            await redis_json_set(
                self.redis_client,
                cache_key,
                metadata,
                ex=cache_ttl
            )
            
            logger.debug(f"Cached metadata for file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache metadata: {e}")
            return False
    
    async def get_cached_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached file metadata.
        
        Args:
            file_id: File identifier
            
        Returns:
            Cached metadata or None if not found
        """
        try:
            if not self.redis_client:
                return None
            
            cache_key = f"file_cache:metadata:{file_id}"
            return await redis_json_get(self.redis_client, cache_key)
            
        except Exception as e:
            logger.error(f"Failed to get cached metadata: {e}")
            return None
    
    async def cache_thumbnail_path(
        self,
        file_id: str,
        size: str,
        thumbnail_path: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache thumbnail file path.
        
        Args:
            file_id: File identifier
            size: Thumbnail size
            thumbnail_path: Path to thumbnail file
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully
        """
        try:
            if not self.redis_client:
                return False
            
            cache_key = f"file_cache:thumbnail:{file_id}:{size}"
            cache_ttl = ttl or self.cache_ttl['thumbnail']
            
            await self.redis_client.set(cache_key, thumbnail_path, ex=cache_ttl)
            
            logger.debug(f"Cached thumbnail path for file {file_id}, size {size}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache thumbnail path: {e}")
            return False
    
    async def get_cached_thumbnail_path(
        self,
        file_id: str,
        size: str
    ) -> Optional[str]:
        """
        Get cached thumbnail path.
        
        Args:
            file_id: File identifier
            size: Thumbnail size
            
        Returns:
            Cached thumbnail path or None if not found
        """
        try:
            if not self.redis_client:
                return None
            
            cache_key = f"file_cache:thumbnail:{file_id}:{size}"
            result = await self.redis_client.get(cache_key)
            
            return result.decode() if isinstance(result, bytes) else result
            
        except Exception as e:
            logger.error(f"Failed to get cached thumbnail path: {e}")
            return None
    
    async def cache_file_access_stats(
        self,
        file_id: str,
        user_id: str,
        access_type: str = "download"
    ) -> bool:
        """
        Cache file access statistics.
        
        Args:
            file_id: File identifier
            user_id: User who accessed the file
            access_type: Type of access (download, view, stream)
            
        Returns:
            True if cached successfully
        """
        try:
            if not self.redis_client:
                return False
            
            # Increment access counter
            counter_key = f"file_cache:access_count:{file_id}"
            await self.redis_client.incr(counter_key)
            await self.redis_client.expire(counter_key, 86400)  # 1 day
            
            # Store recent access
            access_key = f"file_cache:recent_access:{file_id}"
            access_data = {
                "user_id": user_id,
                "access_type": access_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add to list (keep last 100 accesses)
            await self.redis_client.lpush(access_key, json.dumps(access_data))
            await self.redis_client.ltrim(access_key, 0, 99)
            await self.redis_client.expire(access_key, 86400)  # 1 day
            
            logger.debug(f"Cached access stats for file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache access stats: {e}")
            return False
    
    async def get_file_access_stats(self, file_id: str) -> Dict[str, Any]:
        """
        Get file access statistics.
        
        Args:
            file_id: File identifier
            
        Returns:
            Dictionary with access statistics
        """
        try:
            if not self.redis_client:
                return {}
            
            # Get access count
            counter_key = f"file_cache:access_count:{file_id}"
            access_count = await self.redis_client.get(counter_key)
            access_count = int(access_count) if access_count else 0
            
            # Get recent accesses
            access_key = f"file_cache:recent_access:{file_id}"
            recent_accesses = await self.redis_client.lrange(access_key, 0, 9)  # Last 10
            
            recent_access_data = []
            for access in recent_accesses:
                try:
                    access_data = json.loads(access.decode() if isinstance(access, bytes) else access)
                    recent_access_data.append(access_data)
                except json.JSONDecodeError:
                    continue
            
            return {
                "total_accesses": access_count,
                "recent_accesses": recent_access_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get access stats: {e}")
            return {}
    
    async def cache_file_content_hash(
        self,
        file_path: str,
        content_hash: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache file content hash for integrity checking.
        
        Args:
            file_path: Path to file
            content_hash: Hash of file content
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully
        """
        try:
            if not self.redis_client:
                return False
            
            cache_key = f"file_cache:hash:{hashlib.md5(file_path.encode()).hexdigest()}"
            cache_ttl = ttl or self.cache_ttl['file_content']
            
            await self.redis_client.set(cache_key, content_hash, ex=cache_ttl)
            
            logger.debug(f"Cached content hash for file {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache content hash: {e}")
            return False
    
    async def get_cached_content_hash(self, file_path: str) -> Optional[str]:
        """
        Get cached file content hash.
        
        Args:
            file_path: Path to file
            
        Returns:
            Cached content hash or None if not found
        """
        try:
            if not self.redis_client:
                return None
            
            cache_key = f"file_cache:hash:{hashlib.md5(file_path.encode()).hexdigest()}"
            result = await self.redis_client.get(cache_key)
            
            return result.decode() if isinstance(result, bytes) else result
            
        except Exception as e:
            logger.error(f"Failed to get cached content hash: {e}")
            return None
    
    async def invalidate_file_cache(self, file_id: str) -> bool:
        """
        Invalidate all cached data for a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            True if invalidated successfully
        """
        try:
            if not self.redis_client:
                return False
            
            # Get all cache keys for this file
            patterns = [
                f"file_cache:metadata:{file_id}",
                f"file_cache:thumbnail:{file_id}:*",
                f"file_cache:access_count:{file_id}",
                f"file_cache:recent_access:{file_id}"
            ]
            
            deleted_count = 0
            for pattern in patterns:
                if '*' in pattern:
                    # Handle wildcard patterns
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        deleted_count += await self.redis_client.delete(*keys)
                else:
                    # Handle exact keys
                    deleted_count += await self.redis_client.delete(pattern)
            
            logger.info(f"Invalidated {deleted_count} cache entries for file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False
    
    async def cleanup_expired_cache(self) -> Dict[str, int]:
        """
        Clean up expired cache entries.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            if not self.redis_client:
                return {"cleaned": 0}
            
            # Redis automatically handles TTL expiration, but we can clean up
            # any orphaned entries or perform maintenance
            
            # Get all file cache keys
            cache_patterns = [
                "file_cache:metadata:*",
                "file_cache:thumbnail:*",
                "file_cache:hash:*"
            ]
            
            total_keys = 0
            for pattern in cache_patterns:
                keys = await self.redis_client.keys(pattern)
                total_keys += len(keys)
            
            logger.info(f"File cache contains {total_keys} entries")
            
            return {"total_entries": total_keys, "cleaned": 0}
            
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
            return {"cleaned": 0}
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            if not self.redis_client:
                return {}
            
            stats = {}
            
            # Count entries by type
            cache_types = {
                "metadata": "file_cache:metadata:*",
                "thumbnails": "file_cache:thumbnail:*",
                "access_counts": "file_cache:access_count:*",
                "content_hashes": "file_cache:hash:*"
            }
            
            for cache_type, pattern in cache_types.items():
                keys = await self.redis_client.keys(pattern)
                stats[f"{cache_type}_count"] = len(keys)
            
            # Get memory usage info if available
            try:
                info = await self.redis_client.info("memory")
                stats["memory_used"] = info.get("used_memory_human", "unknown")
            except Exception:
                pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    async def warm_cache_for_popular_files(self, limit: int = 100) -> Dict[str, int]:
        """
        Warm cache for most frequently accessed files.
        
        Args:
            limit: Maximum number of files to warm
            
        Returns:
            Dictionary with warming statistics
        """
        try:
            if not self.redis_client:
                return {"warmed": 0}
            
            # Get most accessed files
            access_pattern = "file_cache:access_count:*"
            access_keys = await self.redis_client.keys(access_pattern)
            
            # Get access counts and sort
            file_access_counts = []
            for key in access_keys:
                try:
                    count = await self.redis_client.get(key)
                    if count:
                        file_id = key.decode().split(':')[-1] if isinstance(key, bytes) else key.split(':')[-1]
                        file_access_counts.append((file_id, int(count)))
                except Exception:
                    continue
            
            # Sort by access count (descending)
            file_access_counts.sort(key=lambda x: x[1], reverse=True)
            
            # Warm cache for top files
            warmed_count = 0
            for file_id, access_count in file_access_counts[:limit]:
                try:
                    # Pre-load metadata if not cached
                    metadata_key = f"file_cache:metadata:{file_id}"
                    if not await self.redis_client.exists(metadata_key):
                        # This would typically load from primary storage
                        # For now, we'll just mark it as a candidate for warming
                        logger.debug(f"Cache warming candidate: {file_id} (access count: {access_count})")
                    
                    warmed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to warm cache for file {file_id}: {e}")
            
            logger.info(f"Cache warming completed: {warmed_count} files processed")
            
            return {
                "warmed": warmed_count,
                "candidates": len(file_access_counts),
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Failed to warm cache: {e}")
            return {"warmed": 0}
    
    async def implement_cache_eviction_policy(self) -> Dict[str, int]:
        """
        Implement LRU-style cache eviction for memory management.
        
        Returns:
            Dictionary with eviction statistics
        """
        try:
            if not self.redis_client:
                return {"evicted": 0}
            
            evicted_count = 0
            
            # Get all metadata cache keys with their TTL
            metadata_pattern = "file_cache:metadata:*"
            metadata_keys = await self.redis_client.keys(metadata_pattern)
            
            # Check each key's TTL and access patterns
            for key in metadata_keys:
                try:
                    ttl = await self.redis_client.ttl(key)
                    
                    # If TTL is very low (< 300 seconds), consider for eviction
                    if 0 < ttl < 300:
                        # Check if file has been accessed recently
                        file_id = key.decode().split(':')[-1] if isinstance(key, bytes) else key.split(':')[-1]
                        access_key = f"file_cache:recent_access:{file_id}"
                        
                        recent_accesses = await self.redis_client.llen(access_key)
                        
                        # If no recent accesses, evict early
                        if recent_accesses == 0:
                            await self.redis_client.delete(key)
                            evicted_count += 1
                            logger.debug(f"Evicted cache entry: {file_id}")
                    
                except Exception as e:
                    logger.warning(f"Failed to process cache key {key}: {e}")
            
            logger.info(f"Cache eviction completed: {evicted_count} entries evicted")
            
            return {
                "evicted": evicted_count,
                "total_checked": len(metadata_keys)
            }
            
        except Exception as e:
            logger.error(f"Failed to implement cache eviction: {e}")
            return {"evicted": 0}


# Global cache manager instance
file_cache_manager = FileCacheManager()


# Utility functions
async def cache_file_metadata(
    file_id: str,
    metadata: Dict[str, Any],
    ttl: Optional[int] = None
) -> bool:
    """Cache file metadata."""
    redis_client = await get_redis()
    cache_manager = FileCacheManager(redis_client)
    return await cache_manager.cache_file_metadata(file_id, metadata, ttl)


async def get_cached_file_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """Get cached file metadata."""
    redis_client = await get_redis()
    cache_manager = FileCacheManager(redis_client)
    return await cache_manager.get_cached_metadata(file_id)


async def track_file_access(
    file_id: str,
    user_id: str,
    access_type: str = "download"
) -> bool:
    """Track file access for statistics."""
    redis_client = await get_redis()
    cache_manager = FileCacheManager(redis_client)
    return await cache_manager.cache_file_access_stats(file_id, user_id, access_type)


async def get_file_access_statistics(file_id: str) -> Dict[str, Any]:
    """Get file access statistics."""
    redis_client = await get_redis()
    cache_manager = FileCacheManager(redis_client)
    return await cache_manager.get_file_access_stats(file_id)
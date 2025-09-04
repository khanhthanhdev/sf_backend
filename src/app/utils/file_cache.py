"""
File caching utilities for improved performance.

This module provides caching strategies for file metadata,
thumbnails, and frequently accessed files using database storage.
"""

import asyncio
import hashlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiofiles

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


# Thread-safe in-memory cache with TTL support
class InMemoryCache:
    """Thread-safe in-memory cache with TTL support."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expires_at'] and datetime.utcnow() > entry['expires_at']:
                del self._cache[key]
                return None
            
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        with self._lock:
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': datetime.utcnow()
            }
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (simple wildcard support)."""
        with self._lock:
            if '*' not in pattern:
                return 1 if self.delete(pattern) else 0
            
            prefix = pattern.replace('*', '')
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            return len(keys_to_delete)
    
    def clear_expired(self) -> int:
        """Clear expired entries and return count."""
        with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry['expires_at'] and now > entry['expires_at']
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = self.clear_expired()
            
            return {
                'total_entries': total_entries,
                'expired_cleaned': expired_entries,
                'memory_usage': f"{len(str(self._cache))} bytes (approx)"
            }


# Global cache instance
_cache = InMemoryCache()


class FileCacheManager:
    """Manager for file caching operations using database and in-memory cache."""
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session
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
        Cache file metadata in memory and database.
        
        Args:
            file_id: File identifier
            metadata: Metadata to cache
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully
        """
        try:
            # Cache in memory for fast access
            cache_key = f"file_cache:metadata:{file_id}"
            cache_ttl = ttl or self.cache_ttl['metadata']
            
            _cache.set(cache_key, metadata, cache_ttl)
            
            # Store in database for persistence
            if self.db_session:
                await self._store_cache_entry(
                    key=cache_key,
                    value=metadata,
                    expires_at=datetime.utcnow() + timedelta(seconds=cache_ttl)
                )
            
            logger.debug(f"Cached metadata for file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache metadata: {e}")
            return False
    
    async def get_cached_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached file metadata from memory or database.
        
        Args:
            file_id: File identifier
            
        Returns:
            Cached metadata or None if not found
        """
        try:
            cache_key = f"file_cache:metadata:{file_id}"
            
            # Try memory cache first
            cached_data = _cache.get(cache_key)
            if cached_data is not None:
                return cached_data
            
            # Fallback to database
            if self.db_session:
                db_entry = await self._get_cache_entry(cache_key)
                if db_entry:
                    # Restore to memory cache
                    _cache.set(cache_key, db_entry['value'], self.cache_ttl['metadata'])
                    return db_entry['value']
            
            return None
            
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
            cache_key = f"file_cache:thumbnail:{file_id}:{size}"
            cache_ttl = ttl or self.cache_ttl['thumbnail']
            
            _cache.set(cache_key, thumbnail_path, cache_ttl)
            
            # Store in database for persistence
            if self.db_session:
                await self._store_cache_entry(
                    key=cache_key,
                    value=thumbnail_path,
                    expires_at=datetime.utcnow() + timedelta(seconds=cache_ttl)
                )
            
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
            cache_key = f"file_cache:thumbnail:{file_id}:{size}"
            
            # Try memory cache first
            cached_path = _cache.get(cache_key)
            if cached_path is not None:
                return cached_path
            
            # Fallback to database
            if self.db_session:
                db_entry = await self._get_cache_entry(cache_key)
                if db_entry:
                    # Restore to memory cache
                    _cache.set(cache_key, db_entry['value'], self.cache_ttl['thumbnail'])
                    return db_entry['value']
            
            return None
            
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
            # Increment access counter in memory
            counter_key = f"file_cache:access_count:{file_id}"
            current_count = _cache.get(counter_key) or 0
            _cache.set(counter_key, current_count + 1, 86400)  # 1 day
            
            # Store recent access
            access_key = f"file_cache:recent_access:{file_id}"
            access_data = {
                "user_id": user_id,
                "access_type": access_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Get current access list and add new access
            recent_accesses = _cache.get(access_key) or []
            recent_accesses.insert(0, access_data)
            
            # Keep only last 100 accesses
            if len(recent_accesses) > 100:
                recent_accesses = recent_accesses[:100]
            
            _cache.set(access_key, recent_accesses, 86400)  # 1 day
            
            # Persist to database if available
            if self.db_session:
                await self._store_access_stats_to_db(file_id, user_id, access_type)
            
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
            # Get access count from memory
            counter_key = f"file_cache:access_count:{file_id}"
            access_count = _cache.get(counter_key) or 0
            
            # Get recent accesses from memory
            access_key = f"file_cache:recent_access:{file_id}"
            recent_accesses = _cache.get(access_key) or []
            
            # Get only last 10 for response
            recent_access_data = recent_accesses[:10] if recent_accesses else []
            
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
            cache_key = f"file_cache:hash:{hashlib.md5(file_path.encode()).hexdigest()}"
            cache_ttl = ttl or self.cache_ttl['file_content']
            
            _cache.set(cache_key, content_hash, cache_ttl)
            
            # Store in database for persistence
            if self.db_session:
                await self._store_cache_entry(
                    key=cache_key,
                    value=content_hash,
                    expires_at=datetime.utcnow() + timedelta(seconds=cache_ttl)
                )
            
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
            cache_key = f"file_cache:hash:{hashlib.md5(file_path.encode()).hexdigest()}"
            
            # Try memory cache first
            cached_hash = _cache.get(cache_key)
            if cached_hash is not None:
                return cached_hash
            
            # Fallback to database
            if self.db_session:
                db_entry = await self._get_cache_entry(cache_key)
                if db_entry:
                    # Restore to memory cache
                    _cache.set(cache_key, db_entry['value'], self.cache_ttl['file_content'])
                    return db_entry['value']
            
            return None
            
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
            # Get all cache keys for this file
            patterns = [
                f"file_cache:metadata:{file_id}",
                f"file_cache:thumbnail:{file_id}:",  # prefix for wildcard matching
                f"file_cache:access_count:{file_id}",
                f"file_cache:recent_access:{file_id}"
            ]
            
            deleted_count = 0
            for pattern in patterns:
                if pattern.endswith(':'):
                    # Handle wildcard patterns
                    deleted_count += _cache.delete_pattern(pattern + '*')
                else:
                    # Handle exact keys
                    if _cache.delete(pattern):
                        deleted_count += 1
            
            # Also invalidate from database if available
            if self.db_session:
                await self._invalidate_cache_entries_from_db(file_id)
            
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
            # Clean up expired entries from memory cache
            expired_count = _cache.clear_expired()
            
            # Get cache statistics
            cache_stats = _cache.get_stats()
            total_entries = cache_stats['total_entries']
            
            logger.info(f"File cache cleanup: {expired_count} expired entries removed, {total_entries} total entries")
            
            return {
                "total_entries": total_entries,
                "cleaned": expired_count
            }
            
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
            # Get statistics from memory cache
            cache_stats = _cache.get_stats()
            
            # Count entries by type from memory
            stats = {
                "total_entries": cache_stats['total_entries'],
                "memory_usage": cache_stats['memory_usage'],
                "expired_cleaned": cache_stats['expired_cleaned']
            }
            
            # Count specific cache types
            cache_types = {
                "metadata": "file_cache:metadata:",
                "thumbnails": "file_cache:thumbnail:",
                "access_counts": "file_cache:access_count:",
                "content_hashes": "file_cache:hash:"
            }
            
            for cache_type, prefix in cache_types.items():
                count = 0
                with _cache._lock:
                    for key in _cache._cache.keys():
                        if key.startswith(prefix):
                            count += 1
                stats[f"{cache_type}_count"] = count
            
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
            # Get most accessed files from memory cache
            access_pattern = "file_cache:access_count:"
            file_access_counts = []
            
            with _cache._lock:
                for key, entry in _cache._cache.items():
                    if key.startswith(access_pattern):
                        file_id = key.replace(access_pattern, '')
                        access_count = entry['value']
                        file_access_counts.append((file_id, access_count))
            
            # Sort by access count (descending)
            file_access_counts.sort(key=lambda x: x[1], reverse=True)
            
            # Warm cache for top files
            warmed_count = 0
            for file_id, access_count in file_access_counts[:limit]:
                try:
                    # Check if metadata is cached
                    metadata_key = f"file_cache:metadata:{file_id}"
                    if _cache.get(metadata_key) is None:
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
            evicted_count = 0
            
            # Get all metadata cache keys
            metadata_pattern = "file_cache:metadata:"
            
            with _cache._lock:
                keys_to_evict = []
                now = datetime.utcnow()
                
                for key, entry in _cache._cache.items():
                    if key.startswith(metadata_pattern):
                        # Check if entry is close to expiration (< 5 minutes)
                        if entry['expires_at'] and (entry['expires_at'] - now).total_seconds() < 300:
                            file_id = key.replace(metadata_pattern, '')
                            
                            # Check if file has been accessed recently
                            access_key = f"file_cache:recent_access:{file_id}"
                            recent_accesses = _cache.get(access_key) or []
                            
                            # If no recent accesses, mark for eviction
                            if not recent_accesses:
                                keys_to_evict.append(key)
                
                # Evict identified keys
                for key in keys_to_evict:
                    if key in _cache._cache:
                        del _cache._cache[key]
                        evicted_count += 1
                        file_id = key.replace(metadata_pattern, '')
                        logger.debug(f"Evicted cache entry: {file_id}")
            
            logger.info(f"Cache eviction completed: {evicted_count} entries evicted")
            
            return {
                "evicted": evicted_count,
                "total_checked": len([k for k in _cache._cache.keys() if k.startswith(metadata_pattern)])
            }
            
        except Exception as e:
            logger.error(f"Failed to implement cache eviction: {e}")
            return {"evicted": 0}
    
    # Database helper methods
    async def _store_cache_entry(
        self,
        key: str,
        value: Any,
        expires_at: datetime
    ) -> bool:
        """
        Store cache entry in database for persistence.
        
        Args:
            key: Cache key
            value: Value to store
            expires_at: Expiration timestamp
            
        Returns:
            True if stored successfully
        """
        try:
            if not self.db_session:
                return False
            
            # Store as JSON in a simple cache table
            # This would require a cache table to be created
            query = text("""
                INSERT INTO cache_entries (cache_key, cache_value, expires_at, created_at)
                VALUES (:key, :value, :expires_at, :created_at)
                ON CONFLICT (cache_key) DO UPDATE SET
                    cache_value = EXCLUDED.cache_value,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = CURRENT_TIMESTAMP
            """)
            
            await self.db_session.execute(query, {
                'key': key,
                'value': json.dumps(value) if not isinstance(value, str) else value,
                'expires_at': expires_at,
                'created_at': datetime.utcnow()
            })
            await self.db_session.commit()
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to store cache entry in database: {e}")
            if self.db_session:
                await self.db_session.rollback()
            return False
    
    async def _get_cache_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cache entry from database.
        
        Args:
            key: Cache key
            
        Returns:
            Cache entry or None if not found or expired
        """
        try:
            if not self.db_session:
                return None
            
            query = text("""
                SELECT cache_value, expires_at
                FROM cache_entries
                WHERE cache_key = :key
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """)
            
            result = await self.db_session.execute(query, {'key': key})
            row = result.fetchone()
            
            if not row:
                return None
            
            try:
                value = json.loads(row.cache_value) if row.cache_value.startswith(('{', '[', '"')) else row.cache_value
            except (json.JSONDecodeError, AttributeError):
                value = row.cache_value
            
            return {'value': value}
            
        except Exception as e:
            logger.warning(f"Failed to get cache entry from database: {e}")
            return None
    
    async def _store_access_stats_to_db(
        self,
        file_id: str,
        user_id: str,
        access_type: str
    ) -> bool:
        """
        Store file access statistics to database.
        
        Args:
            file_id: File identifier
            user_id: User who accessed the file
            access_type: Type of access
            
        Returns:
            True if stored successfully
        """
        try:
            if not self.db_session:
                return False
            
            # Store access log in database
            query = text("""
                INSERT INTO file_access_logs (file_id, user_id, access_type, accessed_at)
                VALUES (:file_id, :user_id, :access_type, :accessed_at)
            """)
            
            await self.db_session.execute(query, {
                'file_id': file_id,
                'user_id': user_id,
                'access_type': access_type,
                'accessed_at': datetime.utcnow()
            })
            await self.db_session.commit()
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to store access stats to database: {e}")
            if self.db_session:
                await self.db_session.rollback()
            return False
    
    async def _invalidate_cache_entries_from_db(self, file_id: str) -> bool:
        """
        Invalidate cache entries from database.
        
        Args:
            file_id: File identifier
            
        Returns:
            True if invalidated successfully
        """
        try:
            if not self.db_session:
                return False
            
            # Delete cache entries related to this file
            query = text("""
                DELETE FROM cache_entries
                WHERE cache_key LIKE :pattern
            """)
            
            await self.db_session.execute(query, {
                'pattern': f"%{file_id}%"
            })
            await self.db_session.commit()
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to invalidate cache entries from database: {e}")
            if self.db_session:
                await self.db_session.rollback()
            return False


# Global cache manager instance
file_cache_manager = FileCacheManager()


# Utility functions
async def cache_file_metadata(
    file_id: str,
    metadata: Dict[str, Any],
    ttl: Optional[int] = None,
    db_session: Optional[AsyncSession] = None
) -> bool:
    """Cache file metadata."""
    cache_manager = FileCacheManager(db_session)
    return await cache_manager.cache_file_metadata(file_id, metadata, ttl)


async def get_cached_file_metadata(
    file_id: str,
    db_session: Optional[AsyncSession] = None
) -> Optional[Dict[str, Any]]:
    """Get cached file metadata."""
    cache_manager = FileCacheManager(db_session)
    return await cache_manager.get_cached_metadata(file_id)


async def track_file_access(
    file_id: str,
    user_id: str,
    access_type: str = "download",
    db_session: Optional[AsyncSession] = None
) -> bool:
    """Track file access for statistics."""
    cache_manager = FileCacheManager(db_session)
    return await cache_manager.cache_file_access_stats(file_id, user_id, access_type)


async def get_file_access_statistics(
    file_id: str,
    db_session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """Get file access statistics."""
    cache_manager = FileCacheManager(db_session)
    return await cache_manager.get_file_access_stats(file_id)
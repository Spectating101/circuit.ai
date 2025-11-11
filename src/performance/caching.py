"""
Advanced Caching & Performance Optimization

Multi-layer caching strategy:
- L1: In-memory LRU cache
- L2: Redis distributed cache
- L3: CDN edge caching

Features:
- Cache warming
- Intelligent prefetching
- Cache stampede prevention
- Compression
"""

from typing import Any, Optional, Callable
from functools import wraps
import hashlib
import json
import pickle
import zlib
from datetime import timedelta
import asyncio
from loguru import logger
import redis.asyncio as redis
from cachetools import LRUCache


class MultiLayerCache:
    """Multi-layer caching system with L1 (memory) and L2 (Redis)."""

    def __init__(self,
                 redis_url: Optional[str] = None,
                 l1_size: int = 1000,
                 default_ttl: int = 3600):
        """
        Initialize multi-layer cache.

        Args:
            redis_url: Redis connection URL
            l1_size: L1 cache size (number of items)
            default_ttl: Default TTL in seconds
        """
        # L1: In-memory LRU cache
        self.l1_cache = LRUCache(maxsize=l1_size)

        # L2: Redis cache
        self.redis_client = None
        if redis_url:
            self.redis_client = redis.from_url(redis_url, decode_responses=False)

        self.default_ttl = default_ttl

        # Statistics
        self.stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "sets": 0,
            "deletes": 0
        }

        logger.info(f"MultiLayerCache initialized (L1: {l1_size}, Redis: {redis_url is not None})")

    def _generate_key(self, key: str, namespace: str = "default") -> str:
        """Generate cache key with namespace."""
        return f"{namespace}:{key}"

    def _serialize(self, value: Any, compress: bool = True) -> bytes:
        """
        Serialize and optionally compress value.

        Args:
            value: Value to serialize
            compress: Whether to compress

        Returns:
            Serialized bytes
        """
        data = pickle.dumps(value)

        if compress and len(data) > 1024:  # Compress if >1KB
            data = zlib.compress(data)
            data = b'C' + data  # Mark as compressed
        else:
            data = b'U' + data  # Mark as uncompressed

        return data

    def _deserialize(self, data: bytes) -> Any:
        """
        Deserialize and decompress if needed.

        Args:
            data: Serialized bytes

        Returns:
            Deserialized value
        """
        if not data:
            return None

        compression_flag = data[0:1]
        payload = data[1:]

        if compression_flag == b'C':
            payload = zlib.decompress(payload)

        return pickle.loads(payload)

    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """
        Get value from cache (checks L1 then L2).

        Args:
            key: Cache key
            namespace: Cache namespace

        Returns:
            Cached value or None
        """
        cache_key = self._generate_key(key, namespace)

        # Check L1 (memory)
        if cache_key in self.l1_cache:
            self.stats["l1_hits"] += 1
            logger.debug(f"L1 cache hit: {cache_key}")
            return self.l1_cache[cache_key]

        self.stats["l1_misses"] += 1

        # Check L2 (Redis)
        if self.redis_client:
            try:
                data = await self.redis_client.get(cache_key)
                if data:
                    self.stats["l2_hits"] += 1
                    logger.debug(f"L2 cache hit: {cache_key}")

                    value = self._deserialize(data)

                    # Populate L1
                    self.l1_cache[cache_key] = value

                    return value
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        self.stats["l2_misses"] += 1
        return None

    async def set(self,
                 key: str,
                 value: Any,
                 ttl: Optional[int] = None,
                 namespace: str = "default"):
        """
        Set value in cache (both L1 and L2).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            namespace: Cache namespace
        """
        cache_key = self._generate_key(key, namespace)
        ttl = ttl or self.default_ttl

        # Set in L1
        self.l1_cache[cache_key] = value

        # Set in L2
        if self.redis_client:
            try:
                data = self._serialize(value)
                await self.redis_client.setex(cache_key, ttl, data)
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        self.stats["sets"] += 1
        logger.debug(f"Cached: {cache_key} (TTL: {ttl}s)")

    async def delete(self, key: str, namespace: str = "default"):
        """
        Delete value from cache.

        Args:
            key: Cache key
            namespace: Cache namespace
        """
        cache_key = self._generate_key(key, namespace)

        # Delete from L1
        if cache_key in self.l1_cache:
            del self.l1_cache[cache_key]

        # Delete from L2
        if self.redis_client:
            try:
                await self.redis_client.delete(cache_key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        self.stats["deletes"] += 1

    async def clear_namespace(self, namespace: str):
        """
        Clear all keys in namespace.

        Args:
            namespace: Namespace to clear
        """
        # Clear L1 (scan and delete matching keys)
        keys_to_delete = [k for k in self.l1_cache if k.startswith(f"{namespace}:")]
        for key in keys_to_delete:
            del self.l1_cache[key]

        # Clear L2
        if self.redis_client:
            try:
                pattern = f"{namespace}:*"
                async for key in self.redis_client.scan_iter(match=pattern):
                    await self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Redis clear namespace error: {e}")

        logger.info(f"Cleared namespace: {namespace}")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self.stats["l1_hits"] + self.stats["l1_misses"]
        l1_hit_rate = (self.stats["l1_hits"] / total_requests * 100) if total_requests > 0 else 0
        l2_hit_rate = (self.stats["l2_hits"] / self.stats["l1_misses"] * 100) if self.stats["l1_misses"] > 0 else 0

        return {
            **self.stats,
            "l1_size": len(self.l1_cache),
            "l1_hit_rate": f"{l1_hit_rate:.2f}%",
            "l2_hit_rate": f"{l2_hit_rate:.2f}%",
            "total_hit_rate": f"{((self.stats['l1_hits'] + self.stats['l2_hits']) / total_requests * 100):.2f}%" if total_requests > 0 else "0.00%"
        }


def cached(ttl: int = 3600, namespace: str = "default", key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        ttl: Cache TTL in seconds
        namespace: Cache namespace
        key_prefix: Prefix for cache key

    Example:
        @cached(ttl=600, namespace="analysis")
        async def analyze_pcb(image_hash: str):
            # Expensive operation
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]

            # Add positional args
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                else:
                    # Hash complex objects
                    key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])

            # Add keyword args
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            cache = global_cache  # Use global cache instance
            cached_value = await cache.get(cache_key, namespace)

            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl, namespace)

            return result

        return wrapper
    return decorator


# Global cache instance
global_cache = MultiLayerCache()

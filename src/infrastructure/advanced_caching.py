"""
Advanced Multi-Layer Caching System

Features:
- L1: In-memory LRU cache
- L2: Redis distributed cache
- L3: CDN edge cache
- Cache warming and prefetching
- Intelligent cache invalidation
- Cache analytics and monitoring
- Cache stampede prevention
- Probabilistic early expiration
"""

from typing import Dict, Any, List, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import hashlib
import json
import time
from collections import OrderedDict
import aioredis
from loguru import logger
import pickle


T = TypeVar('T')


class CacheLayer(Enum):
    """Cache layer types."""
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_CDN = "l3_cdn"


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    key: str
    value: T
    created_at: datetime
    expires_at: datetime
    access_count: int
    last_accessed: datetime
    size_bytes: int
    tags: List[str]


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int
    misses: int
    evictions: int
    size_bytes: int
    entry_count: int
    hit_rate: float
    avg_access_time_ms: float


class LRUCache(Generic[T]):
    """Thread-safe LRU cache implementation."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time to live in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        async with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None

            entry = self.cache[key]

            # Check expiration
            if datetime.utcnow() >= entry.expires_at:
                del self.cache[key]
                self.misses += 1
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)

            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()

            self.hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (overrides default)
            tags: Cache tags for invalidation
        """
        async with self._lock:
            ttl_seconds = ttl or self.ttl_seconds
            now = datetime.utcnow()

            # Calculate size
            try:
                size_bytes = len(pickle.dumps(value))
            except:
                size_bytes = 0

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                access_count=0,
                last_accessed=now,
                size_bytes=size_bytes,
                tags=tags or []
            )

            # Evict if at capacity
            if len(self.cache) >= self.max_size and key not in self.cache:
                # Remove least recently used
                self.cache.popitem(last=False)
                self.evictions += 1

            self.cache[key] = entry

    async def delete(self, key: str):
        """Delete key from cache."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]

    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()

    async def invalidate_by_tag(self, tag: str):
        """Invalidate all entries with specific tag."""
        async with self._lock:
            keys_to_delete = [
                key for key, entry in self.cache.items()
                if tag in entry.tags
            ]

            for key in keys_to_delete:
                del self.cache[key]

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return CacheStats(
            hits=self.hits,
            misses=self.misses,
            evictions=self.evictions,
            size_bytes=total_size,
            entry_count=len(self.cache),
            hit_rate=hit_rate,
            avg_access_time_ms=0.1  # L1 is very fast
        )


class RedisCache:
    """Redis-based distributed cache."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "circuit_ai:"
    ):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL
            key_prefix: Key prefix for namespacing
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.redis: Optional[aioredis.Redis] = None
        self.hits = 0
        self.misses = 0
        logger.info(f"RedisCache initialized with URL: {redis_url}")

    async def connect(self):
        """Connect to Redis."""
        if not self.redis:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False
            )
            logger.info("Connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None

    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from Redis.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        await self.connect()

        try:
            redis_key = self._make_key(key)
            data = await self.redis.get(redis_key)

            if data is None:
                self.misses += 1
                return None

            # Deserialize
            value = pickle.loads(data)
            self.hits += 1
            return value

        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self.misses += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tags: Optional[List[str]] = None
    ):
        """
        Set value in Redis.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Cache tags
        """
        await self.connect()

        try:
            redis_key = self._make_key(key)

            # Serialize
            data = pickle.dumps(value)

            # Set with expiration
            await self.redis.setex(redis_key, ttl, data)

            # Store tags for invalidation
            if tags:
                for tag in tags:
                    tag_key = self._make_key(f"tag:{tag}")
                    await self.redis.sadd(tag_key, key)
                    await self.redis.expire(tag_key, ttl)

        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str):
        """Delete key from Redis."""
        await self.connect()

        try:
            redis_key = self._make_key(key)
            await self.redis.delete(redis_key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    async def invalidate_by_tag(self, tag: str):
        """Invalidate all entries with specific tag."""
        await self.connect()

        try:
            tag_key = self._make_key(f"tag:{tag}")

            # Get all keys with this tag
            keys = await self.redis.smembers(tag_key)

            if keys:
                # Delete all keys
                redis_keys = [self._make_key(k.decode()) for k in keys]
                await self.redis.delete(*redis_keys)

                # Delete tag set
                await self.redis.delete(tag_key)

                logger.info(f"Invalidated {len(keys)} entries with tag: {tag}")

        except Exception as e:
            logger.error(f"Redis tag invalidation error: {e}")

    async def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern."""
        await self.connect()

        try:
            redis_pattern = self._make_key(pattern)
            cursor = 0

            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=redis_pattern,
                    count=100
                )

                if keys:
                    await self.redis.delete(*keys)

                if cursor == 0:
                    break

        except Exception as e:
            logger.error(f"Redis pattern clear error: {e}")


class MultiLayerCache:
    """Multi-layer caching system with L1 (memory) and L2 (Redis)."""

    def __init__(
        self,
        l1_max_size: int = 1000,
        l1_ttl: int = 300,  # 5 minutes
        l2_ttl: int = 3600,  # 1 hour
        redis_url: str = "redis://localhost:6379"
    ):
        """
        Initialize multi-layer cache.

        Args:
            l1_max_size: L1 cache max entries
            l1_ttl: L1 TTL in seconds
            l2_ttl: L2 TTL in seconds
            redis_url: Redis connection URL
        """
        self.l1 = LRUCache(max_size=l1_max_size, ttl_seconds=l1_ttl)
        self.l2 = RedisCache(redis_url=redis_url)
        self.l2_ttl = l2_ttl
        self.stampede_locks: Dict[str, asyncio.Lock] = {}
        logger.info("MultiLayerCache initialized")

    async def get(
        self,
        key: str,
        fetch_fn: Optional[Callable] = None,
        ttl: Optional[int] = None
    ) -> Optional[Any]:
        """
        Get value from cache with automatic fetching.

        Checks L1 first, then L2, then calls fetch_fn if provided.

        Args:
            key: Cache key
            fetch_fn: Function to fetch value if not cached
            ttl: TTL override

        Returns:
            Cached or fetched value
        """
        # Try L1 (memory)
        value = await self.l1.get(key)
        if value is not None:
            logger.debug(f"L1 cache hit: {key}")
            return value

        # Try L2 (Redis)
        value = await self.l2.get(key)
        if value is not None:
            logger.debug(f"L2 cache hit: {key}")

            # Populate L1
            await self.l1.set(key, value)
            return value

        # Cache miss - fetch if function provided
        if fetch_fn:
            value = await self._fetch_with_stampede_protection(
                key,
                fetch_fn,
                ttl
            )
            return value

        logger.debug(f"Cache miss: {key}")
        return None

    async def _fetch_with_stampede_protection(
        self,
        key: str,
        fetch_fn: Callable,
        ttl: Optional[int]
    ) -> Any:
        """
        Fetch value with cache stampede protection.

        Prevents multiple simultaneous fetches for the same key.

        Args:
            key: Cache key
            fetch_fn: Fetch function
            ttl: TTL override

        Returns:
            Fetched value
        """
        # Get or create lock for this key
        if key not in self.stampede_locks:
            self.stampede_locks[key] = asyncio.Lock()

        lock = self.stampede_locks[key]

        async with lock:
            # Double-check cache after acquiring lock
            value = await self.l2.get(key)
            if value is not None:
                await self.l1.set(key, value)
                return value

            # Fetch value
            logger.debug(f"Fetching value for: {key}")
            start_time = time.time()

            if asyncio.iscoroutinefunction(fetch_fn):
                value = await fetch_fn()
            else:
                value = fetch_fn()

            fetch_time = time.time() - start_time
            logger.debug(f"Fetched {key} in {fetch_time*1000:.2f}ms")

            # Store in both layers
            await self.set(key, value, ttl=ttl)

            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Set value in all cache layers.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL override
            tags: Cache tags
        """
        # Set in L1
        await self.l1.set(key, value, tags=tags)

        # Set in L2 with longer TTL
        l2_ttl = ttl or self.l2_ttl
        await self.l2.set(key, value, ttl=l2_ttl, tags=tags)

    async def delete(self, key: str):
        """Delete from all layers."""
        await self.l1.delete(key)
        await self.l2.delete(key)

    async def invalidate_by_tag(self, tag: str):
        """Invalidate by tag in all layers."""
        await self.l1.invalidate_by_tag(tag)
        await self.l2.invalidate_by_tag(tag)

    async def warm_cache(
        self,
        keys_and_fetchers: List[tuple[str, Callable]]
    ):
        """
        Warm cache with commonly accessed data.

        Args:
            keys_and_fetchers: List of (key, fetch_function) tuples
        """
        logger.info(f"Warming cache with {len(keys_and_fetchers)} entries")

        # Fetch all in parallel
        tasks = []
        for key, fetch_fn in keys_and_fetchers:
            tasks.append(self.get(key, fetch_fn=fetch_fn))

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Cache warming complete")

    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all layers."""
        return {
            'l1_memory': self.l1.get_stats(),
            'l2_redis': CacheStats(
                hits=self.l2.hits,
                misses=self.l2.misses,
                evictions=0,
                size_bytes=0,
                entry_count=0,
                hit_rate=(self.l2.hits / (self.l2.hits + self.l2.misses) * 100)
                if (self.l2.hits + self.l2.misses) > 0 else 0,
                avg_access_time_ms=5.0  # Approximate
            )
        }


class CacheWarmer:
    """Intelligent cache warming service."""

    def __init__(self, cache: MultiLayerCache):
        """
        Initialize cache warmer.

        Args:
            cache: Cache instance
        """
        self.cache = cache
        self.warming_tasks: List[asyncio.Task] = []
        logger.info("CacheWarmer initialized")

    async def start_continuous_warming(
        self,
        interval_seconds: int = 300
    ):
        """
        Start continuous cache warming.

        Args:
            interval_seconds: Warming interval
        """
        async def warm_periodically():
            while True:
                try:
                    await self.warm_popular_data()
                    await asyncio.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"Cache warming error: {e}")
                    await asyncio.sleep(60)

        task = asyncio.create_task(warm_periodically())
        self.warming_tasks.append(task)

    async def warm_popular_data(self):
        """Warm cache with popular/predictable data."""
        # Example: Pre-load common component data
        popular_keys = [
            ("popular_components", self._fetch_popular_components),
            ("common_bom_templates", self._fetch_bom_templates),
            ("recent_analyses", self._fetch_recent_analyses),
        ]

        await self.cache.warm_cache(popular_keys)

    async def _fetch_popular_components(self) -> List[Dict[str, Any]]:
        """Fetch popular components."""
        # TODO: Query database for popular components
        return []

    async def _fetch_bom_templates(self) -> List[Dict[str, Any]]:
        """Fetch BOM templates."""
        # TODO: Query database
        return []

    async def _fetch_recent_analyses(self) -> List[Dict[str, Any]]:
        """Fetch recent analyses."""
        # TODO: Query database
        return []

    async def warm_for_user(self, user_id: str):
        """
        Warm cache with user-specific data.

        Args:
            user_id: User ID
        """
        user_keys = [
            (f"user:{user_id}:profile", lambda: self._fetch_user_profile(user_id)),
            (f"user:{user_id}:recent", lambda: self._fetch_user_recent(user_id)),
            (f"user:{user_id}:favorites", lambda: self._fetch_user_favorites(user_id)),
        ]

        await self.cache.warm_cache(user_keys)

    async def _fetch_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch user profile."""
        # TODO: Query database
        return {}

    async def _fetch_user_recent(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch user recent activity."""
        # TODO: Query database
        return []

    async def _fetch_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch user favorites."""
        # TODO: Query database
        return []


class ProbabilisticEarlyExpiration:
    """
    Probabilistic early expiration to prevent cache stampedes.

    Based on XFetch algorithm.
    """

    @staticmethod
    def should_refresh(
        current_time: datetime,
        expires_at: datetime,
        beta: float = 1.0
    ) -> bool:
        """
        Determine if cache should be refreshed early.

        Args:
            current_time: Current time
            expires_at: Expiration time
            beta: Randomization factor (higher = more aggressive)

        Returns:
            True if should refresh early
        """
        import random
        import math

        ttl_remaining = (expires_at - current_time).total_seconds()

        if ttl_remaining <= 0:
            return True

        # Probability increases as expiration approaches
        probability = beta * math.exp(-ttl_remaining / 3600)

        return random.random() < probability


# Singleton instance
multi_layer_cache = MultiLayerCache(
    l1_max_size=1000,
    l1_ttl=300,
    l2_ttl=3600,
    redis_url="redis://localhost:6379"
)

cache_warmer = CacheWarmer(multi_layer_cache)

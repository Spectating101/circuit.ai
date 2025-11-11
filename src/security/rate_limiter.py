"""
IP-based rate limiting with Redis backend

Provides comprehensive rate limiting:
- Per-IP rate limiting
- Per-user rate limiting
- Per-endpoint rate limiting
- Sliding window algorithm
- Redis-backed for distributed systems
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from loguru import logger
import redis
import hashlib
import time
from functools import wraps

class IPRateLimiter:
    """
    IP-based rate limiter using Redis sliding window algorithm.

    Features:
    - Sliding window rate limiting
    - Per-IP, per-endpoint limits
    - Configurable time windows
    - Distributed-friendly (Redis)
    - Graceful fallback (in-memory)
    """

    def __init__(self,
                 redis_client: Optional[redis.Redis] = None,
                 default_limit: int = 60,
                 default_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client instance (None for in-memory)
            default_limit: Default requests per window
            default_window: Default window in seconds
        """
        self.redis_client = redis_client
        self.default_limit = default_limit
        self.default_window = default_window

        # In-memory fallback storage
        self._memory_storage = {}

        # Track if Redis is available
        self._redis_available = self._check_redis()

        logger.info(f"IPRateLimiter initialized (Redis: {self._redis_available})")

    def _check_redis(self) -> bool:
        """Check if Redis is available."""
        if not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory fallback: {e}")
            return False

    def _get_client_identifier(self, request: Request, user_id: Optional[str] = None) -> str:
        """
        Get unique identifier for client (IP + user_id if available).

        Args:
            request: FastAPI Request object
            user_id: Optional user ID

        Returns:
            Unique client identifier
        """
        ip = get_client_ip(request)

        if user_id:
            # Hash user_id for privacy
            user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
            return f"ip:{ip}:user:{user_hash}"

        return f"ip:{ip}"

    def _check_rate_limit_redis(self,
                                key: str,
                                limit: int,
                                window: int) -> Tuple[bool, dict]:
        """
        Check rate limit using Redis sliding window.

        Args:
            key: Rate limit key
            limit: Max requests
            window: Time window in seconds

        Returns:
            Tuple of (allowed, info_dict)
        """
        now = time.time()
        window_start = now - window

        try:
            # Use Redis sorted set for sliding window
            pipe = self.redis_client.pipeline()

            # Remove old entries outside window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request timestamp
            pipe.zadd(key, {str(now): now})

            # Set expiration
            pipe.expire(key, window * 2)

            results = pipe.execute()

            current_count = results[1]  # Count before adding new request
            allowed = current_count < limit

            # Get oldest request timestamp for reset calculation
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            reset_time = now + window if not oldest else oldest[0][1] + window

            info = {
                "limit": limit,
                "remaining": max(0, limit - current_count - 1),
                "reset": int(reset_time),
                "retry_after": int(reset_time - now) if not allowed else 0
            }

            return allowed, info

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fall back to in-memory
            self._redis_available = False
            return self._check_rate_limit_memory(key, limit, window)

    def _check_rate_limit_memory(self,
                                 key: str,
                                 limit: int,
                                 window: int) -> Tuple[bool, dict]:
        """
        Check rate limit using in-memory storage (fallback).

        Args:
            key: Rate limit key
            limit: Max requests
            window: Time window in seconds

        Returns:
            Tuple of (allowed, info_dict)
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=window)

        # Initialize key if not exists
        if key not in self._memory_storage:
            self._memory_storage[key] = []

        # Clean old entries
        self._memory_storage[key] = [
            ts for ts in self._memory_storage[key]
            if ts > window_start
        ]

        current_count = len(self._memory_storage[key])
        allowed = current_count < limit

        if allowed:
            self._memory_storage[key].append(now)

        # Calculate reset time
        reset_time = (self._memory_storage[key][0] + timedelta(seconds=window)) if self._memory_storage[key] else (now + timedelta(seconds=window))
        retry_after = int((reset_time - now).total_seconds()) if not allowed else 0

        info = {
            "limit": limit,
            "remaining": max(0, limit - current_count - 1),
            "reset": int(reset_time.timestamp()),
            "retry_after": retry_after
        }

        return allowed, info

    def check_rate_limit(self,
                        request: Request,
                        endpoint: str,
                        user_id: Optional[str] = None,
                        limit: Optional[int] = None,
                        window: Optional[int] = None) -> Tuple[bool, dict]:
        """
        Check if request is within rate limits.

        Args:
            request: FastAPI Request object
            endpoint: API endpoint identifier
            user_id: Optional user ID
            limit: Requests per window (default: self.default_limit)
            window: Window in seconds (default: self.default_window)

        Returns:
            Tuple of (allowed, info_dict)
        """
        limit = limit or self.default_limit
        window = window or self.default_window

        # Build rate limit key
        client_id = self._get_client_identifier(request, user_id)
        key = f"ratelimit:{client_id}:{endpoint}"

        # Check using Redis or memory
        if self._redis_available:
            return self._check_rate_limit_redis(key, limit, window)
        else:
            return self._check_rate_limit_memory(key, limit, window)

    def get_rate_limit_info(self,
                           request: Request,
                           endpoint: str,
                           user_id: Optional[str] = None,
                           limit: Optional[int] = None,
                           window: Optional[int] = None) -> dict:
        """
        Get rate limit information without incrementing counter.

        Args:
            request: FastAPI Request object
            endpoint: API endpoint identifier
            user_id: Optional user ID
            limit: Requests per window
            window: Window in seconds

        Returns:
            Rate limit info dict
        """
        limit = limit or self.default_limit
        window = window or self.default_window

        client_id = self._get_client_identifier(request, user_id)
        key = f"ratelimit:{client_id}:{endpoint}"

        now = time.time()

        if self._redis_available:
            try:
                count = self.redis_client.zcount(key, now - window, now)
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = now + window if not oldest else oldest[0][1] + window

                return {
                    "limit": limit,
                    "remaining": max(0, limit - count),
                    "reset": int(reset_time),
                    "window": window
                }
            except Exception as e:
                logger.error(f"Failed to get rate limit info from Redis: {e}")

        # In-memory fallback
        if key in self._memory_storage:
            window_start = datetime.now() - timedelta(seconds=window)
            count = sum(1 for ts in self._memory_storage[key] if ts > window_start)
            reset_time = (self._memory_storage[key][0] + timedelta(seconds=window)).timestamp() if self._memory_storage[key] else (now + window)

            return {
                "limit": limit,
                "remaining": max(0, limit - count),
                "reset": int(reset_time),
                "window": window
            }

        return {
            "limit": limit,
            "remaining": limit,
            "reset": int(now + window),
            "window": window
        }


def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request.

    Checks headers for proxied requests:
    - X-Forwarded-For
    - X-Real-IP
    - CF-Connecting-IP (Cloudflare)

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address
    """
    # Check forwarded headers (for reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first (client IP)
        return forwarded_for.split(',')[0].strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Check Cloudflare header
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # Fall back to direct client address
    if request.client:
        return request.client.host

    return "unknown"


def rate_limit_middleware(rate_limiter: IPRateLimiter,
                          limit: int = 60,
                          window: int = 60):
    """
    Decorator for rate limiting endpoints.

    Usage:
        @app.get("/endpoint")
        @rate_limit_middleware(rate_limiter, limit=100, window=60)
        async def endpoint(request: Request):
            ...

    Args:
        rate_limiter: IPRateLimiter instance
        limit: Max requests per window
        window: Window in seconds

    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Extract user_id if available
            user_id = None
            if hasattr(request.state, 'user'):
                user_id = request.state.user.get('user_id')

            # Get endpoint path
            endpoint = request.url.path

            # Check rate limit
            allowed, info = rate_limiter.check_rate_limit(
                request, endpoint, user_id, limit, window
            )

            # Add rate limit headers to response
            if hasattr(request.state, 'rate_limit_info'):
                request.state.rate_limit_info = info

            if not allowed:
                # Rate limit exceeded
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {info['retry_after']} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(info['limit']),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(info['reset']),
                        "Retry-After": str(info['retry_after'])
                    }
                )

            # Execute endpoint
            return await func(request, *args, **kwargs)

        return wrapper
    return decorator

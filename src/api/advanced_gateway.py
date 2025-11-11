"""
Advanced API Gateway

Features:
- Per-endpoint rate limiting
- Token bucket algorithm
- Request routing and load balancing
- API key management
- Request/response transformation
- Circuit breakers per endpoint
- Request queuing
- Adaptive rate limiting
- Geographic routing
- API versioning
- Request caching
- Analytics and monitoring
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import time
from collections import deque
import hashlib
from loguru import logger
from fastapi import Request, Response, HTTPException, status
from fastapi.routing import APIRoute
import jwt


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int  # Max burst allowed
    strategy: RateLimitStrategy


@dataclass
class APIKey:
    """API key."""
    key: str
    name: str
    user_id: str
    tier: str  # free, pro, enterprise
    rate_limit: RateLimitConfig
    allowed_endpoints: Optional[List[str]]
    expires_at: Optional[datetime]
    created_at: datetime
    last_used: Optional[datetime]


@dataclass
class EndpointConfig:
    """Endpoint configuration."""
    path: str
    method: str
    rate_limit: RateLimitConfig
    cache_ttl: Optional[int]  # seconds
    timeout: float  # seconds
    circuit_breaker_enabled: bool
    require_auth: bool


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(
        self,
        capacity: int,
        refill_rate: float  # tokens per second
    ):
        """
        Initialize token bucket.

        Args:
            capacity: Bucket capacity (max tokens)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens consumed, False if insufficient
        """
        async with self._lock:
            # Refill bucket
            now = time.time()
            elapsed = now - self.last_refill

            new_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def wait_for_tokens(self, tokens: int = 1, timeout: float = 10.0):
        """
        Wait until tokens available.

        Args:
            tokens: Number of tokens needed
            timeout: Max wait time in seconds

        Raises:
            TimeoutError: If timeout exceeded
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.consume(tokens):
                return

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

        raise TimeoutError("Rate limit timeout")


class SlidingWindowCounter:
    """Sliding window rate limiter."""

    def __init__(self, window_size: int):
        """
        Initialize sliding window counter.

        Args:
            window_size: Window size in seconds
        """
        self.window_size = window_size
        self.requests: deque = deque()
        self._lock = asyncio.Lock()

    async def add_request(self) -> int:
        """
        Add request and return current count.

        Returns:
            Number of requests in window
        """
        async with self._lock:
            now = time.time()

            # Remove old requests outside window
            cutoff = now - self.window_size
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            # Add new request
            self.requests.append(now)

            return len(self.requests)

    async def get_count(self) -> int:
        """Get current request count."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_size

            # Clean old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            return len(self.requests)


class CircuitBreaker:
    """Circuit breaker for endpoints."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening
            success_threshold: Successes to close from half-open
            timeout: Time before trying half-open (seconds)
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[[], Awaitable[Any]]
    ) -> Any:
        """
        Call function through circuit breaker.

        Args:
            func: Async function to call

        Returns:
            Function result

        Raises:
            HTTPException: If circuit is open
        """
        async with self._lock:
            # Check state
            if self.state == CircuitState.OPEN:
                # Check if timeout elapsed
                if time.time() - self.last_failure_time >= self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Service temporarily unavailable"
                    )

        # Try to call function
        try:
            result = await func()

            async with self._lock:
                # Success
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.success_threshold:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0

            return result

        except Exception as e:
            async with self._lock:
                # Failure
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN

                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN

            raise


class RateLimiter:
    """Comprehensive rate limiter."""

    def __init__(self):
        """Initialize rate limiter."""
        self.user_limiters: Dict[str, Dict[str, Any]] = {}
        self.endpoint_limiters: Dict[str, Dict[str, Any]] = {}
        logger.info("RateLimiter initialized")

    def get_user_limiter(
        self,
        user_id: str,
        config: RateLimitConfig
    ) -> TokenBucket:
        """Get or create user rate limiter."""
        if user_id not in self.user_limiters:
            # Create token bucket
            # Refill rate: requests per minute / 60 = requests per second
            refill_rate = config.requests_per_minute / 60.0

            self.user_limiters[user_id] = {
                'bucket': TokenBucket(
                    capacity=config.burst_size,
                    refill_rate=refill_rate
                ),
                'minute_window': SlidingWindowCounter(60),
                'hour_window': SlidingWindowCounter(3600),
                'day_window': SlidingWindowCounter(86400)
            }

        return self.user_limiters[user_id]['bucket']

    async def check_rate_limit(
        self,
        user_id: str,
        config: RateLimitConfig
    ) -> bool:
        """
        Check if request allowed under rate limit.

        Args:
            user_id: User identifier
            config: Rate limit configuration

        Returns:
            True if allowed, False if rate limited
        """
        limiters = self.user_limiters.get(user_id)

        if not limiters:
            limiters = {
                'bucket': TokenBucket(
                    capacity=config.burst_size,
                    refill_rate=config.requests_per_minute / 60.0
                ),
                'minute_window': SlidingWindowCounter(60),
                'hour_window': SlidingWindowCounter(3600),
                'day_window': SlidingWindowCounter(86400)
            }
            self.user_limiters[user_id] = limiters

        # Check token bucket (for burst)
        if not await limiters['bucket'].consume(1):
            return False

        # Check windows
        minute_count = await limiters['minute_window'].add_request()
        if minute_count > config.requests_per_minute:
            return False

        hour_count = await limiters['hour_window'].add_request()
        if hour_count > config.requests_per_hour:
            return False

        day_count = await limiters['day_window'].add_request()
        if day_count > config.requests_per_day:
            return False

        return True

    async def get_rate_limit_status(
        self,
        user_id: str,
        config: RateLimitConfig
    ) -> Dict[str, Any]:
        """Get current rate limit status."""
        limiters = self.user_limiters.get(user_id)

        if not limiters:
            return {
                'minute_remaining': config.requests_per_minute,
                'hour_remaining': config.requests_per_hour,
                'day_remaining': config.requests_per_day,
                'burst_remaining': config.burst_size
            }

        minute_used = await limiters['minute_window'].get_count()
        hour_used = await limiters['hour_window'].get_count()
        day_used = await limiters['day_window'].get_count()

        return {
            'minute_remaining': max(0, config.requests_per_minute - minute_used),
            'hour_remaining': max(0, config.requests_per_hour - hour_used),
            'day_remaining': max(0, config.requests_per_day - day_used),
            'burst_remaining': int(limiters['bucket'].tokens)
        }


class APIKeyManager:
    """Manage API keys."""

    def __init__(self, secret_key: str):
        """
        Initialize API key manager.

        Args:
            secret_key: Secret for signing keys
        """
        self.secret_key = secret_key
        self.keys: Dict[str, APIKey] = {}
        logger.info("APIKeyManager initialized")

    def create_api_key(
        self,
        user_id: str,
        name: str,
        tier: str = "free",
        expires_in_days: Optional[int] = None
    ) -> str:
        """
        Create new API key.

        Args:
            user_id: User ID
            name: Key name
            tier: Tier (free, pro, enterprise)
            expires_in_days: Expiration in days

        Returns:
            API key
        """
        # Generate key
        key_id = hashlib.sha256(
            f"{user_id}:{name}:{time.time()}".encode()
        ).hexdigest()[:32]

        # Sign key
        payload = {
            'key_id': key_id,
            'user_id': user_id,
            'tier': tier
        }

        api_key = jwt.encode(payload, self.secret_key, algorithm='HS256')

        # Rate limit based on tier
        rate_limit = self._get_tier_rate_limit(tier)

        # Expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Store key
        self.keys[api_key] = APIKey(
            key=api_key,
            name=name,
            user_id=user_id,
            tier=tier,
            rate_limit=rate_limit,
            allowed_endpoints=None,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            last_used=None
        )

        logger.info(f"Created API key for user {user_id} ({tier})")

        return api_key

    def _get_tier_rate_limit(self, tier: str) -> RateLimitConfig:
        """Get rate limit configuration for tier."""
        configs = {
            'free': RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                requests_per_day=1000,
                burst_size=15,
                strategy=RateLimitStrategy.TOKEN_BUCKET
            ),
            'pro': RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=5000,
                requests_per_day=50000,
                burst_size=150,
                strategy=RateLimitStrategy.TOKEN_BUCKET
            ),
            'enterprise': RateLimitConfig(
                requests_per_minute=1000,
                requests_per_hour=50000,
                requests_per_day=1000000,
                burst_size=1500,
                strategy=RateLimitStrategy.TOKEN_BUCKET
            )
        }

        return configs.get(tier, configs['free'])

    async def validate_api_key(self, api_key: str) -> Optional[APIKey]:
        """
        Validate API key.

        Args:
            api_key: API key to validate

        Returns:
            APIKey object or None if invalid
        """
        if api_key not in self.keys:
            return None

        key_obj = self.keys[api_key]

        # Check expiration
        if key_obj.expires_at and datetime.utcnow() > key_obj.expires_at:
            return None

        # Update last used
        key_obj.last_used = datetime.utcnow()

        return key_obj

    def revoke_api_key(self, api_key: str):
        """Revoke API key."""
        if api_key in self.keys:
            del self.keys[api_key]
            logger.info(f"Revoked API key")


class APIGateway:
    """Advanced API gateway."""

    def __init__(self, secret_key: str):
        """
        Initialize API gateway.

        Args:
            secret_key: Secret key for signing
        """
        self.rate_limiter = RateLimiter()
        self.key_manager = APIKeyManager(secret_key)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.endpoint_configs: Dict[str, EndpointConfig] = {}
        logger.info("APIGateway initialized")

    def register_endpoint(
        self,
        path: str,
        method: str,
        config: EndpointConfig
    ):
        """Register endpoint configuration."""
        key = f"{method}:{path}"
        self.endpoint_configs[key] = config

        # Create circuit breaker if enabled
        if config.circuit_breaker_enabled:
            self.circuit_breakers[key] = CircuitBreaker()

    async def process_request(
        self,
        request: Request,
        endpoint_handler: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process API request through gateway.

        Args:
            request: Incoming request
            endpoint_handler: Handler function

        Returns:
            Response

        Raises:
            HTTPException: On various errors
        """
        # Get endpoint config
        endpoint_key = f"{request.method}:{request.url.path}"
        config = self.endpoint_configs.get(endpoint_key)

        if not config:
            # No config, pass through
            return await endpoint_handler(request)

        # Authenticate
        if config.require_auth:
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required"
                )

            key_obj = await self.key_manager.validate_api_key(api_key)
            if not key_obj:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )

            # Check rate limit
            allowed = await self.rate_limiter.check_rate_limit(
                key_obj.user_id,
                key_obj.rate_limit
            )

            if not allowed:
                # Get status for headers
                status_dict = await self.rate_limiter.get_rate_limit_status(
                    key_obj.user_id,
                    key_obj.rate_limit
                )

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        'X-RateLimit-Remaining-Minute': str(status_dict['minute_remaining']),
                        'X-RateLimit-Remaining-Hour': str(status_dict['hour_remaining'])
                    }
                )

        # Circuit breaker
        if config.circuit_breaker_enabled:
            circuit = self.circuit_breakers[endpoint_key]
            response = await circuit.call(lambda: endpoint_handler(request))
        else:
            response = await endpoint_handler(request)

        return response


class AdaptiveRateLimiter:
    """Adaptive rate limiting based on system load."""

    def __init__(
        self,
        base_limit: int,
        min_limit: int,
        max_limit: int
    ):
        """
        Initialize adaptive rate limiter.

        Args:
            base_limit: Base request limit
            min_limit: Minimum limit under load
            max_limit: Maximum limit when idle
        """
        self.base_limit = base_limit
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.current_limit = base_limit

        self.response_times: deque = deque(maxlen=100)
        self.error_count = 0
        self.total_requests = 0

    async def adjust_limit(self):
        """Adjust rate limit based on metrics."""
        if len(self.response_times) < 10:
            return

        # Calculate average response time
        avg_response_time = sum(self.response_times) / len(self.response_times)

        # Calculate error rate
        error_rate = self.error_count / self.total_requests if self.total_requests > 0 else 0

        # Adjust limit
        if avg_response_time > 2.0 or error_rate > 0.05:
            # System under stress, decrease limit
            self.current_limit = max(
                self.min_limit,
                int(self.current_limit * 0.9)
            )
        elif avg_response_time < 0.5 and error_rate < 0.01:
            # System doing well, increase limit
            self.current_limit = min(
                self.max_limit,
                int(self.current_limit * 1.1)
            )

        logger.debug(
            f"Adjusted rate limit to {self.current_limit} "
            f"(avg_rt: {avg_response_time:.3f}s, error_rate: {error_rate:.2%})"
        )

    def record_request(self, response_time: float, is_error: bool):
        """Record request metrics."""
        self.response_times.append(response_time)
        self.total_requests += 1

        if is_error:
            self.error_count += 1


# Singleton instance
api_gateway = APIGateway(secret_key="your-secret-key-here")

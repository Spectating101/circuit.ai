"""
Reliability module for Circuit.AI

Provides:
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff
- Graceful degradation
- Health checking
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .retry import RetryStrategy, retry_with_backoff, async_retry_with_backoff
from .health_checker import HealthChecker, ServiceStatus
from .fallback import FallbackManager, with_fallback

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState",
    "RetryStrategy",
    "retry_with_backoff",
    "async_retry_with_backoff",
    "HealthChecker",
    "ServiceStatus",
    "FallbackManager",
    "with_fallback",
]

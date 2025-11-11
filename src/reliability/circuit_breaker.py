"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by detecting when a service is failing
and automatically "opening" the circuit to prevent further calls.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, reject requests immediately
- HALF_OPEN: Testing if service has recovered
"""

from enum import Enum
from typing import Callable, Any, Optional, TypeVar
from datetime import datetime, timedelta
import asyncio
from functools import wraps
from loguru import logger

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Example:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        @breaker.call
        async def api_call():
            return await external_api.fetch()
    """

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception,
                 name: Optional[str] = None):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
            name: Optional name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "unnamed"

        # State tracking
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._half_open_attempts = 0

        logger.info(f"CircuitBreaker '{self.name}' initialized (threshold={failure_threshold}, timeout={recovery_timeout}s)")

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit state."""
        self._check_and_update_state()
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self.state == CircuitBreakerState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self.state == CircuitBreakerState.HALF_OPEN

    def _check_and_update_state(self):
        """Check if we should transition states."""
        if self._state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                time_since_failure = (datetime.now() - self._last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    self._transition_to_half_open()

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        logger.info(f"CircuitBreaker '{self.name}': OPEN -> HALF_OPEN (testing recovery)")
        self._state = CircuitBreakerState.HALF_OPEN
        self._half_open_attempts = 0

    def _transition_to_open(self):
        """Transition to open state."""
        logger.warning(f"CircuitBreaker '{self.name}': CLOSED/HALF_OPEN -> OPEN (failures={self._failure_count})")
        self._state = CircuitBreakerState.OPEN
        self._last_failure_time = datetime.now()

    def _transition_to_closed(self):
        """Transition to closed state."""
        logger.info(f"CircuitBreaker '{self.name}': HALF_OPEN -> CLOSED (recovered)")
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_success_time = datetime.now()

    def _record_success(self):
        """Record successful call."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Successful test, close circuit
            self._transition_to_closed()
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self._failure_count = max(0, self._failure_count - 1)

        self._last_success_time = datetime.now()

    def _record_failure(self):
        """Record failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        logger.warning(f"CircuitBreaker '{self.name}' failure {self._failure_count}/{self.failure_threshold}")

        if self._failure_count >= self.failure_threshold:
            self._transition_to_open()

    def call(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to wrap function with circuit breaker.

        Args:
            func: Function to wrap

        Returns:
            Wrapped function
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Check if circuit is open
            if self.is_open:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self._last_failure_time.isoformat() if self._last_failure_time else 'unknown'}"
                )

            try:
                # Call function
                result = func(*args, **kwargs)
                self._record_success()
                return result

            except self.expected_exception as e:
                self._record_failure()
                raise

        return wrapper

    def call_async(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Async decorator to wrap coroutine with circuit breaker.

        Args:
            func: Async function to wrap

        Returns:
            Wrapped async function
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Check if circuit is open
            if self.is_open:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self._last_failure_time.isoformat() if self._last_failure_time else 'unknown'}"
                )

            try:
                # Call function
                result = await func(*args, **kwargs)
                self._record_success()
                return result

            except self.expected_exception as e:
                self._record_failure()
                raise

        return wrapper

    def get_status(self) -> dict:
        """
        Get circuit breaker status.

        Returns:
            Status dictionary
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "last_success": self._last_success_time.isoformat() if self._last_success_time else None,
            "recovery_timeout": self.recovery_timeout
        }


# Global circuit breakers for common services
_circuit_breakers = {}


def get_circuit_breaker(name: str,
                       failure_threshold: int = 5,
                       recovery_timeout: int = 60) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Recovery timeout in seconds

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers."""
    return {
        name: breaker.get_status()
        for name, breaker in _circuit_breakers.items()
    }

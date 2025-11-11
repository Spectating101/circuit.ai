"""
Unit tests for reliability module

Tests:
- Circuit breaker
- Retry with exponential backoff
- Health checking
"""

import pytest
import asyncio
from datetime import datetime
import time

from src.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    get_circuit_breaker
)
from src.reliability.retry import (
    RetryStrategy,
    retry_with_backoff,
    async_retry_with_backoff
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.is_closed

    def test_successful_calls(self):
        """Test successful calls keep circuit closed."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        @breaker.call
        def successful_call():
            return "success"

        # Multiple successful calls
        for _ in range(10):
            result = successful_call()
            assert result == "success"

        assert breaker.is_closed

    def test_failure_opens_circuit(self):
        """Test failures open the circuit."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        @breaker.call
        def failing_call():
            raise Exception("Test failure")

        # Trigger failures
        for i in range(3):
            with pytest.raises(Exception):
                failing_call()

        # Circuit should now be open
        assert breaker.is_open

    def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls immediately."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)

        @breaker.call
        def failing_call():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                failing_call()

        assert breaker.is_open

        # Next call should be rejected without executing
        with pytest.raises(CircuitBreakerOpenError):
            failing_call()

    def test_recovery_to_half_open(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        @breaker.call
        def failing_call():
            raise Exception("Test failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                failing_call()

        assert breaker.is_open

        # Wait for recovery timeout
        time.sleep(1.5)

        # Check state (should trigger transition to HALF_OPEN)
        assert breaker.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """Test successful call in HALF_OPEN closes circuit."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        call_count = [0]

        @breaker.call
        def conditional_call():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Fail")
            return "success"

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                conditional_call()

        assert breaker.is_open

        # Wait for recovery
        time.sleep(1.5)

        # Successful call should close circuit
        result = conditional_call()
        assert result == "success"
        assert breaker.is_closed

    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self):
        """Test async circuit breaker."""
        breaker = CircuitBreaker(name="test_async", failure_threshold=3)

        @breaker.call_async
        async def async_call():
            await asyncio.sleep(0.1)
            return "success"

        result = await async_call()
        assert result == "success"
        assert breaker.is_closed

    def test_get_status(self):
        """Test circuit breaker status reporting."""
        breaker = CircuitBreaker(name="test")
        status = breaker.get_status()

        assert status['name'] == 'test'
        assert status['state'] == 'closed'
        assert status['failure_count'] == 0


class TestRetryStrategy:
    """Test retry strategy."""

    def test_initial_delay(self):
        """Test initial delay calculation."""
        strategy = RetryStrategy(initial_delay=1.0, jitter=False)
        delay = strategy.get_delay(1)
        assert delay == 1.0

    def test_exponential_backoff(self):
        """Test exponential backoff."""
        strategy = RetryStrategy(
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )

        assert strategy.get_delay(1) == 1.0
        assert strategy.get_delay(2) == 2.0
        assert strategy.get_delay(3) == 4.0

    def test_max_delay(self):
        """Test max delay cap."""
        strategy = RetryStrategy(
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )

        delay = strategy.get_delay(10)
        assert delay <= 5.0

    def test_jitter(self):
        """Test jitter adds randomness."""
        strategy = RetryStrategy(initial_delay=1.0, jitter=True)

        delays = [strategy.get_delay(1) for _ in range(10)]

        # Should have variation
        assert len(set(delays)) > 1
        # All should be around 1.0 (between 0.5 and 1.5)
        assert all(0.5 <= d <= 1.5 for d in delays)


class TestRetryDecorator:
    """Test retry decorator."""

    def test_retry_success_first_attempt(self):
        """Test successful call on first attempt."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, initial_delay=0.1)
        def successful_call():
            call_count[0] += 1
            return "success"

        result = successful_call()
        assert result == "success"
        assert call_count[0] == 1

    def test_retry_success_after_failures(self):
        """Test retry succeeds after initial failures."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, initial_delay=0.1)
        def eventually_successful():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"

        result = eventually_successful()
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_max_attempts_exceeded(self):
        """Test retry fails after max attempts."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, initial_delay=0.1)
        def always_fails():
            call_count[0] += 1
            raise Exception("Always fails")

        with pytest.raises(Exception) as exc_info:
            always_fails()

        assert "Always fails" in str(exc_info.value)
        assert call_count[0] == 3

    def test_retry_specific_exception(self):
        """Test retry only specific exceptions."""
        call_count = [0]

        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.1,
            exceptions=(ValueError,)
        )
        def raises_different_error():
            call_count[0] += 1
            raise TypeError("Wrong exception type")

        with pytest.raises(TypeError):
            raises_different_error()

        # Should fail immediately, not retry
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry decorator."""
        call_count = [0]

        @async_retry_with_backoff(max_attempts=3, initial_delay=0.1)
        async def async_eventually_successful():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Temporary failure")
            await asyncio.sleep(0.01)
            return "success"

        result = await async_eventually_successful()
        assert result == "success"
        assert call_count[0] == 2


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Retry Logic with Exponential Backoff

Provides automatic retry for transient failures with:
- Exponential backoff
- Jitter to prevent thundering herd
- Configurable max attempts
- Custom exception handling
"""

import time
import random
import asyncio
from typing import Callable, TypeVar, Optional, Type, Tuple
from functools import wraps
from loguru import logger

T = TypeVar('T')


class RetryStrategy:
    """Configuration for retry behavior."""

    def __init__(self,
                 max_attempts: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True,
                 exceptions: Tuple[Type[Exception], ...] = (Exception,)):
        """
        Initialize retry strategy.

        Args:
            max_attempts: Maximum retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Add random jitter to delays
            exceptions: Exception types to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt.

        Args:
            attempt: Attempt number (1-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: initial_delay * (base ^ (attempt - 1))
        delay = min(
            self.initial_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )

        # Add jitter (random factor between 0.5 and 1.5)
        if self.jitter:
            delay *= (0.5 + random.random())

        return delay


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry function with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter
        exceptions: Exception types to retry on
        on_retry: Optional callback(exception, attempt)

    Example:
        @retry_with_backoff(max_attempts=5, initial_delay=2.0)
        def api_call():
            return requests.get("https://api.example.com/data")
    """
    strategy = RetryStrategy(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, strategy.max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except strategy.exceptions as e:
                    last_exception = e

                    if attempt == strategy.max_attempts:
                        # Last attempt failed
                        logger.error(
                            f"Function {func.__name__} failed after {strategy.max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay
                    delay = strategy.get_delay(attempt)

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{strategy.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt)

                    # Wait before retry
                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def async_retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Async decorator to retry coroutine with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter
        exceptions: Exception types to retry on
        on_retry: Optional callback(exception, attempt)

    Example:
        @async_retry_with_backoff(max_attempts=5, initial_delay=2.0)
        async def api_call():
            async with session.get("https://api.example.com/data") as resp:
                return await resp.json()
    """
    strategy = RetryStrategy(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, strategy.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except strategy.exceptions as e:
                    last_exception = e

                    if attempt == strategy.max_attempts:
                        # Last attempt failed
                        logger.error(
                            f"Async function {func.__name__} failed after {strategy.max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay
                    delay = strategy.get_delay(attempt)

                    logger.warning(
                        f"Async function {func.__name__} failed (attempt {attempt}/{strategy.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt)

                    # Wait before retry
                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


# Convenience functions for common retry patterns

def retry_api_call(func: Callable[..., T]) -> Callable[..., T]:
    """
    Quick retry for API calls (5 attempts, 2s initial delay).

    Example:
        @retry_api_call
        def fetch_data():
            return requests.get("https://api.example.com/data")
    """
    return retry_with_backoff(
        max_attempts=5,
        initial_delay=2.0,
        max_delay=30.0
    )(func)


def retry_db_operation(func: Callable[..., T]) -> Callable[..., T]:
    """
    Quick retry for database operations (3 attempts, 0.5s initial delay).

    Example:
        @retry_db_operation
        def save_to_db(data):
            session.add(data)
            session.commit()
    """
    return retry_with_backoff(
        max_attempts=3,
        initial_delay=0.5,
        max_delay=5.0
    )(func)


async def retry_async_api_call(func: Callable[..., T]) -> Callable[..., T]:
    """
    Quick retry for async API calls.

    Example:
        @retry_async_api_call
        async def fetch_data():
            async with session.get("https://api.example.com/data") as resp:
                return await resp.json()
    """
    return async_retry_with_backoff(
        max_attempts=5,
        initial_delay=2.0,
        max_delay=30.0
    )(func)

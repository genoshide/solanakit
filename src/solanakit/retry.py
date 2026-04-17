"""
Async & sync retry decorators with exponential backoff and full jitter.

Usage::

    from genosys.retry import async_retry, sync_retry, RetryError

    # Async — wrap any coroutine
    @async_retry(max_attempts=4, base_delay=1.0, max_delay=30.0)
    async def fetch_data():
        return await session.get("/endpoint")

    # Sync — wrap a regular function
    @sync_retry(max_attempts=3, base_delay=0.5, exceptions=(ConnectionError,))
    def check_rpc():
        return web3.is_connected()

If every attempt fails, ``RetryError`` is raised with the last exception
attached as ``__cause__``.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Full-jitter exponential backoff::

        delay = random(0, min(max_delay, base_delay * exponential_base ** attempt))

    Full jitter prevents thundering-herd when many coroutines retry at the same time.
    """
    cap = min(max_delay, base_delay * (exponential_base ** attempt))
    return random.uniform(0, cap) if jitter else cap


# ---------------------------------------------------------------------------
# async_retry
# ---------------------------------------------------------------------------

def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> Callable:
    """
    Decorator — wraps an **async** function with retry logic.

    Parameters
    ----------
    max_attempts : int
        Total number of tries including the first call (default 3).
    base_delay : float
        Starting sleep time in seconds (default 1.0).
    max_delay : float
        Upper cap for the computed sleep time (default 60.0).
    exponential_base : float
        Multiplier applied per attempt (default 2.0 → 1 s, 2 s, 4 s …).
    jitter : bool
        Add full random jitter to prevent thundering-herd (default True).
    exceptions : tuple
        Exception types that trigger a retry.
        Any exception **not** in this tuple propagates immediately.
    on_retry : callable | None
        Optional ``callback(attempt_number, exception, delay)`` called
        just before each sleep.  Useful for custom log messages.

    Raises
    ------
    RetryError
        When all attempts are exhausted.

    Example
    -------
    ::

        @async_retry(max_attempts=5, base_delay=0.5, exceptions=(aiohttp.ClientError,))
        async def call_api():
            async with session.get(url) as r:
                return await r.json()
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    remaining = max_attempts - attempt - 1

                    if remaining == 0:
                        break

                    delay = _compute_delay(
                        attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    if on_retry is not None:
                        on_retry(attempt + 1, exc, delay)
                    else:
                        logger.warning(
                            "%s failed (attempt %d/%d): %s — retrying in %.2fs",
                            func.__qualname__,
                            attempt + 1,
                            max_attempts,
                            exc,
                            delay,
                        )

                    await asyncio.sleep(delay)

            raise RetryError(
                f"{func.__qualname__} failed after {max_attempts} attempt(s): {last_exc}",
                attempts=max_attempts,
                last_exception=last_exc,
            ) from last_exc

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# sync_retry
# ---------------------------------------------------------------------------

def sync_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> Callable:
    """
    Decorator — wraps a **synchronous** function with retry logic.

    Same parameters as :func:`async_retry` but uses ``time.sleep`` instead
    of ``asyncio.sleep``.  Use this for blocking code (Web3 calls, healthchecks).

    Example
    -------
    ::

        @sync_retry(max_attempts=3, base_delay=1.0, exceptions=(Exception,))
        def get_balance():
            return web3.eth.get_balance(address)
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    remaining = max_attempts - attempt - 1

                    if remaining == 0:
                        break

                    delay = _compute_delay(
                        attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    if on_retry is not None:
                        on_retry(attempt + 1, exc, delay)
                    else:
                        logger.warning(
                            "%s failed (attempt %d/%d): %s — retrying in %.2fs",
                            func.__qualname__,
                            attempt + 1,
                            max_attempts,
                            exc,
                            delay,
                        )

                    time.sleep(delay)

            raise RetryError(
                f"{func.__qualname__} failed after {max_attempts} attempt(s): {last_exc}",
                attempts=max_attempts,
                last_exception=last_exc,
            ) from last_exc

        return wrapper

    return decorator

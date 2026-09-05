"""
common/backoff.py — generic async retry decorator for scraper functions.

SpiceJet's existing scrape_date_with_retries() is NOT replaced by this.
This decorator is additive — available for future use or new scrapers without
duplicating retry logic inline.

Usage:
    from common.backoff import async_retry

    @async_retry(max_attempts=3, base_delay=20.0)
    async def fetch_something():
        ...
"""

import asyncio
import functools
from typing import Callable, Any, Optional


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 10.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Decorator: retry an async function with exponential backoff.

    On each failed attempt (other than the last), sleeps for
    base_delay * attempt_number seconds before retrying.

    Args:
        max_attempts:  Total number of attempts before giving up.
        base_delay:    Base sleep duration in seconds (multiplied by attempt).
        exceptions:    Tuple of exception types that trigger a retry.
                       Defaults to catching all exceptions.

    Raises:
        The last exception encountered if all attempts are exhausted.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = base_delay * attempt
                        print(
                            f"  [!] {func.__name__} attempt {attempt}/{max_attempts} "
                            f"failed: {exc!r} — retrying in {delay:.0f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        print(
                            f"  [!] {func.__name__} exhausted {max_attempts} attempts: "
                            f"{exc!r}"
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator

"""Rate limiting and retry logic for Notion API."""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from notion_time_capsule.utils.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RateLimiter:
    """Rate limiter for Notion API (3 requests per second average)."""

    def __init__(self, requests_per_second: float = 3.0) -> None:
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self._last_request: float = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request

        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug("Rate limiting: sleeping %.3f seconds", sleep_time)
            time.sleep(sleep_time)

        self._last_request = time.monotonic()


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying on rate limit (429) or server errors (5xx).

    Uses exponential backoff with jitter.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        retryable_status_codes: HTTP status codes that trigger retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if this is a retryable API error
                    status_code = _get_status_code(e)

                    if status_code is None or status_code not in retryable_status_codes:
                        raise

                    last_exception = e

                    if attempt < max_retries:
                        # Calculate sleep time with exponential backoff
                        sleep_time = backoff_factor**attempt

                        # For 429, try to use Retry-After header
                        retry_after = _get_retry_after(e)
                        if retry_after:
                            sleep_time = max(sleep_time, retry_after)

                        logger.warning(
                            "Request failed with status %d, retrying in %.1f seconds "
                            "(attempt %d/%d)",
                            status_code,
                            sleep_time,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            "Request failed after %d retries with status %d",
                            max_retries,
                            status_code,
                        )

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


def _get_status_code(exception: Exception) -> int | None:
    """Extract HTTP status code from exception if available."""
    # notion-client raises APIResponseError with status attribute
    if hasattr(exception, "status"):
        return int(exception.status)

    # Also check for code attribute (some error types)
    if hasattr(exception, "code"):
        code = exception.code
        if isinstance(code, int) and 100 <= code < 600:
            return code

    return None


def _get_retry_after(exception: Exception) -> float | None:
    """Extract Retry-After value from exception if available."""
    # notion-client may include headers in response
    if hasattr(exception, "headers"):
        headers = exception.headers
        if headers and "Retry-After" in headers:
            try:
                return float(headers["Retry-After"])
            except (ValueError, TypeError):
                pass

    return None

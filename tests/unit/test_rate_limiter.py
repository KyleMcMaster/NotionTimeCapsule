"""Tests for rate limiter and retry decorator."""

import time
from unittest.mock import MagicMock, patch

import pytest

from notion_time_capsule.notion.rate_limiter import (
    RateLimiter,
    _get_retry_after,
    _get_status_code,
    with_retry,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_first_request_no_wait(self) -> None:
        """First request should not wait."""
        limiter = RateLimiter(requests_per_second=3.0)

        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start

        # Should be nearly instant
        assert elapsed < 0.1

    def test_respects_rate_limit(self) -> None:
        """Should wait to respect rate limit between requests."""
        limiter = RateLimiter(requests_per_second=10.0)  # 100ms between requests

        limiter.wait()
        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start

        # Should wait approximately 100ms
        assert elapsed >= 0.09  # Allow small timing variance

    def test_no_wait_if_enough_time_passed(self) -> None:
        """Should not wait if enough time has passed."""
        limiter = RateLimiter(requests_per_second=10.0)

        limiter.wait()
        time.sleep(0.15)  # Wait longer than required

        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start

        # Should not wait
        assert elapsed < 0.05

    def test_custom_rate(self) -> None:
        """Should respect custom rate."""
        limiter = RateLimiter(requests_per_second=5.0)  # 200ms between requests

        limiter.wait()
        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start

        # Should wait approximately 200ms
        assert elapsed >= 0.18


class TestWithRetry:
    """Tests for with_retry decorator."""

    def test_returns_result_on_success(self) -> None:
        """Should return result when function succeeds."""

        @with_retry(max_retries=3)
        def successful_func() -> str:
            return "success"

        result = successful_func()

        assert result == "success"

    def test_retries_on_retryable_error(self) -> None:
        """Should retry on retryable status codes."""
        call_count = 0

        class MockAPIError(Exception):
            def __init__(self, status: int) -> None:
                self.status = status

        @with_retry(max_retries=3, backoff_factor=0.01)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise MockAPIError(429)
            return "success"

        result = flaky_func()

        assert result == "success"
        assert call_count == 3

    def test_raises_on_non_retryable_error(self) -> None:
        """Should raise immediately on non-retryable errors."""
        call_count = 0

        class MockAPIError(Exception):
            def __init__(self, status: int) -> None:
                self.status = status

        @with_retry(max_retries=3)
        def error_func() -> str:
            nonlocal call_count
            call_count += 1
            raise MockAPIError(404)  # Not retryable

        with pytest.raises(MockAPIError):
            error_func()

        assert call_count == 1  # No retry

    def test_raises_after_max_retries(self) -> None:
        """Should raise after exhausting retries."""
        call_count = 0

        class MockAPIError(Exception):
            def __init__(self, status: int) -> None:
                self.status = status

        @with_retry(max_retries=2, backoff_factor=0.01)
        def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise MockAPIError(500)

        with pytest.raises(MockAPIError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries

    def test_exponential_backoff(self) -> None:
        """Should use exponential backoff."""
        timestamps: list[float] = []

        class MockAPIError(Exception):
            def __init__(self, status: int) -> None:
                self.status = status

        @with_retry(max_retries=2, backoff_factor=0.1)
        def always_fails() -> str:
            timestamps.append(time.monotonic())
            raise MockAPIError(500)

        with pytest.raises(MockAPIError):
            always_fails()

        # Check backoff timing
        assert len(timestamps) == 3
        first_wait = timestamps[1] - timestamps[0]
        second_wait = timestamps[2] - timestamps[1]

        # First retry: 0.1^0 = 0.1s (actually 1s with factor)
        # Second retry: 0.1^1 = 0.1s (actually 0.1*2 = 0.2s)
        # The backoff is backoff_factor ** attempt
        assert first_wait >= 0.05  # ~0.1s
        assert second_wait >= 0.05  # ~0.1s

    def test_retries_on_server_errors(self) -> None:
        """Should retry on 5xx errors."""
        for status_code in [500, 502, 503, 504]:
            call_count = 0

            class MockAPIError(Exception):
                def __init__(self, status: int) -> None:
                    self.status = status

            @with_retry(max_retries=1, backoff_factor=0.01)
            def server_error() -> str:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise MockAPIError(status_code)
                return "success"

            result = server_error()
            assert result == "success"
            assert call_count == 2

    def test_preserves_function_metadata(self) -> None:
        """Should preserve function name and docstring."""

        @with_retry(max_retries=3)
        def documented_func() -> str:
            """This is a docstring."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."

    def test_raises_on_non_api_exception(self) -> None:
        """Should raise immediately for non-API exceptions."""
        call_count = 0

        @with_retry(max_retries=3)
        def raises_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("not an API error")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count == 1  # No retry


class TestGetStatusCode:
    """Tests for _get_status_code helper."""

    def test_extracts_status_attribute(self) -> None:
        """Should extract status from exception."""

        class APIError(Exception):
            def __init__(self, status: int) -> None:
                self.status = status

        error = APIError(429)
        assert _get_status_code(error) == 429

    def test_extracts_code_attribute(self) -> None:
        """Should extract code from exception."""

        class ErrorWithCode(Exception):
            def __init__(self, code: int) -> None:
                self.code = code

        error = ErrorWithCode(500)
        assert _get_status_code(error) == 500

    def test_returns_none_for_no_status(self) -> None:
        """Should return None when no status found."""
        error = ValueError("no status")
        assert _get_status_code(error) is None

    def test_ignores_invalid_code(self) -> None:
        """Should ignore non-HTTP codes."""

        class ErrorWithInvalidCode(Exception):
            def __init__(self, code: int) -> None:
                self.code = code

        error = ErrorWithInvalidCode(42)  # Not a valid HTTP code
        assert _get_status_code(error) is None


class TestGetRetryAfter:
    """Tests for _get_retry_after helper."""

    def test_extracts_retry_after_header(self) -> None:
        """Should extract Retry-After from headers."""

        class APIError(Exception):
            def __init__(self, headers: dict) -> None:
                self.headers = headers

        error = APIError({"Retry-After": "5"})
        assert _get_retry_after(error) == 5.0

    def test_returns_none_without_header(self) -> None:
        """Should return None when no Retry-After header."""

        class APIError(Exception):
            def __init__(self, headers: dict) -> None:
                self.headers = headers

        error = APIError({})
        assert _get_retry_after(error) is None

    def test_returns_none_for_invalid_value(self) -> None:
        """Should return None for non-numeric Retry-After."""

        class APIError(Exception):
            def __init__(self, headers: dict) -> None:
                self.headers = headers

        error = APIError({"Retry-After": "invalid"})
        assert _get_retry_after(error) is None

    def test_returns_none_without_headers(self) -> None:
        """Should return None when exception has no headers."""
        error = ValueError("no headers")
        assert _get_retry_after(error) is None

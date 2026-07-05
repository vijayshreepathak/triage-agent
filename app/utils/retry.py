"""Async retry with exponential backoff.

One retry implementation for the whole codebase (LLM calls, search calls)
instead of ad-hoc loops in each tool — retries are a cross-cutting concern,
so they live in utils, and every retry is logged with attempt number.

Kept dependency-free (no tenacity) so the backoff behavior is fully
explicit and trivially unit-testable with a fake clock.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts fail. Carries the last underlying error."""

    def __init__(self, operation: str, attempts: int, last_error: BaseException) -> None:
        super().__init__(f"{operation} failed after {attempts} attempts: {last_error!r}")
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    operation_name: str,
    max_retries: int = 3,
    base_delay_seconds: float = 0.5,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> tuple[T, int]:
    """Run ``operation``, retrying transient failures with exponential backoff.

    Args:
        operation: Zero-arg async callable to execute.
        operation_name: Human-readable name for logs.
        max_retries: Retries *after* the first attempt (3 => up to 4 calls).
        base_delay_seconds: Delay grows as base * 2**attempt.
        retryable_exceptions: Only these are retried; anything else propagates
            immediately (e.g. a Pydantic ValidationError on our own bug should
            fail fast, not burn retries).

    Returns:
        Tuple of (result, retry_count) so callers can report retry metrics.

    Raises:
        RetryExhaustedError: When every attempt failed.
    """
    last_error: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            result = await operation()
            return result, attempt
        except retryable_exceptions as exc:  # noqa: PERF203 - retry loop by design
            last_error = exc
            if attempt >= max_retries:
                break
            delay = base_delay_seconds * (2**attempt)
            logger.warning(
                "retryable failure, backing off",
                extra={
                    "operation": operation_name,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "delay_seconds": delay,
                    "error": repr(exc),
                },
            )
            await asyncio.sleep(delay)
    assert last_error is not None
    raise RetryExhaustedError(operation_name, max_retries + 1, last_error)

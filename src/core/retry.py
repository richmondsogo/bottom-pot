"""
Retry decorator for ATS API fetch methods and outbound HTTP requests.

Retries only on retryable errors (HTTP 429, 408, 5xx, timeouts, connection/network errors)
with exponential backoff and full jitter, honoring the Retry-After header when present.
Default max 2 retries (3 attempts total).
Never retries non-retryable errors (e.g., 400, 401, 403, 404, 410, 422, circuit-open skips).
Enforces delay caps (5s per-delay cap, 10s total delay cap per job).
Supports dependency injection for clock, sleep, and RNG for fast deterministic testing.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
import email.utils
import functools
import random
import time
from typing import Any, Callable, Coroutine

import httpx
from loguru import logger

from src.project_files.extraction_outcome import ExtractionOutcome, ExtractionResult
from src.project_files.http_resilience import CircuitBreakerOpenError


_current_attempts: ContextVar[int] = ContextVar("_current_attempts", default=1)


def get_current_attempts() -> int:
    """Return the current attempt count in the active async context."""
    return _current_attempts.get()


def _parse_retry_after(
    header: str | None,
    clock_func: Callable[[], float] = time.time,
) -> float | None:
    """
    Parse a Retry-After header string, supporting both integer seconds and HTTP-date.
    Returns delta in seconds, or None if parsing fails.
    """
    if not header:
        return None
    try:
        return max(0.0, float(header.strip()))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(header)
        now_ts = clock_func()
        now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        return max(0.0, (dt - now).total_seconds())
    except Exception:
        return None


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay_per_retry: float = 5.0,
    max_total_delay: float = 10.0,
    is_idempotent: bool = True,
    clock_func: Callable[[], float] = time.time,
    sleep_func: Callable[[float], Coroutine[Any, Any, None]] = asyncio.sleep,
    rng_func: Callable[[float, float], float] = random.uniform,
) -> Callable:
    """
    Async decorator factory for bounded retries with jitter and Retry-After controls.

    - max_attempts: 1 initial attempt + (max_attempts - 1) retries (default 3 total).
    - base_delay: base backoff in seconds (default 0.5s).
    - max_delay_per_retry: maximum delay for a single retry (default 5.0s).
    - max_total_delay: cumulative backoff delay budget across all retries (default 10.0s).
    - is_idempotent: only idempotent operations (e.g. GET) should be retried.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            total_slept = 0.0
            last_exc: Exception | None = None

            for attempt in range(max_attempts):
                _current_attempts.set(attempt + 1)
                try:
                    res = await func(*args, **kwargs)

                    # Handle functions returning ExtractionResult directly
                    if isinstance(res, ExtractionResult):
                        if res.outcome in (ExtractionOutcome.RATE_LIMITED, ExtractionOutcome.RETRYABLE_ERROR):
                            if not is_idempotent or attempt == max_attempts - 1:
                                return res

                            remaining_delay_budget = max(0.0, max_total_delay - total_slept)
                            exp_delay = min(max_delay_per_retry, base_delay * (2 ** attempt))
                            delay = min(rng_func(0.0, exp_delay), remaining_delay_budget)

                            if delay <= 0:
                                return res

                            logger.warning(
                                f"[retry] Outcome {res.outcome.value} on attempt {attempt + 1}/{max_attempts}. "
                                f"Retrying in {delay:.2f}s — {func.__qualname__}"
                            )
                            total_slept += delay
                            res_sleep = sleep_func(delay)
                            if asyncio.iscoroutine(res_sleep):
                                await res_sleep
                            continue

                    return res

                except CircuitBreakerOpenError:
                    # Circuit breaker open: host is tripped, never retry
                    raise

                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code

                    # Non-idempotent requests are never retried
                    if not is_idempotent:
                        raise

                    # Never retry non-retryable 4xx (400, 401, 403, 404, 410, etc.)
                    if 400 <= status < 500 and status not in (408, 429):
                        raise

                    if status == 429 or status == 408 or (500 <= status < 600):
                        if attempt == max_attempts - 1:
                            raise

                        remaining_delay_budget = max(0.0, max_total_delay - total_slept)
                        retry_after = _parse_retry_after(exc.response.headers.get("retry-after"), clock_func=clock_func)

                        if retry_after is not None:
                            if retry_after > remaining_delay_budget:
                                logger.warning(
                                    f"[retry] Retry-After ({retry_after:.1f}s) exceeds remaining budget ({remaining_delay_budget:.1f}s). Giving up as rate_limited."
                                )
                                raise
                            delay = min(retry_after, max_delay_per_retry, remaining_delay_budget)
                        else:
                            exp_delay = min(max_delay_per_retry, base_delay * (2 ** attempt))
                            delay = min(rng_func(0.0, exp_delay), remaining_delay_budget)

                        if delay <= 0:
                            raise

                        logger.warning(
                            f"[retry] HTTP {status} on attempt {attempt + 1}/{max_attempts}. "
                            f"Retrying in {delay:.2f}s — {func.__qualname__}"
                        )
                        last_exc = exc
                        total_slept += delay
                        res_sleep = sleep_func(delay)
                        if asyncio.iscoroutine(res_sleep):
                            await res_sleep
                        continue

                    raise

                except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as exc:
                    if not is_idempotent or attempt == max_attempts - 1:
                        raise

                    remaining_delay_budget = max(0.0, max_total_delay - total_slept)
                    exp_delay = min(max_delay_per_retry, base_delay * (2 ** attempt))
                    delay = min(rng_func(0.0, exp_delay), remaining_delay_budget)

                    if delay <= 0:
                        raise

                    logger.warning(
                        f"[retry] {type(exc).__name__} on attempt {attempt + 1}/{max_attempts}. "
                        f"Retrying in {delay:.2f}s — {func.__qualname__}"
                    )
                    last_exc = exc
                    total_slept += delay
                    res_sleep = sleep_func(delay)
                    if asyncio.iscoroutine(res_sleep):
                        await res_sleep
                    continue

            if last_exc is not None:
                raise last_exc
            raise RuntimeError(f"Retry loop exited unexpectedly in {func.__qualname__}")

        return wrapper

    return decorator

"""
Retry decorator for ATS API fetch methods and outbound HTTP requests.

Retries only on HTTP 429, 5xx, and timeouts with exponential backoff and jitter,
honoring the Retry-After header when present. Max 2 retries (3 attempts total).
Never retries other 4xx (e.g., 400, 401, 403, 404, 422).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import email.utils
import functools
import random
from typing import Callable

import httpx
from loguru import logger


def _parse_retry_after(header: str | None) -> float | None:
    if not header:
        return None
    try:
        return max(0.0, float(header.strip()))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(header)
        now = datetime.now(timezone.utc)
        return max(0.0, (dt - now).total_seconds())
    except Exception:
        return None


def with_retry(max_attempts: int = 3, base_delay: float = 1.0) -> Callable:
    """
    Async decorator factory.

    Retries on HTTP 429, 5xx, or httpx.TimeoutException.
    Max 2 retries (3 attempts total by default).
    Honors Retry-After header if present, otherwise uses exponential backoff + jitter.
    Never retries other 4xx or connection errors.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)

                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code

                    # Never retry other 4xx (404, 403, 400, 401, etc.)
                    if 400 <= status < 500 and status != 429:
                        raise

                    if status == 429 or (500 <= status < 600):
                        if attempt == max_attempts - 1:
                            raise

                        retry_after = _parse_retry_after(exc.response.headers.get("retry-after"))
                        if retry_after is not None:
                            delay = min(retry_after, 10.0)
                        else:
                            jitter = random.uniform(0.05, 0.4)
                            delay = min(base_delay * (2 ** attempt) + jitter, 10.0)

                        logger.warning(
                            f"[retry] HTTP {status} on attempt {attempt + 1}/{max_attempts}. "
                            f"Retrying in {delay:.2f}s — {func.__qualname__}"
                        )
                        last_exc = exc
                        await asyncio.sleep(delay)
                        continue

                    raise

                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                    # Network unreachability — do not retry, bubble up
                    raise

                except httpx.TimeoutException as exc:
                    # Read/write timeout — retryable
                    if attempt == max_attempts - 1:
                        raise

                    jitter = random.uniform(0.05, 0.4)
                    delay = min(base_delay * (2 ** attempt) + jitter, 10.0)
                    logger.warning(
                        f"[retry] Timeout on attempt {attempt + 1}/{max_attempts}. "
                        f"Retrying in {delay:.2f}s — {func.__qualname__}"
                    )
                    last_exc = exc
                    await asyncio.sleep(delay)
                    continue

            if last_exc is not None:
                raise last_exc
            raise RuntimeError(f"Retry loop exited unexpectedly in {func.__qualname__}")

        return wrapper

    return decorator

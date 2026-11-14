"""
HTTP resilience primitives:
1. Global and per-host concurrency semaphores.
2. Per-host circuit breaker (5 consecutive failures -> 10m cooldown).
3. Response size cap (stop streaming after 3 MB).
4. Telemetry tracking for circuit breaker skips.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import email.utils
import random
import time
from typing import Any, AsyncIterator, Callable
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

from src.config import settings
from src.project_files.url_safety import UnsafeRedirectError, is_safe_public_https_url


class CircuitBreakerOpenError(Exception):
    """Raised when an outbound request is skipped because the host circuit is tripped."""
    def __init__(self, host: str):
        super().__init__(f"Circuit breaker is OPEN for host '{host}'")
        self.host = host


class HostRateLimitedError(Exception):
    """Raised when an outbound request is skipped because the host is currently in rate-limit backoff."""
    def __init__(self, host: str, retry_after: float):
        super().__init__(f"Host '{host}' is rate limited. Backoff active for {retry_after:.1f}s.")
        self.host = host
        self.retry_after = retry_after


class ResilienceManager:
    def __init__(self):
        self._global_semaphore: asyncio.Semaphore | None = None
        self._host_semaphores: dict[str, asyncio.Semaphore] = {}
        self._host_failures: dict[str, int] = {}
        self._host_tripped_until: dict[str, float] = {}
        self._circuit_breaker_skips: dict[str, int] = {}
        self._host_rate_limited_until: dict[str, float] = {}
        self._host_rate_limit_backoff: dict[str, float] = {}

    def _get_global_semaphore(self) -> asyncio.Semaphore:
        if self._global_semaphore is None:
            self._global_semaphore = asyncio.Semaphore(settings.global_concurrency_limit)
        return self._global_semaphore

    def _get_host_semaphore(self, host: str) -> asyncio.Semaphore:
        if host not in self._host_semaphores:
            self._host_semaphores[host] = asyncio.Semaphore(settings.per_host_concurrency_limit)
        return self._host_semaphores[host]

    @staticmethod
    def extract_host(url: str) -> str:
        try:
            return urlparse(url).netloc.lower() or "unknown"
        except Exception:
            return "unknown"

    def is_host_open(self, host: str) -> bool:
        """Returns True if host is healthy; False if circuit breaker is tripped."""
        tripped_until = self._host_tripped_until.get(host, 0.0)
        now = time.time()
        if now < tripped_until:
            self._circuit_breaker_skips[host] = self._circuit_breaker_skips.get(host, 0) + 1
            logger.warning(
                f"[circuit_breaker] Skipping request to '{host}' (tripped until {tripped_until - now:.1f}s left)"
            )
            return False
        return True

    def record_success(self, host: str) -> None:
        self._host_failures[host] = 0
        self._host_tripped_until.pop(host, None)
        now = time.time()
        until = self._host_rate_limited_until.get(host)
        if until is None or now >= until:
            self._host_rate_limited_until.pop(host, None)
            self._host_rate_limit_backoff.pop(host, None)

    def record_failure(self, host: str) -> None:
        failures = self._host_failures.get(host, 0) + 1
        self._host_failures[host] = failures
        if failures >= settings.circuit_breaker_failure_threshold:
            cooldown = settings.circuit_breaker_cooldown_seconds
            self._host_tripped_until[host] = time.time() + cooldown
            logger.error(
                f"[circuit_breaker] Tripping circuit breaker for host '{host}' for {cooldown}s after {failures} consecutive failures"
            )

    def record_rate_limit(self, host: str, retry_after: str | float | None = None) -> float:
        """Record a 429 response, doubling per-host backoff or honoring Retry-After, capped at 60s."""
        delay: float | None = None
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except (ValueError, TypeError):
                try:
                    dt = email.utils.parsedate_to_datetime(str(retry_after))
                    if dt:
                        delay = max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
                except Exception:
                    delay = None

        if delay is None or delay <= 0:
            prev = self._host_rate_limit_backoff.get(host, 2.5)
            delay = min(prev * 2, 60.0)
        else:
            delay = min(delay, 60.0)

        self._host_rate_limit_backoff[host] = delay
        new_until = time.time() + delay
        existing_until = self._host_rate_limited_until.get(host, 0.0)
        self._host_rate_limited_until[host] = max(existing_until, new_until)
        logger.warning(f"[resilience] Host '{host}' rate limited (429). Backing off for {delay:.1f}s")
        return delay

    def is_host_rate_limited(self, host: str) -> bool:
        """Returns True if host is currently backing off after 429."""
        until = self._host_rate_limited_until.get(host)
        if until is None:
            return False
        if time.time() < until:
            return True
        self._host_rate_limited_until.pop(host, None)
        return False

    def _ensure_host_ready(self, host: str) -> None:
        if not self.is_host_open(host):
            raise CircuitBreakerOpenError(host)

        until = self._host_rate_limited_until.get(host)
        if until is not None:
            now = time.time()
            if now < until:
                raise HostRateLimitedError(host, until - now)
            self._host_rate_limited_until.pop(host, None)

    def get_skips_by_host(self) -> dict[str, int]:
        return dict(self._circuit_breaker_skips)

    def reset(self) -> None:
        self._global_semaphore = None
        self._host_semaphores.clear()
        self._host_failures.clear()
        self._host_tripped_until.clear()
        self._circuit_breaker_skips.clear()
        self._host_rate_limited_until.clear()
        self._host_rate_limit_backoff.clear()

    @asynccontextmanager
    async def throttle(self, url: str) -> AsyncIterator[str]:
        host = self.extract_host(url)
        self._ensure_host_ready(host)

        global_sem = self._get_global_semaphore()
        host_sem = self._get_host_semaphore(host)

        async with global_sem:
            async with host_sem:
                self._ensure_host_ready(host)
                yield host


resilience_manager = ResilienceManager()


async def throttled_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 10.0,
    follow_redirects: bool = False,
) -> httpx.Response:
    """
    Execute an HTTP GET under the shared resilience_manager semaphores,
    circuit breaker, and 429 Retry-After backoff, recording response outcomes.
    """
    host = resilience_manager.extract_host(url)
    async with resilience_manager.throttle(url):
        try:
            resp = await client.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        except Exception:
            resilience_manager.record_failure(host)
            raise

        status = resp.status_code
        if status == 429:
            resilience_manager.record_rate_limit(host, resp.headers.get("retry-after"))
        elif status >= 500:
            resilience_manager.record_failure(host)
        elif status < 500:
            resilience_manager.record_success(host)
        return resp


async def fetch_page_with_cap(
    client: httpx.AsyncClient,
    url: str,
    headers: dict | None = None,
    timeout: float = 10.0,
    max_bytes: int | None = None,
    follow_redirects: bool = True,
) -> tuple[int, str, httpx.Headers]:
    """
    Fetch an HTTP page streaming chunks, stopping after max_bytes (default 3 MB).
    Returns (status_code, decoded_text, response_headers).
    """
    limit_bytes = max_bytes if max_bytes is not None else settings.max_response_bytes

    async with resilience_manager.throttle(url) as host:
        try:
            async with client.stream(
                "GET",
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            ) as resp:
                status = resp.status_code
                resp_headers = resp.headers

                # Read up to limit_bytes
                buffer = bytearray()
                async for chunk in resp.aiter_bytes():
                    needed = limit_bytes - len(buffer)
                    if len(chunk) >= needed:
                        buffer.extend(chunk[:needed])
                        logger.debug(
                            f"Reached response size cap ({limit_bytes} bytes) for {url}. Truncating read."
                        )
                        break
                    buffer.extend(chunk)

                text = buffer.decode("utf-8", errors="replace")

                if status < 500 and status != 429:
                    resilience_manager.record_success(host)
                elif status == 429:
                    retry_after = resp_headers.get("retry-after")
                    resilience_manager.record_rate_limit(host, retry_after)
                elif status >= 500:
                    resilience_manager.record_failure(host)

                return status, text, resp_headers

        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            resilience_manager.record_failure(host)
            raise
        except Exception:
            raise


async def fetch_public_https_with_validated_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers_fn: Callable[[str], dict | None] | None = None,
    timeout: float = 10.0,
    max_bytes: int | None = None,
    max_hops: int = 5,
    url_validator: Callable[[str], bool] | None = None,
    on_hop: Callable[[str], None] | None = None,
) -> tuple[int, str, httpx.Headers, str]:
    """
    Fetch *url* with automatic redirects disabled, validating initial URL and every
    ``Location`` target with *url_validator* (default: ``is_safe_public_https_url``)
    before issuing each hop. Enforces *max_hops*, *timeout*, and *max_bytes*.
    """
    validator = url_validator or is_safe_public_https_url
    current_url = url

    for hop in range(max_hops + 1):
        if not validator(current_url):
            raise UnsafeRedirectError(f"Unsafe or non-public destination rejected: {current_url}")
        if on_hop is not None:
            on_hop(current_url)

        req_headers = headers_fn(current_url) if headers_fn is not None else None
        status, text, resp_headers = await fetch_page_with_cap(
            client,
            current_url,
            headers=req_headers,
            timeout=timeout,
            max_bytes=max_bytes,
            follow_redirects=False,
        )
        if 300 <= status < 400:
            location = resp_headers.get("location") or resp_headers.get("Location")
            if not location:
                return status, text, resp_headers, current_url
            if hop >= max_hops:
                raise UnsafeRedirectError(f"Redirect hop limit ({max_hops}) exceeded for {url}")
            next_url = urljoin(current_url, str(location).strip())
            if not validator(next_url):
                raise UnsafeRedirectError(f"Unsafe redirect destination rejected: {next_url}")
            current_url = next_url
            continue

        return status, text, resp_headers, current_url

    raise UnsafeRedirectError(f"Redirect hop limit ({max_hops}) exceeded for {url}")

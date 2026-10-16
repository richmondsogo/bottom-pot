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
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.config import settings


class CircuitBreakerOpenError(Exception):
    """Raised when an outbound request is skipped because the host circuit is tripped."""
    def __init__(self, host: str):
        super().__init__(f"Circuit breaker is OPEN for host '{host}'")
        self.host = host


class ResilienceManager:
    def __init__(self):
        self._global_semaphore: asyncio.Semaphore | None = None
        self._host_semaphores: dict[str, asyncio.Semaphore] = {}
        self._host_failures: dict[str, int] = {}
        self._host_tripped_until: dict[str, float] = {}
        self._circuit_breaker_skips: dict[str, int] = {}

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
        if host in self._host_tripped_until:
            del self._host_tripped_until[host]

    def record_failure(self, host: str) -> None:
        failures = self._host_failures.get(host, 0) + 1
        self._host_failures[host] = failures
        if failures >= settings.circuit_breaker_failure_threshold:
            cooldown = settings.circuit_breaker_cooldown_seconds
            self._host_tripped_until[host] = time.time() + cooldown
            logger.error(
                f"[circuit_breaker] Tripping circuit breaker for host '{host}' for {cooldown}s after {failures} consecutive failures"
            )

    def get_skips_by_host(self) -> dict[str, int]:
        return dict(self._circuit_breaker_skips)

    def reset(self) -> None:
        self._global_semaphore = None
        self._host_semaphores.clear()
        self._host_failures.clear()
        self._host_tripped_until.clear()
        self._circuit_breaker_skips.clear()

    @asynccontextmanager
    async def throttle(self, url: str) -> AsyncIterator[str]:
        host = self.extract_host(url)
        if not self.is_host_open(host):
            raise CircuitBreakerOpenError(host)

        global_sem = self._get_global_semaphore()
        host_sem = self._get_host_semaphore(host)

        async with global_sem:
            async with host_sem:
                yield host


resilience_manager = ResilienceManager()


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
    host = resilience_manager.extract_host(url)

    if not resilience_manager.is_host_open(host):
        raise CircuitBreakerOpenError(host)

    global_sem = resilience_manager._get_global_semaphore()
    host_sem = resilience_manager._get_host_semaphore(host)

    async with global_sem:
        async with host_sem:
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
                    elif status >= 500:
                        resilience_manager.record_failure(host)

                    return status, text, resp_headers

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
                resilience_manager.record_failure(host)
                raise
            except Exception:
                raise

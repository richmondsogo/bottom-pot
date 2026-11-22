"""
Shared SSRF-validated, resilience-gated HTTP transport helpers for monitored adapters.

Every monitored provider routes its outbound HTTP calls through ``fetch_provider_bytes``
so concurrency semaphores, per-host circuit breakers, 429 Retry-After backoff,
SSRF URL/DNS checks, and fail-closed streaming response caps apply uniformly.
"""

from __future__ import annotations

import httpx

from src.core.http_headers import browser_headers
from src.core.http_resilience import throttled_stream_bytes
from src.core.settings import settings
from src.safety.url_safety import (
    DnsResolver,
    UnsafeRedirectError,
    is_safe_public_https_url,
)


def validate_board_token_safety(token: str | None) -> bool:
    """Reject empty, control-char, or URL-injection tokens across all monitored providers."""
    if not isinstance(token, str):
        return False
    cleaned = token.strip()
    if not cleaned:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cleaned):
        return False
    if cleaned.startswith(".") or cleaned.endswith("."):
        return False
    return not any(bad in cleaned for bad in ("/", "\\", "?", "#", "@", ".."))


def build_conditional_headers(
    url: str,
    accept: str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
    accept_gzip: bool = False,
) -> dict[str, str]:
    """Build standard browser-like conditional GET headers for provider polling."""
    headers = browser_headers(url, accept)
    if accept_gzip:
        headers["Accept-Encoding"] = "gzip, deflate"
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return headers


def validate_provider_url(
    url: str,
    *,
    client: httpx.AsyncClient,
    resolver: DnsResolver | None = None,
    validate_dns: bool | None = None,
) -> None:
    """
    Validate *url* is a public HTTPS endpoint safe against SSRF before dispatching HTTP.

    When using a real transport (not ``httpx.MockTransport``) or when an explicit
    *resolver* / ``validate_dns=True`` is supplied, also enforces public-IP DNS resolution.
    """
    if not is_safe_public_https_url(url, resolve_dns=False):
        raise UnsafeRedirectError(f"Unsafe or malformed provider URL rejected: {url}")

    if validate_dns is not None:
        should_resolve = bool(validate_dns)
    elif resolver is not None:
        should_resolve = True
    else:
        transport = getattr(client, "_transport", None)
        should_resolve = not isinstance(transport, httpx.MockTransport)

    if should_resolve and not is_safe_public_https_url(url, resolve_dns=True, resolver=resolver):
        raise UnsafeRedirectError(f"Unsafe provider destination or DNS resolution rejected: {url}")


async def fetch_provider_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 8.0,
    max_bytes: int | None = None,
    follow_redirects: bool = False,
    resolver: DnsResolver | None = None,
    validate_dns: bool | None = None,
) -> tuple[int, bytes, httpx.Headers]:
    """
    Validate *url* against SSRF rules and execute a bounded, resilience-gated streaming GET.
    """
    validate_provider_url(
        url,
        client=client,
        resolver=resolver,
        validate_dns=validate_dns,
    )
    effective_max_bytes = int(max_bytes if max_bytes is not None else settings.max_response_bytes)
    return await throttled_stream_bytes(
        client,
        url,
        headers=headers,
        timeout=timeout,
        max_bytes=effective_max_bytes,
        follow_redirects=follow_redirects,
    )

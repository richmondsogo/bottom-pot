"""
Shared SSRF-safe public HTTPS URL validation utilities.

Used by redirect/custom-domain resolvers and company-logo extractors to guarantee
strict HTTPS-only public destinations and block loopback, private, link-local,
unspecified, multicast, reserved, and cloud-metadata addresses.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx


class UnsafeRedirectError(ValueError):
    """Raised when a URL, redirect target, or DNS resolution points to an unsafe non-public destination."""

_BLOCKED_HOSTNAMES: frozenset[str] = frozenset({
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
})

_BLOCKED_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".internal",
    ".localhost",
    ".arpa",
    ".home.arpa",
)


def _is_public_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        return _is_public_ip(ip_obj.ipv4_mapped)
    return not (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    )


def resolve_safe_public_ips(hostname: str, port: int = 443) -> list[str]:
    """
    Resolve *hostname* to verified public IP address strings, or raise ``UnsafeRedirectError``.

    Checks blocklisted hostnames/suffixes, raw IP literals, and every A/AAAA record
    returned by ``socket.getaddrinfo``.
    """
    cleaned = (hostname or "").strip().lower().rstrip(".")
    if not cleaned:
        raise UnsafeRedirectError("Empty hostname")
    if cleaned in _BLOCKED_HOSTNAMES or cleaned.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeRedirectError(f"Blocked internal/metadata hostname: {cleaned}")

    try:
        ip_obj = ipaddress.ip_address(cleaned)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if not _is_public_ip(ip_obj):
            raise UnsafeRedirectError(f"Blocked non-public IP literal: {cleaned}")
        return [str(ip_obj)]

    if "." not in cleaned:
        raise UnsafeRedirectError(f"Non-FQDN hostname rejected: {cleaned}")

    try:
        addr_info = socket.getaddrinfo(cleaned, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeRedirectError(f"DNS resolution failed for {cleaned}: {exc}") from exc

    if not addr_info:
        raise UnsafeRedirectError(f"DNS returned no records for {cleaned}")

    resolved_ips: list[str] = []
    for _, _, _, _, sockaddr in addr_info:
        if not sockaddr:
            continue
        raw_ip = str(sockaddr[0])
        if "%" in raw_ip:
            raise UnsafeRedirectError(f"Scoped IP address rejected for {cleaned}")
        try:
            resolved_ip = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise UnsafeRedirectError(f"Malformed resolved IP for {cleaned}: {raw_ip}") from exc
        if not _is_public_ip(resolved_ip):
            raise UnsafeRedirectError(f"Hostname {cleaned} resolved to non-public IP {raw_ip}")
        ip_str = str(resolved_ip)
        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

    if not resolved_ips:
        raise UnsafeRedirectError(f"No valid public IP addresses resolved for {cleaned}")
    return resolved_ips


class PublicPinningNetworkBackend(httpcore.AnyIOBackend):
    """
    httpcore network backend that pins outbound TCP connections to a validated public IP.

    ``httpcore.AsyncHTTPConnection`` preserves the original hostname on ``self._origin`` for
    both the HTTP ``Host`` header and TLS SNI / SAN certificate verification while passing
    ``host`` here solely for ``connect_tcp``. Resolving and dialing the validated IP inside
    ``connect_tcp`` removes the DNS TOCTOU gap between pre-flight URL checks and direct TCP
    socket establishment (effective when traffic uses this transport directly without an
    external proxy or overridden mock transport).
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            validated_ips = resolve_safe_public_ips(host, port)
        except UnsafeRedirectError as exc:
            raise httpcore.ConnectError(str(exc)) from exc

        last_exc: Exception | None = None
        for ip_addr in validated_ips:
            try:
                return await super().connect_tcp(
                    ip_addr,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectError as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc


def create_ssrf_safe_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Create an ``httpx.AsyncClient`` configured for SSRF-hardened fetching:
    - ``follow_redirects=False`` by default
    - ``trust_env=False`` so environment proxies cannot bypass destination checks or IP pinning
    - Direct ``PublicPinningNetworkBackend`` bound to the async connection pool
    """
    trust_env = kwargs.pop("trust_env", False)
    if "transport" not in kwargs:
        transport = httpx.AsyncHTTPTransport(trust_env=trust_env)
        if hasattr(transport, "_pool") and hasattr(transport._pool, "_network_backend"):
            transport._pool._network_backend = PublicPinningNetworkBackend()
        kwargs["transport"] = transport
    kwargs.setdefault("follow_redirects", False)
    return httpx.AsyncClient(trust_env=trust_env, **kwargs)


def is_safe_public_https_url(url: str | None, *, resolve_dns: bool = True) -> bool:
    """
    Validate that *url* is a well-formed public HTTPS URL safe against SSRF.

    - Requires ``https`` scheme.
    - Rejects embedded credentials (user:pass@host) and control characters.
    - Rejects loopback, private RFC1918/ULA, link-local, metadata, and local domains.
    - When ``resolve_dns=True``, resolves host A/AAAA records and rejects if resolution
      fails or yields any non-public IP address.
    """
    if not url or not isinstance(url, str):
        return False
    cleaned = url.strip()
    if not cleaned or any(ord(ch) < 32 for ch in cleaned):
        return False

    try:
        parts = urlsplit(cleaned)
    except Exception:
        return False

    if parts.scheme.lower() != "https":
        return False
    if parts.username or parts.password or "@" in parts.netloc:
        return False

    hostname = (parts.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return False
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(_BLOCKED_SUFFIXES):
        return False

    try:
        ip_obj = ipaddress.ip_address(hostname)
        return _is_public_ip(ip_obj)
    except ValueError:
        pass

    if "." not in hostname:
        return False

    if not resolve_dns:
        return True

    try:
        resolve_safe_public_ips(hostname, parts.port or 443)
    except UnsafeRedirectError:
        return False

    return True

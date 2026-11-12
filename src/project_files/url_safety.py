"""
Shared SSRF-safe public HTTPS URL validation utilities.

Used by redirect/custom-domain resolvers and company-logo extractors to guarantee
strict HTTPS-only public destinations and block loopback, private, link-local,
unspecified, multicast, reserved, and cloud-metadata addresses.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

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
        # Disallow direct raw IP literals for SSRF defense-in-depth unless explicitly checked public;
        # private/loopback/link-local/unspecified always rejected above.
        return _is_public_ip(ip_obj)
    except ValueError:
        pass

    if "." not in hostname:
        return False

    if not resolve_dns:
        return True

    try:
        addr_info = socket.getaddrinfo(hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return False

    if not addr_info:
        return False

    for _, _, _, _, sockaddr in addr_info:
        if not sockaddr:
            continue
        raw_ip = str(sockaddr[0]).split("%", 1)[0]
        try:
            resolved_ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            return False
        if not _is_public_ip(resolved_ip):
            return False

    return True

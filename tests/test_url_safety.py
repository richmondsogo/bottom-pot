"""Hermetic unit and integration tests for SSRF-safe URL validation & DNS injection."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import httpcore
import httpx
import pytest

from src.ats.ats_page_enricher import enrich_ats_page_result
from src.core.http_resilience import fetch_public_https_with_validated_redirects
from src.extraction.extraction_outcome import ExtractionOutcome
from src.providers.board_adapters import TeamtailorBoardAdapter
from src.safety.url_safety import (
    DnsResolver,
    PublicPinningNetworkBackend,
    StaticDnsResolver,
    SystemDnsResolver,
    UnsafeRedirectError,
    create_ssrf_safe_async_client,
    get_dns_resolver,
    is_safe_public_https_url,
    resolve_safe_public_ips,
    use_dns_resolver,
)
from src.storage.company_board_registry import CompanyBoard
from tests.conftest import _REAL_GETADDRINFO, OfflineDnsBlockedError

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "teamtailor"


def test_public_host_ipv4_and_ipv6_ok():
    resolver = StaticDnsResolver({
        "careers.example.com": ["93.184.216.34", "93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"],
    })
    assert isinstance(resolver, DnsResolver)

    ips = resolve_safe_public_ips("  Careers.Example.COM. ", 443, resolver=resolver)
    assert ips == ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]
    assert is_safe_public_https_url("https://careers.example.com/jobs/1", resolver=resolver) is True
    assert resolve_safe_public_ips("93.184.216.34", 443, resolver=resolver) == ["93.184.216.34"]
    assert resolve_safe_public_ips("2606:2800:220:1:248:1893:25c8:1946", 443, resolver=resolver) == [
        "2606:2800:220:1:248:1893:25c8:1946"
    ]


@pytest.mark.parametrize(
    "non_public_v4",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
    ],
)
def test_private_and_reserved_ipv4_rejected(non_public_v4: str):
    resolver = StaticDnsResolver({"bad-v4.example.com": non_public_v4})
    with pytest.raises(UnsafeRedirectError):
        resolve_safe_public_ips(non_public_v4, 443, resolver=resolver)
    with pytest.raises(UnsafeRedirectError):
        resolve_safe_public_ips("bad-v4.example.com", 443, resolver=resolver)
    assert is_safe_public_https_url(f"https://{non_public_v4}/hook", resolver=resolver) is False
    assert is_safe_public_https_url("https://bad-v4.example.com/hook", resolver=resolver) is False


@pytest.mark.parametrize(
    "non_public_v6",
    [
        "::1",
        "fc00::1",
        "fd12::1",
        "fe80::1",
        "::",
        "ff02::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "fe80::1%eth0",
    ],
)
def test_private_and_reserved_ipv6_rejected(non_public_v6: str):
    resolver = StaticDnsResolver({"bad-v6.example.com": non_public_v6})
    with pytest.raises(UnsafeRedirectError):
        resolve_safe_public_ips("bad-v6.example.com", 443, resolver=resolver)
    assert is_safe_public_https_url("https://bad-v6.example.com/hook", resolver=resolver) is False
    if "%" not in non_public_v6:
        with pytest.raises(UnsafeRedirectError):
            resolve_safe_public_ips(non_public_v6, 443, resolver=resolver)
        assert is_safe_public_https_url(f"https://[{non_public_v6}]/hook", resolver=resolver) is False


def test_mixed_public_and_private_records_rejected():
    resolver = StaticDnsResolver({
        "mixed-v4.example.com": ["93.184.216.34", "10.20.30.40"],
        "mixed-v6.example.com": ["2606:2800:220:1:248:1893:25c8:1946", "fe80::1"],
    })
    for host in ("mixed-v4.example.com", "mixed-v6.example.com"):
        with pytest.raises(UnsafeRedirectError, match="non-public IP"):
            resolve_safe_public_ips(host, 443, resolver=resolver)
        assert is_safe_public_https_url(f"https://{host}/jobs", resolver=resolver) is False


def test_resolution_failure_empty_and_malformed_records_rejected():
    resolver = StaticDnsResolver({
        "empty.example.com": [],
        "malformed.example.com": ["not-an-ip"],
    })

    with pytest.raises(UnsafeRedirectError, match="DNS resolution failed"):
        resolve_safe_public_ips("unlisted.example.com", 443, resolver=resolver)
    assert is_safe_public_https_url("https://unlisted.example.com/jobs", resolver=resolver) is False

    with pytest.raises(UnsafeRedirectError, match="no records"):
        resolve_safe_public_ips("empty.example.com", 443, resolver=resolver)

    with pytest.raises(UnsafeRedirectError, match="Malformed"):
        resolve_safe_public_ips("malformed.example.com", 443, resolver=resolver)

    for bad_host in ("", "localhost", "metadata.google.internal", "app.local", "intranet"):
        with pytest.raises(UnsafeRedirectError):
            resolve_safe_public_ips(bad_host, 443, resolver=resolver)

    for bad_url in (
        "http://careers.example.com/jobs",
        "https://user:pass@careers.example.com/jobs",
        "https://app.internal/jobs",
        "https://careers.example.com/jobs\n",
    ):
        assert is_safe_public_https_url(bad_url, resolver=resolver) is False


@pytest.mark.anyio
async def test_dns_rebinding_between_preflight_validation_and_connect_tcp(monkeypatch):
    class RebindingDnsResolver:
        def __init__(self) -> None:
            self.calls = 0

        def resolve(self, hostname: str, port: int = 443) -> list[str]:
            self.calls += 1
            if self.calls == 1:
                return ["93.184.216.34"]
            return ["127.0.0.1"]

    dialed: list[tuple[str, int]] = []
    sentinel = object()

    async def fake_connect(self_inner, host, port, timeout=None, local_address=None, socket_options=None):
        dialed.append((host, port))
        return sentinel

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect)

    rebinding = RebindingDnsResolver()
    assert is_safe_public_https_url("https://rebind.example.com/jobs/1", resolver=rebinding) is True
    assert rebinding.calls == 1

    async with create_ssrf_safe_async_client(resolver=rebinding, timeout=10.0) as client:
        backend = client._transport._pool._network_backend
        assert isinstance(backend, PublicPinningNetworkBackend)
        with pytest.raises(httpcore.ConnectError, match="non-public IP"):
            await backend.connect_tcp("rebind.example.com", 443)

    assert rebinding.calls == 2
    assert dialed == []

    stable = StaticDnsResolver({"pinned.example.com": "93.184.216.34"})
    pin_backend = PublicPinningNetworkBackend(resolver=stable)
    stream = await pin_backend.connect_tcp("pinned.example.com", 443)
    assert stream is sentinel
    assert dialed == [("93.184.216.34", 443)]


@pytest.mark.parametrize(
    "unsafe_location",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://127.0.0.1/admin",
        "https://private.example.com/internal",
        "https://nxdomain.example.com/missing",
    ],
)
@pytest.mark.anyio
async def test_unsafe_redirect_rejected_without_second_fetch(unsafe_location: str):
    resolver = StaticDnsResolver({
        "careers.example.com": "93.184.216.34",
        "private.example.com": "10.0.0.5",
    })
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        return httpx.Response(302, headers={"Location": unsafe_location}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UnsafeRedirectError):
            await fetch_public_https_with_validated_redirects(
                client,
                "https://careers.example.com/jobs/1",
                resolver=resolver,
            )

    assert fetched == ["https://careers.example.com/jobs/1"]


@pytest.mark.anyio
async def test_per_hop_redirect_validation_hop_limit_and_timeout():
    resolver = StaticDnsResolver({
        "start.example.com": "93.184.216.34",
        "mid.example.com": "93.184.216.35",
        "final.example.com": "93.184.216.36",
        "bad.example.com": "192.168.1.5",
    })

    # 1. Valid 2-hop public redirect chain succeeds and validates every hop.
    fetched_ok: list[str] = []

    def ok_handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        fetched_ok.append(u)
        if u == "https://start.example.com/1":
            return httpx.Response(302, headers={"Location": "https://mid.example.com/2"}, request=request)
        if u == "https://mid.example.com/2":
            return httpx.Response(301, headers={"Location": "https://final.example.com/3"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        status, body, _, final_url = await fetch_public_https_with_validated_redirects(
            client,
            "https://start.example.com/1",
            max_hops=3,
            resolver=resolver,
        )
    assert status == 200
    assert body == "ok"
    assert final_url == "https://final.example.com/3"
    assert fetched_ok == [
        "https://start.example.com/1",
        "https://mid.example.com/2",
        "https://final.example.com/3",
    ]

    # 2. Unsafe 3rd hop stops before fetching the unsafe target.
    fetched_mid_bad: list[str] = []

    def mid_bad_handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        fetched_mid_bad.append(u)
        if u == "https://start.example.com/1":
            return httpx.Response(302, headers={"Location": "https://mid.example.com/2"}, request=request)
        if u == "https://mid.example.com/2":
            return httpx.Response(302, headers={"Location": "https://bad.example.com/secret"}, request=request)
        return httpx.Response(200, text="should never fetch", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mid_bad_handler)) as client:
        with pytest.raises(UnsafeRedirectError):
            await fetch_public_https_with_validated_redirects(
                client,
                "https://start.example.com/1",
                max_hops=5,
                resolver=resolver,
            )
    assert fetched_mid_bad == ["https://start.example.com/1", "https://mid.example.com/2"]

    # 3. Redirect limit enforced strictly.
    fetched_loop: list[str] = []

    def loop_handler(request: httpx.Request) -> httpx.Response:
        fetched_loop.append(str(request.url))
        hop = len(fetched_loop)
        return httpx.Response(
            302,
            headers={"Location": f"https://mid.example.com/step/{hop}"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(loop_handler)) as client:
        with pytest.raises(UnsafeRedirectError, match="hop limit"):
            await fetch_public_https_with_validated_redirects(
                client,
                "https://start.example.com/1",
                max_hops=2,
                resolver=resolver,
            )
    assert len(fetched_loop) == 3

    # 4. Timeout propagates cleanly without being treated as safe.
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        with pytest.raises(httpx.ReadTimeout):
            await fetch_public_https_with_validated_redirects(
                client,
                "https://start.example.com/1",
                timeout=0.5,
                resolver=resolver,
            )


@pytest.mark.anyio
async def test_fixture_replay_teamtailor_rss_and_page_with_no_real_dns():
    dotworld_xml = (FIXTURE_DIR / "dotworld_rss.xml").read_bytes()
    meta = json.loads((FIXTURE_DIR / "b6057b16.json").read_text(encoding="utf-8"))
    page_html = (FIXTURE_DIR / "b6057b16.html").read_text(encoding="utf-8")
    page_url = meta["url"]

    resolver = StaticDnsResolver({
        "dotworld.teamtailor.com": "93.184.216.34",
        "sparteo.teamtailor.com": "93.184.216.34",
    })

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u == "https://dotworld.teamtailor.com/jobs.rss":
            return httpx.Response(200, content=dotworld_xml)
        if u == page_url:
            return httpx.Response(200, text=page_html)
        return httpx.Response(404)

    board = CompanyBoard(
        id=1,
        company_name="Dotworld",
        company_slug="dotworld",
        ats_provider="teamtailor",
        board_token="dotworld",
        board_url="https://dotworld.teamtailor.com",
        discovery_source="fixture",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="verified",
        monitoring_capability="supported",
    )

    with use_dns_resolver(resolver):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            res = await TeamtailorBoardAdapter().check_board(board, client)
            job, ext_res = await enrich_ats_page_result(
                page_url,
                "teamtailor",
                "",
                "",
                "chief data officer",
                client,
            )

    assert res.success is True
    assert len(res.listings) == 7
    assert ext_res.outcome == ExtractionOutcome.SUCCESS
    assert job is not None
    assert job.title == "Chief Data Officer"


def test_production_resolver_is_default_when_nothing_injected(expect_dns_tripwire):
    default_resolver = get_dns_resolver()
    assert isinstance(default_resolver, SystemDnsResolver)

    static = StaticDnsResolver({"example.com": "93.184.216.34"})
    with use_dns_resolver(static):
        assert get_dns_resolver() is static
        with use_dns_resolver(None):
            assert isinstance(get_dns_resolver(), SystemDnsResolver)
        assert get_dns_resolver() is static
    assert isinstance(get_dns_resolver(), SystemDnsResolver)

    with pytest.raises(OfflineDnsBlockedError, match="example.com"):
        default_resolver.resolve("example.com", 443)
    with pytest.raises(OfflineDnsBlockedError, match="example.com"):
        resolve_safe_public_ips("example.com", 443)
    with pytest.raises(OfflineDnsBlockedError, match="example.com"):
        is_safe_public_https_url("https://example.com/jobs")
    assert len(expect_dns_tripwire) == 3


@pytest.mark.live
def test_live_marker_bypasses_offline_dns_tripwire():
    assert socket.getaddrinfo is _REAL_GETADDRINFO
    assert isinstance(get_dns_resolver(), SystemDnsResolver)

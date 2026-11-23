"""
Step 47 TDD: Teamtailor Monitoring, Snapshot Completeness, HTML Fallback, and Direct Routing.

Covers all 20 required scenarios from Step 47 specification using captured real fixtures
and deterministic mocked HTTP transports (zero live HTTP requests, zero Serper spend).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
import pytest

from src.ats.ats_url_parser import parse_teamtailor_board_root_url
from src.ats.direct_board_router import probe_direct_boards, probe_teamtailor_board
from src.core.models import JobListing
from src.monitoring.board_monitor import BoardMonitor
from src.providers.board_adapters import (
    BOARD_ADAPTERS,
    BoardCheckResult,
    TeamtailorBoardAdapter,
    _parse_teamtailor_html_jobs_page,
    parse_teamtailor_rss_feed,
)
from src.safety.url_safety import StaticDnsResolver, use_dns_resolver
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoard,
    CompanyBoardRegistry,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "teamtailor"

_TEAMTAILOR_MONITORING_DNS = StaticDnsResolver({
    "acme.teamtailor.com": "93.184.216.34",
    "bigco.teamtailor.com": "93.184.216.34",
    "careers.gravita.com": "93.184.216.34",
    "cc-jobs-jobsity.na.teamtailor.com": "93.184.216.34",
    "cyc.teamtailor.com": "93.184.216.34",
    "dotworld.teamtailor.com": "93.184.216.34",
    "errco.teamtailor.com": "93.184.216.34",
    "gravita.teamtailor.com": "93.184.216.34",
    "loopco.teamtailor.com": "93.184.216.34",
    "navco.teamtailor.com": "93.184.216.34",
    "paystack.teamtailor.com": "93.184.216.34",
    "worksterjobs.teamtailor.com": "93.184.216.34",
})


@pytest.fixture(autouse=True)
def _offline_teamtailor_dns():
    with use_dns_resolver(_TEAMTAILOR_MONITORING_DNS):
        yield


def _make_board(
    token: str = "dotworld",
    company_name: str = "Dotworld",
    *,
    board_id: int = 1,
    etag: str | None = None,
    last_modified: str | None = None,
    content_fingerprint: str | None = None,
) -> CompanyBoard:
    return CompanyBoard(
        id=board_id,
        company_name=company_name,
        company_slug=token,
        ats_provider="teamtailor",
        board_token=token,
        board_url=f"https://{token}.teamtailor.com",
        discovery_source="search",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
        etag=etag,
        last_modified=last_modified,
        content_fingerprint=content_fingerprint,
    )


def _build_rss(
    items_xml: list[str],
    *,
    company_title: str = "Acme Corp",
    board_link: str = "https://acme.teamtailor.com/jobs",
) -> str:
    joined = "\n".join(items_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:tt="https://teamtailor.com/locations">\n'
        "  <channel>\n"
        f"    <title>{escape(company_title)}</title>\n"
        "    <description>Current job openings</description>\n"
        f"    <link>{escape(board_link)}</link>\n"
        f"{joined}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def _build_rss_item(
    job_id: int,
    *,
    slug_host: str = "acme.teamtailor.com",
    title: str = "Software Engineer",
    description: str = "<p>Build reliable backend services in Python.</p>",
    pub_date: str = "Tue, 17 Nov 2026 10:00:00 +0000",
    remote_status: str = "fully",
    city: str = "Lagos",
    country: str = "Nigeria",
    department: str = "Engineering",
    role: str = "Backend",
) -> str:
    url = f"https://{slug_host}/jobs/{job_id}-role-{job_id}"
    return (
        "    <item>\n"
        f"      <title>{escape(title)}</title>\n"
        f"      <description>{escape(description)}</description>\n"
        f"      <pubDate>{escape(pub_date)}</pubDate>\n"
        f"      <link>{escape(url)}</link>\n"
        f"      <remoteStatus>{escape(remote_status)}</remoteStatus>\n"
        f"      <guid>guid-{job_id}</guid>\n"
        '      <tt:locations>\n'
        "        <tt:location>\n"
        f"          <tt:name>{escape(city)} {escape(country)}</tt:name>\n"
        f"          <tt:city>{escape(city)}</tt:city>\n"
        f"          <tt:country>{escape(country)}</tt:country>\n"
        "        </tt:location>\n"
        "      </tt:locations>\n"
        f"      <tt:department>{escape(department)}</tt:department>\n"
        f"      <tt:role>{escape(role)}</tt:role>\n"
        "    </item>"
    )


def _build_html_jobs_page(
    slug: str,
    job_ids: list[int],
    *,
    next_page: int | None = None,
    include_frame: bool = True,
) -> str:
    items = []
    for jid in job_ids:
        items.append(
            '<li class="w-full">'
            f'<a href="https://{slug}.teamtailor.com/jobs/{jid}-role-{jid}">Role {jid}</a>'
            '<div class="text-md mt-4"><span>Engineering</span><span> · </span><span>Remote</span></div>'
            "</li>"
        )
    nav = (
        f'<a href="/jobs/show_more?page={next_page - 1}&amp;page={next_page}">Show 20 more</a>'
        if next_page is not None
        else ""
    )
    inner = f"<ul>{''.join(items)}</ul>{nav}"
    frame = f'<turbo-frame id="jobs_list">{inner}</turbo-frame>' if include_frame else inner
    return (
        "<!DOCTYPE html><html><head><title>Careers</title></head><body>"
        f'<header><a href="/"><img alt="{slug} career site" '
        'src="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/logo.png"/></a></header>'
        f"{frame}</body></html>"
    )


def test_registry_and_adapter_wiring():
    assert "teamtailor" in MONITORABLE_PROVIDERS
    assert "teamtailor" in BOARD_ADAPTERS
    assert isinstance(BOARD_ADAPTERS["teamtailor"], TeamtailorBoardAdapter)
    assert parse_teamtailor_board_root_url("https://dotworld.teamtailor.com") == "dotworld"
    assert parse_teamtailor_board_root_url("https://dotworld.teamtailor.com/jobs") == "dotworld"
    assert parse_teamtailor_board_root_url("https://cc-jobs-jobsity.na.teamtailor.com/jobs") == "cc-jobs-jobsity.na"
    assert parse_teamtailor_board_root_url("https://dotworld.teamtailor.com/jobs/8642089-data") is None
    assert parse_teamtailor_board_root_url("https://support.teamtailor.com/en") is None


def test_real_teamtailor_rss_fixtures_dotworld_and_gravita_valid():
    dotworld_xml = (FIXTURE_DIR / "dotworld_rss.xml").read_bytes()
    gravita_xml = (FIXTURE_DIR / "gravita_rss.xml").read_bytes()

    items_dw, meta_dw, err_dw = parse_teamtailor_rss_feed(dotworld_xml)
    assert err_dw is None
    assert meta_dw["channel_title"] == "Dotworld"
    assert len(items_dw) == 7
    assert all(it["job_id"].isdigit() for it in items_dw)
    assert all("dotworld.teamtailor.com/jobs/" in it["link"] for it in items_dw)

    items_gr, meta_gr, err_gr = parse_teamtailor_rss_feed(gravita_xml)
    assert err_gr is None
    assert meta_gr["channel_title"] == "Gravita"
    assert len(items_gr) == 16
    assert any("careers.gravita.com/jobs/" in it["link"] for it in items_gr)

    workster_html = (FIXTURE_DIR / "worksterjobs_jobs_p1.html").read_text(encoding="utf-8")
    html_items, next_page, html_err = _parse_teamtailor_html_jobs_page(
        workster_html,
        expected_host="worksterjobs.teamtailor.com",
    )
    assert html_err is None
    assert len(html_items) == 20
    assert next_page == 2


@pytest.mark.anyio
async def test_1_valid_rss_parsing_and_canonical_fields():
    dotworld_xml = (FIXTURE_DIR / "dotworld_rss.xml").read_bytes()
    board_html = _build_html_jobs_page("dotworld", [8642089], include_frame=True)

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://dotworld.teamtailor.com/jobs.rss":
            return httpx.Response(
                200,
                content=dotworld_xml,
                headers={
                    "content-type": "application/rss+xml; charset=utf-8",
                    "etag": 'W/"dw-1"',
                    "last-modified": "Tue, 17 Nov 2026 11:04:34 GMT",
                },
            )
        if str(req.url) == "https://dotworld.teamtailor.com/jobs":
            return httpx.Response(200, text=board_html)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("dotworld"), client)

    assert res.success is True
    assert res.not_modified is False
    assert res.snapshot_complete is True
    assert len(res.listings) == 7
    assert res.etag == 'W/"dw-1"'
    assert res.last_modified == "Tue, 17 Nov 2026 11:04:34 GMT"
    first = res.listings[0]
    assert first.provider == "teamtailor"
    assert first.company == "Dotworld"
    assert first.description and len(first.description) > 50
    assert first.posted_at is not None
    assert first.work_model in ("remote", "hybrid", "in_person", None)


@pytest.mark.anyio
async def test_2_malformed_xml_fails_without_closing():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss><channel><item><title>Unclosed")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board(), client)

    assert res.success is False
    assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_3_missing_or_invalid_job_identifier_rejected():
    bad_xml = _build_rss([
        "    <item><title>No Link</title><link>https://acme.teamtailor.com/about</link></item>"
    ])

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=bad_xml)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("acme", "Acme"), client)

    assert res.success is False
    assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_4_duplicate_entries_in_rss_rejected():
    dup_xml = _build_rss([
        _build_rss_item(1001, title="Role A"),
        _build_rss_item(1001, title="Role A Duplicate"),
    ])

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=dup_xml)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("acme", "Acme"), client)

    assert res.success is False
    assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_5_canonical_url_and_custom_domain_identity_validation():
    gravita_xml = (FIXTURE_DIR / "gravita_rss.xml").read_bytes()

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://gravita.teamtailor.com/jobs.rss":
            return httpx.Response(200, content=gravita_xml)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("gravita", "Gravita"), client)

    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 16
    assert all(j.id.startswith("teamtailor:gravita:") for j in res.listings)
    assert any(str(j.source_url).startswith("https://careers.gravita.com/jobs/") for j in res.listings)


@pytest.mark.anyio
async def test_6_and_18_conditional_304_does_not_close_jobs(tmp_path: Path):
    db_file = str(tmp_path / "tt_304.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(company_name="Acme", ats_provider="teamtailor", board_token="acme")
    assert board is not None
    existing = JobListing(
        id="teamtailor:acme:101",
        provider="teamtailor",
        data_source="api",
        title="Existing Engineer",
        company="Acme",
        source_url="https://acme.teamtailor.com/jobs/101-existing-engineer",
        apply_url="https://acme.teamtailor.com/jobs/101-existing-engineer",
        scraped_at=datetime.now(timezone.utc),
        ats_source="teamtailor",
        query_used="board_monitor",
    )
    reg.upsert_monitored_job(existing, board_id=board.id)
    reg.record_check_success(board.id, active_job_count=1, etag='W/"etag-1"', last_modified="Tue, 17 Nov 2026 10:00:00 GMT")
    board = reg.get_board("teamtailor", "acme")
    assert board is not None

    seen_headers: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen_headers.update({k.lower(): v for k, v in req.headers.items()})
        return httpx.Response(304)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await monitor.check_single_board(board, client, cache_store=cache)

    assert res.success is True
    assert res.not_modified is True
    assert seen_headers.get("if-none-match") == 'W/"etag-1"'
    assert seen_headers.get("if-modified-since") == "Tue, 17 Nov 2026 10:00:00 GMT"
    active_jobs = reg.get_monitored_jobs_for_board(board.id)
    assert "teamtailor:acme:101" in active_jobs
    with reg._get_connection() as conn:
        row = conn.execute(
            "SELECT status, missing_confirmation_count FROM monitored_jobs WHERE job_id = ?",
            ("teamtailor:acme:101",),
        ).fetchone()
    assert row == ("active", 0)


@pytest.mark.anyio
async def test_7_http_errors_and_timeouts_fail_without_closing():
    def handler_503(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    def handler_timeout(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=req)

    for h in (handler_503, handler_timeout):
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as client:
            res = await TeamtailorBoardAdapter().check_board(_make_board(), client)
        assert res.success is False
        assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_8_rss_below_100_items_is_complete_without_html_pagination():
    rss_xml = _build_rss([_build_rss_item(i) for i in range(1, 15)])
    urls_called: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        urls_called.append(str(req.url))
        if str(req.url).endswith("/jobs.rss"):
            return httpx.Response(200, text=rss_xml)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("acme", "Acme"), client)

    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 14
    assert not any("?page=" in u for u in urls_called)


@pytest.mark.anyio
async def test_9_10_11_12_rss_100_cap_and_ignored_page2_triggers_html_fallback():
    """
    Tests scenarios 9, 10, 11, 12:
    - RSS returns exactly 100 items and ignores ?page=2 (returns identical 100 items).
    - HTML /jobs?page=1..6 supplies all 110 jobs cleanly, marking snapshot_complete=True.
    """
    rss_100 = _build_rss([_build_rss_item(1000 + i) for i in range(100)])
    all_110_ids = [1000 + i for i in range(110)]
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        calls.append(u)
        if u.startswith("https://bigco.teamtailor.com/jobs.rss"):
            # Even if ?page=2 is requested, Teamtailor RSS returns the identical 100 items
            return httpx.Response(200, text=rss_100)
        if u == "https://bigco.teamtailor.com/jobs?page=1":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[0:20], next_page=2))
        if u == "https://bigco.teamtailor.com/jobs?page=2":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[20:40], next_page=3))
        if u == "https://bigco.teamtailor.com/jobs?page=3":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[40:60], next_page=4))
        if u == "https://bigco.teamtailor.com/jobs?page=4":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[60:80], next_page=5))
        if u == "https://bigco.teamtailor.com/jobs?page=5":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[80:100], next_page=6))
        if u == "https://bigco.teamtailor.com/jobs?page=6":
            return httpx.Response(200, text=_build_html_jobs_page("bigco", all_110_ids[100:110], next_page=None))
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("bigco", "BigCo"), client)

    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 110
    rss_by_id = {j.id: j for j in res.listings}
    # RSS items retain full description; extra HTML-only items #1100-#1109 keep authentic URL/title without fake description
    assert rss_by_id["teamtailor:bigco:1000"].description is not None
    assert rss_by_id["teamtailor:bigco:1109"].description is None


@pytest.mark.anyio
async def test_13_repeated_html_page_detected_and_marked_incomplete():
    rss_100 = _build_rss([_build_rss_item(2000 + i) for i in range(100)])
    page1 = _build_html_jobs_page("loopco", list(range(2000, 2020)), next_page=2)
    page2_dup = _build_html_jobs_page("loopco", list(range(2000, 2020)), next_page=3)

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u == "https://loopco.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=rss_100)
        if u == "https://loopco.teamtailor.com/jobs?page=1":
            return httpx.Response(200, text=page1)
        if u == "https://loopco.teamtailor.com/jobs?page=2":
            return httpx.Response(200, text=page2_dup)
        raise AssertionError(f"Should not request further pages after duplicate: {u}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("loopco", "LoopCo"), client)

    assert res.success is True
    assert res.snapshot_complete is False
    assert len(res.listings) == 100


@pytest.mark.anyio
async def test_14_pagination_loop_self_or_backward_page_marked_incomplete():
    rss_100 = _build_rss([_build_rss_item(3000 + i) for i in range(100)])
    page1 = _build_html_jobs_page("cyc", list(range(3000, 3020)), next_page=2)
    page2_loop = _build_html_jobs_page("cyc", list(range(3020, 3040)), next_page=1)

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u == "https://cyc.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=rss_100)
        if u == "https://cyc.teamtailor.com/jobs?page=1":
            return httpx.Response(200, text=page1)
        if u == "https://cyc.teamtailor.com/jobs?page=2":
            return httpx.Response(200, text=page2_loop)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("cyc", "Cyc"), client)

    assert res.success is True
    assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_15_failed_or_malformed_later_html_page_marked_incomplete():
    rss_100 = _build_rss([_build_rss_item(4000 + i) for i in range(100)])
    page1 = _build_html_jobs_page("errco", list(range(4000, 4020)), next_page=2)

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u == "https://errco.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=rss_100)
        if u == "https://errco.teamtailor.com/jobs?page=1":
            return httpx.Response(200, text=page1)
        if u == "https://errco.teamtailor.com/jobs?page=2":
            return httpx.Response(500, text="Server Error")
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await TeamtailorBoardAdapter().check_board(_make_board("errco", "ErrCo"), client)

    assert res.success is True
    assert res.snapshot_complete is False
    assert len(res.listings) == 100
    assert res.etag is None  # incomplete fallback must not cache conditional validators


@pytest.mark.anyio
async def test_16_partial_snapshot_never_closes_missing_jobs(tmp_path: Path):
    db_file = str(tmp_path / "tt_partial.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(company_name="BigCo", ats_provider="teamtailor", board_token="bigco")
    assert board is not None
    # Job #9999 was previously active (e.g. item #105 that didn't fit in the 100-item RSS cap)
    old_job = JobListing(
        id="teamtailor:bigco:9999",
        provider="teamtailor",
        data_source="api",
        title="Staff SRE",
        company="BigCo",
        source_url="https://bigco.teamtailor.com/jobs/9999-staff-sre",
        apply_url="https://bigco.teamtailor.com/jobs/9999-staff-sre",
        scraped_at=datetime.now(timezone.utc),
        ats_source="teamtailor",
        query_used="board_monitor",
    )
    reg.upsert_monitored_job(old_job, board_id=board.id)

    rss_100 = _build_rss([_build_rss_item(5000 + i) for i in range(100)])

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://bigco.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=rss_100, headers={"etag": 'W/"cap"'})
        # HTML fallback fails 502 -> partial snapshot
        return httpx.Response(502)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # Poll 3 consecutive times with incomplete snapshots -> must NEVER close 9999
        for _ in range(3):
            res = await monitor.check_single_board(board, client, cache_store=cache)
            assert res.success is True
            assert res.snapshot_complete is False

    active_jobs = reg.get_monitored_jobs_for_board(board.id)
    assert "teamtailor:bigco:9999" in active_jobs
    assert "teamtailor:bigco:5000" in active_jobs
    with reg._get_connection() as conn:
        row = conn.execute(
            "SELECT status, missing_confirmation_count FROM monitored_jobs WHERE job_id = ?",
            ("teamtailor:bigco:9999",),
        ).fetchone()
    assert row == ("active", 0)


@pytest.mark.anyio
async def test_17_complete_snapshot_closes_genuinely_missing_jobs_after_confirmation(tmp_path: Path):
    db_file = str(tmp_path / "tt_close.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(company_name="Dotworld", ats_provider="teamtailor", board_token="dotworld")
    assert board is not None
    gone_job = JobListing(
        id="teamtailor:dotworld:999999",
        provider="teamtailor",
        data_source="api",
        title="Retired Role",
        company="Dotworld",
        source_url="https://dotworld.teamtailor.com/jobs/999999-retired-role",
        apply_url="https://dotworld.teamtailor.com/jobs/999999-retired-role",
        scraped_at=datetime.now(timezone.utc),
        ats_source="teamtailor",
        query_used="board_monitor",
    )
    reg.upsert_monitored_job(gone_job, board_id=board.id)

    small_rss = _build_rss([_build_rss_item(8642089, slug_host="dotworld.teamtailor.com", title="Data Analyst")])

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://dotworld.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=small_rss)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res1 = await monitor.check_single_board(board, client, cache_store=cache)
        assert res1.snapshot_complete is True
        assert "teamtailor:dotworld:999999" in reg.get_monitored_jobs_for_board(board.id)

        res2 = await monitor.check_single_board(board, client, cache_store=cache)
        assert res2.snapshot_complete is True
        assert "teamtailor:dotworld:999999" not in reg.get_monitored_jobs_for_board(board.id)
        with reg._get_connection() as conn:
            row = conn.execute(
                "SELECT status, missing_confirmation_count FROM monitored_jobs WHERE job_id = ?",
                ("teamtailor:dotworld:999999",),
            ).fetchone()
        assert row == ("closed", 2)


@pytest.mark.anyio
async def test_19_and_20_other_providers_retain_behavior_and_teamtailor_e2e_and_direct_router(tmp_path: Path):
    # Verify BoardCheckResult preserves snapshot_complete=True default for existing providers
    assert BoardCheckResult(success=True).snapshot_complete is True

    # End-to-end registry upgrade from pre-Step-47 'unsupported' + BoardMonitor + Direct Router
    db_file = str(tmp_path / "tt_e2e.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    # Simulate legacy pre-Step-47 'unsupported' teamtailor row in SQLite, then re-discover/sync
    now = time.time()
    with reg._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO company_boards (
                company_name, company_slug, ats_provider, board_token, board_url,
                discovery_source, first_discovered_at, last_discovered_at,
                verification_status, monitoring_capability, next_scheduled_check
            ) VALUES (?, ?, 'teamtailor', 'dotworld', 'https://dotworld.teamtailor.com', 'search', ?, ?, 'candidate', 'unsupported', ?)
            """,
            ("Dotworld", "dotworld", now, now, now),
        )
        conn.commit()

    promoted = reg.register_candidate(company_name="Dotworld", ats_provider="teamtailor", board_token="dotworld")
    assert promoted is not None
    assert promoted.monitoring_capability == "supported"

    dotworld_xml = (FIXTURE_DIR / "dotworld_rss.xml").read_bytes()

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://dotworld.teamtailor.com/jobs.rss":
            return httpx.Response(200, content=dotworld_xml, headers={"etag": 'W/"e2e"'})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # Monitor poll due boards -> populates monitored_jobs & url_cache
        monitored = await monitor.poll_due_boards(client=client, cache_store=cache)
        assert len(monitored) == 7
        cached_first = cache.get_url_cache(monitored[0].source_url)
        assert cached_first is not None

        # Direct board router probe
        probed = await probe_teamtailor_board("dotworld", client)
        assert len(probed) == 7
        via_router = await probe_direct_boards(["dotworld"], client, platforms=["teamtailor"])
        assert len(via_router) == 7


@pytest.mark.anyio
async def test_teamtailor_completeness_preservation_remote_none_multilocation_and_regional_na(tmp_path: Path):
    db_file = str(tmp_path / "tt_preserve.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(
        company_name="Jobsity",
        ats_provider="teamtailor",
        board_token="cc-jobs-jobsity.na",
    )
    assert board is not None
    assert board.board_url == "https://cc-jobs-jobsity.na.teamtailor.com"

    job_url = "https://cc-jobs-jobsity.na.teamtailor.com/jobs/726924-go-engineer"
    # Pre-seed url_cache with richer HTML-scraped salary, requirements, and verified logo
    pre_seeded = JobListing(
        id="teamtailor:cc-jobs-jobsity.na:726924",
        provider="teamtailor",
        data_source="scrape",
        title="Go Engineer",
        company="Jobsity",
        salary="$120,000 - $140,000/yr",
        requirements="5+ years Go & distributed systems",
        company_logo_url="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/jobsity.png",
        company_logo_source="teamtailor_header",
        company_logo_verified=True,
        source_url=job_url,
        apply_url=job_url,
        scraped_at=datetime.now(timezone.utc),
        ats_source="teamtailor",
        query_used="search",
    )
    cache.set_url_cache(job_url, pre_seeded)

    multi_loc_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:tt="https://teamtailor.com/locations">\n'
        "  <channel>\n"
        "    <title>Jobsity</title>\n"
        "    <link>https://cc-jobs-jobsity.na.teamtailor.com/jobs</link>\n"
        "    <item>\n"
        "      <title>Go Engineer</title>\n"
        "      <description>&lt;p&gt;Build distributed microservices in Go.&lt;/p&gt;</description>\n"
        "      <pubDate>Tue, 17 Nov 2026 09:00:00 +0000</pubDate>\n"
        f"      <link>{job_url}</link>\n"
        "      <remoteStatus>none</remoteStatus>\n"
        "      <guid>uuid-na-726924</guid>\n"
        "      <tt:locations>\n"
        "        <tt:location><tt:name>Lisbon Portugal</tt:name><tt:city>Lisbon</tt:city><tt:country>Portugal</tt:country></tt:location>\n"
        "        <tt:location><tt:name>Porto Portugal</tt:name><tt:city>Porto</tt:city><tt:country>Portugal</tt:country></tt:location>\n"
        "      </tt:locations>\n"
        "      <tt:department>Engineering</tt:department>\n"
        "      <tt:role>Backend</tt:role>\n"
        "    </item>\n"
        "  </channel>\n"
        "</rss>\n"
    )

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://cc-jobs-jobsity.na.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=multi_loc_xml)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await monitor.check_single_board(board, client, cache_store=cache)

    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 1
    job = res.listings[0]
    assert job.location == "Lisbon, Portugal; Porto, Portugal"
    assert job.work_model is None  # remoteStatus="none" must never fabricate in_person
    assert job.salary == "$120,000 - $140,000/yr"  # preserved from url_cache!
    assert job.requirements == "5+ years Go & distributed systems"  # preserved from url_cache!
    assert job.company_logo_verified is True  # verified logo preserved!


@pytest.mark.anyio
async def test_failed_checks_across_all_adapters_mark_snapshot_incomplete_and_pagination_handles_prev_links():
    from src.providers.board_adapters import (
        AshbyBoardAdapter,
        GreenhouseBoardAdapter,
        LeverBoardAdapter,
        RecruiteeBoardAdapter,
        SmartRecruitersBoardAdapter,
        WorkableBoardAdapter,
    )

    assert BoardCheckResult(success=False).snapshot_complete is False

    def err_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(err_handler)) as client:
        for provider, adapter_cls in (
            ("greenhouse", GreenhouseBoardAdapter),
            ("lever", LeverBoardAdapter),
            ("ashby", AshbyBoardAdapter),
            ("workable", WorkableBoardAdapter),
            ("recruitee", RecruiteeBoardAdapter),
            ("smartrecruiters", SmartRecruitersBoardAdapter),
            ("teamtailor", TeamtailorBoardAdapter),
        ):
            res = await adapter_cls().check_board(_make_board("acme", "Acme"), client)
            assert res.success is False
            assert res.snapshot_complete is False, f"{provider} failed check must not look complete"

    # Doctype/Entity beyond byte 4096 must still be rejected
    padding = "<!-- " + ("x" * 5000) + " -->"
    evil_xml = (
        f'<?xml version="1.0"?>{padding}<!DOCTYPE foo [<!ENTITY xxe "pwn">]>'
        "<rss version='2.0'><channel><title>X</title></channel></rss>"
    ).encode("utf-8")
    _, _, xml_err = parse_teamtailor_rss_feed(evil_xml)
    assert xml_err is not None

    # HTML page 2 containing a 'Previous (?page=1)' link BEFORE 'Next (?page=3)' must advance to page 3
    rss_100 = _build_rss([_build_rss_item(6000 + i) for i in range(100)])
    p1 = _build_html_jobs_page("navco", list(range(6000, 6020)), next_page=2)
    p2 = (
        '<html><body><turbo-frame id="jobs_list">'
        '<ul>'
        + "".join(
            f'<li><a href="https://navco.teamtailor.com/jobs/{jid}-role">Role {jid}</a></li>'
            for jid in range(6020, 6040)
        )
        + '</ul>'
        '<a href="/jobs?page=1">Previous</a>'
        '<a href="/jobs/show_more?page=2&amp;page=3">Show more</a>'
        "</turbo-frame></body></html>"
    )
    p3 = _build_html_jobs_page("navco", list(range(6100, 6105)), next_page=None)

    def nav_handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u == "https://navco.teamtailor.com/jobs.rss":
            return httpx.Response(200, text=rss_100)
        if u == "https://navco.teamtailor.com/jobs?page=1":
            return httpx.Response(200, text=p1)
        if u == "https://navco.teamtailor.com/jobs?page=2":
            return httpx.Response(200, text=p2)
        if u == "https://navco.teamtailor.com/jobs?page=3":
            return httpx.Response(200, text=p3)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(nav_handler)) as client:
        res_nav = await TeamtailorBoardAdapter().check_board(_make_board("navco", "NavCo"), client)

    assert res_nav.success is True
    assert res_nav.snapshot_complete is True
    assert len(res_nav.listings) == 105


def test_preexisting_unsupported_teamtailor_rows_promoted_on_registry_init(tmp_path: Path):

    db_file = str(tmp_path / "tt_legacy_upgrade.sqlite")
    reg1 = CompanyBoardRegistry(db_path=db_file)
    with reg1._get_connection() as conn:
        now = time.time()
        conn.execute(
            """
            INSERT INTO company_boards (
                company_name, company_slug, ats_provider, board_token, board_url,
                discovery_source, first_discovered_at, last_discovered_at,
                verification_status, monitoring_capability, next_scheduled_check
            ) VALUES ('Dotworld', 'dotworld', 'teamtailor', 'dotworld', 'https://dotworld.teamtailor.com', 'search', ?, ?, 'candidate', 'unsupported', NULL)
            """,
            (now, now),
        )
        conn.commit()

    # Re-opening registry triggers _ensure_db(), which promotes pre-existing 'unsupported' teamtailor rows
    reg2 = CompanyBoardRegistry(db_path=db_file)
    promoted = reg2.get_board("teamtailor", "dotworld")
    assert promoted is not None
    assert promoted.monitoring_capability == "supported"
    due = reg2.get_due_monitoring_boards(limit=10)
    assert any(b.board_token == "dotworld" for b in due)


def test_parse_teamtailor_rss_preserves_full_all_locations_when_display_truncated():
    multi_loc_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:tt="https://teamtailor.com/locations">\n'
        "  <channel>\n"
        "    <title>Paystack</title>\n"
        "    <link>https://paystack.teamtailor.com/jobs</link>\n"
        "    <item>\n"
        "      <title>Senior DevOps Engineer</title>\n"
        "      <description>&lt;p&gt;Build payment infrastructure.&lt;/p&gt;</description>\n"
        "      <pubDate>Tue, 17 Nov 2026 10:00:00 +0000</pubDate>\n"
        "      <link>https://paystack.teamtailor.com/jobs/7001-devops</link>\n"
        "      <remoteStatus>hybrid</remoteStatus>\n"
        "      <guid>guid-7001</guid>\n"
        "      <tt:locations>\n"
        "        <tt:location><tt:name>Accra Ghana</tt:name><tt:city>Accra</tt:city><tt:country>Ghana</tt:country></tt:location>\n"
        "        <tt:location><tt:name>Cape Town ZA</tt:name><tt:city>Cape Town</tt:city><tt:country>South Africa</tt:country></tt:location>\n"
        "        <tt:location><tt:name>Dubai UAE</tt:name><tt:city>Dubai</tt:city><tt:country>United Arab Emirates</tt:country></tt:location>\n"
        "        <tt:location><tt:name>Lagos NG</tt:name><tt:city>Lagos</tt:city><tt:country>Nigeria</tt:country></tt:location>\n"
        "        <tt:location><tt:name>Nairobi KE</tt:name><tt:city>Nairobi</tt:city><tt:country>Kenya</tt:country></tt:location>\n"
        "      </tt:locations>\n"
        "    </item>\n"
        "  </channel>\n"
        "</rss>\n"
    ).encode("utf-8")

    items, _meta, err = parse_teamtailor_rss_feed(multi_loc_xml)
    assert err is None
    assert len(items) == 1
    assert "(+" in (items[0]["location"] or "")
    assert items[0]["all_locations"] == [
        "Accra, Ghana",
        "Cape Town, South Africa",
        "Dubai, United Arab Emirates",
        "Lagos, Nigeria",
        "Nairobi, Kenya",
    ]

    from src.providers.board_adapters import _teamtailor_rss_item_to_listing

    listing = _teamtailor_rss_item_to_listing(items[0], board_token="paystack")
    assert listing.eligibility is not None
    assert set(listing.eligibility.allowed_country_codes or []) >= {"GH", "ZA", "AE", "NG", "KE"}

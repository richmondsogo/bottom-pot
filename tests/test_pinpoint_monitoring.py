"""
Step 51 Tests: Pinpoint (`pinpointhq`) Monitoring, Feed Validation, Eligibility & Compensation,
URL Normalization, Conditional ETag, Direct Board Routing, and Discovery Registration.

Uses captured real Pinpoint JSON & HTML fixtures (`tests/fixtures/real/pinpointhq/`) and
deterministic `httpx.MockTransport` handlers with isolated `tmp_path` SQLite DBs
(zero live HTTP requests, zero Serper credits, zero writes to operational DB).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.ats_url_parser import (
    SUPPORTED_ATS_PATTERNS,
    parse_ats_url,
    parse_pinpoint_board_root_url,
)
from src.project_files.board_adapters import (
    BOARD_ADAPTERS,
    BoardCheckResult,
    PinpointBoardAdapter,
    _pinpoint_item_to_listing,
    parse_pinpoint_postings_json,
)
from src.project_files.board_monitor import BoardMonitor
from src.project_files.cache_store import CacheStore
from src.project_files.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoard,
    CompanyBoardRegistry,
    build_canonical_board_url,
)
from src.project_files.direct_board_router import (
    probe_direct_boards,
    probe_pinpoint_board,
)
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.http_resilience import ResponseTooLargeError
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.url_normalizer import (
    build_url_match_key,
    canonicalize_pinpoint_posting_url,
    normalize_job_url,
    url_carries_job_identifier,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "pinpointhq"


def _make_board(
    token: str = "pathify",
    company_name: str = "Pathify",
    *,
    board_id: int = 1,
    board_url: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    content_fingerprint: str | None = None,
) -> CompanyBoard:
    return CompanyBoard(
        id=board_id,
        company_name=company_name,
        company_slug=token,
        ats_provider="pinpointhq",
        board_token=token,
        board_url=board_url or f"https://{token}.pinpointhq.com",
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


def _posting_dict(
    posting_id: str | int = "1001",
    uuid: str = "5287daee-876a-4fd2-b6e2-ead3aa0c23e7",
    *,
    slug: str = "acme",
    title: str = "Backend Python Engineer",
    loc_name: str = "Lagos, Nigeria",
    city: str = "Lagos",
    province: str = "Nigeria",
    workplace_type: str = "remote",
    employment_type: str = "full_time",
    department: str = "Engineering",
    description: str = "<p>Build distributed Python APIs for global teams.</p>",
    skills: str = "<ul><li>5+ years Python experience</li></ul>",
    deadline_at: str | None = "2026-12-31",
    compensation_visible: bool = False,
    compensation_min: float | None = None,
    compensation_max: float | None = None,
    compensation_curr: str | None = None,
    compensation_freq: str | None = None,
) -> dict:
    return {
        "id": str(posting_id),
        "title": title,
        "url": f"https://{slug}.pinpointhq.com/en/postings/{uuid}",
        "path": f"/en/postings/{uuid}",
        "description": description,
        "key_responsibilities": "<ul><li>Ship reliable backend systems</li></ul>",
        "key_responsibilities_header": "Key Responsibilities",
        "skills_knowledge_expertise": skills,
        "skills_knowledge_expertise_header": "Skills, Knowledge & Expertise",
        "benefits": "<p>Remote stipend</p>",
        "benefits_header": "Benefits",
        "workplace_type": workplace_type,
        "workplace_type_text": workplace_type.title(),
        "employment_type": employment_type,
        "employment_type_text": employment_type.replace("_", " ").title(),
        "compensation": None,
        "compensation_minimum": compensation_min,
        "compensation_maximum": compensation_max,
        "compensation_currency": compensation_curr,
        "compensation_frequency": compensation_freq,
        "compensation_visible": compensation_visible,
        "deadline_at": deadline_at,
        "reporting_to": "VP Engineering",
        "job": {
            "id": "9001",
            "requisition_id": f"REQ-{posting_id}",
            "department": {"id": "10", "name": department} if department else None,
            "division": None,
            "structure_custom_group_one": None,
        },
        "location": {
            "id": "50",
            "name": loc_name,
            "city": city,
            "province": province,
            "postal_code": "",
            "street_address": "",
        },
    }


# ---------------------------------------------------------------------------
# 1. Registry, Adapter Registration, URL Parsing & Normalization
# ---------------------------------------------------------------------------


def test_01_pinpoint_registered_as_supported_and_monitorable():
    assert "pinpointhq" in SUPPORTED_ATS_PATTERNS
    assert "pinpointhq" in MONITORABLE_PROVIDERS
    assert "pinpointhq" in BOARD_ADAPTERS
    assert isinstance(BOARD_ADAPTERS["pinpointhq"], PinpointBoardAdapter)
    assert build_canonical_board_url("pinpointhq", "sunking") == "https://sunking.pinpointhq.com"


def test_02_pinpoint_url_parsing_variants_and_exclusions():
    uuid = "5287daee-876a-4fd2-b6e2-ead3aa0c23e7"
    p_en = parse_ats_url(f"https://pathify.pinpointhq.com/en/postings/{uuid}")
    assert p_en is not None
    assert p_en.ats == "pinpointhq"
    assert p_en.company_slug == "pathify"
    assert p_en.job_id == uuid

    p_root_loc = parse_ats_url(f"https://PATHIFY.pinpointhq.com/pt-BR/postings/{uuid.upper()}/applications/new?utm_source=x")
    assert p_root_loc is not None
    assert p_root_loc.ats == "pinpointhq"
    assert p_root_loc.company_slug == "pathify"
    assert p_root_loc.job_id == uuid

    p_no_loc = parse_ats_url(f"https://sunking.pinpointhq.com/postings/{uuid}")
    assert p_no_loc is not None
    assert p_no_loc.company_slug == "sunking"
    assert p_no_loc.job_id == uuid

    p_legacy = parse_ats_url("https://pathify.pinpointhq.com/jobs/597321")
    assert p_legacy is not None
    assert p_legacy.ats == "pinpointhq"
    assert p_legacy.company_slug == "pathify"
    assert p_legacy.job_id == "597321"

    # Reserved platform subdomains and board roots must NOT parse as individual jobs
    assert parse_ats_url(f"https://www.pinpointhq.com/en/postings/{uuid}") is None
    assert parse_ats_url(f"https://developers.pinpointhq.com/postings/{uuid}") is None
    assert parse_ats_url("https://sunking.pinpointhq.com/") is None
    assert parse_ats_url("https://sunking.pinpointhq.com/postings.json") is None

    # Board root parser accepts board roots and rejects job pages & reserved subdomains
    assert parse_pinpoint_board_root_url("https://sunking.pinpointhq.com/") == "sunking"
    assert parse_pinpoint_board_root_url("https://pathify.pinpointhq.com/en") == "pathify"
    assert parse_pinpoint_board_root_url("https://indrive.pinpointhq.com/jobs") == "indrive"
    assert parse_pinpoint_board_root_url("https://www.pinpointhq.com/") is None
    assert parse_pinpoint_board_root_url("https://developers.pinpointhq.com/docs/job-feeds-overview") is None
    assert parse_pinpoint_board_root_url(f"https://pathify.pinpointhq.com/en/postings/{uuid}") is None


def test_03_pinpoint_url_normalization_collapses_variants_to_single_match_key():
    uuid = "5287daee-876a-4fd2-b6e2-ead3aa0c23e7"
    u1 = f"http://pathify.pinpointhq.com/en/postings/{uuid.upper()}/?utm_source=linkedin"
    u2 = f"https://pathify.pinpointhq.com/postings/{uuid}"
    u3 = f"https://pathify.pinpointhq.com/en/postings/{uuid}/applications/new#apply"
    u4 = f"https://PATHIFY.pinpointhq.com/fr/postings/{uuid}/apply"

    k1 = build_url_match_key(u1, "pinpointhq")
    k2 = build_url_match_key(u2, "pinpointhq")
    k3 = build_url_match_key(u3, "pinpointhq")
    k4 = build_url_match_key(u4, None)

    expected = f"https://pathify.pinpointhq.com/postings/{uuid}"
    assert k1 == k2 == k3 == k4 == expected
    assert canonicalize_pinpoint_posting_url(u3) == expected
    assert normalize_job_url(u1, "pinpointhq").startswith("https://pathify.pinpointhq.com/")
    assert url_carries_job_identifier(u3, "pinpointhq") is True
    assert url_carries_job_identifier("https://pathify.pinpointhq.com/", "pinpointhq") is False


# ---------------------------------------------------------------------------
# 2. Real Captured Fixture Validation (Pathify, Bizimply, WorkWithUs, Sun King, Calligo)
# ---------------------------------------------------------------------------


def test_04_real_pathify_fixture_extracts_compensation_work_model_and_restriction():
    raw_bytes = (FIXTURE_DIR / "pathify_postings.json").read_bytes()
    items, err = parse_pinpoint_postings_json(raw_bytes, expected_slug="pathify")
    assert err is None
    assert len(items) == 4

    listings = [_pinpoint_item_to_listing(it, board_token="pathify", board_company_name="Pathify") for it in items]
    swe = next(j for j in listings if j.title == "Software Engineer")
    assert swe.id == "pinpointhq:pathify:5287daee-876a-4fd2-b6e2-ead3aa0c23e7"
    assert swe.source_record_id == "558423"
    assert "pinpointhq:pathify:558423" in swe.aliases
    assert swe.provider == "pinpointhq"
    assert swe.ats_source == "pinpointhq"
    assert swe.data_source == "api"
    assert swe.company == "Pathify"
    assert swe.department == "Engineering"
    assert swe.location == "Australia (Remote)"
    assert swe.work_model == "remote"
    assert swe.employment_type == "full_time"
    # ADR 0001: /postings.json omits created timestamp; never synthesize posted_at
    assert swe.posted_at is None
    assert swe.salary is not None
    assert swe.salary.minimum == 135000
    assert swe.salary.maximum == 165000
    assert swe.salary.currency == "AUD"
    assert swe.salary.period == "year"
    assert swe.requirements is not None and "Django" in swe.requirements
    assert swe.apply_url.endswith("/applications/new")
    # Restriction detected from "Australia (Remote)" / "Unrestricted working rights in Australia"
    assert swe.eligibility is not None
    assert swe.eligibility.nigeria_eligible is False


def test_05_real_bizimply_workwithus_sunking_and_empty_calligo_fixtures():
    biz_items, biz_err = parse_pinpoint_postings_json(
        (FIXTURE_DIR / "bizimply_postings.json").read_bytes(), expected_slug="bizimply"
    )
    assert biz_err is None and len(biz_items) == 2
    biz_listings = [_pinpoint_item_to_listing(it, board_token="bizimply", board_company_name="Bizimply") for it in biz_items]
    sdet = next(j for j in biz_listings if "SDET" in j.title)
    assert sdet.location == "Egypt"
    assert sdet.work_model == "remote"
    assert sdet.salary is None  # compensation_visible=false
    assert sdet.requirements is not None and "Playwright" in sdet.requirements

    wwu_items, wwu_err = parse_pinpoint_postings_json(
        (FIXTURE_DIR / "workwithus_postings.json").read_bytes(), expected_slug="workwithus"
    )
    assert wwu_err is None and len(wwu_items) == 3
    wwu_listings = [_pinpoint_item_to_listing(it, board_token="workwithus", board_company_name="Pinpoint") for it in wwu_items]
    tse = next(j for j in wwu_listings if "Technical Success" in j.title)
    assert "Python" in (tse.requirements or "")

    sk_items, sk_err = parse_pinpoint_postings_json(
        (FIXTURE_DIR / "sunking_africa_subset_postings.json").read_bytes(), expected_slug="sunking"
    )
    assert sk_err is None and len(sk_items) == 4
    sk_listings = [_pinpoint_item_to_listing(it, board_token="sunking", board_company_name="Sun King") for it in sk_items]
    techops = next(j for j in sk_listings if "TechOps" in j.title)
    assert techops.location == "Africa"
    assert techops.work_model == "hybrid"
    assert techops.employment_type == "full_time"  # permanent_full_time -> full_time
    assert techops.department == "Global Analytics and Technology"
    abm = next(j for j in sk_listings if "Afikpo" in j.title)
    assert abm.location == "Nigeria"  # location.name preserved rather than city=Lagos
    assert abm.work_model == "in_person"

    empty_items, empty_err = parse_pinpoint_postings_json(
        (FIXTURE_DIR / "calligo_postings_empty.json").read_bytes(), expected_slug="calligo"
    )
    assert empty_err is None
    assert empty_items == []


# ---------------------------------------------------------------------------
# 3. ADR 0001 Strict Mapping & Fail-Closed Validation Tests
# ---------------------------------------------------------------------------


def test_06_pinpoint_adr0001_guards_never_fabricate_posted_at_or_hidden_salary():
    # Even when deadline_at is set, posted_at must remain None because /postings.json has no pubDate.
    # Also permanent-only or unrecognized employment_type must stay None rather than guessing from text.
    item_payload = {
        "data": [
            {
                **_posting_dict(
                    "777",
                    title="Research Engineer",
                    employment_type="casual",
                    description="<p>This is a full-time research role. Salary $120,000/yr.</p>",
                    deadline_at="2026-12-30T23:59:59Z",
                    compensation_visible=False,
                    compensation_min=120000.0,
                    compensation_max=150000.0,
                    compensation_curr="USD",
                    compensation_freq="year",
                ),
                "compensation": "$120,000 - $150,000 / year",
            }
        ]
    }
    items, err = parse_pinpoint_postings_json(json.dumps(item_payload).encode("utf-8"), expected_slug="acme")
    assert err is None and len(items) == 1
    listing = _pinpoint_item_to_listing(items[0], board_token="acme")
    assert listing.posted_at is None
    assert listing.employment_type is None
    # Note: hidden structured compensation (compensation_visible=False) is suppressed
    assert listing.raw_workplace_type == "remote"


def test_07_parse_pinpoint_postings_json_fails_closed_on_malformed_or_cross_tenant():
    valid = _posting_dict("1", slug="acme")

    for bad_payload in (
        b"",
        b"{not json",
        b"[]",
        b"{}",
        json.dumps({"data": "not-a-list"}).encode(),
        json.dumps({"data": ["not-an-object"]}).encode(),
        json.dumps({"data": [{**valid, "id": ""}]}).encode(),
        json.dumps({"data": [{**valid, "title": "  "}]}).encode(),
        json.dumps({"data": [{**valid, "url": ""}]}).encode(),
        json.dumps({"data": [{**valid, "url": "", "path": ""}]}).encode(),
        json.dumps({"data": [{**valid, "url": "https://evil.com/en/postings/5287daee-876a-4fd2-b6e2-ead3aa0c23e7"}]}).encode(),
        json.dumps({"data": [{**valid, "url": "https://other.pinpointhq.com/en/postings/5287daee-876a-4fd2-b6e2-ead3aa0c23e7"}]}).encode(),
        json.dumps({"data": [valid, valid]}).encode(),
    ):
        items, err = parse_pinpoint_postings_json(bad_payload, expected_slug="acme")
        assert items == []
        assert err is not None


# ---------------------------------------------------------------------------
# 4. Adapter HTTP Handling, ETag 304, Fingerprint & Closure Safety
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_08_pinpoint_adapter_handles_200_304_fingerprint_and_errors():
    adapter = PinpointBoardAdapter()
    raw_bytes = (FIXTURE_DIR / "bizimply_postings.json").read_bytes()

    # Poll 1: 200 OK with W/ ETag
    def h_ok(req: httpx.Request) -> httpx.Response:
        assert str(req.url) == "https://bizimply.pinpointhq.com/postings.json"
        return httpx.Response(200, content=raw_bytes, headers={"ETag": 'W/"etag-v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_ok)) as client:
        r1 = await adapter.check_board(_make_board("bizimply", "Bizimply"), client)

    assert r1.success is True
    assert r1.not_modified is False
    assert r1.snapshot_complete is True
    assert r1.missing_confirmation_threshold == 2
    assert r1.etag == 'W/"etag-v1"'
    assert r1.content_fingerprint is not None
    assert len(r1.listings) == 2

    # Poll 2: Conditional If-None-Match -> 304 Not Modified
    seen_inm: list[str | None] = []

    def h_304(req: httpx.Request) -> httpx.Response:
        seen_inm.append(req.headers.get("if-none-match"))
        return httpx.Response(304, headers={"ETag": 'W/"etag-v1"'})

    b2 = _make_board("bizimply", "Bizimply", etag=r1.etag, content_fingerprint=r1.content_fingerprint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(h_304)) as client:
        r2 = await adapter.check_board(b2, client)

    assert seen_inm == ['W/"etag-v1"']
    assert r2.success is True
    assert r2.not_modified is True
    assert r2.snapshot_complete is True

    # Poll 3: Changed ETag but identical body -> fingerprint short-circuits
    def h_same_body(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw_bytes, headers={"ETag": 'W/"etag-v2"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_same_body)) as client:
        r3 = await adapter.check_board(b2, client)

    assert r3.success is True
    assert r3.not_modified is True
    assert r3.etag == 'W/"etag-v2"'

    # Poll 4: Redirects (tenant rename), 404, 429, 500 must fail closed
    for status_code, hdrs in (
        (301, {"Location": "https://pssg.pinpointhq.com/postings.json"}),
        (404, {}),
        (429, {"Retry-After": "60"}),
        (500, {}),
    ):
        def h_fail(req: httpx.Request, sc=status_code, hd=hdrs) -> httpx.Response:
            return httpx.Response(sc, headers=hd)

        async with httpx.AsyncClient(transport=httpx.MockTransport(h_fail)) as client:
            r_err = await adapter.check_board(_make_board("bizimply", "Bizimply"), client)

        assert r_err.success is False
        assert r_err.snapshot_complete is False


@pytest.mark.anyio
async def test_09_pinpoint_adapter_rejects_oversize_response():
    adapter = PinpointBoardAdapter()
    large_json = json.dumps({"data": [_posting_dict(str(i), f"5287daee-876a-4fd2-b6e2-ead3aa0c{i:04d}") for i in range(50)]}).encode()

    def h_big(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=large_json)

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_big)) as client:
        res = await adapter.check_board(_make_board("acme", "Acme"), client, max_response_bytes=512)

    assert res.success is False
    assert res.snapshot_complete is False
    assert "exceeded" in (res.error or "").lower() or "limit" in (res.error or "").lower()


@pytest.mark.anyio
async def test_10_board_monitor_enforces_two_strike_closure_and_error_safety(tmp_path: Path):
    db_file = str(tmp_path / "pinpoint_monitor.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(
        ats_provider="pinpointhq",
        board_token="acme",
        company_name="Acme Co",
        board_url="https://acme.pinpointhq.com",
    )
    assert board is not None and board.monitoring_capability == "supported"

    u1 = "5287daee-876a-4fd2-b6e2-ead3aa0c0001"
    u2 = "5287daee-876a-4fd2-b6e2-ead3aa0c0002"
    snap_two = json.dumps({"data": [_posting_dict("1", u1, title="Role 1"), _posting_dict("2", u2, title="Role 2")]}).encode()
    snap_one = json.dumps({"data": [_posting_dict("1", u1, title="Role 1")]}).encode()
    snap_empty = (FIXTURE_DIR / "calligo_postings_empty.json").read_bytes()

    def _status_and_missing(jid: str) -> tuple[str, int]:
        with sqlite3.connect(db_file) as c:
            row = c.execute(
                "SELECT status, missing_confirmation_count FROM monitored_jobs WHERE job_id = ?",
                (jid,),
            ).fetchone()
        assert row is not None
        return row[0], row[1]

    # Poll 1: 2 active jobs
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=snap_two, headers={"ETag": '"v1"'}))) as client:
        r1 = await monitor.check_single_board(board, client)
    assert r1.success is True and len(r1.listings) == 2
    assert _status_and_missing(f"pinpointhq:acme:{u2}") == ("active", 0)

    # Poll 2: Transient 500 error must NOT close or increment missing counter
    board = reg.get_board("pinpointhq", "acme")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(500))) as client:
        r_err = await monitor.check_single_board(board, client)
    assert r_err.success is False
    assert _status_and_missing(f"pinpointhq:acme:{u2}") == ("active", 0)

    # Poll 2b: Board-level 404 on /postings.json fails closed (snapshot_complete=False) and must NOT close jobs
    board = reg.get_board("pinpointhq", "acme")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        r_404 = await monitor.check_single_board(board, client)
    assert r_404.success is False
    assert r_404.snapshot_complete is False
    assert _status_and_missing(f"pinpointhq:acme:{u2}") == ("active", 0)
    assert _status_and_missing(f"pinpointhq:acme:{u1}") == ("active", 0)

    # Poll 3: Complete snapshot missing u2 -> miss strike 1 (still active!)
    board = reg.get_board("pinpointhq", "acme")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=snap_one, headers={"ETag": '"v2"'}))) as client:
        await monitor.check_single_board(board, client)
    assert _status_and_missing(f"pinpointhq:acme:{u2}") == ("active", 1)

    # Poll 4: Empty snapshot {"data":[]} -> miss strike 2 closes u2, miss strike 1 on u1!
    board = reg.get_board("pinpointhq", "acme")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=snap_empty, headers={"ETag": '"v3"'}))) as client:
        await monitor.check_single_board(board, client)
    assert _status_and_missing(f"pinpointhq:acme:{u2}") == ("closed", 2)
    assert _status_and_missing(f"pinpointhq:acme:{u1}") == ("active", 1)


# ---------------------------------------------------------------------------
# 5. Direct Board Router, Search Pipeline Registration & Detail Page Enricher
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_11_direct_board_router_probes_pinpoint():
    pathify_bytes = (FIXTURE_DIR / "pathify_postings.json").read_bytes()
    empty_bytes = (FIXTURE_DIR / "calligo_postings_empty.json").read_bytes()
    seen_hosts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_hosts.append(req.url.host)
        if req.url.host == "pathify.pinpointhq.com":
            return httpx.Response(200, content=pathify_bytes)
        if req.url.host == "calligo.pinpointhq.com":
            return httpx.Response(200, content=empty_bytes)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        direct = await probe_pinpoint_board("pathify", client)
        empty = await probe_pinpoint_board("calligo", client)
        missing = await probe_pinpoint_board("nonexistent-co", client)
        invalid = await probe_pinpoint_board("pinpoint", client)
        routed = await probe_direct_boards(["pathify"], client, platforms=["pinpointhq"])

    assert len(direct) == 4
    assert all(j.id.startswith("pinpointhq:pathify:") for j in direct)
    assert empty == []
    assert missing == []
    assert invalid == []
    assert len(routed) == 4
    assert "pathify.pinpointhq.com" in seen_hosts


@pytest.mark.anyio
async def test_12_search_pipeline_registers_pinpoint_board_root_and_enriches_detail_jsonld(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import src.project_files.search_pipeline as sp_mod

    db_file = str(tmp_path / "pipeline_pinpoint.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monkeypatch.setattr(sp_mod, "company_board_registry", reg)
    monkeypatch.setattr(sp_mod, "cache_store", cache)

    orch = SearchOrchestrator()

    # 1. Board root URL registers monitorable candidate cleanly without wasting single-page fetch
    root_item = {"link": "https://sunking.pinpointhq.com/", "title": "Jobs at Sun King", "snippet": ""}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        res_root = await orch._enrich_ats_item("pinpointhq", root_item, "python", client)

    assert res_root is None
    board = reg.get_board("pinpointhq", "sunking")
    assert board is not None
    assert board.monitoring_capability == "supported"
    assert board.board_url == "https://sunking.pinpointhq.com"

    # 2. Individual posting HTML page enriches via Schema.org JobPosting JSON-LD (including datePosted & baseSalary)
    detail_html = (FIXTURE_DIR / "pathify_detail_sample.html").read_bytes()
    detail_url = "https://pathify.pinpointhq.com/en/postings/5287daee-876a-4fd2-b6e2-ead3aa0c23e7"

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=detail_html, headers={"content-type": "text/html"}))
    ) as client:
        listing, outcome = await enrich_ats_page_result(
            url=detail_url,
            provider="pinpointhq",
            search_title="Software Engineer - Pathify",
            snippet="Python / Django",
            query_used="python",
            client=client,
        )

    assert outcome.outcome == ExtractionOutcome.SUCCESS
    assert listing is not None
    assert listing.id == "pinpointhq:pathify:5287daee-876a-4fd2-b6e2-ead3aa0c23e7"
    assert listing.company == "Pathify"
    assert listing.posted_at is not None  # JSON-LD datePosted 2026-08-10T00:19:39+01:00
    assert listing.salary is not None and listing.salary.currency == "AUD"
    assert listing.salary.minimum == 135000 and listing.salary.maximum == 165000
    assert listing.work_model == "remote"
    assert listing.eligibility is not None and listing.eligibility.nigeria_eligible is False

    # 3. 404 on closed Pinpoint posting maps to NOT_FOUND
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        closed_listing, closed_outcome = await enrich_ats_page_result(
            url="https://pathify.pinpointhq.com/en/postings/00000000-0000-0000-0000-000000000000",
            provider="pinpointhq",
            search_title="Closed Role",
            snippet="",
            query_used="python",
            client=client,
        )
    assert closed_listing is None
    assert closed_outcome.outcome == ExtractionOutcome.NOT_FOUND


@pytest.mark.anyio
async def test_13_pinpoint_direct_routing_and_monitoring_use_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    from src.config import settings
    from src.project_files import board_adapters as ba_mod
    from src.project_files import direct_board_router as dbr_mod

    pathify_bytes = (FIXTURE_DIR / "pathify_postings.json").read_bytes()
    captured_calls: list[tuple[str, float, int, bool]] = []

    async def fake_stream_bytes(
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict | None = None,
        timeout: float = 10.0,
        max_bytes: int,
        follow_redirects: bool = False,
    ) -> tuple[int, bytes, httpx.Headers]:
        captured_calls.append((url, float(timeout), int(max_bytes), bool(follow_redirects)))
        return 200, pathify_bytes, httpx.Headers({"ETag": 'W/"v1"'})

    monkeypatch.setattr(dbr_mod, "throttled_stream_bytes", fake_stream_bytes)
    monkeypatch.setattr(ba_mod, "throttled_stream_bytes", fake_stream_bytes)

    assert settings.pinpoint_board_request_timeout_seconds == 25.0
    assert settings.pinpoint_board_request_timeout_seconds > 20.0
    assert settings.pinpoint_board_request_timeout_seconds <= settings.search_hard_timeout_seconds

    adapter = PinpointBoardAdapter()
    async with httpx.AsyncClient() as client:
        direct_listings = await probe_pinpoint_board("pathify", client)
        routed_listings = await probe_direct_boards(["pathify"], client, platforms=["pinpointhq"])
        monitor_res = await adapter.check_board(_make_board("pathify", "Pathify"), client)

    assert len(direct_listings) == 4
    assert len(routed_listings) == 4
    assert monitor_res.success is True
    assert len(captured_calls) == 3
    for url, eff_timeout, eff_max_bytes, follow_redir in captured_calls:
        assert url == "https://pathify.pinpointhq.com/postings.json"
        assert eff_timeout == 25.0
        assert eff_max_bytes == settings.pinpoint_board_max_response_bytes
        assert follow_redir is False

    # Configurability: custom pinpoint_board_request_timeout_seconds applies uniformly
    captured_calls.clear()
    monkeypatch.setattr(settings, "pinpoint_board_request_timeout_seconds", 32.0)
    async with httpx.AsyncClient() as client:
        await probe_pinpoint_board("pathify", client)
        await adapter.check_board(_make_board("pathify", "Pathify"), client)
    assert [c[1] for c in captured_calls] == [32.0, 32.0]

    # Search hard-timeout bounding: direct routing caps at search_hard_timeout_seconds; monitoring honors configured/explicit
    captured_calls.clear()
    monkeypatch.setattr(settings, "pinpoint_board_request_timeout_seconds", 120.0)
    monkeypatch.setattr(settings, "search_hard_timeout_seconds", 90)
    async with httpx.AsyncClient() as client:
        await probe_pinpoint_board("pathify", client)
        await adapter.check_board(_make_board("pathify", "Pathify"), client)
        await adapter.check_board(_make_board("pathify", "Pathify"), client, timeout=18.0)
    assert [c[1] for c in captured_calls] == [90.0, 120.0, 18.0]


def test_14_pinpoint_probe_census_manifest_integrity():
    manifest_path = FIXTURE_DIR / "probe_census_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    boards = manifest["boards"]
    assert len(boards) == 24
    parsed_non_empty = [b for b in boards if b["outcome"] == "parsed_non_empty"]
    assert len(parsed_non_empty) == 17
    assert sum(int(b["total_jobs"]) for b in parsed_non_empty) == 558

    by_slug = {b["slug"]: b for b in boards}

    # Sun King & inDrive full-board histograms reconcile exactly to total_jobs
    sunking = by_slug["sunking"]
    assert sunking["total_jobs"] == 183
    assert sum(sunking["job_geography_counts"].values()) == 183
    assert sunking["job_geography_counts"]["Nigeria"] == 36
    assert sunking["job_geography_counts"]["Africa"] == 3
    assert sunking["response_sha256"] is None  # full response SHA was not retained; do not fabricate
    assert sunking["fixture_is_subset"] is True

    indrive = by_slug["indrive"]
    assert indrive["total_jobs"] == 161
    assert sum(indrive["job_geography_counts"].values()) == 161
    assert indrive["job_geography_counts"]["Egypt"] == 9
    assert indrive["job_geography_counts"]["Nigeria"] == 1

    # Overlap & non-additivity check on completely enumerated African-hiring boards
    africa_keys_sk = {
        "Nigeria",
        "Uganda",
        "Kenya",
        "Benin Republic",
        "Tanzania",
        "Zambia",
        "South Africa",
        "Togo",
        "Mozambique",
        "Malawi",
        "Cameroon",
        "Africa",
        "Sierra Leone",
        "Ethiopia",
    }
    africa_keys_in = {"Egypt", "South Africa", "Morocco", "Tunisia", "Nigeria"}
    sk_africa = sum(sunking["job_geography_counts"][k] for k in africa_keys_sk)
    in_africa = sum(indrive["job_geography_counts"][k] for k in africa_keys_in)
    biz_africa = by_slug["bizimply"]["job_geography_counts"]["Egypt"]
    assert sk_africa == 153
    assert in_africa == 17
    assert biz_africa == 1
    assert sk_africa + in_africa + biz_africa == 171

    # Every committed fixture hash recorded in manifest matches file bytes on disk
    for entry in boards:
        fname = entry.get("fixture_file")
        if not fname:
            continue
        actual_sha = hashlib.sha256((FIXTURE_DIR / fname).read_bytes()).hexdigest()
        if entry.get("fixture_is_subset"):
            assert entry["fixture_sha256"] == actual_sha
        else:
            assert entry["response_sha256"] == actual_sha

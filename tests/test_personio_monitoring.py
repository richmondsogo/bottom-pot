"""
Step 49 TDD: Personio Monitoring, Bilingual XML Feed Merge, Conditional ETag Correctness,
Snapshot Completeness, .com/.de Normalization, Direct Routing, and Discovery Registration.

Uses captured real Personio XML fixtures (`tests/fixtures/real/personio/`) and
deterministic `httpx.MockTransport` handlers with isolated `tmp_path` SQLite DBs
(zero live HTTP requests, zero Serper credits, zero writes to operational DB).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from xml.sax.saxutils import escape

import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.ats_url_parser import (
    parse_ats_url,
    parse_personio_board_root_url,
)
from src.project_files.board_adapters import (
    BOARD_ADAPTERS,
    BoardCheckResult,
    PersonioBoardAdapter,
    parse_personio_xml_feed,
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
    probe_personio_board,
)
from src.project_files.models import JobListing
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.url_normalizer import (
    build_url_match_key,
    normalize_job_url,
    url_carries_job_identifier,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "personio"


def _make_board(
    token: str = "montana",
    company_name: str = "Montana",
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
        ats_provider="personio",
        board_token=token,
        board_url=board_url or f"https://{token}.jobs.personio.com",
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


def _pos_xml(
    job_id: str | int = 1001,
    *,
    name: str = "Backend Software Engineer",
    subcompany: str | None = "Acme GmbH",
    office: str | None = "Berlin",
    additional_offices: list[str] | None = None,
    department: str | None = "Engineering",
    recruiting_category: str | None = "Permanent",
    employment_type: str | None = "permanent",
    seniority: str | None = "experienced",
    schedule: str | None = "full-time",
    years_of_experience: str | None = "3-5",
    keywords: str | None = "python,fastapi",
    occupation: str | None = "software_and_web_development",
    occupation_category: str | None = "it_software",
    created_at: str | None = "2026-11-15T10:30:00+00:00",
    descriptions: list[tuple[str, str]] | None = None,
    salary_info: dict[str, str] | None = None,
) -> str:
    parts = ["  <position>"]
    if job_id is not None:
        parts.append(f"    <id>{escape(str(job_id))}</id>")
    if subcompany is not None:
        parts.append(f"    <subcompany>{escape(subcompany)}</subcompany>")
    if office is not None:
        parts.append(f"    <office>{escape(office)}</office>")
    if additional_offices is not None:
        parts.append("    <additionalOffices>")
        for extra in additional_offices:
            parts.append(f"      <office>{escape(extra)}</office>")
        parts.append("    </additionalOffices>")
    if department is not None:
        parts.append(f"    <department>{escape(department)}</department>")
    if recruiting_category is not None:
        parts.append(f"    <recruitingCategory>{escape(recruiting_category)}</recruitingCategory>")
    if name is not None:
        parts.append(f"    <name>{escape(name)}</name>")
    if employment_type is not None:
        parts.append(f"    <employmentType>{escape(employment_type)}</employmentType>")
    if seniority is not None:
        parts.append(f"    <seniority>{escape(seniority)}</seniority>")
    if schedule is not None:
        parts.append(f"    <schedule>{escape(schedule)}</schedule>")
    if years_of_experience is not None:
        parts.append(f"    <yearsOfExperience>{escape(years_of_experience)}</yearsOfExperience>")
    if keywords is not None:
        parts.append(f"    <keywords>{escape(keywords)}</keywords>")
    if occupation is not None:
        parts.append(f"    <occupation>{escape(occupation)}</occupation>")
    if occupation_category is not None:
        parts.append(f"    <occupationCategory>{escape(occupation_category)}</occupationCategory>")
    if created_at is not None:
        parts.append(f"    <createdAt>{escape(created_at)}</createdAt>")
    if salary_info is not None:
        parts.append("    <salaryInformation>")
        for k, v in salary_info.items():
            parts.append(f"      <{k}>{escape(str(v))}</{k}>")
        parts.append("    </salaryInformation>")
    if descriptions is not None:
        parts.append("    <jobDescriptions>")
        for heading, val in descriptions:
            parts.append("      <jobDescription>")
            parts.append(f"        <name>{escape(heading)}</name>")
            parts.append(f"        <value><![CDATA[{val}]]></value>")
            parts.append("      </jobDescription>")
        parts.append("    </jobDescriptions>")
    parts.append("  </position>")
    return "\n".join(parts)


def _feed_xml(positions: list[str]) -> str:
    body = "\n".join(positions)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<workzag-jobs>\n"
        f"{body}\n"
        "</workzag-jobs>\n"
    )


# ---------------------------------------------------------------------------
# 1. Wiring, Registry, and URL Parsing / Normalization
# ---------------------------------------------------------------------------


def test_01_personio_registered_in_monitorable_providers_and_adapters():
    assert "personio" in MONITORABLE_PROVIDERS
    assert "personio" in BOARD_ADAPTERS
    assert isinstance(BOARD_ADAPTERS["personio"], PersonioBoardAdapter)
    assert build_canonical_board_url("personio", "montana") == "https://montana.jobs.personio.com"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://montana.jobs.personio.com", "montana"),
        ("https://montana.jobs.personio.com/", "montana"),
        ("https://montana.jobs.personio.de", "montana"),
        ("https://montana.jobs.personio.de/", "montana"),
        ("https://Montana.jobs.personio.com/?language=en#top", "montana"),
        ("https://adbaker-gmbh.jobs.personio.de/", "adbaker-gmbh"),
    ],
)
def test_02_parse_personio_board_root_url_accepts_com_and_de(url: str, expected: str):
    assert parse_personio_board_root_url(url) == expected


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "http://montana.jobs.personio.com/",
        "https://montana.jobs.personio.com/job/2852393",
        "https://montana.jobs.personio.de/job/2852393-role",
        "https://montana.jobs.personio.com/xml",
        "https://montana.jobs.personio.com/jobs",
        "https://jobs.personio.com",
        "https://jobs.personio.de/",
        "https://www.jobs.personio.com",
        "https://personio.jobs.personio.com",
        "https://test-company.jobs.personio.com",
        "https://careers.jobs.personio.com",
        "https://montana.teamtailor.com/",
        "https://montana.jobs.personio.com.evil.example/",
    ],
)
def test_03_parse_personio_board_root_url_rejects_invalid_and_posting_urls(bad_url: str):
    assert parse_personio_board_root_url(bad_url) is None


def test_04_com_and_de_posting_urls_parse_and_normalize_to_same_canonical_key():
    com_url = "https://montana.jobs.personio.com/job/2852393?utm_source=serper#apply"
    de_url = "http://Montana.jobs.personio.de/job/2852393/"

    p_com = parse_ats_url(com_url)
    p_de = parse_ats_url(de_url)
    assert p_com is not None and p_de is not None
    assert (p_com.ats, p_com.company_slug, p_com.job_id) == ("personio", "montana", "2852393")
    assert (p_de.ats, p_de.company_slug, p_de.job_id) == ("personio", "montana", "2852393")

    assert normalize_job_url(com_url, "personio") == "https://montana.jobs.personio.com/job/2852393"
    assert normalize_job_url(de_url, "personio") == "https://montana.jobs.personio.com/job/2852393"
    assert build_url_match_key(com_url, "personio") == build_url_match_key(de_url, "personio")
    assert url_carries_job_identifier(de_url, "personio") is True
    assert url_carries_job_identifier("https://montana.jobs.personio.de/", "personio") is False


# ---------------------------------------------------------------------------
# 2. Captured Real Fixture Parsing & Adapter Behavior
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_05_real_fixture_montana_bilingual_merge():
    montana_en = (FIXTURE_DIR / "montana_xml_en.xml").read_bytes()
    montana_def = (FIXTURE_DIR / "montana_xml_default.xml").read_bytes()
    requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requested.append(str(req.url))
        if req.url.params.get("language") == "en":
            return httpx.Response(200, content=montana_en, headers={"ETag": '"en-montana"'})
        return httpx.Response(200, content=montana_def, headers={"ETag": '"def-montana"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("montana", "Montana"), client)

    assert requested == [
        "https://montana.jobs.personio.com/xml?language=en",
        "https://montana.jobs.personio.com/xml",
    ]
    assert res.success is True
    assert res.snapshot_complete is True
    assert res.not_modified is False
    assert res.missing_confirmation_threshold == 2
    assert len(res.listings) == 20
    assert all(j.id.startswith("personio:montana:") for j in res.listings)
    assert all(j.description and len(j.description.strip()) > 20 for j in res.listings)

    first = next(j for j in res.listings if j.id == "personio:montana:2863267")
    assert first.company == "MONTANA Energie-Handel GmbH & Co. KG"
    assert "Oberhaching" in (first.location or "")
    assert "Grünwald" in (first.location or "")

    sal_job = next(j for j in res.listings if j.id == "personio:montana:2776122")
    assert sal_job.salary is not None
    assert sal_job.salary.minimum == 42000
    assert sal_job.salary.maximum == 50000
    assert sal_job.salary.currency == "EUR"
    assert sal_job.salary.period == "year"


@pytest.mark.anyio
async def test_06_real_fixture_saeki_en_only_single_get():
    saeki_en = (FIXTURE_DIR / "saeki_xml_en.xml").read_bytes()
    requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requested.append(str(req.url))
        return httpx.Response(200, content=saeki_en, headers={"ETag": '"en-saeki"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("saeki", "SAEKI Robotics"), client)

    assert requested == ["https://saeki.jobs.personio.com/xml?language=en"]
    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 9
    assert all(j.company == "SAEKI Robotics" for j in res.listings)
    assert all(j.description for j in res.listings)


@pytest.mark.anyio
async def test_07_real_fixture_enopai_fills_sparse_without_overwriting_english():
    enopai_en = (FIXTURE_DIR / "enopai_xml_en.xml").read_bytes()
    enopai_def = (FIXTURE_DIR / "enopai_xml_default.xml").read_bytes()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, content=enopai_en, headers={"ETag": '"en-enopai"'})
        return httpx.Response(200, content=enopai_def, headers={"ETag": '"def-enopai"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("enopai", "EnopAI"), client)

    assert res.success is True
    assert res.snapshot_complete is True
    assert len(res.listings) == 4
    assert all(j.id.startswith("personio:enopai:") for j in res.listings)
    assert all(j.description for j in res.listings)


@pytest.mark.anyio
async def test_08_real_fixture_traviangames_empty_xml_is_complete_snapshot():
    empty_xml = (FIXTURE_DIR / "traviangames_xml_empty.xml").read_bytes()
    requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requested.append(str(req.url))
        return httpx.Response(200, content=empty_xml, headers={"ETag": '"empty-tg"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("traviangames", "Travian Games"), client)

    assert requested == ["https://traviangames.jobs.personio.com/xml?language=en"]
    assert res.success is True
    assert res.snapshot_complete is True
    assert res.listings == []


@pytest.mark.anyio
async def test_09_bilingual_merge_prefers_en_fills_default_and_leaves_sparse_none():
    en_xml = _feed_xml([
        _pos_xml(101, name="Platform Engineer", descriptions=[("Role", "<p>English platform description</p>")]),
        _pos_xml(102, name="Sales Manager", descriptions=[]),
        _pos_xml(103, name="Sparse Role", descriptions=None),
    ])
    def_xml = _feed_xml([
        _pos_xml(101, name="Plattform-Ingenieur", descriptions=[("Rolle", "<p>Deutsche Beschreibung darf EN nicht ueberschreiben</p>")]),
        _pos_xml(102, name="Sales Manager", descriptions=[("Aufgaben", "<p>Verantwortung fuer DACH Kunden</p>")]),
        _pos_xml(103, name="Sparse Role", descriptions=[]),
    ])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=en_xml, headers={"ETag": '"en-1"'})
        return httpx.Response(200, text=def_xml, headers={"ETag": '"def-1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("acme-de", "Acme DE"), client)

    assert res.success is True
    assert res.snapshot_complete is True
    by_id = {j.id: j for j in res.listings}
    assert "English platform description" in (by_id["personio:acme-de:101"].description or "")
    assert "Deutsche Beschreibung" not in (by_id["personio:acme-de:101"].description or "")
    assert by_id["personio:acme-de:101"].title == "Platform Engineer"
    assert "Verantwortung fuer DACH Kunden" in (by_id["personio:acme-de:102"].description or "")
    assert by_id["personio:acme-de:103"].description is None


# ---------------------------------------------------------------------------
# 3. XML Parser Fail-Closed Validation & HTTP Error Safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"   \n  ",
        b'<?xml version="1.0"?><!DOCTYPE workzag-jobs [<!ENTITY xxe "pwn">]><workzag-jobs></workzag-jobs>',
        b'<?xml version="1.0"?><workzag-jobs><position><id>1</id><name>A</name></position></workzag-jobs><!-- <!ENTITY late "boom"> -->',
        b"<workzag-jobs><position><id>1</id></workzag-jobs>",  # malformed XML
        b"<rss><channel></channel></rss>",  # wrong root tag
        b'<?xml version="1.0" encoding="utf-8"?><workzag-jobs><position><id>abc</id><name>Dev</name></position></workzag-jobs>',  # non-numeric ID
        b'<?xml version="1.0" encoding="utf-8"?><workzag-jobs><position><id></id><name>Dev</name></position></workzag-jobs>',  # empty ID
        b'<?xml version="1.0" encoding="utf-8"?><workzag-jobs><position><id>12</id><name>   </name></position></workzag-jobs>',  # empty name
        b'<?xml version="1.0" encoding="utf-8"?><workzag-jobs><position><id>12</id><name>A</name></position><position><id>12</id><name>B</name></position></workzag-jobs>',  # duplicate ID
    ],
)
def test_10_parse_personio_xml_feed_rejects_invalid_and_unsafe_payloads(payload: bytes):
    items, err = parse_personio_xml_feed(payload)
    assert items == []
    assert err is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status_code",
    [302, 404, 429, 500, 503],
)
async def test_11_adapter_fails_closed_on_http_error_or_redirect(status_code: int):
    def handler(req: httpx.Request) -> httpx.Response:
        hdrs = {"Location": "https://evil.example/xml"} if status_code == 302 else {}
        return httpx.Response(status_code, headers=hdrs)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("montana"), client)

    assert res.success is False
    assert res.snapshot_complete is False


@pytest.mark.anyio
async def test_12_adapter_fails_closed_on_timeout_and_oversized_response():
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("montana"), client)
    assert res.success is False
    assert res.snapshot_complete is False

    big_xml = _feed_xml([_pos_xml(i, descriptions=[("Role", "<p>" + ("x" * 300) + "</p>")]) for i in range(1, 20)])

    def oversized_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=big_xml)

    async with httpx.AsyncClient(transport=httpx.MockTransport(oversized_handler)) as client:
        res_big = await PersonioBoardAdapter().check_board(_make_board("montana"), client, max_response_bytes=512)
    assert res_big.success is False
    assert res_big.snapshot_complete is False


# ---------------------------------------------------------------------------
# 4. Bilingual ETag / 304 Conditional Request Matrix (All 10 Cases)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_13_conditional_single_language_en_304_short_circuits():
    saeki_en = (FIXTURE_DIR / "saeki_xml_en.xml").read_bytes()
    seen_inm: list[str | None] = []

    def handler_initial(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=saeki_en, headers={"ETag": '"en-saeki-1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_initial)) as client:
        first = await PersonioBoardAdapter().check_board(_make_board("saeki"), client)
    assert first.success and first.etag and not first.not_modified

    board2 = _make_board("saeki", etag=first.etag, content_fingerprint=first.content_fingerprint)

    def handler_304(req: httpx.Request) -> httpx.Response:
        seen_inm.append(req.headers.get("if-none-match"))
        return httpx.Response(304)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_304)) as client:
        second = await PersonioBoardAdapter().check_board(board2, client)

    assert seen_inm == ['"en-saeki-1"']
    assert second.success is True
    assert second.not_modified is True
    assert second.snapshot_complete is True


@pytest.mark.anyio
async def test_14_conditional_bilingual_both_304_short_circuits():
    montana_en = (FIXTURE_DIR / "montana_xml_en.xml").read_bytes()
    montana_def = (FIXTURE_DIR / "montana_xml_default.xml").read_bytes()

    def handler1(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, content=montana_en, headers={"ETag": '"en-m1"'})
        return httpx.Response(200, content=montana_def, headers={"ETag": '"def-m1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler1)) as client:
        first = await PersonioBoardAdapter().check_board(_make_board("montana"), client)

    seen_reqs: list[tuple[str, str | None]] = []

    def handler2(req: httpx.Request) -> httpx.Response:
        seen_reqs.append((str(req.url), req.headers.get("if-none-match")))
        return httpx.Response(304)

    board2 = _make_board("montana", etag=first.etag, content_fingerprint=first.content_fingerprint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler2)) as client:
        second = await PersonioBoardAdapter().check_board(board2, client)

    assert seen_reqs == [
        ("https://montana.jobs.personio.com/xml?language=en", '"en-m1"'),
        ("https://montana.jobs.personio.com/xml", '"def-m1"'),
    ]
    assert second.success is True
    assert second.not_modified is True
    assert second.snapshot_complete is True


@pytest.mark.anyio
async def test_15_conditional_en_304_plus_default_200_updates_merged_jobs():
    en_xml = _feed_xml([_pos_xml(201, name="Product Engineer", descriptions=[])])
    def_v1 = _feed_xml([_pos_xml(201, name="Product Engineer", descriptions=[("Aufgaben", "<p>Alt Text</p>")])])
    def_v2 = _feed_xml([_pos_xml(201, name="Product Engineer", descriptions=[("Aufgaben", "<p>Neu aktualisierte Beschreibung</p>")])])

    def h1(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=en_xml, headers={"ETag": '"en-v1"'})
        return httpx.Response(200, text=def_v1, headers={"ETag": '"def-v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h1)) as client:
        r1 = await PersonioBoardAdapter().check_board(_make_board("montana"), client)
    assert r1.success and len(r1.listings) == 1

    # On poll 2: ?language=en returns 304 when If-None-Match matches, but default /xml changed to 200!
    def h2(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            if req.headers.get("if-none-match") == '"en-v1"':
                return httpx.Response(304)
            return httpx.Response(200, text=en_xml, headers={"ETag": '"en-v1"'})
        assert req.headers.get("if-none-match") == '"def-v1"'
        return httpx.Response(200, text=def_v2, headers={"ETag": '"def-v2"'})

    b2 = _make_board("montana", etag=r1.etag, content_fingerprint=r1.content_fingerprint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(h2)) as client:
        r2 = await PersonioBoardAdapter().check_board(b2, client)

    assert r2.success is True
    assert r2.snapshot_complete is True
    assert r2.not_modified is False
    assert "Neu aktualisierte Beschreibung" in (r2.listings[0].description or "")
    assert r2.content_fingerprint != r1.content_fingerprint
    assert r2.etag != r1.etag


@pytest.mark.anyio
async def test_16_conditional_default_304_plus_en_200_updates_without_failing():
    en_v1 = _feed_xml([
        _pos_xml(301, name="Role One", descriptions=[("About", "<p>EN v1</p>")]),
        _pos_xml(302, name="Role Two", descriptions=[]),
    ])
    en_v2 = _feed_xml([
        _pos_xml(301, name="Role One", descriptions=[("About", "<p>EN v2 updated text</p>")]),
        _pos_xml(302, name="Role Two", descriptions=[]),
    ])
    def_v1 = _feed_xml([
        _pos_xml(301, name="Role One", descriptions=[]),
        _pos_xml(302, name="Role Two", descriptions=[("Rolle", "<p>DE fallback for 302</p>")]),
    ])

    def h1(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=en_v1, headers={"ETag": '"en-301"'})
        return httpx.Response(200, text=def_v1, headers={"ETag": '"def-301"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h1)) as client:
        r1 = await PersonioBoardAdapter().check_board(_make_board("enopai"), client)

    def h2(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            assert req.headers.get("if-none-match") == '"en-301"'
            return httpx.Response(200, text=en_v2, headers={"ETag": '"en-302"'})
        # Conditional check returns 304; unconditional fallback hydration returns 200
        if req.headers.get("if-none-match") == '"def-301"':
            return httpx.Response(304)
        return httpx.Response(200, text=def_v1, headers={"ETag": '"def-301"'})

    b2 = _make_board("enopai", etag=r1.etag, content_fingerprint=r1.content_fingerprint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(h2)) as client:
        r2 = await PersonioBoardAdapter().check_board(b2, client)

    assert r2.success is True
    assert r2.snapshot_complete is True
    assert r2.not_modified is False
    by_id = {j.id: j for j in r2.listings}
    assert "EN v2 updated text" in (by_id["personio:enopai:301"].description or "")
    assert "DE fallback for 302" in (by_id["personio:enopai:302"].description or "")


@pytest.mark.anyio
async def test_17_bilingual_transition_fallback_to_en_only_and_same_fingerprint_short_circuit():
    en_only_xml = _feed_xml([_pos_xml(401, name="Role", descriptions=[("Role", "<p>Complete EN</p>")])])
    calls: list[str] = []

    def h(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(200, text=en_only_xml, headers={"ETag": '"en-new"'})

    # Board previously needed fallback, now EN has all descriptions
    board = _make_board("acme-b", etag='p1:{"en":"\\"old\\"","def":"\\"olddef\\"","fb":1}')
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as client:
        r1 = await PersonioBoardAdapter().check_board(board, client)
    assert calls == ["https://acme-b.jobs.personio.com/xml?language=en"]
    assert r1.success and r1.snapshot_complete

    # Second check: new ETag header, identical XML content fingerprint -> not_modified=True
    board2 = _make_board("acme-b", etag=r1.etag, content_fingerprint=r1.content_fingerprint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as client:
        r2 = await PersonioBoardAdapter().check_board(board2, client)
    assert r2.success is True
    assert r2.not_modified is True
    assert r2.snapshot_complete is True


@pytest.mark.anyio
async def test_18_inconsistent_ids_or_incomplete_fallback_fails_closed():
    en_xml = _feed_xml([
        _pos_xml(1, descriptions=[]),
        _pos_xml(2, descriptions=[("Role", "<p>EN</p>")]),
    ])
    def_mismatched = _feed_xml([
        _pos_xml(1, descriptions=[("Role", "<p>DE 1</p>")]),
        _pos_xml(999, descriptions=[("Role", "<p>DE 999</p>")]),
    ])

    def h_mismatch(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=en_xml)
        return httpx.Response(200, text=def_mismatched)

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_mismatch)) as client:
        r_mis = await PersonioBoardAdapter().check_board(_make_board("montana"), client)
    assert r_mis.success is False
    assert r_mis.snapshot_complete is False

    def h_def_fail(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=en_xml)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_def_fail)) as client:
        r_fail = await PersonioBoardAdapter().check_board(_make_board("montana"), client)
    assert r_fail.success is False
    assert r_fail.snapshot_complete is False

    # Case: fallback was required previously, EN returns 304, Default returns 500 -> fail closed
    board_fb = _make_board("montana", etag='p1:{"en":"\\"e1\\"","def":"\\"d1\\"","fb":1}')

    def h_en304_def500(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(304)
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_en304_def500)) as client:
        r_err = await PersonioBoardAdapter().check_board(board_fb, client)
    assert r_err.success is False
    assert r_err.snapshot_complete is False

    # Case: EN 304, Default 200, then unconditional EN refetch returns 502 -> fail closed
    def h_en304_def200_en502(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            if req.headers.get("if-none-match"):
                return httpx.Response(304)
            return httpx.Response(502)
        return httpx.Response(200, text=def_mismatched)

    async with httpx.AsyncClient(transport=httpx.MockTransport(h_en304_def200_en502)) as client:
        r_refetch_err = await PersonioBoardAdapter().check_board(board_fb, client)
    assert r_refetch_err.success is False
    assert r_refetch_err.snapshot_complete is False


# ---------------------------------------------------------------------------
# 5. Field Normalization, Work Model ADR 0001/0002, Completeness Preservation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_19_field_normalization_employment_salary_location_and_work_model():
    xml = _feed_xml([
        _pos_xml(
            501,
            name="Senior Backend Engineer",
            subcompany=None,
            office="Munich",
            additional_offices=["Berlin", "Munich"],
            department="Platform",
            recruiting_category="Permanent Employee",
            employment_type="permanent",
            schedule="part-time",
            seniority="senior",
            years_of_experience="5-7",
            keywords="python,go",
            occupation="software_and_web_development",
            occupation_category="it_software",
            created_at="2026-10-27T15:59:02+00:00",
            salary_info={"min": "0.00", "max": "0.00", "currencyCode": "EUR", "type": "yearly"},
            descriptions=[("Overview", "<p>Build distributed systems. #LI-Remote</p>")],
        ),
        _pos_xml(
            502,
            name="Operations Coordinator",
            subcompany="Acme Ops GmbH",
            office="Zurich",
            additional_offices=[],
            employment_type="fixed_term",
            schedule="full-time",
            descriptions=[("Tasks", "<p>Coordinate office logistics.</p>")],
        ),
        _pos_xml(
            503,
            name="Working Student Engineering",
            office="Hamburg",
            employment_type="permanent",
            schedule="full-or-part-time",
            descriptions=[("Tasks", "<p>Assist the team in Hamburg.</p>")],
        ),
        _pos_xml(
            504,
            name="Summer Intern",
            office="Remote",
            employment_type="intern",
            schedule="full-time",
            descriptions=[("Tasks", "<p>Summer engineering internship.</p>")],
        ),
    ])

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml, headers={"ETag": '"norm-1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await PersonioBoardAdapter().check_board(_make_board("acme-norm", "Acme Norm"), client)

    assert res.success is True
    assert len(res.listings) == 4
    by_id = {j.id: j for j in res.listings}

    j501 = by_id["personio:acme-norm:501"]
    assert j501.company == "Acme Norm"
    assert j501.employment_type == "part_time"  # schedule=part-time beats permanent
    assert j501.location == "Munich; Berlin"
    assert j501.work_model == "remote"
    assert "#LI-Remote" not in (j501.description or "")
    assert j501.salary is None  # zero salary rejected per ADR 0001
    assert j501.posted_at is not None
    assert j501.posted_at.year == 2026 and j501.posted_at.month == 10 and j501.posted_at.day == 27

    j502 = by_id["personio:acme-norm:502"]
    assert j502.company == "Acme Ops GmbH"
    assert j502.employment_type == "contract"  # fixed_term -> contract
    assert j502.work_model is None  # ADR 0001: unstated stays None

    j503 = by_id["personio:acme-norm:503"]
    assert j503.employment_type is None  # full-or-part-time ambiguous stays None per ADR 0001
    assert j503.work_model is None

    j504 = by_id["personio:acme-norm:504"]
    assert j504.employment_type == "internship"
    assert j504.work_model == "remote"


@pytest.mark.anyio
async def test_20_board_monitor_missing_job_lifecycle_and_completeness_preservation(tmp_path: Path):
    db_file = str(tmp_path / "personio_monitor.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)

    board = reg.register_candidate(company_name="Acme DE", ats_provider="personio", board_token="acme-de")
    assert board is not None and board.monitoring_capability == "supported"

    # Seed richer cached listing (e.g., from HTML JSON-LD before monitor poll)
    rich_cached = JobListing(
        id="personio:acme-de:701",
        provider="personio",
        data_source="scrape",
        title="Software Engineer",
        company="Acme DE",
        location="Munich",
        work_model="hybrid",
        description="Rich cached JSON-LD description retained across sparse XML updates.",
        source_url="https://acme-de.jobs.personio.com/job/701",
        apply_url="https://acme-de.jobs.personio.com/job/701",
        scraped_at=datetime.now(timezone.utc),
        ats_source="personio",
        query_used="serper",
    )
    cache.set_url_cache(rich_cached.source_url, rich_cached)

    # Poll 1: jobs 701 (sparse in both feeds) and 702
    v1_en = _feed_xml([
        _pos_xml(701, name="Software Engineer", office="Munich", descriptions=[]),
        _pos_xml(702, name="DevOps Engineer", office="Berlin", descriptions=[("Role", "<p>K8s</p>")]),
    ])
    v1_def = _feed_xml([
        _pos_xml(701, name="Software Engineer", office="Munich", descriptions=[]),
        _pos_xml(702, name="DevOps Engineer", office="Berlin", descriptions=[]),
    ])

    def h1(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("language") == "en":
            return httpx.Response(200, text=v1_en, headers={"ETag": '"e1"'})
        return httpx.Response(200, text=v1_def, headers={"ETag": '"d1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(h1)) as client:
        r1 = await monitor.check_single_board(board, client)
    assert r1.success is True
    cached_after = cache.get_url_cache("https://acme-de.jobs.personio.com/job/701")
    assert cached_after is not None
    assert cached_after.description == rich_cached.description
    assert cached_after.work_model == "hybrid"

    # Poll 2: incomplete error must NOT close or increment missing counter for 702
    def h_err(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    board = reg.get_board("personio", "acme-de")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(h_err)) as client:
        r_err = await monitor.check_single_board(board, client)
    assert r_err.success is False and r_err.snapshot_complete is False

    def _status_and_missing(job_id: str) -> tuple[str, int]:
        with sqlite3.connect(db_file) as c:
            row = c.execute(
                "SELECT status, missing_confirmation_count FROM monitored_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        assert row is not None
        return row[0], row[1]

    assert _status_and_missing("personio:acme-de:702") == ("active", 0)

    # Poll 3: complete snapshot missing 702 -> confirmation 1 (still active!)
    v2_en = _feed_xml([_pos_xml(701, name="Software Engineer", office="Munich", descriptions=[("Role", "<p>Now filled</p>")])])

    def h_miss1(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=v2_en, headers={"ETag": '"e2"'})

    board = reg.get_board("personio", "acme-de")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(h_miss1)) as client:
        await monitor.check_single_board(board, client)
    assert _status_and_missing("personio:acme-de:702") == ("active", 1)

    # Poll 4: valid empty XML (<workzag-jobs></workzag-jobs>) -> confirmation 2 -> 702 closes, 701 confirmation 1!
    empty_xml = (FIXTURE_DIR / "traviangames_xml_empty.xml").read_bytes()

    def h_empty(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=empty_xml, headers={"ETag": '"e3"'})

    board = reg.get_board("personio", "acme-de")
    assert board is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(h_empty)) as client:
        await monitor.check_single_board(board, client)
    assert _status_and_missing("personio:acme-de:702") == ("closed", 2)
    assert _status_and_missing("personio:acme-de:701") == ("active", 1)


# ---------------------------------------------------------------------------
# 6. Pre-existing Row Auto-Promotion, .com/.de Dedup, Direct Router, Discovery, Enricher
# ---------------------------------------------------------------------------


def test_21_ensure_db_auto_promotes_preexisting_unsupported_montana_row(tmp_path: Path):
    db_file = str(tmp_path / "legacy_montana.sqlite")
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE company_boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                company_slug TEXT NOT NULL,
                ats_provider TEXT NOT NULL,
                board_token TEXT NOT NULL,
                board_url TEXT NOT NULL,
                discovery_source TEXT NOT NULL,
                source_posting_url TEXT,
                first_discovered_at REAL NOT NULL,
                last_discovered_at REAL NOT NULL,
                verification_status TEXT NOT NULL DEFAULT 'candidate',
                monitoring_capability TEXT NOT NULL DEFAULT 'unsupported',
                last_successful_check REAL,
                next_scheduled_check REAL,
                failure_count INTEGER NOT NULL DEFAULT 0,
                polling_priority INTEGER NOT NULL DEFAULT 1,
                etag TEXT,
                last_modified TEXT,
                content_fingerprint TEXT,
                active_job_count INTEGER DEFAULT 0,
                UNIQUE(ats_provider, board_token)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO company_boards (
                company_name, company_slug, ats_provider, board_token, board_url,
                discovery_source, first_discovered_at, last_discovered_at,
                verification_status, monitoring_capability
            ) VALUES (
                'Montana', 'montana', 'personio', 'montana', 'https://montana.jobs.personio.de',
                'search', 100.0, 100.0, 'candidate', 'unsupported'
            )
            """
        )
        conn.commit()

    reg = CompanyBoardRegistry(db_path=db_file)
    promoted = reg.get_board("personio", "montana")
    assert promoted is not None
    assert promoted.monitoring_capability == "supported"
    due = reg.get_due_monitoring_boards(limit=10)
    assert any(b.ats_provider == "personio" and b.board_token == "montana" for b in due)

    # Re-registering via .com or .de does not create a second board row
    reg.register_candidate(ats_provider="personio", board_token="montana", board_url="https://montana.jobs.personio.com")
    reg.register_candidate(ats_provider="personio", board_token="montana", board_url="https://montana.jobs.personio.de")
    with sqlite3.connect(db_file) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM company_boards WHERE ats_provider='personio' AND board_token='montana'"
        ).fetchone()[0]
    assert count == 1


@pytest.mark.anyio
async def test_22_direct_board_router_probes_personio():
    montana_en = (FIXTURE_DIR / "montana_xml_en.xml").read_bytes()
    montana_def = (FIXTURE_DIR / "montana_xml_default.xml").read_bytes()
    seen_urls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_urls.append(str(req.url))
        if req.url.host == "montana.jobs.personio.com":
            if req.url.params.get("language") == "en":
                return httpx.Response(200, content=montana_en)
            return httpx.Response(200, content=montana_def)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        direct = await probe_personio_board("montana", client)
        missing = await probe_personio_board("nonexistent-co", client)
        invalid = await probe_personio_board("personio", client)
        routed = await probe_direct_boards(["montana"], client, platforms=["personio"])

    assert len(direct) == 20
    assert all(j.id.startswith("personio:montana:") for j in direct)
    assert missing == []
    assert invalid == []
    assert len(routed) == 20
    assert "https://montana.jobs.personio.com/xml?language=en" in seen_urls


@pytest.mark.anyio
async def test_23_search_pipeline_registers_personio_board_root_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import src.project_files.search_pipeline as sp_mod

    db_file = str(tmp_path / "pipeline_personio.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monkeypatch.setattr(sp_mod, "company_board_registry", reg)
    monkeypatch.setattr(sp_mod, "cache_store", cache)

    orch = SearchOrchestrator()
    item = {"link": "https://enopai.jobs.personio.de/", "title": "Jobs at EnopAI", "snippet": ""}

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        res = await orch._enrich_ats_item("personio", item, "python", client)

    assert res is None
    board = reg.get_board("personio", "enopai")
    assert board is not None
    assert board.monitoring_capability == "supported"
    assert board.board_url == "https://enopai.jobs.personio.com"


@pytest.mark.anyio
async def test_24_ats_page_enricher_handles_both_personio_com_and_de_html():
    html = """
    <html><head>
      <title>Senior Python Dev | Jobs at Work for Montana</title>
      <meta property="og:title" content="Senior Python Dev | Jobs at Work for Montana" />
    </head><body>
      <h1>Senior Python Dev</h1>
      <script>window.__DATA__ = {"main_office": "Munich", "schedule": "full-time", "department": "Engineering"};</script>
      <p>Build scalable backend services in Python for energy trading.</p>
    </body></html>
    """

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        listing, outcome = await enrich_ats_page_result(
            url="https://montana.jobs.personio.de/job/2852393",
            provider="personio",
            search_title="Senior Python Dev",
            snippet="",
            query_used="python",
            client=client,
        )

    assert listing is not None
    assert listing.location == "Munich"
    assert listing.employment_type == "full_time"

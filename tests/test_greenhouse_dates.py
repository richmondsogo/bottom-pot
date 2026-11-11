import datetime
import httpx
import pytest
from datetime import timezone

from src.project_files.board_adapters import GreenhouseBoardAdapter
from src.project_files.company_board_registry import CompanyBoard, CompanyBoardRegistry
from src.project_files.search_pipeline import SearchOrchestrator, SearchParams


@pytest.mark.anyio
async def test_greenhouse_first_published_vs_updated_at_in_adapter():
    """Verify GreenhouseBoardAdapter uses first_published as raw_date/posted_at,

    and does NOT fall back to updated_at.
    """
    adapter = GreenhouseBoardAdapter()
    board = CompanyBoard(
        id=1,
        company_name="Acme",
        company_slug="acme",
        ats_provider="greenhouse",
        board_token="acme",
        board_url="https://boards.greenhouse.io/acme",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    gh_payload = {
        "jobs": [
            # Job 1: updated_at is recent, but first_published is 60 days ago
            {
                "id": 101,
                "title": "Staff Distributed Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-10T12:00:00Z",
                "first_published": "2026-09-01T00:00:00Z",
                "content": "<p>Long-running posting with recent copy edit.</p>",
            },
            # Job 2: first_published is absent entirely
            {
                "id": 102,
                "title": "Platform Reliability Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-10T12:00:00Z",
                "content": "<p>Posting with unknown original publication date.</p>",
            },
        ]
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gh_payload))) as client:
        res = await adapter.check_board(board, client)

    assert res.success is True
    assert len(res.listings) == 2

    job1 = next(j for j in res.listings if j.id.endswith("101"))
    job2 = next(j for j in res.listings if j.id.endswith("102"))

    # Job 1 posted_at must reflect first_published, NOT updated_at
    assert job1.posted_at is not None
    assert job1.posted_at.year == 2026
    assert job1.posted_at.month == 9
    assert job1.posted_at.day == 1

    # Job 2 posted_at must be None because authoritative first_published was absent
    assert job2.posted_at is None


@pytest.mark.anyio
async def test_greenhouse_individual_job_endpoint_lookup():
    """Verify get_job_detail queries /v1/boards/{token}/jobs/{id} for authoritative first_published."""
    adapter = GreenhouseBoardAdapter()
    board = CompanyBoard(
        id=2,
        company_name="Acme",
        company_slug="acme",
        ats_provider="greenhouse",
        board_token="acme",
        board_url="https://boards.greenhouse.io/acme",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    detail_payload = {
        "id": 201,
        "title": "Security Engineer",
        "first_published": "2026-08-15T10:00:00Z",
        "updated_at": "2026-11-10T12:00:00Z",
    }

    def handler(req: httpx.Request):
        if "/jobs/201" in str(req.url):
            return httpx.Response(200, json=detail_payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        detail = await adapter.get_job_detail("acme", 201, client)

    assert detail is not None
    assert detail.get("first_published") == "2026-08-15T10:00:00Z"


@pytest.mark.anyio
async def test_greenhouse_recent_updated_but_old_first_published_excluded_from_recent_search(tmp_path, monkeypatch):
    """Regression test: job with recent updated_at but old first_published must NOT appear

    in a recent-posting search (e.g. posted_within_days=7).
    """
    db_file = str(tmp_path / "gh_date_test.sqlite")
    monkeypatch.setattr("src.config.settings.sqlite_db_path", db_file)
    monkeypatch.setattr("src.config.settings.serper_api_key", "")
    monkeypatch.setattr("src.config.settings.serper_mode", "cache_only")

    registry = CompanyBoardRegistry(db_path=db_file)
    adapter = GreenhouseBoardAdapter()

    board = CompanyBoard(
        id=1,
        company_name="Acme",
        company_slug="acme",
        ats_provider="greenhouse",
        board_token="acme",
        board_url="https://boards.greenhouse.io/acme",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    gh_payload = {
        "jobs": [
            {
                "id": 301,
                "title": "Principal Architect",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/301",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-10T12:00:00Z",  # Recent edit (today)
                "first_published": "2026-01-15T00:00:00Z",  # Old publication date
                "content": "<p>Architectural leadership role.</p>",
            },
            {
                "id": 302,
                "title": "Junior Architect",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/302",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-10T12:00:00Z",  # Recent edit (today)
                # first_published absent
                "content": "<p>Junior role with unverified publication date.</p>",
            },
        ]
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gh_payload))) as client:
        res = await adapter.check_board(board, client)

    for listing in res.listings:
        registry.upsert_monitored_job(listing)

    # Search with posted_within_days=7
    recent_matches = registry.search_monitored_jobs(query="Architect", posted_within_days=7)
    assert len(recent_matches) == 0, f"Expected 0 recent jobs, got {len(recent_matches)}: {[j.title for j in recent_matches]}"

    # Unfiltered search finds both jobs
    all_matches = registry.search_monitored_jobs(query="Architect", posted_within_days=None)
    assert len(all_matches) == 2

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


@pytest.mark.anyio
async def test_greenhouse_production_monitor_fetches_first_published_via_single_board(tmp_path, monkeypatch):
    """Integration test: BoardMonitor.check_single_board() must obtain first_published

    from the individual-job endpoint for newly discovered jobs when absent from list response,
    and persist the authoritative date to SQLite.
    """
    from src.project_files.board_monitor import BoardMonitor

    db_file = str(tmp_path / "gh_monitor_date_test.sqlite")
    monkeypatch.setattr("src.config.settings.sqlite_db_path", db_file)
    monkeypatch.setattr("src.config.settings.serper_api_key", "")
    monkeypatch.setattr("src.config.settings.serper_mode", "cache_only")

    registry = CompanyBoardRegistry(db_path=db_file)
    monitor = BoardMonitor(registry=registry)

    board = registry.register_candidate(
        company_name="Acme",
        ats_provider="greenhouse",
        board_token="acme",
        source_url="https://boards.greenhouse.io/acme",
    )
    assert board is not None

    gh_list_payload = {
        "jobs": [
            {
                "id": 401,
                "title": "Principal Distributed Architect",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/401",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-10T12:00:00Z",  # Recent edit (today)
                # first_published absent from list response
                "content": "<p>Core infrastructure systems role.</p>",
            }
        ]
    }

    gh_detail_payload = {
        "id": 401,
        "title": "Principal Distributed Architect",
        "first_published": "2026-08-01T00:00:00Z",  # 3 months ago
        "updated_at": "2026-11-10T12:00:00Z",
    }

    detail_calls = []

    def handler(req: httpx.Request):
        url_str = str(req.url)
        if "/jobs/401" in url_str:
            detail_calls.append(url_str)
            return httpx.Response(200, json=gh_detail_payload)
        if "/jobs?content=true" in url_str:
            return httpx.Response(200, json=gh_list_payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await monitor.check_single_board(board, client)

    assert res.success is True
    assert len(detail_calls) == 1, f"Expected 1 individual detail call, got {len(detail_calls)}"

    # Check persisted job in SQLite
    persisted = registry.get_monitored_job("greenhouse:acme:401")
    assert persisted is not None
    assert persisted.posted_at is not None
    assert persisted.posted_at.year == 2026
    assert persisted.posted_at.month == 8
    assert persisted.posted_at.day == 1

    # Recent search must exclude this job because its first_published is old
    recent_matches = registry.search_monitored_jobs(query="Architect", posted_within_days=7)
    assert len(recent_matches) == 0, f"Expected 0 recent matches, got {len(recent_matches)}"

    # Unfiltered search finds the job
    all_matches = registry.search_monitored_jobs(query="Architect", posted_within_days=None)
    assert len(all_matches) == 1


@pytest.mark.anyio
async def test_greenhouse_production_monitor_avoids_repeated_detail_lookups_for_known_dates(tmp_path, monkeypatch):
    """Verify subsequent board checks do NOT re-query individual detail endpoints for jobs

    whose authoritative publication dates are already stored in the database, even if content changes.
    """
    from src.project_files.board_monitor import BoardMonitor

    db_file = str(tmp_path / "gh_monitor_dedup_lookups.sqlite")
    monkeypatch.setattr("src.config.settings.sqlite_db_path", db_file)
    monkeypatch.setattr("src.config.settings.serper_api_key", "")
    monkeypatch.setattr("src.config.settings.serper_mode", "cache_only")

    registry = CompanyBoardRegistry(db_path=db_file)
    monitor = BoardMonitor(registry=registry)

    board = registry.register_candidate(
        company_name="Acme",
        ats_provider="greenhouse",
        board_token="acme",
        source_url="https://boards.greenhouse.io/acme",
    )
    assert board is not None

    gh_list_payload_1 = {
        "jobs": [
            {
                "id": 501,
                "title": "Senior Reliability Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/501",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-01T12:00:00Z",
                "content": "<p>Initial description</p>",
            }
        ]
    }

    gh_detail_payload = {
        "id": 501,
        "title": "Senior Reliability Engineer",
        "first_published": "2026-07-15T00:00:00Z",
        "updated_at": "2026-11-01T12:00:00Z",
    }

    detail_calls = []

    def handler_1(req: httpx.Request):
        url_str = str(req.url)
        if "/jobs/501" in url_str:
            detail_calls.append(url_str)
            return httpx.Response(200, json=gh_detail_payload)
        if "/jobs?content=true" in url_str:
            return httpx.Response(200, json=gh_list_payload_1)
        return httpx.Response(404)

    # 1. First poll: newly discovered job triggers detail lookup
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_1)) as client:
        res1 = await monitor.check_single_board(board, client)

    assert res1.success is True
    assert len(detail_calls) == 1

    job1 = registry.get_monitored_job("greenhouse:acme:501")
    assert job1 is not None
    assert job1.posted_at is not None
    assert job1.posted_at.month == 7

    # 2. Second poll: job description or title is edited (new updated_at -> fingerprint changes)
    # But first_published is already known in the database!
    gh_list_payload_2 = {
        "jobs": [
            {
                "id": 501,
                "title": "Lead Reliability Engineer",  # Title updated
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/501",
                "location": {"name": "Remote"},
                "updated_at": "2026-11-11T12:00:00Z",  # New update date
                "content": "<p>Updated description with new team details</p>",
            }
        ]
    }

    def handler_2(req: httpx.Request):
        url_str = str(req.url)
        if "/jobs/501" in url_str:
            detail_calls.append(url_str)
            return httpx.Response(200, json=gh_detail_payload)
        if "/jobs?content=true" in url_str:
            return httpx.Response(200, json=gh_list_payload_2)
        return httpx.Response(404)

    # Fetch updated board record
    board_refreshed = registry.get_board("greenhouse", "acme")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_2)) as client:
        res2 = await monitor.check_single_board(board_refreshed, client)

    assert res2.success is True
    # The detail endpoint should NOT have been called again!
    assert len(detail_calls) == 1, f"Expected detail_calls to stay 1, but got {len(detail_calls)}"

    # The updated job must still preserve its known publication date
    job2 = registry.get_monitored_job("greenhouse:acme:501")
    assert job2 is not None
    assert job2.title == "Lead Reliability Engineer"
    assert job2.posted_at is not None
    assert job2.posted_at.month == 7


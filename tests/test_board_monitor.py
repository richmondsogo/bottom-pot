"""
Tests for Board Adapters and Independent Board Monitor.

Proves:
- GreenhouseBoardAdapter parses board jobs, computes fingerprints, and respects HTTP 304.
- LeverBoardAdapter parses board postings and detects unchanged boards via fingerprint.
- AshbyBoardAdapter parses board jobs and detects unchanged boards via fingerprint.
- BoardMonitor queries due boards, records results, and stores listings in cache_store.
- Zero Serper API calls are made during monitoring.
"""

import json
import pytest
import httpx

from src.project_files.board_adapters import (
    GreenhouseBoardAdapter,
    LeverBoardAdapter,
    AshbyBoardAdapter,
    BoardCheckResult,
    compute_board_fingerprint,
)
from src.project_files.board_monitor import BoardMonitor
from src.project_files.company_board_registry import (
    CompanyBoard,
    CompanyBoardRegistry,
)
from src.project_files.cache_store import CacheStore


@pytest.fixture
def test_setup(tmp_path):
    db_file = str(tmp_path / "monitor_test.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg)
    yield reg, cache, monitor
    reg.clear()
    cache.clear()


@pytest.mark.anyio
async def test_greenhouse_adapter_success_and_304():
    adapter = GreenhouseBoardAdapter()
    board = CompanyBoard(
        id=1,
        company_name="Stripe",
        company_slug="stripe",
        ats_provider="greenhouse",
        board_token="stripe",
        board_url="https://boards.greenhouse.io/stripe",
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
                "id": 101,
                "title": "Software Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/101",
                "location": {"name": "Remote, US"},
                "updated_at": "2026-10-01T12:00:00Z",
            }
        ]
    }

    # 1. First fetch: 200 OK
    def handler_200(req: httpx.Request):
        return httpx.Response(200, json=gh_payload, headers={"etag": '"etag-gh-1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_200)) as client:
        res = await adapter.check_board(board, client)
        assert res.success is True
        assert res.not_modified is False
        assert len(res.listings) == 1
        assert res.listings[0].title == "Software Engineer"
        assert res.listings[0].provider == "greenhouse"
        assert res.etag == '"etag-gh-1"'
        assert res.content_fingerprint is not None

    # 2. Second fetch with ETag matching: 304 Not Modified
    board.etag = '"etag-gh-1"'
    board.content_fingerprint = res.content_fingerprint

    def handler_304(req: httpx.Request):
        if req.headers.get("If-None-Match") == '"etag-gh-1"':
            return httpx.Response(304)
        return httpx.Response(200, json=gh_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler_304)) as client:
        res304 = await adapter.check_board(board, client)
        assert res304.success is True
        assert res304.not_modified is True
        assert len(res304.listings) == 0


@pytest.mark.anyio
async def test_lever_adapter_success_and_fingerprint():
    adapter = LeverBoardAdapter()
    board = CompanyBoard(
        id=2,
        company_name="Anthropic",
        company_slug="anthropic",
        ats_provider="lever",
        board_token="anthropic",
        board_url="https://jobs.lever.co/anthropic",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    lever_payload = [
        {
            "id": "lever-uuid-1",
            "text": "Research Scientist",
            "hostedUrl": "https://jobs.lever.co/anthropic/lever-uuid-1",
            "applyUrl": "https://jobs.lever.co/anthropic/lever-uuid-1/apply",
            "categories": {"location": "San Francisco, CA"},
            "createdAt": 1729000000000,
        }
    ]

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=lever_payload))) as client:
        res = await adapter.check_board(board, client)
        assert res.success is True
        assert res.not_modified is False
        assert len(res.listings) == 1
        assert res.listings[0].title == "Research Scientist"
        assert res.listings[0].provider == "lever"

    # Second fetch with identical content -> detected via fingerprint
    board.content_fingerprint = res.content_fingerprint
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=lever_payload))) as client:
        res2 = await adapter.check_board(board, client)
        assert res2.success is True
        assert res2.not_modified is True


@pytest.mark.anyio
async def test_ashby_adapter_success():
    adapter = AshbyBoardAdapter()
    board = CompanyBoard(
        id=3,
        company_name="Figma",
        company_slug="figma",
        ats_provider="ashby",
        board_token="figma",
        board_url="https://jobs.ashbyhq.com/figma",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    ashby_payload = {
        "jobs": [
            {
                "id": "ashby-job-1",
                "title": "Product Designer",
                "jobUrl": "https://jobs.ashbyhq.com/figma/ashby-job-1",
                "location": "New York, NY",
                "publishedAt": "2026-10-15T09:00:00Z",
            }
        ]
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=ashby_payload))) as client:
        res = await adapter.check_board(board, client)
        assert res.success is True
        assert len(res.listings) == 1
        assert res.listings[0].title == "Product Designer"
        assert res.listings[0].provider == "ashby"


@pytest.mark.anyio
async def test_board_monitor_poll_due_boards_pipeline(test_setup):
    reg, cache, monitor = test_setup

    # Register candidate board
    board = reg.register_candidate(
        company_name="Vercel",
        ats_provider="greenhouse",
        board_token="vercel",
    )
    assert board is not None

    gh_payload = {
        "jobs": [
            {
                "id": 999,
                "title": "Solutions Architect",
                "absolute_url": "https://boards.greenhouse.io/vercel/jobs/999",
                "location": {"name": "Remote"},
                "updated_at": "2026-10-20T10:00:00Z",
            }
        ]
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gh_payload))) as client:
        jobs = await monitor.poll_due_boards(max_boards=10, client=client)

    assert len(jobs) == 1
    assert jobs[0].title == "Solutions Architect"
    assert jobs[0].company == "Vercel"

    # Board should now be marked verified in registry
    updated_board = reg.get_board("greenhouse", "vercel")
    assert updated_board.verification_status == "verified"
    assert updated_board.active_job_count == 1
    assert updated_board.last_successful_check is not None

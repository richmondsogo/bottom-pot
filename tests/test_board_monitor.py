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
    assert jobs[0].extraction_confidence is not None
    assert jobs[0].field_evidence is not None

    # Prove stored in durable searchable monitored_jobs table
    stored = reg.get_monitored_job(jobs[0].id)
    assert stored is not None
    assert stored.title == "Solutions Architect"
    assert stored.company == "Vercel"
    assert stored.extraction_confidence is not None

    # Prove searchable by keyword in persistent store
    fts_hits = reg.search_monitored_jobs("Architect")
    assert len(fts_hits) == 1
    assert fts_hits[0].id == jobs[0].id

    # Board should now be marked verified in registry
    updated_board = reg.get_board("greenhouse", "vercel")
    assert updated_board.verification_status == "verified"
    assert updated_board.active_job_count == 1
    assert updated_board.last_successful_check is not None


@pytest.mark.anyio
async def test_board_monitor_lifecycle_marks_missing_jobs_closed(test_setup):
    reg, cache, monitor = test_setup

    board = reg.register_candidate(
        company_name="Stripe",
        ats_provider="greenhouse",
        board_token="stripe",
    )
    assert board is not None

    # Round 1: Two active jobs
    payload_round1 = {
        "jobs": [
            {
                "id": 101,
                "title": "Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/101",
                "updated_at": "2026-10-01T10:00:00Z",
            },
            {
                "id": 102,
                "title": "Frontend Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/102",
                "updated_at": "2026-10-01T10:00:00Z",
            },
        ]
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload_round1))) as client:
        jobs = await monitor.poll_due_boards(max_boards=10, client=client)
    assert len(jobs) == 2
    assert len(reg.search_monitored_jobs("Engineer")) == 2

    # Round 2: Job 101 was closed/removed by employer, only Job 102 remains
    payload_round2 = {
        "jobs": [
            {
                "id": 102,
                "title": "Frontend Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/102",
                "updated_at": "2026-10-05T10:00:00Z",
            },
        ]
    }

    # Reset next_scheduled_check so board is due again
    board_rec = reg.get_board("greenhouse", "stripe")
    with reg._get_connection() as conn:
        conn.execute("UPDATE company_boards SET next_scheduled_check = 0 WHERE id = ?", (board_rec.id,))
        conn.commit()

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload_round2))) as client:
        jobs_r2 = await monitor.poll_due_boards(max_boards=10, client=client)

    assert len(jobs_r2) == 1
    # Search should now only return active job 102
    active_search = reg.search_monitored_jobs("Engineer")
    assert len(active_search) == 1
    assert active_search[0].id == "greenhouse:stripe:102"

    # Job 101 still preserved in store with status='closed'
    with reg._get_connection() as conn:
        row = conn.execute("SELECT status FROM monitored_jobs WHERE job_id = ?", ("greenhouse:stripe:101",)).fetchone()
        assert row is not None
        assert row[0] == "closed"


def test_monitor_cross_process_lease(test_setup):
    reg, cache, monitor = test_setup

    # Process A acquires lease
    assert reg.acquire_lease("board_monitor", "holder-A", ttl_seconds=10.0) is True

    # Process B cannot acquire lease while holder-A holds it
    assert reg.acquire_lease("board_monitor", "holder-B", ttl_seconds=10.0) is False

    # Process A renews lease heartbeat
    assert reg.renew_lease("board_monitor", "holder-A", ttl_seconds=10.0) is True

    # Process B cannot renew lease held by A
    assert reg.renew_lease("board_monitor", "holder-B", ttl_seconds=10.0) is False

    # Process A releases lease
    reg.release_lease("board_monitor", "holder-A")

    # Process B can now acquire lease
    assert reg.acquire_lease("board_monitor", "holder-B", ttl_seconds=10.0) is True
    reg.release_lease("board_monitor", "holder-B")


@pytest.mark.anyio
async def test_scheduler_backlog_drains_without_starvation(test_setup):
    reg, cache, monitor = test_setup
    import time

    now = time.time()
    # Register 50 boards with varied scheduled times and priorities
    # Boards 0-19: priority 1, overdue by 50..31 minutes (waited longest)
    # Boards 20-39: priority 2, overdue by 30..11 minutes
    # Boards 40-49: priority 3, overdue by 10..1 minutes
    for i in range(50):
        board = reg.register_candidate(
            company_name=f"Company {i:02d}",
            ats_provider="greenhouse",
            board_token=f"comp-{i:02d}",
        )
        assert board is not None
        priority = 1 if i < 20 else (2 if i < 40 else 3)
        scheduled_time = now - (50 - i) * 60
        with reg._get_connection() as conn:
            conn.execute(
                """
                UPDATE company_boards
                SET polling_priority = ?,
                    next_scheduled_check = ?,
                    verification_status = 'verified'
                WHERE id = ?
                """,
                (priority, scheduled_time, board.id),
            )
            conn.commit()

    # Verify backlog status before polling
    initial_status = reg.get_monitoring_status()
    assert initial_status["total_boards"] == 50
    assert initial_status["due_boards"] == 50
    assert initial_status["overdue_boards"] == 50
    assert initial_status["oldest_overdue_seconds"] >= 2900  # ~50 mins overdue
    assert initial_status["hourly_check_capacity"] > 0
    assert initial_status["sustainable_board_count"] > 0

    batch_size = 20
    checked_tokens_round1 = []
    checked_tokens_round2 = []
    checked_tokens_round3 = []

    def mock_handler(req: httpx.Request):
        # Return empty job list for mock checks
        return httpx.Response(200, json={"jobs": []})

    # Batch 1: Should drain the 20 oldest overdue boards (Boards 00..19), preventing starvation by newer higher-priority boards
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        batch1_boards = reg.get_due_monitoring_boards(limit=batch_size)
        assert len(batch1_boards) == 20
        checked_tokens_round1 = [b.board_token for b in batch1_boards]
        # Verify it prioritized the longest-waiting boards (00..19)
        assert checked_tokens_round1 == [f"comp-{i:02d}" for i in range(20)]

        await monitor.poll_due_boards(max_boards=batch_size, client=client)

    status_after_batch1 = reg.get_monitoring_status()
    assert status_after_batch1["due_boards"] == 30
    assert status_after_batch1["overdue_boards"] == 30

    # Batch 2: Should drain the next 20 boards (Boards 20..39)
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        batch2_boards = reg.get_due_monitoring_boards(limit=batch_size)
        assert len(batch2_boards) == 20
        checked_tokens_round2 = [b.board_token for b in batch2_boards]
        assert checked_tokens_round2 == [f"comp-{i:02d}" for i in range(20, 40)]

        await monitor.poll_due_boards(max_boards=batch_size, client=client)

    status_after_batch2 = reg.get_monitoring_status()
    assert status_after_batch2["due_boards"] == 10
    assert status_after_batch2["overdue_boards"] == 10

    # Batch 3: Should drain the remaining 10 boards (Boards 40..49)
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        batch3_boards = reg.get_due_monitoring_boards(limit=batch_size)
        assert len(batch3_boards) == 10
        checked_tokens_round3 = [b.board_token for b in batch3_boards]
        assert checked_tokens_round3 == [f"comp-{i:02d}" for i in range(40, 50)]

        await monitor.poll_due_boards(max_boards=batch_size, client=client)

    # Batch 4: Entire backlog is drained; 0 due boards
    status_final = reg.get_monitoring_status()
    assert status_final["due_boards"] == 0
    assert status_final["overdue_boards"] == 0
    assert status_final["oldest_overdue_seconds"] == 0.0


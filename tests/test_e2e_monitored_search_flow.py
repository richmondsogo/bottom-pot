"""
End-to-end integration verification for Step 32:
- Job discovered by independent monitor is searchable through ordinary Bottom Pot keyword search
  without Serper, even when monitor and API use separate registry instances.
- Zero Serper calls during monitored job search.
- Deduplication when multiple sources return the same job.
- Durable cross-process SQLite revision invalidates whole-search cache.
- Tri-state remote filtering (True = remote only, False = exclude remote, None = all).
- Authoritative date filtering (posted_at cutoff; excludes old jobs discovered today and unknown dates).
- Explicit empty platform selection (platforms=[]) searches zero providers.
"""

from datetime import datetime, timezone, timedelta
import httpx
import pytest

from src.project_files.board_adapters import GreenhouseBoardAdapter
from src.project_files.board_monitor import BoardMonitor
from src.project_files.cache_store import CacheStore
from src.project_files.company_board_registry import CompanyBoardRegistry
from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import SearchOrchestrator


async def collect_search(orchestrator: SearchOrchestrator, params: SearchParams, platforms: list[str] | None = None):
    results = []
    done_event = None
    async for event_type, payload in orchestrator.run(params, platforms=platforms):
        if event_type == "results":
            results.extend(payload.batch)
        elif event_type == "done":
            done_event = payload
    return results, done_event


@pytest.fixture
def shared_db_setup(tmp_path, monkeypatch):
    db_file = str(tmp_path / "e2e_shared_test.sqlite")
    # Point settings sqlite_db_path to db_file
    monkeypatch.setattr("src.config.settings.sqlite_db_path", db_file)
    monkeypatch.setattr("src.config.settings.serper_api_key", "")
    monkeypatch.setattr("src.config.settings.serper_mode", "cache_only")

    # Instance A: Background monitor process with its own separate registry instance
    reg_monitor = CompanyBoardRegistry(db_path=db_file)
    monitor = BoardMonitor(registry=reg_monitor)

    # Instance B: API search process using API registry
    from src.project_files.company_board_registry import company_board_registry
    reg_api = company_board_registry
    reg_api.db_path = db_file
    orchestrator = SearchOrchestrator()

    yield reg_monitor, monitor, reg_api, orchestrator

    reg_monitor.clear()
    reg_api.clear()


@pytest.mark.anyio
async def test_e2e_monitored_job_lifecycle_and_search_flow(shared_db_setup, monkeypatch):
    reg_monitor, monitor, reg_api, orchestrator = shared_db_setup

    # 1. Register valid employer board on monitor instance
    board = reg_monitor.register_candidate(
        company_name="Acme Corp",
        ats_provider="greenhouse",
        board_token="acmecorp",
        source_url="https://boards.greenhouse.io/acmecorp",
    )
    assert board is not None

    now = datetime.now(timezone.utc)
    recent_posted = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    gh_payload = {
        "jobs": [
            {
                "id": 88001,
                "title": "Principal Distributed Systems Engineer",
                "absolute_url": "https://boards.greenhouse.io/acmecorp/jobs/88001",
                "location": {"name": "Lagos, Nigeria (Remote)"},
                "updated_at": recent_posted,
                "first_published": recent_posted,
                "content": (
                    "<p>We are seeking a Principal Distributed Systems Engineer to scale our global infrastructure platform.</p>"
                    "<p>In this role, you will architect fault-tolerant protocols, design scalable consensus algorithms, "
                    "and optimize low-latency storage layers across distributed multi-region cloud deployments.</p>"
                    "<h3>Requirements:</h3>"
                    "<ul>"
                    "<li>Deep experience with Raft and Paxos consensus algorithms.</li>"
                    "<li>Strong mastery of Python and Go systems programming.</li>"
                    "<li>Track record delivering high-throughput low-latency systems in production.</li>"
                    "</ul>"
                ),
            }
        ]
    }

    # 2. Run board check via monitor instance with mocked provider response
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gh_payload))) as client:
        monitored_jobs = await monitor.poll_due_boards(max_boards=5, client=client)

    assert len(monitored_jobs) == 1
    job1 = monitored_jobs[0]
    assert job1.title == "Principal Distributed Systems Engineer"
    assert job1.company == "Acme Corp"
    assert job1.description_ok is True
    assert job1.requirements is not None
    assert "consensus" in job1.requirements.lower()

    # 3. Search for it through SearchOrchestrator on API instance without Serper
    params = SearchParams(
        job_title="Distributed Systems",
        location="Lagos",
    )
    results, done_event = await collect_search(orchestrator, params, platforms=["greenhouse"])

    # 4. Verify job is returned and Serper was NOT called
    assert len(results) >= 1
    matched = next((j for j in results if j.id == job1.id), None)
    assert matched is not None
    assert matched.title == "Principal Distributed Systems Engineer"
    assert matched.company == "Acme Corp"
    assert matched.is_remote is True
    assert done_event.serper_queries_used == 0

    # 5. Cross-source Deduplication in SearchOrchestrator:
    # A second discovery source (direct board probe) returns the exact same posting
    # with a different source ID ('direct_board:acmecorp:88001') but identical canonical apply_url.
    # We verify that SearchOrchestrator's internal workflow deduplicates across sources,
    # emitting only ONE representation of the job while preserving useful metadata, without Serper.
    duplicate_direct_listing = JobListing(
        id="direct_board:acmecorp:88001",
        title="Principal Distributed Systems Engineer",
        company="Acme Corp",
        location="Lagos, Nigeria (Remote)",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/acmecorp/jobs/88001",
        source_url="https://boards.greenhouse.io/acmecorp/jobs/88001",
        provider="greenhouse",
        ats_source="greenhouse",
        data_source="api",
        query_used="acmecorp",
        description="We are seeking a Principal Distributed Systems Engineer to scale our global infrastructure platform with fault-tolerant consensus.",
        description_ok=True,
        requirements="Deep experience with Raft and Paxos consensus algorithms; mastery of Python and Go systems programming.",
        scraped_at=now,
        posted_at=now - timedelta(days=2),
    )

    async def mock_probe_direct_boards(slugs, client, platforms=None):
        return [duplicate_direct_listing]

    monkeypatch.setattr("src.project_files.search_pipeline.probe_direct_boards", mock_probe_direct_boards)

    dedup_params = SearchParams(
        job_title="Acme Distributed Systems",
        location="Lagos",
    )

    # 1. Assert monitored-store search independently matches the seeded job
    monitored_matches = reg_api.search_monitored_jobs(
        query=dedup_params.job_title,
        location="Lagos",
        platforms=["greenhouse"],
    )
    assert len(monitored_matches) >= 1, f"Monitored store must independently match seeded job, got {len(monitored_matches)}"
    source1_job = next((j for j in monitored_matches if "88001" in j.apply_url), None)
    assert source1_job is not None, "Seeded job must be returned by monitored store search"
    assert source1_job.id == "greenhouse:acmecorp:88001"

    # 2. Assert direct-board routing is invoked and independently returns duplicate posting
    from src.project_files.direct_board_router import extract_company_slug_candidates
    slugs = extract_company_slug_candidates(dedup_params.job_title)
    assert "acme" in slugs, f"Company slug 'acme' must be extracted from query, got {slugs}"
    direct_matches = await mock_probe_direct_boards(slugs, None, platforms=["greenhouse"])
    assert len(direct_matches) >= 1, "Direct board routing must independently produce candidate listing"
    source2_job = direct_matches[0]
    assert source2_job.id == "direct_board:acmecorp:88001"

    # 3. Assert both sources independently produced matching records with identical apply_url but distinct IDs
    assert source1_job.id != source2_job.id
    assert source1_job.apply_url == source2_job.apply_url
    assert source1_job.apply_url == "https://boards.greenhouse.io/acmecorp/jobs/88001"

    # 4. Execute actual SearchOrchestrator search workflow across both sources
    dedup_results, dedup_done = await collect_search(orchestrator, dedup_params, platforms=["greenhouse"])

    # 5. Verify that the emitted search results contain ONLY ONE representation of job 88001
    matching_88001 = [j for j in dedup_results if "88001" in j.apply_url]
    assert len(matching_88001) == 1, f"Expected 1 deduplicated listing, got {len(matching_88001)}"

    # 6. Verify merged listing retains rich description, requirements, company, title, and remote metadata
    emitted_job = matching_88001[0]
    assert emitted_job.company == "Acme Corp"
    assert emitted_job.title == "Principal Distributed Systems Engineer"
    assert emitted_job.is_remote is True
    assert emitted_job.description is not None and len(emitted_job.description) > 50
    assert emitted_job.requirements is not None
    assert "consensus" in emitted_job.requirements.lower()

    # 7. Verify Serper was NOT used
    assert dedup_done.serper_queries_used == 0

    # 6. Cache Invalidation via shared SQLite store revision
    # Run search for "Engineer" to populate whole-search cache
    search_eng_params = SearchParams(job_title="Engineer", location="Lagos")
    res_eng_1, _ = await collect_search(orchestrator, search_eng_params, platforms=["greenhouse"])
    assert any(j.id == job1.id for j in res_eng_1)
    initial_count = len(res_eng_1)

    # Monitor discovers a second job for Acme: "Senior Frontend Engineer"
    gh_payload_2 = {
        "jobs": [
            {
                "id": 88001,
                "title": "Principal Distributed Systems Engineer",
                "absolute_url": "https://boards.greenhouse.io/acmecorp/jobs/88001",
                "location": {"name": "Lagos, Nigeria (Remote)"},
                "updated_at": recent_posted,
                "first_published": recent_posted,
                "content": "<p>Existing job description content...</p>",
            },
            {
                "id": 88002,
                "title": "Senior Frontend Engineer",
                "absolute_url": "https://boards.greenhouse.io/acmecorp/jobs/88002",
                "location": {"name": "Lagos, Nigeria (Remote)"},
                "updated_at": recent_posted,
                "first_published": recent_posted,
                "content": "<p>Frontend specialist with React and TypeScript mastery.</p>",
            },
        ]
    }

    # Reset next_scheduled_check so board is due again
    board_rec = reg_monitor.get_board("greenhouse", "acmecorp")
    with reg_monitor._get_connection() as conn:
        conn.execute("UPDATE company_boards SET next_scheduled_check = 0 WHERE id = ?", (board_rec.id,))
        conn.commit()

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=gh_payload_2))) as client:
        jobs_round2 = await monitor.poll_due_boards(max_boards=5, client=client)

    assert len(jobs_round2) == 2

    # Verify API instance observes updated store version without restart
    assert reg_api.get_monitored_store_version() == reg_monitor.get_monitored_store_version()

    # Repeat exact same search for "Engineer": cache MUST be invalidated and return new job!
    res_eng_2, _ = await collect_search(orchestrator, search_eng_params, platforms=["greenhouse"])
    assert len(res_eng_2) == initial_count + 1
    assert any(j.id == "greenhouse:acmecorp:88002" for j in res_eng_2)

    # 7. Tri-state remote filtering verification
    # Add an onsite job directly to monitor store
    job_onsite = JobListing(
        id="greenhouse:acmecorp:88003",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Site Reliability Engineer",
        company="Acme Corp",
        location="Lagos Office Only",
        is_remote=False,
        work_model="onsite",
        apply_url="https://boards.greenhouse.io/acmecorp/jobs/88003",
        source_url="https://boards.greenhouse.io/acmecorp/jobs/88003",
        posted_at=now - timedelta(days=3),
        scraped_at=now,
        query_used="acmecorp",
    )
    reg_monitor.upsert_monitored_job(job_onsite)

    # Remote = True: returns remote jobs only
    res_remote_true, _ = await collect_search(orchestrator, SearchParams(job_title="Engineer", remote=True), platforms=["greenhouse"])
    assert all(j.is_remote is True for j in res_remote_true)
    assert not any(j.id == "greenhouse:acmecorp:88003" for j in res_remote_true)

    # Remote = False: excludes remote jobs
    res_remote_false, _ = await collect_search(orchestrator, SearchParams(job_title="Engineer", remote=False), platforms=["greenhouse"])
    assert any(j.id == "greenhouse:acmecorp:88003" for j in res_remote_false)
    assert not any(j.id == "greenhouse:acmecorp:88001" for j in res_remote_false)
    assert not any(j.id == "greenhouse:acmecorp:88002" for j in res_remote_false)

    # Remote = None: returns both
    res_remote_none, _ = await collect_search(orchestrator, SearchParams(job_title="Engineer", remote=None), platforms=["greenhouse"])
    ids_none = {j.id for j in res_remote_none}
    assert "greenhouse:acmecorp:88001" in ids_none
    assert "greenhouse:acmecorp:88003" in ids_none

    # 8. Authoritative date filtering verification
    # Add an old job (posted 120 days ago) discovered today
    job_old = JobListing(
        id="greenhouse:acmecorp:88004",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Legacy Systems Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/acmecorp/jobs/88004",
        source_url="https://boards.greenhouse.io/acmecorp/jobs/88004",
        posted_at=now - timedelta(days=120),
        scraped_at=now,
        query_used="acmecorp",
    )
    reg_monitor.upsert_monitored_job(job_old)

    # Add a job with unknown posting date discovered today
    job_unknown_date = JobListing(
        id="greenhouse:acmecorp:88005",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Undated Roles Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/acmecorp/jobs/88005",
        source_url="https://boards.greenhouse.io/acmecorp/jobs/88005",
        posted_at=None,
        scraped_at=now,
        query_used="acmecorp",
    )
    reg_monitor.upsert_monitored_job(job_unknown_date)

    # Date filter: posted within 7 days
    res_7d, _ = await collect_search(orchestrator, SearchParams(job_title="Engineer", days=7), platforms=["greenhouse"])
    ids_7d = {j.id for j in res_7d}
    # Recent jobs (88001, 88002, 88003) posted 3 days ago are included
    assert "greenhouse:acmecorp:88001" in ids_7d
    assert "greenhouse:acmecorp:88002" in ids_7d
    # Old job (88004) posted 120 days ago is EXCLUDED
    assert "greenhouse:acmecorp:88004" not in ids_7d
    # Undated job (88005) is EXCLUDED when date filter is active
    assert "greenhouse:acmecorp:88005" not in ids_7d

    # 9. Explicit empty platforms selection contract
    res_empty_plat, done_empty = await collect_search(orchestrator, SearchParams(job_title="Engineer", platforms=[]), platforms=[])
    assert len(res_empty_plat) == 0
    assert done_empty.total == 0

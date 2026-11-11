"""
Cross-instance regression test for durable SQLite monitored-store revision.

Verifies:
1. Two separate CompanyBoardRegistry instances pointing to the same SQLite database file.
2. Search pipeline runs using the first instance and caches results (Serper disabled).
3. The second instance simulates the monitor discovering a new job.
4. The first instance observes the incremented durable SQLite revision.
5. Repeating the search retrieves the newly discovered job immediately without waiting for cache TTL.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from src.config import settings
from src.project_files.company_board_registry import CompanyBoardRegistry
from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import SearchOrchestrator, _cache


@pytest.mark.anyio
async def test_cross_instance_monitored_store_revision_invalidates_search_cache(
    tmp_path: Path, monkeypatch
):
    # Disable Serper completely
    monkeypatch.setattr(settings, "serper_api_key", "")
    _cache.clear()

    db_path = str(tmp_path / "shared_registry.sqlite")

    # Instance 1: Used by the API / search pipeline process
    reg1 = CompanyBoardRegistry(db_path=db_path)
    # Instance 2: Used by an independent CLI monitor process
    reg2 = CompanyBoardRegistry(db_path=db_path)

    # Initial versions match
    v1 = reg1.get_monitored_store_version()
    v2 = reg2.get_monitored_store_version()
    assert v1 == v2

    now = datetime.now(timezone.utc)
    job1 = JobListing(
        id="greenhouse:acme:1",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Staff Distributed Systems Engineer",
        company="Acme Corp",
        company_slug="acme",
        location="Remote",
        work_model="remote",
        is_remote=True,
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        posted_at=now,
        scraped_at=now,
        query_used="acme",
    )

    # Populate job1 via instance 2 (initial discovery)
    assert reg2.upsert_monitored_job(job1) is True

    # Search via instance 1
    monkeypatch.setattr("src.project_files.search_pipeline.company_board_registry", reg1)
    monkeypatch.setattr("src.project_files.company_board_registry.company_board_registry", reg1)

    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Distributed Systems", include_nigerian_sites=False)

    # First search: returns job1 and caches the search result
    first_results = []
    async for event_name, event_data in orchestrator.run(params):
        if event_name == "results":
            first_results.extend(event_data.batch)
    assert len(first_results) == 1
    assert first_results[0].id == "greenhouse:acme:1"

    # Second search: hits cache (DoneEvent.cached == True)
    second_cached = False
    async for event_name, event_data in orchestrator.run(params):
        if event_name == "done":
            second_cached = event_data.cached
    assert second_cached is True

    # Monitor (Instance 2 in another process) discovers a second job
    job2 = JobListing(
        id="lever:beta:2",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Senior Distributed Systems Architect",
        company="Beta Corp",
        company_slug="beta",
        location="Remote",
        work_model="remote",
        is_remote=True,
        apply_url="https://jobs.lever.co/beta/2",
        source_url="https://jobs.lever.co/beta/2",
        posted_at=now,
        scraped_at=now,
        query_used="beta",
    )
    assert reg2.upsert_monitored_job(job2) is True

    # Step 5: Verify the first instance observes the updated database revision
    updated_v1 = reg1.get_monitored_store_version()
    updated_v2 = reg2.get_monitored_store_version()
    assert updated_v1 == updated_v2
    assert updated_v1 > v1

    # Step 6: Repeat the search with instance 1: cache must be busted and return BOTH jobs
    third_results = []
    third_cached = True
    async for event_name, event_data in orchestrator.run(params):
        if event_name == "results":
            third_results.extend(event_data.batch)
        elif event_name == "done":
            third_cached = event_data.cached

    assert third_cached is False
    assert len(third_results) == 2
    found_ids = {j.id for j in third_results}
    assert found_ids == {"greenhouse:acme:1", "lever:beta:2"}

"""
Tests for searching persistent monitored jobs and whole-search cache behavior.

Verifies:
1. Searching while offline or without Serper retrieves stored monitored jobs.
2. Monitored jobs are deduplicated against search results via GlobalDeduplicator.
3. Search filters (location, remote, platform, exclude keywords) are respected.
4. Whole-search cache is invalidated / versioned when monitor discovers new jobs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest
import httpx

from src.config import settings
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    company_board_registry,
)
from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import SearchOrchestrator, _cache


@pytest.fixture
def clean_test_env(tmp_path: Path, monkeypatch):
    db_file = str(tmp_path / "test_search_store.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    monkeypatch.setattr("src.project_files.search_pipeline.company_board_registry", reg)
    monkeypatch.setattr("src.project_files.company_board_registry.company_board_registry", reg)
    _cache.clear()
    yield reg
    reg.clear()
    _cache.clear()


@pytest.mark.anyio
async def test_search_without_serper_retrieves_monitored_jobs(clean_test_env, monkeypatch):
    reg = clean_test_env
    monkeypatch.setattr(settings, "serper_api_key", "")

    now = datetime.now(timezone.utc)
    job1 = JobListing(
        id="greenhouse:stripe:101",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Senior Python Backend Engineer",
        company="Stripe",
        company_slug="stripe",
        location="Remote, US",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/stripe/jobs/101",
        source_url="https://boards.greenhouse.io/stripe/jobs/101",
        extraction_confidence=0.95,
        posted_at=now,
        scraped_at=now,
        query_used="stripe",
    )
    job2 = JobListing(
        id="lever:linear:202",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Frontend React Developer",
        company="Linear",
        company_slug="linear",
        location="San Francisco, CA",
        is_remote=False,
        work_model="in_person",
        apply_url="https://jobs.lever.co/linear/202",
        source_url="https://jobs.lever.co/linear/202",
        extraction_confidence=0.90,
        posted_at=now,
        scraped_at=now,
        query_used="linear",
    )
    assert reg.upsert_monitored_job(job1) is True
    assert reg.upsert_monitored_job(job2) is True

    orchestrator = SearchOrchestrator()
    params = SearchParams(
        job_title="Python Engineer",
        include_nigerian_sites=False,
    )

    collected_batches: list[list[JobListing]] = []
    done_event = None

    async for event_type, payload in orchestrator.run(params):
        if event_type == "results":
            collected_batches.append(payload.batch)
        elif event_type == "done":
            done_event = payload

    all_jobs = [job for b in collected_batches for job in b]
    assert len(all_jobs) == 1
    assert all_jobs[0].id == "greenhouse:stripe:101"
    assert all_jobs[0].title == "Senior Python Backend Engineer"
    assert all_jobs[0].company == "Stripe"
    assert done_event is not None
    assert done_event.total == 1


@pytest.mark.anyio
async def test_monitored_jobs_deduplicated_against_search_results(clean_test_env, monkeypatch):
    reg = clean_test_env
    monkeypatch.setattr(settings, "serper_api_key", "test-serper-key")

    now = datetime.now(timezone.utc)
    monitored_job = JobListing(
        id="greenhouse:datadog:303",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Site Reliability Engineer",
        company="Datadog",
        company_slug="datadog",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/datadog/jobs/303",
        source_url="https://boards.greenhouse.io/datadog/jobs/303",
        extraction_confidence=0.88,
        posted_at=now,
        scraped_at=now,
        query_used="datadog",
    )
    assert reg.upsert_monitored_job(monitored_job) is True

    # Simulate Serper returning the same job posting URL
    serper_response = {
        "organic": [
            {
                "title": "Site Reliability Engineer - Datadog",
                "link": "https://boards.greenhouse.io/datadog/jobs/303",
                "snippet": "Join Datadog as Site Reliability Engineer",
            }
        ]
    }

    def mock_transport(req: httpx.Request):
        if "google.serper.dev" in str(req.url):
            return httpx.Response(200, json=serper_response)
        elif "boards-api.greenhouse.io" in str(req.url):
            return httpx.Response(200, json={
                "id": 303,
                "title": "Site Reliability Engineer",
                "absolute_url": "https://boards.greenhouse.io/datadog/jobs/303",
                "location": {"name": "Remote"},
                "content": "<p>Description</p>",
            })
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_transport)) as client:
        orchestrator = SearchOrchestrator()
        params = SearchParams(
            job_title="Reliability Engineer",
            include_nigerian_sites=False,
        )

        all_emitted: list[JobListing] = []
        async for event_type, payload in orchestrator.run(params, platforms=["greenhouse"], client=client):
            if event_type == "results":
                all_emitted.extend(payload.batch)

        # Confirm deduplication kept exactly one item for job 303
        datadog_jobs = [j for j in all_emitted if "303" in j.id]
        assert len(datadog_jobs) == 1
        assert datadog_jobs[0].company == "Datadog"


@pytest.mark.anyio
async def test_monitored_jobs_filters_respected(clean_test_env):
    reg = clean_test_env
    now = datetime.now(timezone.utc)

    # Job A: Remote Greenhouse job
    job_a = JobListing(
        id="greenhouse:co:1",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Remote Backend Engineer",
        company="Company A",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://boards.greenhouse.io/co/1",
        source_url="https://boards.greenhouse.io/co/1",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    # Job B: Onsite Lever job in Lagos
    job_b = JobListing(
        id="lever:co:2",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Lagos Backend Engineer",
        company="Company B",
        location="Lagos, Nigeria",
        is_remote=False,
        work_model="in_person",
        apply_url="https://jobs.lever.co/co/2",
        source_url="https://jobs.lever.co/co/2",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    # Job C: Ashby DevOps job
    job_c = JobListing(
        id="ashby:co:3",
        provider="ashby",
        data_source="api",
        ats_source="ashby",
        title="Senior DevOps Engineer",
        company="Company C",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url="https://jobs.ashbyhq.com/co/3",
        source_url="https://jobs.ashbyhq.com/co/3",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )

    reg.upsert_monitored_job(job_a)
    reg.upsert_monitored_job(job_b)
    reg.upsert_monitored_job(job_c)

    # 1. Test is_remote=True filter
    remote_results = reg.search_monitored_jobs("Engineer", is_remote=True)
    remote_ids = {j.id for j in remote_results}
    assert "greenhouse:co:1" in remote_ids
    assert "ashby:co:3" in remote_ids
    assert "lever:co:2" not in remote_ids

    # 2. Test platform filter
    gh_only = reg.search_monitored_jobs("Engineer", platforms=["greenhouse"])
    assert len(gh_only) == 1
    assert gh_only[0].id == "greenhouse:co:1"

    # 3. Test location filter
    lagos_only = reg.search_monitored_jobs("Engineer", location="Lagos")
    assert len(lagos_only) == 1
    assert lagos_only[0].id == "lever:co:2"

    # 4. Test exclude_keywords
    no_devops = reg.search_monitored_jobs("Engineer", exclude_keywords=["DevOps"])
    no_devops_ids = {j.id for j in no_devops}
    assert "ashby:co:3" not in no_devops_ids


@pytest.mark.anyio
async def test_whole_search_cache_invalidated_by_monitor_discovery(clean_test_env, monkeypatch):
    reg = clean_test_env
    monkeypatch.setattr(settings, "serper_api_key", "")

    now = datetime.now(timezone.utc)
    job1 = JobListing(
        id="greenhouse:figma:1",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Staff Infrastructure Engineer",
        company="Figma",
        apply_url="https://boards.greenhouse.io/figma/1",
        source_url="https://boards.greenhouse.io/figma/1",
        posted_at=now,
        scraped_at=now,
        query_used="figma",
    )
    reg.upsert_monitored_job(job1)

    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Infrastructure", include_nigerian_sites=False)

    # First search: returns Figma job and populates whole-search cache
    res1: list[JobListing] = []
    async for event_type, payload in orchestrator.run(params):
        if event_type == "results":
            res1.extend(payload.batch)
    assert len(res1) == 1
    assert res1[0].company == "Figma"

    # Second search: cache hit (verified by cached=True in DoneEvent)
    done_cached = False
    async for event_type, payload in orchestrator.run(params):
        if event_type == "done" and payload.cached:
            done_cached = True
    assert done_cached is True

    # Monitor discovers a second job and upserts it -> increments store version
    job2 = JobListing(
        id="lever:stripe:2",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Principal Infrastructure Architect",
        company="Stripe",
        apply_url="https://jobs.lever.co/stripe/2",
        source_url="https://jobs.lever.co/stripe/2",
        posted_at=now,
        scraped_at=now,
        query_used="stripe",
    )
    reg.upsert_monitored_job(job2)

    # Third search: cache-busted automatically, immediately retrieves both jobs!
    res3: list[JobListing] = []
    cached_flag = True
    async for event_type, payload in orchestrator.run(params):
        if event_type == "results":
            res3.extend(payload.batch)
        elif event_type == "done":
            cached_flag = payload.cached

    assert cached_flag is False
    assert len(res3) == 2
    res3_companies = {j.company for j in res3}
    assert "Figma" in res3_companies
    assert "Stripe" in res3_companies

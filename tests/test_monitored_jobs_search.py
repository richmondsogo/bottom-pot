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


@pytest.mark.anyio
async def test_monitored_jobs_remote_and_posting_age_filters(clean_test_env):
    reg = clean_test_env
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=30)
    recent_date = now - timedelta(days=2)

    # 1. Old job discovered today (posted 30 days ago)
    job_old = JobListing(
        id="greenhouse:co:old",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Old Engineer Discovered Today",
        company="Company Old",
        location="Berlin",
        work_model="onsite",
        is_remote=False,
        apply_url="https://boards.greenhouse.io/co/old",
        source_url="https://boards.greenhouse.io/co/old",
        posted_at=old_date,
        scraped_at=now,
        query_used="co",
    )

    # 2. Recently posted job (posted 2 days ago, remote)
    job_recent_remote = JobListing(
        id="lever:co:recent_remote",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Recent Remote Engineer",
        company="Company Remote",
        location="Remote",
        work_model="remote",
        is_remote=True,
        apply_url="https://jobs.lever.co/co/recent_remote",
        source_url="https://jobs.lever.co/co/recent_remote",
        posted_at=recent_date,
        scraped_at=now,
        query_used="co",
    )

    # 3. Hybrid job (posted 2 days ago)
    job_recent_hybrid = JobListing(
        id="ashby:co:recent_hybrid",
        provider="ashby",
        data_source="api",
        ats_source="ashby",
        title="Recent Hybrid Engineer",
        company="Company Hybrid",
        location="London",
        work_model="hybrid",
        is_remote=False,
        apply_url="https://jobs.ashbyhq.com/co/recent_hybrid",
        source_url="https://jobs.ashbyhq.com/co/recent_hybrid",
        posted_at=recent_date,
        scraped_at=now,
        query_used="co",
    )

    # 4. Job with unknown work model and no verified posting date (posted_at is None)
    job_unknown = JobListing(
        id="greenhouse:co:unknown",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Active Unknown Engineer",
        company="Company Unknown",
        location="Lagos, Nigeria",
        work_model=None,
        is_remote=None,
        apply_url="https://boards.greenhouse.io/co/unknown",
        source_url="https://boards.greenhouse.io/co/unknown",
        posted_at=None,
        scraped_at=now,
        query_used="co",
    )

    reg.upsert_monitored_job(job_old)
    reg.upsert_monitored_job(job_recent_remote)
    reg.upsert_monitored_job(job_recent_hybrid)
    reg.upsert_monitored_job(job_unknown)

    # --- Test Work Arrangement Filters ---
    # is_remote=True -> ONLY verified remote
    remote_only = reg.search_monitored_jobs("Engineer", is_remote=True)
    remote_ids = {j.id for j in remote_only}
    assert remote_ids == {"lever:co:recent_remote"}

    # is_remote=False -> Exclude remote (includes onsite, hybrid, and unknown)
    non_remote = reg.search_monitored_jobs("Engineer", is_remote=False)
    non_remote_ids = {j.id for j in non_remote}
    assert "lever:co:recent_remote" not in non_remote_ids
    assert "greenhouse:co:old" in non_remote_ids
    assert "ashby:co:recent_hybrid" in non_remote_ids
    assert "greenhouse:co:unknown" in non_remote_ids

    # is_remote=None -> All arrangements
    all_remote = reg.search_monitored_jobs("Engineer", is_remote=None)
    assert len(all_remote) == 4

    # --- Test Authoritative Posting Age Filters ---
    # posted_within_days=7:
    # - job_old (30 days ago) is EXCLUDED even though discovered today
    # - job_unknown (no verified posted_at) is EXCLUDED
    # - job_recent_remote and job_recent_hybrid (2 days ago) are INCLUDED
    recent_jobs = reg.search_monitored_jobs("Engineer", posted_within_days=7)
    recent_ids = {j.id for j in recent_jobs}
    assert recent_ids == {"lever:co:recent_remote", "ashby:co:recent_hybrid"}
    assert "greenhouse:co:old" not in recent_ids
    assert "greenhouse:co:unknown" not in recent_ids

    # Without posted_within_days filter:
    # All jobs including unknown posted date and old job are returned
    unfiltered_jobs = reg.search_monitored_jobs("Engineer", posted_within_days=None)
    assert len(unfiltered_jobs) == 4


@pytest.mark.anyio
async def test_monitored_jobs_work_model_precedence_over_location(clean_test_env):
    """Regression test: explicit work_model takes strict precedence over location text heuristics.

    - Explicit hybrid ('hybrid') with location 'Remote, London':
        * is_remote=True: NOT returned (hybrid is not remote-only)
        * is_remote=False: RETURNED (retained in non-remote)
    - Explicit onsite ('onsite') with location 'Remote Office, New York':
        * is_remote=True: NOT returned
        * is_remote=False: RETURNED
    - Explicit remote ('remote') with location 'Austin, TX':
        * is_remote=True: RETURNED
        * is_remote=False: NOT returned
    - Unknown work_model (None) with location 'Remote, UK':
        * is_remote=True: RETURNED (location fallback)
        * is_remote=False: NOT returned
    - Unknown work_model (None) with location 'Cambridge, UK':
        * is_remote=True: NOT returned
        * is_remote=False: RETURNED
    - Unknown work_model (None) with location None:
        * is_remote=True: NOT returned
        * is_remote=False: RETURNED
    """
    reg = clean_test_env
    now = datetime.now(timezone.utc)

    job_hybrid_remote_loc = JobListing(
        id="greenhouse:co:hybrid_remote_loc",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Staff Hybrid Engineer",
        company="Company Alpha",
        location="Remote, London",
        work_model="hybrid",
        is_remote=False,
        apply_url="https://boards.greenhouse.io/co/1",
        source_url="https://boards.greenhouse.io/co/1",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    job_onsite_remote_loc = JobListing(
        id="lever:co:onsite_remote_loc",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Onsite Systems Engineer",
        company="Company Beta",
        location="Remote Office, New York",
        work_model="onsite",
        is_remote=False,
        apply_url="https://jobs.lever.co/co/2",
        source_url="https://jobs.lever.co/co/2",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    job_remote_explicit = JobListing(
        id="ashby:co:remote_explicit",
        provider="ashby",
        data_source="api",
        ats_source="ashby",
        title="Cloud Platform Engineer",
        company="Company Gamma",
        location="Austin, TX",
        work_model="remote",
        is_remote=True,
        apply_url="https://jobs.ashbyhq.com/co/3",
        source_url="https://jobs.ashbyhq.com/co/3",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    job_unknown_remote_loc = JobListing(
        id="greenhouse:co:unknown_remote_loc",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Backend Engineer",
        company="Company Delta",
        location="Remote, UK",
        work_model=None,
        is_remote=None,
        apply_url="https://boards.greenhouse.io/co/4",
        source_url="https://boards.greenhouse.io/co/4",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    job_unknown_onsite_loc = JobListing(
        id="lever:co:unknown_onsite_loc",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Hardware Engineer",
        company="Company Epsilon",
        location="Cambridge, UK",
        work_model=None,
        is_remote=None,
        apply_url="https://jobs.lever.co/co/5",
        source_url="https://jobs.lever.co/co/5",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )
    job_unknown_no_loc = JobListing(
        id="ashby:co:unknown_no_loc",
        provider="ashby",
        data_source="api",
        ats_source="ashby",
        title="Data Scientist Engineer",
        company="Company Zeta",
        location=None,
        work_model=None,
        is_remote=None,
        apply_url="https://jobs.ashbyhq.com/co/6",
        source_url="https://jobs.ashbyhq.com/co/6",
        posted_at=now,
        scraped_at=now,
        query_used="co",
    )

    for j in [
        job_hybrid_remote_loc,
        job_onsite_remote_loc,
        job_remote_explicit,
        job_unknown_remote_loc,
        job_unknown_onsite_loc,
        job_unknown_no_loc,
    ]:
        reg.upsert_monitored_job(j)

    # 1. is_remote=True -> Must only match verified remote (explicit remote or unknown with remote location)
    remote_matches = reg.search_monitored_jobs("Engineer", is_remote=True)
    remote_ids = {j.id for j in remote_matches}
    assert remote_ids == {"ashby:co:remote_explicit", "greenhouse:co:unknown_remote_loc"}, f"Got {remote_ids}"

    # 2. is_remote=False -> Must exclude verified remote jobs, but retain hybrid, onsite, and unknown non-remote
    non_remote_matches = reg.search_monitored_jobs("Engineer", is_remote=False)
    non_remote_ids = {j.id for j in non_remote_matches}
    assert "ashby:co:remote_explicit" not in non_remote_ids
    assert "greenhouse:co:unknown_remote_loc" not in non_remote_ids
    assert "greenhouse:co:hybrid_remote_loc" in non_remote_ids, "Hybrid job with 'Remote' in location was incorrectly excluded from non-remote!"
    assert "lever:co:onsite_remote_loc" in non_remote_ids, "Onsite job with 'Remote' in location was incorrectly excluded from non-remote!"
    assert "lever:co:unknown_onsite_loc" in non_remote_ids
    assert "ashby:co:unknown_no_loc" in non_remote_ids
    assert non_remote_ids == {
        "greenhouse:co:hybrid_remote_loc",
        "lever:co:onsite_remote_loc",
        "lever:co:unknown_onsite_loc",
        "ashby:co:unknown_no_loc",
    }

    # 3. is_remote=None -> All 6 jobs returned
    all_matches = reg.search_monitored_jobs("Engineer", is_remote=None)
    assert len(all_matches) == 6


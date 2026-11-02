"""
Tests for GlobalDeduplicator and In-Memory Cache.
"""

from datetime import datetime, timezone
import pytest

from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import (
    CacheEntry,
    GlobalDeduplicator,
    _cache,
    _cache_get,
    _cache_key,
    _cache_set,
)


def _sample_listing(id_: str, provider: str = "greenhouse") -> JobListing:
    return JobListing(
        id=id_,
        provider=provider,
        data_source="api",
        title="Software Engineer",
        company="Stripe",
        company_slug="stripe",
        scraped_at=datetime.now(timezone.utc),
        apply_url=f"https://boards.greenhouse.io/stripe/jobs/{id_}",
        source_url=f"https://boards.greenhouse.io/stripe/jobs/{id_}",
        query_used="test",
        ats_source=provider,
    )


def test_deduplicator_filters_duplicates():
    dedup = GlobalDeduplicator()

    batch1 = [_sample_listing("1"), _sample_listing("2")]
    res1 = dedup.filter(batch1)
    assert len(res1) == 2

    # Batch 2 contains item 2 again and item 3
    batch2 = [_sample_listing("2"), _sample_listing("3")]
    res2 = dedup.filter(batch2)
    assert len(res2) == 1
    assert res2[0].id == "3"

    # Batch 3 with only seen items returns empty list
    batch3 = [_sample_listing("1"), _sample_listing("3")]
    res3 = dedup.filter(batch3)
    assert len(res3) == 0


def test_deduplicator_emits_upgraded_arrival_and_ignores_lower():
    dedup = GlobalDeduplicator()

    # 1. Snippet (rank 1)
    snippet = JobListing(
        id="greenhouse:stripe:100",
        provider="greenhouse",
        data_source="snippet",
        title="Software Engineer - Backend",
        company="Stripe",
        company_slug="stripe",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stripe/jobs/100",
        source_url="https://boards.greenhouse.io/stripe/jobs/100",
        query_used="test",
        ats_source="greenhouse",
    )

    # 2. Enriched API record (rank 3)
    api_record = JobListing(
        id="greenhouse:stripe:100",
        provider="greenhouse",
        data_source="api",
        title="Software Engineer - Backend",
        company="Stripe",
        company_slug="stripe",
        description="Comprehensive backend description with full details.",
        description_ok=True,
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stripe/jobs/100",
        source_url="https://boards.greenhouse.io/stripe/jobs/100",
        query_used="test",
        ats_source="greenhouse",
    )

    # Snippet arrives first -> emitted
    out1 = dedup.filter([snippet])
    assert len(out1) == 1
    assert out1[0].data_source == "snippet"

    # API arrives second -> upgraded, emitted!
    out2 = dedup.filter([api_record])
    assert len(out2) == 1
    assert out2[0].data_source == "api"
    assert out2[0].description_ok is True

    # Snippet arrives third -> lower ranked, NEVER emitted
    out3 = dedup.filter([snippet])
    assert len(out3) == 0


def test_deduplicator_order_independent_final_state():
    dedup_a = GlobalDeduplicator()
    dedup_b = GlobalDeduplicator()

    snippet = JobListing(
        id="greenhouse:stripe:200",
        provider="greenhouse",
        data_source="snippet",
        title="Frontend Engineer",
        company="Stripe",
        company_slug="stripe",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stripe/jobs/200",
        source_url="https://boards.greenhouse.io/stripe/jobs/200",
        query_used="test",
        ats_source="greenhouse",
    )

    api_record = JobListing(
        id="greenhouse:stripe:200",
        provider="greenhouse",
        data_source="api",
        title="Frontend Engineer",
        company="Stripe",
        company_slug="stripe",
        description="Detailed frontend engineer role description.",
        description_ok=True,
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/stripe/jobs/200",
        source_url="https://boards.greenhouse.io/stripe/jobs/200",
        query_used="test",
        ats_source="greenhouse",
    )

    # Sequence A: Snippet then API
    dedup_a.filter([snippet])
    dedup_a.filter([api_record])

    # Sequence B: API then Snippet
    dedup_b.filter([api_record])
    dedup_b.filter([snippet])

    # Final internal records are identical in fields and source rank
    final_a = dedup_a._emitted[0]
    final_b = dedup_b._emitted[0]

    assert final_a.id == final_b.id
    assert final_a.data_source == final_b.data_source == "api"
    assert final_a.description == final_b.description
    assert final_a.extraction_confidence == final_b.extraction_confidence


@pytest.mark.anyio
async def test_search_pipeline_total_does_not_inflate_on_upgraded_record():
    import httpx
    from src.project_files.search_pipeline import SearchOrchestrator
    from src.project_files.cache_store import cache_store

    cache_store.clear()
    orchestrator = SearchOrchestrator()

    snippet = JobListing(
        id="greenhouse:acme:300",
        provider="greenhouse",
        data_source="snippet",
        title="DevOps Engineer",
        company="Acme",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/300",
        source_url="https://boards.greenhouse.io/acme/jobs/300",
        query_used="test",
        ats_source="greenhouse",
    )

    api_record = JobListing(
        id="greenhouse:acme:300",
        provider="greenhouse",
        data_source="api",
        title="DevOps Engineer",
        company="Acme",
        company_slug="acme",
        description="Full DevOps description with infra details.",
        description_ok=True,
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/300",
        source_url="https://boards.greenhouse.io/acme/jobs/300",
        query_used="test",
        ats_source="greenhouse",
    )

    call_seq = 0

    async def mock_serper(platform, query, params, client, **kwargs):
        nonlocal call_seq
        call_seq += 1
        if platform == "greenhouse":
            return (platform, [snippet], True)
        elif platform == "lever":
            # Lever returns the upgraded API record for the same job URL
            return (platform, [api_record], True)
        return (platform, [], True)

    orchestrator._search_ats_serper = mock_serper
    params = SearchParams(job_title="DevOps", include_nigerian_sites=False)

    events = [e async for e in orchestrator.run(params, platforms=["greenhouse", "lever"])]

    results_events = [e[1] for e in events if e[0] == "results"]
    done_event = next(e[1] for e in events if e[0] == "done")

    # Done total must NOT be 2; it must be exactly 1!
    assert done_event.total == 1
    # The last emitted batch item for this job has data_source == 'api'
    last_batch_item = results_events[-1].batch[0]
    assert last_batch_item.data_source == "api"


@pytest.mark.anyio
async def test_search_pipeline_preserves_jobs_that_listings_match_considers_equal_when_dedup_keeps_separate():
    """Two jobs that listings_match would consider equal but the deduplicator keeps separate must both survive in all_collected."""
    from unittest.mock import MagicMock, patch
    from src.project_files.search_pipeline import SearchOrchestrator
    from src.project_files.cache_store import cache_store
    from src.project_files.deduplicator import listings_match

    cache_store.clear()
    orchestrator = SearchOrchestrator()

    # Two jobs sharing an identical apply URL, which listings_match would consider equal:
    job_a = JobListing(
        id="source_a:101",
        provider="source_a",
        data_source="api",
        title="Software Engineer",
        company="Acme Corp",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://jobs.example.com/acme/roles/101",
        source_url="https://jobs.example.com/acme/roles/101",
        query_used="test",
        ats_source="source_a",
    )
    job_b = JobListing(
        id="source_b:102",
        provider="source_b",
        data_source="api",
        title="Software Engineer",
        company="Acme Corp",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://jobs.example.com/acme/roles/101",
        source_url="https://jobs.example.com/acme/roles/101",
        query_used="test",
        ats_source="source_b",
    )

    # Confirm listings_match would consider them equal
    assert listings_match(job_a, job_b) is True

    async def mock_serper(platform, query, params, client, **kwargs):
        if platform == "greenhouse":
            return (platform, [job_a], True)
        elif platform == "lever":
            return (platform, [job_b], True)
        return (platform, [], True)

    # Mock deduplicator that keeps both separate (emits both without alias overlap)
    mock_dedup = MagicMock()
    mock_dedup.filter.side_effect = lambda listings: listings

    orchestrator._search_ats_serper = mock_serper
    params = SearchParams(job_title="Software Engineer", include_nigerian_sites=False)

    with patch("src.project_files.search_pipeline.GlobalDeduplicator", return_value=mock_dedup):
        events = [e async for e in orchestrator.run(params, platforms=["greenhouse", "lever"])]

    done_event = next(e[1] for e in events if e[0] == "done")
    # Both jobs survived in all_collected; total must be 2, not 1!
    assert done_event.total == 2


@pytest.mark.anyio
async def test_search_pipeline_emits_upgrades_when_cap_reached_and_caps_new_jobs():
    """Upgrades are emitted even when the max-results cap has been reached, and the cap still applies to new jobs."""
    from src.project_files.search_pipeline import SearchOrchestrator
    from src.project_files.cache_store import cache_store

    cache_store.clear()
    orchestrator = SearchOrchestrator()

    # Initial 2 snippet jobs that fill the cap (max_results = 2)
    job1_snippet = JobListing(
        id="greenhouse:acme:1",
        provider="greenhouse",
        data_source="snippet",
        title="Job 1 Snippet",
        company="Acme",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        query_used="test",
        ats_source="greenhouse",
    )
    job2_snippet = JobListing(
        id="greenhouse:acme:2",
        provider="greenhouse",
        data_source="snippet",
        title="Job 2 Snippet",
        company="Acme",
        company_slug="acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/2",
        source_url="https://boards.greenhouse.io/acme/jobs/2",
        query_used="test",
        ats_source="greenhouse",
    )

    # An upgraded API record for job 1
    job1_api = JobListing(
        id="greenhouse:acme:1",
        provider="greenhouse",
        data_source="api",
        title="Job 1 Enriched Title",
        company="Acme",
        company_slug="acme",
        description="Full enriched description for job 1",
        description_ok=True,
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        query_used="test",
        ats_source="greenhouse",
    )
    # A third distinct job (new job)
    job3_snippet = JobListing(
        id="greenhouse:beta:3",
        provider="greenhouse",
        data_source="snippet",
        title="Job 3 New",
        company="Beta",
        company_slug="beta",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/beta/jobs/3",
        source_url="https://boards.greenhouse.io/beta/jobs/3",
        query_used="test",
        ats_source="greenhouse",
    )

    # In greenhouse results: job1_snippet and job2_snippet fill the cap (2).
    # Then job1_api arrives as an upgrade, and job3_snippet arrives as a new job.
    async def mock_serper(platform, query, params, client, **kwargs):
        if platform == "greenhouse":
            return (platform, [job1_snippet, job2_snippet, job1_api, job3_snippet], True)
        return (platform, [], True)

    orchestrator._search_ats_serper = mock_serper
    params = SearchParams(job_title="Engineer", max_results=2, include_nigerian_sites=False)

    events = [e async for e in orchestrator.run(params, platforms=["greenhouse"])]

    results_events = [e[1] for e in events if e[0] == "results"]
    done_event = next(e[1] for e in events if e[0] == "done")

    # 1. Total stays capped at 2 (job 3 was rejected by the cap)
    assert done_event.total == 2

    # 2. Collect all items emitted across results batches
    all_emitted_items = [item for event in results_events for item in event.batch]

    # 3. Upgrade for job 1 was emitted even though cap was reached by job1 and job2
    upgraded_emissions = [item for item in all_emitted_items if item.id == "greenhouse:acme:1" and item.data_source == "api"]
    assert len(upgraded_emissions) == 1
    assert upgraded_emissions[0].title == "Job 1 Enriched Title"

    # 4. Job 3 was rejected by the cap and was never emitted
    assert not any(item.id == "greenhouse:beta:3" for item in all_emitted_items)



def test_cache_set_and_get():
    _cache.clear()
    params = SearchParams(job_title="Product Manager")
    key = _cache_key(params)

    assert _cache_get(key) is None

    entry = CacheEntry(
        results=[_sample_listing("100")],
        providers_searched=["greenhouse"],
        serper_queries_used=1,
    )
    _cache_set(key, entry)

    retrieved = _cache_get(key)
    assert retrieved is not None
    assert len(retrieved.results) == 1
    assert retrieved.results[0].id == "100"


def test_cache_key_scopes_by_platforms():
    params = SearchParams(job_title="Product Manager")
    base_key = _cache_key(params)
    assert _cache_key(params, None) == base_key

    gh_key = _cache_key(params, ["greenhouse"])
    gh_lever_key = _cache_key(params, ["greenhouse", "lever"])
    lever_gh_key = _cache_key(params, ["Lever", " GREENHOUSE "])

    assert gh_key != base_key
    assert gh_key != gh_lever_key
    assert gh_lever_key == lever_gh_key

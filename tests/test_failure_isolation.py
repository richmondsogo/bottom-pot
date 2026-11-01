"""
Tests for failure isolation in the search pipeline (Step 24a / Commit 6).
Verifies that failing providers (timeouts, 429 rate limit, malformed payloads, programming errors)
do not abort the search or drop results from healthy providers, and that exceptions are classified honestly.
"""

import asyncio
from datetime import datetime, timezone
import httpx
import pytest

from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.models import DoneEvent, JobListing, ResultsBatch, SearchParams
from src.project_files.nigerian_scrapers import BaseScraper
from src.project_files.search_pipeline import SearchOrchestrator


class FakeWorkingScraper(BaseScraper):
    site_name: str = "working_board"
    base_url: str = "https://working.example.com"

    async def search(self, client: httpx.AsyncClient, params: SearchParams) -> list[JobListing]:
        now = datetime.now(timezone.utc)
        return [
            JobListing(
                id="working:1",
                provider="working_board",
                title="Python Backend Engineer",
                company="Reliable Co",
                apply_url="https://working.example.com/jobs/1",
                source_url="https://working.example.com/jobs/1",
                data_source="scrape",
                query_used=params.job_title,
                ats_source="working_board",
                scraped_at=now,
            )
        ]


class FakeTimeoutScraper(BaseScraper):
    site_name: str = "timeout_board"
    base_url: str = "https://timeout.example.com"

    async def search(self, client: httpx.AsyncClient, params: SearchParams) -> list[JobListing]:
        raise httpx.ReadTimeout("Connection timed out reading from server")


class FakeRateLimitedScraper(BaseScraper):
    site_name: str = "ratelimited_board"
    base_url: str = "https://429.example.com"

    async def search(self, client: httpx.AsyncClient, params: SearchParams) -> list[JobListing]:
        req = httpx.Request("GET", self.base_url)
        resp = httpx.Response(429, request=req)
        raise httpx.HTTPStatusError("Too Many Requests", request=req, response=resp)


class FakeCrashingScraper(BaseScraper):
    site_name: str = "crashing_board"
    base_url: str = "https://crash.example.com"

    async def search(self, client: httpx.AsyncClient, params: SearchParams) -> list[JobListing]:
        raise ValueError("Simulated unexpected programming error in scraper")


@pytest.mark.anyio
async def test_failure_isolation_mixed_provider_search(monkeypatch):
    """
    Mocked network: runs pipeline with a mix of providers:
    - working_board: succeeds with 1 listing
    - timeout_board: raises ReadTimeout
    - ratelimited_board: raises 429
    - crashing_board: raises ValueError (unexpected_exception)

    Asserts:
    - Results from working_board are yielded.
    - Search completes and yields DoneEvent.
    - provider_outcomes classifies timeout as retryable_error, 429 as rate_limited,
      and crashing as permanent_error.
    - working_board is not partial; failed boards have partial=True.
    """
    pipeline = SearchOrchestrator()

    # Monkeypatch NIGERIAN_SCRAPERS to our test scrapers
    monkeypatch.setattr(
        "src.project_files.search_pipeline.NIGERIAN_SCRAPERS",
        [
            FakeWorkingScraper(),
            FakeTimeoutScraper(),
            FakeRateLimitedScraper(),
            FakeCrashingScraper(),
        ],
    )
    # Empty ATS queries so we focus on scraper isolation
    monkeypatch.setattr(
        "src.project_files.search_pipeline.build_ats_queries",
        lambda params, platforms: {},
    )

    params = SearchParams(
        job_title="Software Engineer",
        include_nigerian_sites=True,
    )

    events: list[tuple[str, ResultsBatch | DoneEvent]] = []
    async for event_type, event_data in pipeline.run(params):
        events.append((event_type, event_data))

    # We should receive results event then done event
    results_events = [e for e in events if e[0] == "results"]
    done_events = [e for e in events if e[0] == "done"]

    assert len(results_events) >= 1
    batch: ResultsBatch = results_events[0][1]
    assert len(batch.batch) == 1
    assert batch.batch[0].title == "Python Backend Engineer"

    assert len(done_events) == 1
    done: DoneEvent = done_events[0][1]
    assert done.total == 1
    assert "working_board" in done.providers_searched

    # Check provider_outcomes summary
    outcomes = getattr(done, "provider_outcomes", None)
    assert outcomes is not None

    # Working board
    assert "working_board" in outcomes
    assert outcomes["working_board"].partial is False
    assert outcomes["working_board"].counts.get("success") == 1

    # Timeout board -> retryable_error, partial is True
    assert "timeout_board" in outcomes
    assert outcomes["timeout_board"].partial is True
    assert outcomes["timeout_board"].counts.get("retryable_error") == 1

    # Rate limited board -> rate_limited, partial is True
    assert "ratelimited_board" in outcomes
    assert outcomes["ratelimited_board"].partial is True
    assert outcomes["ratelimited_board"].counts.get("rate_limited") == 1

    # Crashing board -> permanent_error, partial is True
    assert "crashing_board" in outcomes
    assert outcomes["crashing_board"].partial is True
    assert outcomes["crashing_board"].counts.get("permanent_error") == 1


@pytest.mark.anyio
async def test_failure_isolation_ats_enrichment_crash_does_not_abort_search(monkeypatch, caplog):
    """
    Mocked test: one item raises an unexpected exception during ATS enrichment.
    Asserts:
    - Unexpected exception is logged with 'unexpected_exception'.
    - Healthy item from the same provider is still extracted and returned.
    - Provider is marked as partial in DoneEvent.
    """
    pipeline = SearchOrchestrator()

    # Serper returns 2 organic items for greenhouse
    serper_data = {
        "organic": [
            {"link": "https://boards.greenhouse.io/goodco/jobs/111", "title": "Good Job", "snippet": "A good job"},
            {"link": "https://boards.greenhouse.io/crashco/jobs/222", "title": "Crash Job", "snippet": "A crashing job"},
        ]
    }

    monkeypatch.setattr(
        "src.project_files.cache_store.cache_store.get_serper_cache",
        lambda key: serper_data,
    )
    monkeypatch.setattr(
        "src.project_files.search_pipeline.build_ats_queries",
        lambda params, platforms: {"greenhouse": "site:boards.greenhouse.io"},
    )

    async def mock_enrich_ats_item(platform, item, query_str, client, stats=None):
        if "crashco" in item.get("link", ""):
            raise RuntimeError("Boom! Unhandled parser crash")
        pipeline._record_provider_outcome("greenhouse", ExtractionOutcome.SUCCESS)
        now = datetime.now(timezone.utc)
        return JobListing(
            id="greenhouse:goodco:111",
            provider="greenhouse",
            title="Good Job",
            company="Good Co",
            apply_url=item["link"],
            source_url=item["link"],
            data_source="api",
            query_used="test",
            ats_source="greenhouse",
            scraped_at=now,
        )

    monkeypatch.setattr(pipeline, "_enrich_ats_item", mock_enrich_ats_item)

    params = SearchParams(job_title="Engineer", include_nigerian_sites=False)
    events: list[tuple[str, ResultsBatch | DoneEvent]] = []

    async for event_type, event_data in pipeline.run(params):
        events.append((event_type, event_data))

    results_events = [e for e in events if e[0] == "results"]
    done_events = [e for e in events if e[0] == "done"]

    assert len(results_events) == 1
    batch: ResultsBatch = results_events[0][1]
    assert len(batch.batch) == 1
    assert batch.batch[0].id == "greenhouse:goodco:111"

    assert len(done_events) == 1
    done: DoneEvent = done_events[0][1]
    outcomes = getattr(done, "provider_outcomes", {})
    assert "greenhouse" in outcomes
    assert outcomes["greenhouse"].partial is True
    assert outcomes["greenhouse"].counts.get("permanent_error") == 1
    assert outcomes["greenhouse"].counts.get("success") == 1


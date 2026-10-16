"""
Comprehensive tests for Phase 5: Cost, Caching, and Robustness.
All tests use mocked transports; no live or paid APIs are called.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import time

import httpx
import pytest

from src.config import settings
from src.project_files.cache_store import CacheStore, cache_store
from src.project_files.http_resilience import (
    CircuitBreakerOpenError,
    ResilienceManager,
    fetch_page_with_cap,
    resilience_manager,
)
from src.project_files.models import (
    DoneEvent,
    JobListing,
    ResultsBatch,
    SearchParams,
)
from src.project_files.retry import with_retry
from src.project_files.search_pipeline import (
    CacheEntry,
    SearchOrchestrator,
    _cache,
    _cache_get,
    _cache_set,
)


def _make_dummy_listing(url: str, provider: str = "greenhouse") -> JobListing:
    return JobListing(
        id=f"{provider}:test:{hash(url)}",
        provider=provider,
        data_source="api",
        title="Test Engineer",
        company="Acme Corp",
        location="Remote",
        is_remote=True,
        employment_type="full_time",
        work_model="remote",
        scraped_at=datetime.now(timezone.utc),
        apply_url=url,
        source_url=url,
        query_used="test query",
        ats_source=provider,
    )


# ---------------------------------------------------------------------------
# B.1: Persistent Serper Cache & In-Memory LRU Cache
# ---------------------------------------------------------------------------


def test_serper_cache_and_ttl():
    cache_store.clear()
    key = "test_serper_key_123"
    data = {"organic": [{"title": "Job 1", "link": "https://boards.greenhouse.io/co/jobs/1"}]}

    # Miss before set
    assert cache_store.get_serper_cache(key) is None

    # Set and hit
    cache_store.set_serper_cache(key, data, ttl_hours=12)
    cached = cache_store.get_serper_cache(key)
    assert cached == data

    # Expired entry (ttl = -1 second)
    cache_store.set_serper_cache("expired_key", data, ttl_hours=-0.01)
    assert cache_store.get_serper_cache("expired_key") is None


def test_in_memory_lru_cap():
    _cache.clear()
    orig_cap = settings.in_memory_cache_max_entries
    try:
        settings.in_memory_cache_max_entries = 3

        # Add 3 entries
        for i in range(1, 4):
            _cache_set(f"k{i}", CacheEntry(results=[], providers_searched=[], serper_queries_used=0))
        assert list(_cache.keys()) == ["k1", "k2", "k3"]

        # Access k1 to move it to MRU
        _cache_get("k1")
        assert list(_cache.keys()) == ["k2", "k3", "k1"]

        # Adding 4th entry evicts oldest (k2)
        _cache_set("k4", CacheEntry(results=[], providers_searched=[], serper_queries_used=0))
        assert "k2" not in _cache
        assert set(_cache.keys()) == {"k1", "k3", "k4"}
    finally:
        settings.in_memory_cache_max_entries = orig_cap
        _cache.clear()


# ---------------------------------------------------------------------------
# B.2: Smart Pagination
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_smart_pagination_stops_when_organic_below_8():
    cache_store.clear()
    orchestrator = SearchOrchestrator()
    calls = []

    def mock_serper(request: httpx.Request):
        payload = json.loads(request.content)
        calls.append(payload.get("page"))
        # Page 1 returns only 5 results (< 8)
        items = [
            {"title": f"Job {i}", "link": f"https://boards.greenhouse.io/co/jobs/{i}"}
            for i in range(5)
        ]
        return httpx.Response(200, json={"organic": items})

    transport = httpx.MockTransport(mock_serper)
    async with httpx.AsyncClient(transport=transport) as client:
        params = SearchParams(job_title="DevOps", include_nigerian_sites=False)
        events = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=client)]

    # Page 2 must NOT be requested because page 1 had < 8 items
    assert calls == [1]
    done = next(e[1] for e in events if e[0] == "done")
    assert isinstance(done, DoneEvent)
    assert done.serper_calls == 1


@pytest.mark.anyio
async def test_smart_pagination_stops_when_less_than_half_are_job_urls():
    cache_store.clear()
    orchestrator = SearchOrchestrator()
    calls = []

    def mock_serper(request: httpx.Request):
        payload = json.loads(request.content)
        calls.append(payload.get("page"))
        # Page 1 returns 10 items, but only 2 parse as real job URLs (< 50%)
        items = [
            {"title": "Job 1", "link": "https://boards.greenhouse.io/co/jobs/1"},
            {"title": "Job 2", "link": "https://boards.greenhouse.io/co/jobs/2"},
        ] + [
            {"title": f"Marketing {i}", "link": f"https://www.teamtailor.com/integrations/app{i}"}
            for i in range(8)
        ]
        return httpx.Response(200, json={"organic": items})

    transport = httpx.MockTransport(mock_serper)
    async with httpx.AsyncClient(transport=transport) as client:
        params = SearchParams(job_title="DevOps", include_nigerian_sites=False)
        events = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=client)]

    # Only 2 out of 10 are job URLs -> stop pagination
    assert calls == [1]


# ---------------------------------------------------------------------------
# B.3: Daily Budget
# ---------------------------------------------------------------------------


def test_daily_budget_counter_and_reset():
    cache_store.clear()
    day1 = "2026-10-15"
    day2 = "2026-10-16"

    # Budget limit = 2
    allowed, count = cache_store.check_and_increment_daily_budget(budget_limit=2, day_utc=day1)
    assert allowed is True and count == 1
    allowed, count = cache_store.check_and_increment_daily_budget(budget_limit=2, day_utc=day1)
    assert allowed is True and count == 2

    # 3rd request on day1 is rejected
    allowed, count = cache_store.check_and_increment_daily_budget(budget_limit=2, day_utc=day1)
    assert allowed is False and count == 2

    # Midnight UTC rolls over to day2: counter resets!
    allowed, count = cache_store.check_and_increment_daily_budget(budget_limit=2, day_utc=day2)
    assert allowed is True and count == 1


@pytest.mark.anyio
async def test_daily_budget_exhaustion_in_orchestrator():
    cache_store.clear()
    orig_budget = settings.serper_daily_budget
    try:
        settings.serper_daily_budget = 1
        orchestrator = SearchOrchestrator()

        def mock_serper(request: httpx.Request):
            items = [{"title": "Job 1", "link": "https://boards.greenhouse.io/co/jobs/1"}]
            return httpx.Response(200, json={"organic": items})

        transport = httpx.MockTransport(mock_serper)
        async with httpx.AsyncClient(transport=transport) as client:
            params = SearchParams(job_title="Software", include_nigerian_sites=False)
            # Run with 2 platforms; 1st platform consumes budget, 2nd hits exhaustion
            events = [e async for e in orchestrator.run(params, platforms=["greenhouse", "lever"], client=client)]

        done = next(e[1] for e in events if e[0] == "done")
        assert isinstance(done, DoneEvent)
        assert done.budget_exhausted is True
        assert done.serper_calls == 1
        assert "exceeded" in (done.message or "").lower()
    finally:
        settings.serper_daily_budget = orig_budget


# ---------------------------------------------------------------------------
# B.4: Dev Replay (SERPER_MODE=live|cache_only)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dev_replay_cache_only_mode():
    cache_store.clear()
    orig_mode = settings.serper_mode
    try:
        settings.serper_mode = "cache_only"
        orchestrator = SearchOrchestrator()

        called = False

        def mock_serper(request: httpx.Request):
            nonlocal called
            called = True
            return httpx.Response(200, json={"organic": []})

        transport = httpx.MockTransport(mock_serper)
        async with httpx.AsyncClient(transport=transport) as client:
            params = SearchParams(job_title="Data Scientist", include_nigerian_sites=False)
            events = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=client)]

        # Serper transport was NOT called
        assert called is False
        done = next(e[1] for e in events if e[0] == "done")
        assert done.serper_calls == 0
        assert done.total == 0
    finally:
        settings.serper_mode = orig_mode


# ---------------------------------------------------------------------------
# C.1: Disconnects
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_orchestrator_cancels_on_client_disconnect():
    cache_store.clear()
    orchestrator = SearchOrchestrator()

    is_disconnected_state = False

    async def check_disconnect():
        return is_disconnected_state

    async def slow_serper(platform, query, params, client, **kwargs):
        await asyncio.sleep(0.5)
        return (platform, [], True)

    orchestrator._search_ats_serper = slow_serper

    params = SearchParams(job_title="DisconnectTest", include_nigerian_sites=False)

    # Disconnect right after starting
    is_disconnected_state = True
    events = [
        event
        async for event in orchestrator.run(
            params,
            platforms=["greenhouse", "lever"],
            is_disconnected=check_disconnect,
        )
    ]

    # Pipeline cancelled and exited promptly without hanging
    assert len(events) == 0


# ---------------------------------------------------------------------------
# C.2: Concurrency & Semaphores
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_concurrency_semaphores_limit():
    mgr = ResilienceManager()
    active_global = 0
    peak_global = 0
    active_host = 0
    peak_host = 0

    async def worker(url):
        nonlocal active_global, peak_global, active_host, peak_host
        async with mgr.throttle(url):
            active_global += 1
            active_host += 1
            peak_global = max(peak_global, active_global)
            peak_host = max(peak_host, active_host)
            await asyncio.sleep(0.02)
            active_global -= 1
            active_host -= 1

    urls = ["https://boards.greenhouse.io/job/1"] * 10
    await asyncio.gather(*(worker(u) for u in urls))

    # Default per-host semaphore is 3
    assert peak_host <= settings.per_host_concurrency_limit
    assert peak_global <= settings.global_concurrency_limit


# ---------------------------------------------------------------------------
# C.3: Per-URL Cache
# ---------------------------------------------------------------------------


def test_url_cache_stores_and_expires():
    cache_store.clear()
    url = "https://boards.greenhouse.io/acme/jobs/12345"
    listing = _make_dummy_listing(url)

    assert cache_store.get_url_cache(url) is None

    cache_store.set_url_cache(url, listing, ttl_hours=24)
    cached = cache_store.get_url_cache(url)
    assert cached is not None
    assert cached.apply_url == url
    assert cached.title == listing.title

    # Expiration
    cache_store.set_url_cache(url, listing, ttl_hours=-0.1)
    assert cache_store.get_url_cache(url) is None


# ---------------------------------------------------------------------------
# C.4: Retries (429, 5xx, timeouts, Retry-After, no 4xx retries)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retry_on_429_with_retry_after():
    attempt_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def fetch_with_429():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            resp = httpx.Response(429, headers={"Retry-After": "0.01"})
            raise httpx.HTTPStatusError("Rate limited", request=None, response=resp)
        return "success"

    res = await fetch_with_429()
    assert res == "success"
    assert attempt_count == 2


@pytest.mark.anyio
async def test_no_retry_on_404_or_403():
    attempt_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def fetch_404():
        nonlocal attempt_count
        attempt_count += 1
        resp = httpx.Response(404)
        raise httpx.HTTPStatusError("Not found", request=None, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        await fetch_404()

    # Must raise immediately on 1st attempt, zero retries
    assert attempt_count == 1


# ---------------------------------------------------------------------------
# C.5: Circuit Breaker per host
# ---------------------------------------------------------------------------


def test_circuit_breaker_trips_after_5_failures():
    mgr = ResilienceManager()
    host = "flakey.host.com"

    for _ in range(4):
        mgr.record_failure(host)
        assert mgr.is_host_open(host) is True

    # 5th failure trips the breaker
    mgr.record_failure(host)
    assert mgr.is_host_open(host) is False

    # Skips are counted
    skips = mgr.get_skips_by_host()
    assert skips.get(host) == 1


@pytest.mark.anyio
async def test_one_failing_platform_does_not_fail_or_hang_whole_search():
    cache_store.clear()
    orchestrator = SearchOrchestrator()

    async def mixed_serper(platform, query, params, client, **kwargs):
        if platform == "greenhouse":
            raise RuntimeError("Greenhouse API exploded")
        dummy = _make_dummy_listing(f"https://jobs.lever.co/acme/1", provider=platform)
        return (platform, [dummy], True)

    orchestrator._search_ats_serper = mixed_serper
    params = SearchParams(job_title="Engineer", include_nigerian_sites=False)
    events = [event async for event in orchestrator.run(params, platforms=["greenhouse", "lever"])]

    # Lever completed successfully despite greenhouse failing
    results = next(e[1] for e in events if e[0] == "results")
    assert isinstance(results, ResultsBatch)
    assert len(results.batch) == 1
    assert results.batch[0].provider == "lever"

    done = next(e[1] for e in events if e[0] == "done")
    assert isinstance(done, DoneEvent)
    assert done.total == 1


# ---------------------------------------------------------------------------
# C.6: Response Size Cap (3 MB)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_response_size_cap_truncates_at_3mb():
    chunk_1mb = "a" * (1024 * 1024)

    def large_page_handler(request: httpx.Request):
        # 5 MB of content
        return httpx.Response(200, text=chunk_1mb * 5)

    transport = httpx.MockTransport(large_page_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status, text, _ = await fetch_page_with_cap(
            client,
            "https://jobs.example.com/huge-listing",
            max_bytes=3 * 1024 * 1024,
        )

    assert status == 200
    # Length capped at 3 MB
    assert len(text.encode("utf-8")) == 3 * 1024 * 1024

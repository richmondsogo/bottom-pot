"""Offline tests for raised search caps, Serper budgeting, boundary canonicalization, single-flight, and cache v2."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from src.core.models import DoneEvent, JobListing, SearchParams
from src.core.settings import ATS_PLATFORMS, settings
from src.discovery.query_builder import QueryBuilder, build_ats_queries, build_ats_query
from src.discovery.search_canonicalizer import (
    build_serper_cache_key,
    canonicalize_country_code,
    canonicalize_location,
    canonicalize_platforms,
    canonicalize_query_text,
    canonicalize_search_request,
    compute_effective_max_results,
)
from src.discovery.search_pipeline import (
    SearchOrchestrator,
    _cache,
    _cache_key,
)
from src.storage.cache_store import URL_CACHE_VERSION, CacheStore, cache_store
from src.storage.company_board_registry import CompanyBoardRegistry


def _make_listing(idx: int, provider: str = "greenhouse", title: str = "Backend Engineer") -> JobListing:
    url = f"https://boards.greenhouse.io/acme/jobs/{idx}"
    return JobListing(
        id=f"{provider}:acme:{idx}",
        provider=provider,
        ats_source=provider,
        data_source="api",
        title=f"{title} {idx}",
        company="Acme",
        company_slug="acme",
        location="Remote",
        is_remote=True,
        work_model="remote",
        apply_url=url,
        source_url=url,
        query_used="backend engineer",
        posted_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# C3: Boundary Canonicalization & Downstream Query Builder Consistency
# ---------------------------------------------------------------------------


def test_canonicalize_query_text_preserves_token_order_and_normalizes():
    variants = [
        "backend engineer",
        "Backend Engineer",
        "  backend   engineer ",
        "\uff22ackend\u00a0\u00a0\uff25ngineer",
    ]
    assert len({canonicalize_query_text(v) for v in variants}) == 1
    assert canonicalize_query_text("  Backend   Engineer ") == "backend engineer"

    # Curly quotes, dashes, separator spacing, NFKC ligature
    assert canonicalize_query_text("UI / UX  \u2014  \u201c\ufb01nance\u201d \u201926") == 'ui/ux - "finance" \'26'
    assert canonicalize_location("  Lagos ,  Nigeria ") == "lagos, nigeria"
    assert canonicalize_location("   ") is None
    assert canonicalize_country_code("  US ") == "us"
    assert canonicalize_country_code("  ") is None

    # Token order MUST be preserved
    assert canonicalize_query_text("backend engineer") != canonicalize_query_text("engineer backend")


def test_canonicalize_search_request_does_not_mutate_and_preserves_fields_set():
    orig = SearchParams(
        job_title="  Backend   Engineer ",
        location=" Lagos , Nigeria ",
        country_code=" NG ",
        applicant_country=" US ",
        exclude_keywords=["Intern", "contract", " intern "],
        experience_level=" Senior ",
        days_back=0,
    )
    orig_platforms = ["Lever", "greenhouse", "lever"]

    canon_params, canon_platforms = canonicalize_search_request(orig, orig_platforms)

    # Original inputs untouched
    assert orig.job_title == "  Backend   Engineer "
    assert orig.location == " Lagos , Nigeria "
    assert orig.exclude_keywords == ["Intern", "contract", " intern "]
    assert orig.days_back == 0
    assert orig_platforms == ["Lever", "greenhouse", "lever"]

    # Canonical outputs normalized
    assert canon_params.job_title == "backend engineer"
    assert canon_params.location == "lagos, nigeria"
    assert canon_params.country_code == "ng"
    assert canon_params.applicant_country == "us"
    assert canon_params.exclude_keywords == ["contract", "intern"]
    assert canon_params.experience_level == "senior"
    assert canon_params.days_back == 7
    assert canon_platforms == ["greenhouse", "lever"]
    assert "max_results" not in canon_params.model_fields_set

    # platforms None vs [] preserved
    assert canonicalize_platforms(None) is None
    assert canonicalize_platforms([]) == []


def test_query_builder_byte_identical_across_query_variants():
    variants = [
        SearchParams(job_title="backend engineer", location="New York", exclude_keywords=["Intern", "Senior"]),
        SearchParams(job_title="Backend Engineer", location="  new  york ", exclude_keywords=["senior", "intern"]),
        SearchParams(job_title="  backend   engineer ", location="New\u00a0York", exclude_keywords=["INTERN", "senior"]),
    ]

    direct_queries = {build_ats_query("boards.greenhouse.io", v) for v in variants}
    assert len(direct_queries) == 1

    all_queries = {tuple(sorted(build_ats_queries(v).items())) for v in variants}
    assert len(all_queries) == 1

    qb = QueryBuilder(ATS_PLATFORMS[0])
    cli_queries = {qb.build_query_string(v) for v in variants}
    assert len(cli_queries) == 1

    # Token order preserved
    reordered = SearchParams(job_title="engineer backend", location="New York", exclude_keywords=["intern", "senior"])
    assert build_ats_query("boards.greenhouse.io", reordered) != build_ats_query("boards.greenhouse.io", variants[0])


# ---------------------------------------------------------------------------
# C3: Cache Key Equivalence & Invalidation + Serper v2 + URL Cache v2
# ---------------------------------------------------------------------------


def test_cache_key_equivalence_and_invalidation(monkeypatch, tmp_path):
    reg = CompanyBoardRegistry(db_path=str(tmp_path / "cache_key_reg.sqlite"))
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)

    p1 = SearchParams(job_title="backend engineer", days_back=7)
    p2 = SearchParams(job_title="Backend Engineer", days_back=None)
    p3 = SearchParams(job_title="  backend   engineer ", days_back=0, applicant_country="NG")
    assert _cache_key(p1) == _cache_key(p2) == _cache_key(p3)
    assert _cache_key(p1, ["Lever", "greenhouse"]) == _cache_key(p2, ["greenhouse", "lever", "lever"])

    # Token order differs
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="engineer backend"))

    # Distinguishes platforms None vs [] vs explicit list
    assert _cache_key(p1, None) != _cache_key(p1, [])
    assert _cache_key(p1, []) != _cache_key(p1, ["greenhouse"])

    # Invalidated by result-affecting fields
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", country_code="us"))
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", remote=True))
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", days_back=14))
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", max_results=20))
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", include_nigerian_sites=False))
    assert _cache_key(p1) != _cache_key(SearchParams(job_title="backend engineer", live_discovery=True))

    # Invalidated by relevance_mode, serper_mode, store_ver
    base_key = _cache_key(p1)
    monkeypatch.setattr(settings, "relevance_mode", "off")
    assert _cache_key(p1) != base_key
    monkeypatch.setattr(settings, "relevance_mode", "filter")

    monkeypatch.setattr(settings, "serper_mode", "fallback")
    assert _cache_key(p1) != base_key
    monkeypatch.setattr(settings, "serper_mode", "live")

    reg.upsert_monitored_job(_make_listing(1))
    assert _cache_key(p1) != base_key


def test_serper_cache_key_v2_hashes_full_sorted_payload():
    p_a = {"q": 'site:greenhouse.io "backend"', "page": 1, "num": 10, "hl": "en", "tbs": "qdr:d7", "gl": "us"}
    p_b = {"gl": "us", "tbs": "qdr:d7", "hl": "en", "num": 10, "page": 1, "q": 'site:greenhouse.io "backend"'}
    k_a = build_serper_cache_key(p_a)
    k_b = build_serper_cache_key(p_b)
    assert k_a.startswith("serper-v2:")
    assert k_a == k_b

    assert k_a != build_serper_cache_key({**p_a, "hl": "fr"})
    assert k_a != build_serper_cache_key({**p_a, "num": 20})
    assert k_a != build_serper_cache_key({**p_a, "gl": "ng"})


def test_url_cache_v2_invalidates_legacy_unversioned_rows(tmp_path: Path):
    db_file = str(tmp_path / "url_v2.sqlite")
    store = CacheStore(db_path=db_file)
    url = "https://www.myjobmag.com/job/backend-engineer-lagos"
    legacy_listing = _make_listing(99, provider="myjobmag", title="Legacy Jumbled Title")
    fresh_listing = _make_listing(99, provider="myjobmag", title="Fresh Clean Title")

    # Seed legacy unversioned row directly (missing _url_cache_version)
    now = time.time()
    with store._get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (url, legacy_listing.model_dump_json(), now, now + 3600),
        )
        conn.commit()

    # Legacy row is invalidated immediately on single and batch reads
    assert store.get_url_cache(url, provider="myjobmag") is None
    assert store.get_url_cache_batch([url], provider="myjobmag") == {}

    # Fresh write stores URL_CACHE_VERSION and is not polluted by legacy row
    store.set_url_cache(url, fresh_listing, provider="myjobmag")
    got = store.get_url_cache(url)
    assert got is not None
    assert got.title == "Fresh Clean Title 99"
    got_batch = store.get_url_cache_batch([url])
    assert got_batch[url].title == "Fresh Clean Title 99"

    with store._get_connection() as conn:
        raw = conn.execute("SELECT listing_json FROM url_cache WHERE url = ?", (url,)).fetchone()[0]
    assert json.loads(raw)["_url_cache_version"] == URL_CACHE_VERSION


# ---------------------------------------------------------------------------
# C3: Single-Flight Concurrency, Disconnect Isolation & Non-Caching Guards
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_single_flight_coalesces_concurrent_equivalent_searches(monkeypatch):
    _cache.clear()
    cache_store.clear()
    orchestrator = SearchOrchestrator()
    call_count = 0

    async def slow_serper(platform, query_str, params, client, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return (platform, [_make_listing(101, provider=platform)], True)

    monkeypatch.setattr(orchestrator, "_search_ats_serper", slow_serper)
    monkeypatch.setattr(orchestrator, "_search_monitored_store", lambda *a, **kw: asyncio.sleep(0, result=("monitored_store", [], False)))

    async def collect(params: SearchParams):
        items: list[JobListing] = []
        done: DoneEvent | None = None
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for ev, payload in orchestrator.run(params, platforms=["greenhouse"], client=client):
                if ev == "results":
                    items.extend(payload.batch)
                elif ev == "done":
                    done = payload
        return items, done

    p_leader = SearchParams(job_title="Backend Engineer", include_nigerian_sites=False, applicant_country="NG")
    p_follower = SearchParams(job_title="  backend   engineer ", include_nigerian_sites=False, applicant_country="DE")

    (res_a, done_a), (res_b, done_b) = await asyncio.gather(collect(p_leader), collect(p_follower))

    assert call_count == 1
    assert len(res_a) == 1 and len(res_b) == 1
    assert done_a is not None and done_b is not None
    assert done_b.serper_calls == 0
    assert res_a[0].eligibility is not None and res_a[0].eligibility.applicant_assessment.applicant_country_code == "NG"
    assert res_b[0].eligibility is not None and res_b[0].eligibility.applicant_assessment.applicant_country_code == "DE"


@pytest.mark.anyio
async def test_single_flight_follower_disconnect_does_not_cancel_leader(monkeypatch):
    _cache.clear()
    orchestrator = SearchOrchestrator()
    leader_finished = False

    async def slow_serper(platform, query_str, params, client, **kwargs):
        nonlocal leader_finished
        await asyncio.sleep(0.15)
        leader_finished = True
        return (platform, [_make_listing(202, provider=platform)], True)

    monkeypatch.setattr(orchestrator, "_search_ats_serper", slow_serper)

    async def run_leader():
        done = None
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for ev, payload in orchestrator.run(
                SearchParams(job_title="SingleFlight LeaderKeep", include_nigerian_sites=False),
                platforms=["greenhouse"],
                client=client,
            ):
                if ev == "done":
                    done = payload
        return done

    async def run_follower():
        await asyncio.sleep(0.02)
        events = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for ev in orchestrator.run(
                SearchParams(job_title="  singleflight   leaderkeep ", include_nigerian_sites=False),
                platforms=["greenhouse"],
                is_disconnected=lambda: asyncio.sleep(0, result=True),
                client=client,
            ):
                events.append(ev)
        return events

    leader_done, follower_events = await asyncio.gather(run_leader(), run_follower())
    assert leader_finished is True
    assert leader_done is not None and leader_done.total == 1
    assert follower_events == []


@pytest.mark.anyio
async def test_single_flight_leader_cancel_and_failure_do_not_poison_follower(monkeypatch):
    _cache.clear()
    orchestrator = SearchOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "_search_monitored_store",
        lambda *a, **kw: asyncio.sleep(0, result=("monitored_store", [], False)),
    )

    # Path 1: Leader transient failure (no disconnect) -> follower retries cleanly without 0-result poisoning
    attempt = 0
    leader_entered = asyncio.Event()

    async def serper_flaky_then_ok(platform, query_str, params, client, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            leader_entered.set()
            await asyncio.sleep(0.05)
            raise RuntimeError("Leader crashed")
        return (platform, [_make_listing(303, provider=platform)], True)

    monkeypatch.setattr(orchestrator, "_search_ats_serper", serper_flaky_then_ok)

    async def leader_fail():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for _ in orchestrator.run(
                SearchParams(job_title="LeaderCancelTest", include_nigerian_sites=False),
                platforms=["greenhouse"],
                client=client,
            ):
                pass

    async def follower_after_failure():
        await leader_entered.wait()
        results = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for ev, payload in orchestrator.run(
                SearchParams(job_title="leadercanceltest", include_nigerian_sites=False),
                platforms=["greenhouse"],
                client=client,
            ):
                if ev == "results":
                    results.extend(payload.batch)
        return results

    _, follower_res = await asyncio.gather(leader_fail(), follower_after_failure())
    assert attempt == 2
    assert len(follower_res) == 1
    assert follower_res[0].id == "greenhouse:acme:303"
    assert orchestrator._inflight._inflight == {}

    # Path 2: Leader disconnect cancellation -> follower retries cleanly
    _cache.clear()
    leader_entered_cancel = asyncio.Event()
    leader_disconnect = False
    cancel_attempt = 0

    async def serper_slow_then_ok(platform, query_str, params, client, **kwargs):
        nonlocal cancel_attempt
        cancel_attempt += 1
        if cancel_attempt == 1:
            leader_entered_cancel.set()
            await asyncio.sleep(1.5)
        return (platform, [_make_listing(304, provider=platform)], True)

    monkeypatch.setattr(orchestrator, "_search_ats_serper", serper_slow_then_ok)

    async def leader_cancel():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for _ in orchestrator.run(
                SearchParams(job_title="LeaderDisconnectTest", include_nigerian_sites=False),
                platforms=["greenhouse"],
                is_disconnected=lambda: asyncio.sleep(0, result=leader_disconnect),
                client=client,
            ):
                pass

    async def follower_after_cancel():
        await leader_entered_cancel.wait()
        nonlocal leader_disconnect
        leader_disconnect = True
        results = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
            async for ev, payload in orchestrator.run(
                SearchParams(job_title="leaderdisconnecttest", include_nigerian_sites=False),
                platforms=["greenhouse"],
                client=client,
            ):
                if ev == "results":
                    results.extend(payload.batch)
        return results

    _, follower_res_2 = await asyncio.gather(leader_cancel(), follower_after_cancel())
    assert cancel_attempt == 2
    assert len(follower_res_2) == 1
    assert follower_res_2[0].id == "greenhouse:acme:304"
    assert orchestrator._inflight._inflight == {}


@pytest.mark.anyio
async def test_never_caches_failures_budget_exhaustion_or_hard_timeouts(monkeypatch):
    _cache.clear()
    cache_store.clear()
    orchestrator = SearchOrchestrator()
    monkeypatch.setattr(settings, "serper_api_key", "fake-key")
    monkeypatch.setattr(settings, "serper_mode", "live")

    # 1. Transient Serper 500 error -> NOT cached (even with partial results or empty)
    def error_handler(_req: httpx.Request):
        return httpx.Response(500)

    params_err = SearchParams(job_title="TransientErrorNoCache", include_nigerian_sites=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(error_handler)) as client:
        events = [e async for e in orchestrator.run(params_err, platforms=["greenhouse"], client=client)]
    done_err = next(p for ev, p in events if ev == "done")
    assert done_err.partial is True
    assert _cache_key(params_err, ["greenhouse"]) not in _cache

    # Subsequent healthy run on SAME orchestrator is NOT poisoned with partial=True
    def ok_handler(req: httpx.Request):
        if "google.serper.dev" in str(req.url):
            return httpx.Response(200, json={"organic": [{"title": "Role", "link": "https://boards.greenhouse.io/acme/jobs/1"}]})
        return httpx.Response(200, json={"id": 1, "title": "TransientErrorNoCache", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "location": {"name": "Remote"}, "content": "<p>Build systems</p>"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        events_ok = [e async for e in orchestrator.run(params_err, platforms=["greenhouse"], client=client)]
    done_ok = next(p for ev, p in events_ok if ev == "done")
    assert done_ok.partial is False
    assert _cache_key(params_err, ["greenhouse"]) in _cache

    # 2. Budget exhaustion -> NOT cached
    _cache.clear()
    cache_store.clear()
    monkeypatch.setattr(settings, "serper_daily_budget", 1)
    params_budget = SearchParams(job_title="BudgetExhaustNoCache", include_nigerian_sites=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        events_b = [e async for e in orchestrator.run(params_budget, platforms=["greenhouse", "lever"], client=client)]
    done_b = next(p for ev, p in events_b if ev == "done")
    assert done_b.budget_exhausted is True
    assert _cache_key(params_budget, ["greenhouse", "lever"]) not in _cache

    # 3. Hard timeout -> NOT cached
    _cache.clear()
    monkeypatch.setattr(settings, "search_hard_timeout_seconds", 0.05)

    async def hanging_serper(platform, query_str, params, client, **kwargs):
        await asyncio.sleep(1.0)
        return (platform, [_make_listing(999, provider=platform)], True)

    monkeypatch.setattr(orchestrator, "_search_ats_serper", hanging_serper)
    params_to = SearchParams(job_title="TimeoutNoCache", include_nigerian_sites=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(404))) as client:
        events_to = [e async for e in orchestrator.run(params_to, platforms=["greenhouse"], client=client)]
    assert any(ev == "done" for ev, _ in events_to)
    assert _cache_key(params_to, ["greenhouse"]) not in _cache


# ---------------------------------------------------------------------------
# C2: Raised Configurable Caps & Per-Search Serper Query Cap Enforcement
# ---------------------------------------------------------------------------


def test_raised_settings_defaults_and_effective_max_results():
    assert settings.max_results == 300
    assert settings.monitored_store_max_results == 200
    assert settings.nigerian_per_scraper_cap == 30
    assert settings.nigerian_total_cap == 75
    assert settings.serper_max_pages == 5
    assert settings.max_serper_queries_per_search == 60
    assert settings.serper_daily_budget == 500
    assert settings.serper_fallback_min_results == 25
    assert settings.serper_mode == "live"

    # Omitting max_results uses settings.max_results (300) despite SearchParams.max_results=100 default
    omitted = SearchParams(job_title="Backend Engineer")
    assert omitted.max_results == 100
    assert "max_results" not in omitted.model_fields_set
    assert compute_effective_max_results(omitted, settings.max_results) == 300

    # Explicit smaller max_results honored; larger clamped to settings.max_results
    explicit_small = SearchParams(job_title="Backend Engineer", max_results=20)
    assert compute_effective_max_results(explicit_small, settings.max_results) == 20
    explicit_large = SearchParams(job_title="Backend Engineer", max_results=500)
    assert compute_effective_max_results(explicit_large, settings.max_results) == 300


@pytest.mark.anyio
async def test_max_serper_queries_per_search_enforced_and_monitored_store_cap(monkeypatch, tmp_path):
    _cache.clear()
    cache_store.clear()
    monkeypatch.setattr(settings, "serper_api_key", "fake-key")
    monkeypatch.setattr(settings, "serper_mode", "live")
    monkeypatch.setattr(settings, "serper_max_pages", 5)
    monkeypatch.setattr(settings, "max_serper_queries_per_search", 3)
    monkeypatch.setattr(settings, "serper_daily_budget", 500)

    serper_requests = 0

    def serper_handler(req: httpx.Request):
        nonlocal serper_requests
        if "google.serper.dev" in str(req.url):
            serper_requests += 1
            # Return 10 valid URLs so smart pagination wants to fetch next pages
            body = json.loads(req.content)
            page = body["page"]
            items = [
                {"title": f"Backend {page}-{i}", "link": f"https://boards.greenhouse.io/co/jobs/{page}{i}"}
                for i in range(10)
            ]
            return httpx.Response(200, json={"organic": items})
        return httpx.Response(404)

    orchestrator = SearchOrchestrator()
    monkeypatch.setattr(orchestrator, "_enrich_ats_item", lambda *a, **kw: asyncio.sleep(0, result=None))
    params = SearchParams(job_title="Backend Cap Enforce", include_nigerian_sites=False)

    async with httpx.AsyncClient(transport=httpx.MockTransport(serper_handler)) as client:
        events = [
            e
            async for e in orchestrator.run(
                params,
                platforms=["greenhouse", "lever", "ashby", "workable", "smartrecruiters"],
                client=client,
            )
        ]

    done = next(p for ev, p in events if ev == "done")
    assert serper_requests == 3
    assert done.serper_calls == 3
    assert cache_store.get_daily_budget_count() == 3

    # Monitored store cap > 50 honored up to monitored_store_max_results (200)
    reg = CompanyBoardRegistry(db_path=str(tmp_path / "mon_cap.sqlite"))
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)
    now = datetime.now(timezone.utc)
    jobs = [
        JobListing(
            id=f"greenhouse:acme:{i}",
            provider="greenhouse",
            ats_source="greenhouse",
            data_source="api",
            title=f"Backend Engineer {i}",
            company="Acme",
            company_slug="acme",
            apply_url=f"https://boards.greenhouse.io/acme/jobs/{i}",
            source_url=f"https://boards.greenhouse.io/acme/jobs/{i}",
            posted_at=now,
            scraped_at=now,
            query_used="acme",
        )
        for i in range(80)
    ]
    reg.upsert_monitored_jobs_batch(jobs)
    _, mon_results, _ = await orchestrator._search_monitored_store(
        SearchParams(job_title="Backend Engineer"),
        platforms=["greenhouse"],
    )
    assert len(mon_results) == 80

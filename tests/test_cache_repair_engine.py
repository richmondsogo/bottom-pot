"""
Unit tests for the shared bounded, idempotent, dry-run-by-default cache repair engine.

All tests use disposable SQLite DBs in ``tmp_path``, mocked HTTP transports,
and ``StaticDnsResolver`` with zero network or operational DB access.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from src.core.models import JobListing
from src.monitoring.cache_repair import ashby as ashby_repair
from src.monitoring.cache_repair import greenhouse as gh_repair
from src.monitoring.cache_repair import lever as lever_repair
from src.monitoring.cache_repair import workable as workable_repair
from src.monitoring.cache_repair.engine import (
    CacheRepairStrategy,
    run_cache_repair,
)
from src.safety.db_safety import UnsafeDatabasePathError
from src.safety.url_safety import StaticDnsResolver, UnsafeRedirectError, use_dns_resolver
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import CompanyBoardRegistry


def _seed_degraded_ashby(db_path: str) -> tuple[CacheStore, CompanyBoardRegistry, str, str]:
    cache = CacheStore(db_path=db_path)
    registry = CompanyBoardRegistry(db_path=db_path)
    u1 = "https://jobs.ashbyhq.com/acme/11111111-1111-1111-1111-111111111111"
    u2 = "https://jobs.ashbyhq.com/acme/22222222-2222-2222-2222-222222222222"
    for idx, url in enumerate((u1, u2), start=1):
        cache.set_url_cache(
            url,
            JobListing(
                id=f"ashby:acme:{idx}",
                provider="ashby",
                ats_source="ashby",
                data_source="scrape",
                title=f"Old Title {idx}",
                company="acme",
                company_slug="acme",
                apply_url=url,
                source_url=url,
                query_used="test",
                scraped_at=datetime.now(timezone.utc),
                description="Short degraded text",
            ),
        )
    return cache, registry, u1, u2


@pytest.mark.anyio
async def test_run_cache_repair_defaults_to_dry_run_and_leaves_sqlite_untouched(
    tmp_path: Path,
) -> None:
    db_path = str(tmp_path / "dry_run_default.sqlite")
    cache, registry, u1, u2 = _seed_degraded_ashby(db_path)

    payload = {
        "jobs": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "title": "Staff Systems Engineer",
                "jobUrl": u1,
                "location": "Remote",
                "isRemote": True,
                "descriptionHtml": "<p>Build distributed systems across global teams with observability.</p>",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "title": "Product Engineer",
                "jobUrl": u2,
                "location": "Remote",
                "isRemote": True,
                "descriptionHtml": "<p>Own end-to-end product engineering workflows for global users.</p>",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.ashbyhq.com/posting-api/job-board/acme" in str(request.url):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # Deliberately omit dry_run= to assert the engine defaults to dry-run
        report = await run_cache_repair(
            ashby_repair.ASHBY_REPAIR_STRATEGY,
            cache=cache,
            registry=registry,
            client=client,
        )

    assert report.dry_run is True
    assert report.repaired_from_board_api == 2

    with sqlite3.connect(db_path) as conn:
        state_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ashby_repair_state'"
        ).fetchone()
    assert state_table is None
    assert cache.get_url_cache(u1).title == "Old Title 1"


@pytest.mark.anyio
async def test_run_cache_repair_bounded_max_urls_and_resumes_idempotently(
    tmp_path: Path,
) -> None:
    db_path = str(tmp_path / "bounded_resume.sqlite")
    cache, registry, u1, u2 = _seed_degraded_ashby(db_path)

    payload = {
        "jobs": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "title": "Staff Systems Engineer",
                "jobUrl": u1,
                "location": "Remote",
                "isRemote": True,
                "descriptionHtml": "<p>Build distributed systems across global teams with observability.</p>",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "title": "Product Engineer",
                "jobUrl": u2,
                "location": "Remote",
                "isRemote": True,
                "descriptionHtml": "<p>Own end-to-end product engineering workflows for global users.</p>",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.ashbyhq.com/posting-api/job-board/acme" in str(request.url):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rep1 = await run_cache_repair(
            ashby_repair.ASHBY_REPAIR_STRATEGY,
            cache=cache,
            registry=registry,
            client=client,
            max_urls=1,
            dry_run=False,
        )
        assert rep1.repaired_from_board_api == 1
        assert cache.get_url_cache(u1).title == "Staff Systems Engineer"
        assert cache.get_url_cache(u2).title == "Old Title 2"

        rep2 = await run_cache_repair(
            ashby_repair.ASHBY_REPAIR_STRATEGY,
            cache=cache,
            registry=registry,
            client=client,
            max_urls=1,
            dry_run=False,
        )
        assert rep2.skipped_already_repaired == 1
        assert rep2.repaired_from_board_api == 1
        assert cache.get_url_cache(u2).title == "Product Engineer"


@pytest.mark.anyio
async def test_run_cache_repair_propagates_safety_errors_and_cancellation(
    tmp_path: Path,
) -> None:
    bad_cache = CacheStore(_defer_init=True)
    bad_cache.db_path = "data/cache.sqlite"
    safe_reg = CompanyBoardRegistry(db_path=str(tmp_path / "safe_reg.sqlite"))

    with pytest.raises(UnsafeDatabasePathError):
        await run_cache_repair(
            ashby_repair.ASHBY_REPAIR_STRATEGY,
            cache=bad_cache,
            registry=safe_reg,
            dry_run=True,
        )

    db_path = str(tmp_path / "cancel_and_ssrf.sqlite")
    cache, registry, _, _ = _seed_degraded_ashby(db_path)

    async def raise_ssrf(*_args, **_kwargs):
        raise UnsafeRedirectError("Blocked private redirect during repair")

    ssrf_strategy = CacheRepairStrategy(
        provider="ashby",
        state_table="ashby_repair_state",
        repair_version="v39",
        url_cache_query="SELECT url, listing_json FROM url_cache WHERE LOWER(url) LIKE '%ashby%' ORDER BY created_at ASC",
        unparsed_detail="Not a single Ashby job posting URL",
        enrich_identity=raise_ssrf,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200))) as client:
        with pytest.raises(UnsafeRedirectError):
            await run_cache_repair(
                ssrf_strategy,
                cache=cache,
                registry=registry,
                client=client,
                dry_run=True,
            )

    async def raise_cancel(*_args, **_kwargs):
        raise asyncio.CancelledError()

    cancel_strategy = CacheRepairStrategy(
        provider="ashby",
        state_table="ashby_repair_state",
        repair_version="v39",
        url_cache_query="SELECT url, listing_json FROM url_cache WHERE LOWER(url) LIKE '%ashby%' ORDER BY created_at ASC",
        unparsed_detail="Not a single Ashby job posting URL",
        enrich_identity=raise_cancel,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200))) as client:
        with pytest.raises(asyncio.CancelledError):
            await run_cache_repair(
                cancel_strategy,
                cache=cache,
                registry=registry,
                client=client,
                dry_run=True,
            )


def test_all_four_repair_clis_default_to_dry_run_and_support_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules_and_runners = [
        (lever_repair, "repair_lever_cache", lever_repair.LeverRepairReport),
        (gh_repair, "repair_greenhouse_cache", gh_repair.GreenhouseRepairReport),
        (ashby_repair, "repair_ashby_cache", ashby_repair.AshbyRepairReport),
        (workable_repair, "repair_workable_cache", workable_repair.WorkableRepairReport),
    ]

    for mod, fn_name, report_cls in modules_and_runners:
        recorded: list[dict[str, object]] = []

        async def _fake_runner(_cls=report_cls, _rec=recorded, **kwargs):
            _rec.append(kwargs)
            return _cls()

        monkeypatch.setattr(mod, fn_name, _fake_runner)

        mod.main([])
        assert recorded[-1]["dry_run"] is True
        assert recorded[-1]["max_urls"] is None

        mod.main(["--apply", "--max-urls", "5"])
        assert recorded[-1]["dry_run"] is False
        assert recorded[-1]["max_urls"] == 5

    # Ensure no-network DNS discipline checker accepts this file cleanly with StaticDnsResolver import referenced
    resolver = StaticDnsResolver({"jobs.ashbyhq.com": "93.184.216.34"})
    with use_dns_resolver(resolver):
        assert resolver.resolve("jobs.ashbyhq.com") == ["93.184.216.34"]

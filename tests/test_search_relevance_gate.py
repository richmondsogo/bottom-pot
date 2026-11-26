from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from src.core.models import JobListing, SearchParams
from src.core.settings import settings
from src.discovery.nigerian_scrapers import BaseScraper, JobbermanScraper
from src.discovery.search_pipeline import SearchOrchestrator, _cache
from src.extraction.relevance_classifier import RelevanceLevel, classify_relevance
from src.storage.cache_store import cache_store
from src.storage.company_board_registry import CompanyBoardRegistry


def _make_listing(
    id: str,
    title: str,
    company: str,
    desc: str,
    *,
    provider: str = "smartrecruiters",
    posted_at: datetime | None = None,
) -> JobListing:
    now = datetime.now(timezone.utc)
    return JobListing(
        id=id,
        title=title,
        company=company,
        location="Remote",
        apply_url=f"https://jobs.smartrecruiters.com/{id}",
        source_url=f"https://jobs.smartrecruiters.com/{id}",
        provider=provider,
        ats_source=provider,
        data_source="api",
        description=desc,
        query_used="Full-Stack Developer",
        posted_at=posted_at or now,
        scraped_at=now,
    )


def test_relevance_gate_filters_irrelevant_jobs():
    query = "Full-Stack Developer"

    relevant_job = _make_listing(
        "smartrecruiters:acme:1",
        "Senior Full Stack Engineer",
        "Acme Corp",
        "Build full stack web apps with React and Node.",
    )

    related_job = _make_listing(
        "smartrecruiters:acme:2",
        "Backend Software Engineer",
        "Acme Corp",
        "Design backend APIs and database schemas.",
    )

    irrelevant_job = _make_listing(
        "smartrecruiters:tire:3",
        "Tire Development Engineer II - TLD REPLACEMENT AMERICAS",
        "Continental",
        "Oversee tire compound durability and mechanical tests.",
    )

    # Validate individual relevance classifications
    assert classify_relevance(query, relevant_job.title, responsibilities=relevant_job.description).level == RelevanceLevel.STRONG
    assert classify_relevance(query, related_job.title, responsibilities=related_job.description).level == RelevanceLevel.RELATED
    assert classify_relevance(query, irrelevant_job.title, responsibilities=irrelevant_job.description).level == RelevanceLevel.IRRELEVANT

    # Test orchestrator relevance filter method
    orchestrator = SearchOrchestrator()
    filtered = orchestrator._filter_by_relevance(query, [relevant_job, related_job, irrelevant_job])
    filtered_ids = [j.id for j in filtered]

    assert "smartrecruiters:acme:1" in filtered_ids
    assert "smartrecruiters:acme:2" in filtered_ids
    assert "smartrecruiters:tire:3" not in filtered_ids


@pytest.mark.anyio
async def test_monitored_store_path_title_first_ranking_no_starvation_and_rollback(tmp_path: Path, monkeypatch):
    reg = CompanyBoardRegistry(db_path=str(tmp_path / "monitored_rel.sqlite"))
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)
    monkeypatch.setattr("src.storage.company_board_registry.company_board_registry", reg)
    monkeypatch.setattr(settings, "serper_api_key", "")
    monkeypatch.setattr(settings, "relevance_mode", "filter")
    _cache.clear()

    now = datetime.now(timezone.utc)

    # Insert 12 newer body-only traps mentioning "backend" in description only
    for idx in range(12):
        trap = JobListing(
            id=f"greenhouse:trap:{idx}",
            provider="greenhouse",
            data_source="api",
            ats_source="greenhouse",
            title=f"Technical Account Manager I #{idx}",
            company="TrapCorp",
            location="Remote",
            apply_url=f"https://boards.greenhouse.io/trap/jobs/{idx}",
            source_url=f"https://boards.greenhouse.io/trap/jobs/{idx}",
            description="Work with backend engineering teams on customer API issues.",
            posted_at=now - timedelta(hours=idx),
            scraped_at=now,
            query_used="trap",
        )
        assert reg.upsert_monitored_job(trap) is True

    # Insert 5 valid title-matching jobs (including hyphenated and non-tech jobs)
    older_tier1 = JobListing(
        id="greenhouse:acme:be-old",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Senior Backend Engineer",
        company="Acme",
        location="Remote",
        apply_url="https://boards.greenhouse.io/acme/jobs/be-old",
        source_url="https://boards.greenhouse.io/acme/jobs/be-old",
        description="Own distributed services.",
        posted_at=now - timedelta(days=10),
        scraped_at=now,
        query_used="acme",
    )
    newer_tier1 = JobListing(
        id="lever:beta:be-new",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Back-end Developer",
        company="Beta",
        location="Remote",
        apply_url="https://jobs.lever.co/beta/be-new",
        source_url="https://jobs.lever.co/beta/be-new",
        description="Build APIs.",
        posted_at=now - timedelta(days=1),
        scraped_at=now,
        query_used="beta",
    )
    for idx in range(3):
        extra = JobListing(
            id=f"ashby:co:be-{idx}",
            provider="ashby",
            data_source="api",
            ats_source="ashby",
            title="Staff Backend Architect",
            company="Co",
            location="Remote",
            apply_url=f"https://jobs.ashbyhq.com/co/be-{idx}",
            source_url=f"https://jobs.ashbyhq.com/co/be-{idx}",
            description="Platform design.",
            posted_at=now - timedelta(days=4 + idx),
            scraped_at=now,
            query_used="co",
        )
        assert reg.upsert_monitored_job(extra) is True

    assert reg.upsert_monitored_job(older_tier1) is True
    assert reg.upsert_monitored_job(newer_tier1) is True

    # Non-tech roles + non-tech body-only trap
    mkt = JobListing(
        id="ashby:mkt:1",
        provider="ashby",
        data_source="api",
        ats_source="ashby",
        title="Marketing Manager",
        company="GrowthCo",
        location="Remote",
        apply_url="https://jobs.ashbyhq.com/mkt/1",
        source_url="https://jobs.ashbyhq.com/mkt/1",
        description="Lead brand campaigns.",
        posted_at=now - timedelta(days=2),
        scraped_at=now,
        query_used="growthco",
    )
    acct = JobListing(
        id="greenhouse:fin:1",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Senior Accountant",
        company="FinCo",
        location="Remote",
        apply_url="https://boards.greenhouse.io/fin/1",
        source_url="https://boards.greenhouse.io/fin/1",
        description="Manage general ledger.",
        posted_at=now - timedelta(days=1),
        scraped_at=now,
        query_used="finco",
    )
    acct_trap = JobListing(
        id="greenhouse:fin:trap",
        provider="greenhouse",
        data_source="api",
        ats_source="greenhouse",
        title="Operations Associate",
        company="FinCo",
        location="Remote",
        apply_url="https://boards.greenhouse.io/fin/trap",
        source_url="https://boards.greenhouse.io/fin/trap",
        description="Report directly to the Senior Accountant.",
        posted_at=now,
        scraped_at=now,
        query_used="finco",
    )
    for item in (mkt, acct, acct_trap):
        assert reg.upsert_monitored_job(item) is True

    # 1. Direct monitored store query: limit=5 must not starve on 12 body-only traps
    be_hits = reg.search_monitored_jobs("Backend", limit=5)
    assert len(be_hits) == 5
    assert all("Technical Account Manager" not in j.title for j in be_hits)
    assert be_hits[0].id == "lever:beta:be-new"
    assert be_hits[-1].id == "greenhouse:acme:be-old"

    # 2. Full orchestrator monitored path keeps valid tech & non-tech titles and drops traps
    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(404))
    ) as offline_client:
        collected_be: list[JobListing] = []
        async for ev, payload in orchestrator.run(
            SearchParams(job_title="Backend", include_nigerian_sites=False, days_back=30),
            client=offline_client,
        ):
            if ev == "results":
                collected_be.extend(payload.batch)
        assert [j.title for j in collected_be] == [
            "Back-end Developer",
            "Staff Backend Architect",
            "Staff Backend Architect",
            "Staff Backend Architect",
            "Senior Backend Engineer",
        ]

        collected_mkt: list[JobListing] = []
        async for ev, payload in orchestrator.run(
            SearchParams(job_title="Marketing Manager", include_nigerian_sites=False),
            client=offline_client,
        ):
            if ev == "results":
                collected_mkt.extend(payload.batch)
        assert [j.title for j in collected_mkt] == ["Marketing Manager"]

        collected_acct: list[JobListing] = []
        async for ev, payload in orchestrator.run(
            SearchParams(job_title="Senior Accountant", include_nigerian_sites=False),
            client=offline_client,
        ):
            if ev == "results":
                collected_acct.extend(payload.batch)
        assert [j.title for j in collected_acct] == ["Senior Accountant"]

        # 3. Tier 1 ranks ahead of Tier 2 in orchestrator monitored path
        fs_t1 = JobListing(
            id="greenhouse:fs:t1",
            provider="greenhouse",
            data_source="api",
            ats_source="greenhouse",
            title="Full Stack Developer",
            company="FS1",
            location="Remote",
            apply_url="https://boards.greenhouse.io/fs/t1",
            source_url="https://boards.greenhouse.io/fs/t1",
            description="Full stack web apps.",
            posted_at=now - timedelta(days=15),
            scraped_at=now,
            query_used="fs",
        )
        fs_t2 = JobListing(
            id="greenhouse:fs:t2",
            provider="greenhouse",
            data_source="api",
            ats_source="greenhouse",
            title="Senior Full-Stack Engineer",
            company="FS2",
            location="Remote",
            apply_url="https://boards.greenhouse.io/fs/t2",
            source_url="https://boards.greenhouse.io/fs/t2",
            description="Full stack web apps.",
            posted_at=now - timedelta(days=1),
            scraped_at=now,
            query_used="fs",
        )
        assert reg.upsert_monitored_job(fs_t1) is True
        assert reg.upsert_monitored_job(fs_t2) is True

        collected_fs: list[JobListing] = []
        async for ev, payload in orchestrator.run(
            SearchParams(job_title="Full-Stack Developer", include_nigerian_sites=False, days_back=30),
            client=offline_client,
        ):
            if ev == "results":
                collected_fs.extend(payload.batch)
        assert collected_fs[0].id == "greenhouse:fs:t1"
        assert [j.id for j in collected_fs[:2]] == ["greenhouse:fs:t1", "greenhouse:fs:t2"]

    # 4. RELEVANCE_MODE=off restores unfiltered behavior on monitored store
    monkeypatch.setattr(settings, "relevance_mode", "off")
    _cache.clear()
    unfiltered_be = reg.search_monitored_jobs("Backend", limit=20)
    assert any("Technical Account Manager" in j.title for j in unfiltered_be)


@pytest.mark.anyio
async def test_serper_path_blocks_body_only_ranks_tiers_and_respects_relevance_mode(monkeypatch):
    cache_store.clear()
    _cache.clear()
    monkeypatch.setattr(settings, "serper_api_key", "test-key")
    monkeypatch.setattr(settings, "serper_mode", "live")
    monkeypatch.setattr(settings, "relevance_mode", "filter")

    now = datetime.now(timezone.utc)
    serper_payload = {
        "organic": [
            {
                "title": "Technical Account Manager I",
                "link": "https://boards.greenhouse.io/acme/jobs/101",
                "snippet": "Support backend customers",
            },
            {
                "title": "Senior Backend Engineer",
                "link": "https://boards.greenhouse.io/acme/jobs/102",
                "snippet": "Build backend services",
            },
            {
                "title": "Back-end Developer",
                "link": "https://boards.greenhouse.io/acme/jobs/103",
                "snippet": "APIs and storage",
            },
        ]
    }
    gh_jobs = {
        "101": {
            "id": 101,
            "title": "Technical Account Manager I",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
            "location": {"name": "Remote"},
            "updated_at": now.isoformat(),
            "first_published": now.isoformat(),
            "content": "<p>Work with backend teams on integrations.</p>",
        },
        "102": {
            "id": 102,
            "title": "Senior Backend Engineer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
            "location": {"name": "Remote"},
            "updated_at": (now - timedelta(days=8)).isoformat(),
            "first_published": (now - timedelta(days=8)).isoformat(),
            "content": "<p>Design backend microservices.</p>",
        },
        "103": {
            "id": 103,
            "title": "Back-end Developer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/103",
            "location": {"name": "Remote"},
            "updated_at": (now - timedelta(days=1)).isoformat(),
            "first_published": (now - timedelta(days=1)).isoformat(),
            "content": "<p>Build distributed systems.</p>",
        },
    }

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "google.serper.dev" in url:
            return httpx.Response(200, json=serper_payload)
        for jid, payload in gh_jobs.items():
            if f"/jobs/{jid}" in url:
                return httpx.Response(200, json=payload)
        return httpx.Response(404)

    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        _, filtered, _ = await orchestrator._search_ats_serper(
            "greenhouse",
            "site:boards.greenhouse.io Backend",
            SearchParams(job_title="Backend", include_nigerian_sites=False),
            client,
        )
    assert [j.title for j in filtered] == ["Back-end Developer", "Senior Backend Engineer"]

    # Tier 1 ahead of Tier 2 in Serper path
    tier_jobs = [
        _make_listing("greenhouse:acme:201", "Senior Full-Stack Engineer", "Acme", "Full stack", provider="greenhouse", posted_at=now - timedelta(days=1)),
        _make_listing("greenhouse:acme:202", "Full Stack Developer", "Acme", "Full stack", provider="greenhouse", posted_at=now - timedelta(days=12)),
    ]
    ranked = orchestrator._filter_by_relevance("Full-Stack Developer", tier_jobs)
    assert [j.id for j in ranked] == ["greenhouse:acme:202", "greenhouse:acme:201"]

    # RELEVANCE_MODE=off restores unfiltered behavior on Serper path
    monkeypatch.setattr(settings, "relevance_mode", "off")
    cache_store.clear()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        _, unfiltered, _ = await orchestrator._search_ats_serper(
            "greenhouse",
            "site:boards.greenhouse.io Backend",
            SearchParams(job_title="Backend", include_nigerian_sites=False),
            client,
        )
    assert len(unfiltered) == 3
    assert any(j.title == "Technical Account Manager I" for j in unfiltered)


@pytest.mark.anyio
async def test_nigerian_scraper_path_filters_body_only_and_keeps_valid_roles(monkeypatch):
    monkeypatch.setattr(settings, "relevance_mode", "filter")
    now = datetime.now(timezone.utc)

    class FixtureNigerianScraper(BaseScraper):
        site_name = "jobberman"
        base_url = "https://www.jobberman.com"

        async def search(self, client: httpx.AsyncClient, params: SearchParams) -> list[JobListing]:
            return [
                _make_listing(
                    "jobberman:trap",
                    "Technical Account Manager I",
                    "NaijaPay",
                    "Partner with backend engineering on API tickets.",
                    provider="jobberman",
                    posted_at=now,
                ),
                _make_listing(
                    "jobberman:be-old",
                    "Senior Backend Engineer",
                    "NaijaPay",
                    "Build APIs.",
                    provider="jobberman",
                    posted_at=now - timedelta(days=10),
                ),
                _make_listing(
                    "jobberman:be-new",
                    "Back-end Developer",
                    "NaijaPay",
                    "Scale payments.",
                    provider="jobberman",
                    posted_at=now - timedelta(days=1),
                ),
                _make_listing(
                    "jobberman:acct",
                    "Senior Accountant",
                    "NaijaPay",
                    "Financial reporting.",
                    provider="jobberman",
                    posted_at=now - timedelta(days=2),
                ),
            ]

    orchestrator = SearchOrchestrator()
    scraper = FixtureNigerianScraper()
    async with httpx.AsyncClient() as client:
        _, be_results, _ = await orchestrator._search_nigerian_scraper(
            scraper,
            SearchParams(job_title="Backend"),
            client,
        )
        _, acct_results, _ = await orchestrator._search_nigerian_scraper(
            scraper,
            SearchParams(job_title="Senior Accountant"),
            client,
        )

    assert [j.title for j in be_results] == ["Back-end Developer", "Senior Backend Engineer"]
    assert [j.title for j in acct_results] == ["Senior Accountant"]

    # Also verify against real offline Jobberman detail fixture HTML via JobbermanScraper
    fixture_html = Path("tests/fixtures/nigerian/jobberman_sample_detail.html").read_text(encoding="utf-8")
    real_jb = JobbermanScraper()
    detail_md = real_jb.extract_detail_markdown(fixture_html)
    assert detail_md is not None

    # Verify RELEVANCE_MODE=off restores unfiltered behavior on Nigerian scraper path
    monkeypatch.setattr(settings, "relevance_mode", "off")
    async with httpx.AsyncClient() as client:
        _, unfiltered_results, _ = await orchestrator._search_nigerian_scraper(
            scraper,
            SearchParams(job_title="Backend"),
            client,
        )
    assert len(unfiltered_results) == 4
    assert any(j.title == "Technical Account Manager I" for j in unfiltered_results)

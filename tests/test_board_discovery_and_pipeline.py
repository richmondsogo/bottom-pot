"""
Tests for automatic ATS company-board discovery and pipeline integration.

Verifies:
1. Nigerian scrapers (Jobberman, MyJobMag, HotNigerianJobs) automatically extract external
   ATS apply links and register candidate company boards into CompanyBoardRegistry.
2. SearchOrchestrator._enrich_ats_item automatically registers candidate boards.
3. Direct board routing registers discovered boards and records check success.
4. Deduplication and placeholder validation prevent junk from entering the registry.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest
import httpx

from src.storage.company_board_registry import CompanyBoardRegistry
from src.discovery.nigerian_scrapers import (
    JobbermanScraper,
    MyJobMagScraper,
    HotNigerianJobsScraper,
)
from src.core.models import JobListing, SearchParams
from src.extraction.job_extraction_service import RawJobPosting
from src.discovery.search_pipeline import SearchOrchestrator


@pytest.mark.anyio
async def test_jobberman_detail_discovers_greenhouse_board(tmp_path: Path, monkeypatch):
    """Jobberman detail page containing an external Greenhouse link registers candidate board."""
    test_db = tmp_path / "test_jb.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.nigerian_scrapers.company_board_registry", reg)

    detail_html = """
    <html><body>
    <article class="job__details">
        <h1>Senior Backend Engineer</h1>
        <p>Apply directly on company portal:</p>
        <a href="https://boards.greenhouse.io/paystack/jobs/1234567" class="btn">Apply on Company Site</a>
        <div class="job__description">
            <p>We are looking for a Senior Backend Engineer to join Paystack.</p>
        </div>
    </article>
    </body></html>
    """

    now = datetime.now(timezone.utc)
    scraper = JobbermanScraper()
    listing = JobListing(
        id="jb:1",
        provider="jobberman",
        data_source="scrape",
        ats_source="jobberman",
        title="Senior Backend Engineer",
        company="Paystack",
        apply_url="https://www.jobberman.com/listings/senior-backend-engineer-xyz",
        source_url="https://www.jobberman.com/listings/senior-backend-engineer-xyz",
        scraped_at=now,
        query_used="backend",
    )
    raw = RawJobPosting(
        provider="jobberman",
        source_url=listing.apply_url,
        apply_url=listing.apply_url,
        provider_job_id="jb:1",
        raw_title="Senior Backend Engineer",
        raw_company="Paystack",
        scraped_at=now,
    )

    async def mock_fetch(client, url):
        return detail_html

    monkeypatch.setattr(scraper, "fetch_html", mock_fetch)

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(1)
        await scraper._enrich_detail(client, listing, raw, sem)

    # Apply URL should have been updated to direct ATS link
    assert listing.apply_url == "https://boards.greenhouse.io/paystack/jobs/1234567"

    # Candidate board should be registered in the registry
    board = reg.get_board("greenhouse", "paystack")
    assert board is not None
    assert board.board_token == "paystack"
    assert board.company_name == "Paystack"
    assert board.verification_status == "candidate"


@pytest.mark.anyio
async def test_myjobmag_detail_discovers_ashby_board(tmp_path: Path, monkeypatch):
    """MyJobMag detail page containing an Ashby link registers candidate board."""
    test_db = tmp_path / "test_mjm.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.nigerian_scrapers.company_board_registry", reg)

    detail_html = """
    <html><body>
    <div class="job-details">
        <h2>Frontend Architect</h2>
        <a href="https://jobs.ashbyhq.com/moniepoint/5a22839b-1111-2222-3333-444455556666" class="apply-btn">Apply Online</a>
        <div class="job-description">
            <p>Moniepoint is looking for a Frontend Architect.</p>
        </div>
    </div>
    </body></html>
    """

    now = datetime.now(timezone.utc)
    scraper = MyJobMagScraper()
    listing = JobListing(
        id="mjm:1",
        provider="myjobmag",
        data_source="scrape",
        ats_source="myjobmag",
        title="Frontend Architect",
        company="Moniepoint",
        apply_url="https://www.myjobmag.com/job/frontend-architect",
        source_url="https://www.myjobmag.com/job/frontend-architect",
        scraped_at=now,
        query_used="frontend",
    )
    raw = RawJobPosting(
        provider="myjobmag",
        source_url=listing.apply_url,
        apply_url=listing.apply_url,
        provider_job_id="mjm:1",
        raw_title="Frontend Architect",
        raw_company="Moniepoint",
        scraped_at=now,
    )

    async def mock_fetch(client, url):
        return detail_html

    monkeypatch.setattr(scraper, "fetch_html", mock_fetch)

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(1)
        await scraper._enrich_detail(client, listing, raw, sem)

    assert listing.apply_url == "https://jobs.ashbyhq.com/moniepoint/5a22839b-1111-2222-3333-444455556666"
    board = reg.get_board("ashby", "moniepoint")
    assert board is not None
    assert board.board_token == "moniepoint"
    assert board.company_name == "Moniepoint"


@pytest.mark.anyio
async def test_hotnigerianjobs_detail_discovers_lever_board(tmp_path: Path, monkeypatch):
    """HotNigerianJobs detail page with Lever application method registers candidate board."""
    test_db = tmp_path / "test_hnj.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.nigerian_scrapers.company_board_registry", reg)

    detail_html = """
    <html><body>
    <div class="mycase">
        <h1>Flutterwave Graduate Trainee</h1>
        <div class="mycase4">
            <p>Flutterwave invites applications for its Graduate Engineering Trainee Program.</p>
            <p><strong>Method of Application</strong></p>
            <p>Interested candidates should <a href="https://jobs.lever.co/flutterwave/8e4429bf-1111-2222-3333-444455556666">Click Here to Apply</a>.</p>
        </div>
    </div>
    </body></html>
    """

    now = datetime.now(timezone.utc)
    scraper = HotNigerianJobsScraper()
    listing = JobListing(
        id="hnj:1",
        provider="hotnigerianjobs",
        data_source="scrape",
        ats_source="hotnigerianjobs",
        title="Graduate Trainee",
        company="Flutterwave",
        apply_url="https://www.hotnigerianjobs.com/hotjobs/12345/",
        source_url="https://www.hotnigerianjobs.com/hotjobs/12345/",
        scraped_at=now,
        query_used="trainee",
    )

    result = scraper.enrich_listing_from_detail(listing, detail_html)
    assert result is True
    assert listing.apply_url == "https://jobs.lever.co/flutterwave/8e4429bf-1111-2222-3333-444455556666"

    board = reg.get_board("lever", "flutterwave")
    assert board is not None
    assert board.board_token == "flutterwave"
    assert board.company_name == "Flutterwave"


@pytest.mark.anyio
async def test_pipeline_direct_board_probe_registers_verified_board(tmp_path: Path, monkeypatch):
    """SearchOrchestrator._search_direct_boards registers probed boards with success."""
    test_db = tmp_path / "test_pipe.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)

    now = datetime.now(timezone.utc)

    async def mock_probe(slugs, client, platforms=None):
        return [
            JobListing(
                id="greenhouse:stripe:9999",
                provider="greenhouse",
                data_source="api",
                ats_source="greenhouse",
                title="Staff Engineer",
                company="Stripe",
                apply_url="https://boards.greenhouse.io/stripe/jobs/9999",
                source_url="https://boards.greenhouse.io/stripe/jobs/9999",
                scraped_at=now,
                query_used="stripe",
            )
        ]

    monkeypatch.setattr("src.discovery.search_pipeline.probe_direct_boards", mock_probe)

    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient() as client:
        prov, listings, used = await orchestrator._search_direct_boards(
            slugs=["stripe"],
            params=SearchParams(job_title="stripe engineer"),
            platforms=["greenhouse"],
            client=client,
        )

    assert len(listings) == 1
    board = reg.get_board("greenhouse", "stripe")
    assert board is not None
    assert board.board_token == "stripe"
    assert board.company_name == "Stripe"
    assert board.active_job_count == 1
    assert board.failure_count == 0


@pytest.mark.anyio
async def test_pipeline_direct_board_probe_registers_workable_and_recruitee_boards(
    tmp_path: Path, monkeypatch
):
    """
    SearchOrchestrator._search_direct_boards automatically registers every provider in
    MONITORABLE_PROVIDERS (including Workable and Recruitee) from real direct-board probes,
    preserving provider, token, company name, posting source URL, verified logo, and job count.
    """
    import json
    from src.ats import ats_api_client
    test_db = tmp_path / "test_workable_recruitee_pipe.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)
    monkeypatch.setattr(ats_api_client, "company_board_registry", reg)

    workable_dir = Path("tests/fixtures/real/workable")
    recruitee_dir = Path("tests/fixtures/real/recruitee")

    widget_verneek = workable_dir / "widget_verneek.json"
    account_verneek = workable_dir / "account_verneek.json"
    job_verneek = workable_dir / "job_verneek_3DBA754691.json"
    mia_offers = json.loads((recruitee_dir / "miaplaza_offers.json").read_text(encoding="utf-8"))
    mia_html = (recruitee_dir / "miaplaza_board.html").read_text(encoding="utf-8")

    widget_verneek_json = json.loads(widget_verneek.read_text(encoding="utf-8"))
    expected_workable_count = len(widget_verneek_json["jobs"])
    expected_recruitee_count = len(mia_offers["offers"])

    async def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if u == "https://apply.workable.com/api/v1/widget/accounts/verneek":
            return httpx.Response(200, text=widget_verneek.read_text(encoding="utf-8"))
        if u == "https://apply.workable.com/api/v1/accounts/verneek":
            return httpx.Response(200, text=account_verneek.read_text(encoding="utf-8"))
        if u.startswith("https://apply.workable.com/api/v2/accounts/verneek/jobs/"):
            return httpx.Response(200, text=job_verneek.read_text(encoding="utf-8"))
        if u == "https://miaplaza.recruitee.com/api/offers/":
            return httpx.Response(200, json=mia_offers)
        if u == "https://miaplaza.recruitee.com/":
            return httpx.Response(200, text=mia_html)
        return httpx.Response(404)

    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        _, w_listings, _ = await orchestrator._search_direct_boards(
            slugs=["verneek"],
            params=SearchParams(job_title="verneek"),
            platforms=["workable"],
            client=client,
        )
        _, r_listings, _ = await orchestrator._search_direct_boards(
            slugs=["miaplaza"],
            params=SearchParams(job_title="miaplaza"),
            platforms=["recruitee"],
            client=client,
        )

    assert len(w_listings) == expected_workable_count
    w_board = reg.get_board("workable", "verneek")
    assert w_board is not None
    assert w_board.ats_provider == "workable"
    assert w_board.board_token == "verneek"
    assert w_board.company_name == "Verneek"
    assert w_board.source_posting_url is not None and "workable.com" in w_board.source_posting_url
    assert w_board.company_logo_verified is True
    assert w_board.company_logo_url == "https://workablehr.s3.amazonaws.com/uploads/account/logo/456770/logo"
    assert w_board.company_logo_source == "workable_account_logo"
    assert w_board.verification_status == "verified"
    assert w_board.monitoring_capability == "supported"
    assert w_board.active_job_count == expected_workable_count
    assert w_board.last_successful_check is not None
    assert w_board.failure_count == 0

    assert len(r_listings) == expected_recruitee_count
    r_board = reg.get_board("recruitee", "miaplaza")
    assert r_board is not None
    assert r_board.ats_provider == "recruitee"
    assert r_board.board_token == "miaplaza"
    assert r_board.company_name == "Miaplaza"
    assert r_board.source_posting_url is not None and "miaplaza.recruitee.com/o/" in r_board.source_posting_url
    assert r_board.company_logo_verified is True
    assert "careers.recruiteecdn.com" in (r_board.company_logo_url or "")
    assert r_board.company_logo_source == "recruitee_nav_logo"
    assert r_board.verification_status == "verified"
    assert r_board.monitoring_capability == "supported"
    assert r_board.active_job_count == expected_recruitee_count
    assert r_board.last_successful_check is not None
    assert r_board.failure_count == 0


@pytest.mark.anyio
async def test_pipeline_direct_board_probe_skips_empty_or_failed_and_isolates_provider_counts(
    tmp_path: Path, monkeypatch
):
    """
    Failed or empty direct-board probes must not register verified boards, and same-slug boards
    across different MONITORABLE_PROVIDERS record isolated per-provider active_job_count.
    """
    test_db = tmp_path / "test_empty_and_counts.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.discovery.search_pipeline.company_board_registry", reg)

    async def failing_or_empty_handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if "emptycorp.recruitee.com/api/offers/" in u:
            return httpx.Response(200, json={"offers": []})
        if "apply.workable.com/api/v1/widget/accounts/emptycorp" in u:
            return httpx.Response(200, json={"name": "EmptyCorp", "jobs": []})
        return httpx.Response(404)

    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient(transport=httpx.MockTransport(failing_or_empty_handler)) as client:
        _, empty_listings, _ = await orchestrator._search_direct_boards(
            slugs=["missingcorp", "emptycorp"],
            params=SearchParams(job_title="missingcorp"),
            platforms=["recruitee", "greenhouse", "lever", "ashby"],
            client=client,
        )

    assert empty_listings == []
    assert reg.list_boards() == []

    now = datetime.now(timezone.utc)

    async def mock_multi_provider_probe(slugs, client, platforms=None):
        return [
            JobListing(
                id="workable:acme:ABC1",
                provider="workable",
                data_source="api",
                ats_source="workable",
                company_slug="acme",
                title="Role W1",
                company="Acme Workable",
                apply_url="https://apply.workable.com/acme/j/ABC1/apply",
                source_url="https://apply.workable.com/acme/j/ABC1",
                scraped_at=now,
                query_used="acme",
            ),
            JobListing(
                id="recruitee:acme:101",
                provider="recruitee",
                data_source="api",
                ats_source="recruitee",
                company_slug="acme",
                title="Role R1",
                company="Acme Recruitee",
                company_logo_url="https://careers.recruiteecdn.com/acme/logo.png",
                company_logo_source="recruitee_nav_logo",
                company_logo_verified=True,
                apply_url="https://acme.recruitee.com/o/role-r1/c/new",
                source_url="https://acme.recruitee.com/o/role-r1",
                scraped_at=now,
                query_used="acme",
            ),
            JobListing(
                id="recruitee:acme:102",
                provider="recruitee",
                data_source="api",
                ats_source="recruitee",
                company_slug="acme",
                title="Role R2",
                company="Acme Recruitee",
                company_logo_url="https://careers.recruiteecdn.com/acme/logo.png",
                company_logo_source="recruitee_nav_logo",
                company_logo_verified=True,
                apply_url="https://acme.recruitee.com/o/role-r2/c/new",
                source_url="https://acme.recruitee.com/o/role-r2",
                scraped_at=now,
                query_used="acme",
            ),
        ]

    monkeypatch.setattr("src.discovery.search_pipeline.probe_direct_boards", mock_multi_provider_probe)
    async with httpx.AsyncClient() as client:
        _, multi_listings, _ = await orchestrator._search_direct_boards(
            slugs=["acme"],
            params=SearchParams(job_title="acme"),
            platforms=["workable", "recruitee"],
            client=client,
        )

    assert len(multi_listings) == 3
    w_acme = reg.get_board("workable", "acme")
    r_acme = reg.get_board("recruitee", "acme")
    assert w_acme is not None and w_acme.active_job_count == 1
    assert r_acme is not None and r_acme.active_job_count == 2
    assert r_acme.company_logo_verified is True

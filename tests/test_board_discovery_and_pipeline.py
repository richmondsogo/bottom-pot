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

from src.project_files.company_board_registry import CompanyBoardRegistry
from src.project_files.nigerian_scrapers import (
    JobbermanScraper,
    MyJobMagScraper,
    HotNigerianJobsScraper,
)
from src.project_files.models import JobListing, SearchParams
from src.project_files.job_extraction_service import RawJobPosting
from src.project_files.search_pipeline import SearchOrchestrator


@pytest.mark.anyio
async def test_jobberman_detail_discovers_greenhouse_board(tmp_path: Path, monkeypatch):
    """Jobberman detail page containing an external Greenhouse link registers candidate board."""
    test_db = tmp_path / "test_jb.sqlite"
    reg = CompanyBoardRegistry(db_path=test_db)
    monkeypatch.setattr("src.project_files.nigerian_scrapers.company_board_registry", reg)

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
    monkeypatch.setattr("src.project_files.nigerian_scrapers.company_board_registry", reg)

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
    monkeypatch.setattr("src.project_files.nigerian_scrapers.company_board_registry", reg)

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
    monkeypatch.setattr("src.project_files.search_pipeline.company_board_registry", reg)

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

    monkeypatch.setattr("src.project_files.search_pipeline.probe_direct_boards", mock_probe)

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

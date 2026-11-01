"""
Tests for Nigerian scrapers search_result structured outcome emission.
"""

import httpx
import pytest

from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.models import SearchParams
from src.project_files.nigerian_scrapers import (
    HotNigerianJobsScraper,
    JobbermanScraper,
    MyJobMagScraper,
    NgCareersScraper,
)


@pytest.mark.anyio
async def test_jobberman_search_result_success():
    """Test successful Jobberman scrape emits ExtractionOutcome.SUCCESS."""
    html = """
    <html>
      <body>
        <div data-cy="listing-cards-components">
          <article>
            <a data-cy="listing-title-link" href="https://www.jobberman.com/listings/lead-dev-123">Lead Developer</a>
            <p class="text-sm text-link-500">Paystack</p>
            <p class="job-summary">Build robust and reliable payment gateways.</p>
          </article>
        </div>
      </body>
    </html>
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = JobbermanScraper()
        params = SearchParams(job_title="Lead Developer")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert len(listings) == 1
        assert listings[0].title == "Lead Developer"
        assert getattr(listings[0], "extraction_outcome", None) is None


@pytest.mark.anyio
async def test_jobberman_search_result_rate_limited():
    """Test HTTP 429 response on scraper emits ExtractionOutcome.RATE_LIMITED."""
    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Too Many Requests"))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = JobbermanScraper()
        params = SearchParams(job_title="DevOps")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.RATE_LIMITED
        assert res.status_code == 429
        assert listings == []


@pytest.mark.anyio
async def test_jobberman_search_result_bot_blocked():
    """Test Cloudflare/WAF block on scraper emits ExtractionOutcome.PERMANENT_ERROR."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="<title>Just a moment...</title>Checking your browser before accessing."))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = JobbermanScraper()
        params = SearchParams(job_title="Security Lead")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.PERMANENT_ERROR
        assert listings == []


@pytest.mark.anyio
async def test_myjobmag_search_result_rate_limited():
    """Mocked network: test HTTP 429 response on MyJobMag emits ExtractionOutcome.RATE_LIMITED."""
    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Too Many Requests"))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = MyJobMagScraper()
        params = SearchParams(job_title="Backend Engineer")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.RATE_LIMITED
        assert res.status_code == 429
        assert listings == []


@pytest.mark.anyio
async def test_ngcareers_search_result_retired_domain():
    """Mocked network: test retired domain redirect returns SUCCESS with empty listings."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, text="Jobberman redirect", headers={"location": "https://www.jobberman.com/"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = NgCareersScraper()
        params = SearchParams(job_title="Data Engineer")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listings == []


@pytest.mark.anyio
async def test_hotnigerianjobs_search_result_525_retryable():
    """Mocked network: test Cloudflare 525 error emits ExtractionOutcome.RETRYABLE_ERROR."""
    transport = httpx.MockTransport(lambda req: httpx.Response(525, text="Cloudflare Error 525: SSL handshake failed"))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = HotNigerianJobsScraper()
        params = SearchParams(job_title="Frontend Engineer")
        listings, res = await scraper.search_result(client, params)

        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.status_code == 525
        assert listings == []

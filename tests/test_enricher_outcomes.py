"""
Tests for ats_page_enricher.enrich_ats_page_result.
Covers outcome classification, visible degradation on page error/WAF/breaker, and partial success.
"""

import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.http_resilience import resilience_manager


@pytest.mark.anyio
async def test_enrich_ats_page_result_success():
    """Test successful JSON-LD extraction yields ExtractionOutcome.SUCCESS and no degradation."""
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Data Architect",
          "hiringOrganization": "Acme Analytics",
          "jobLocation": "Austin, TX",
          "employmentType": "FULL_TIME",
          "description": "<p>Build data warehouses and pipelines.</p>",
          "datePosted": "2026-03-01"
        }
        </script>
      </head>
      <body><h1>Data Architect</h1></body>
    </html>
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html))
    async with httpx.AsyncClient(transport=transport) as client:
        listing, res = await enrich_ats_page_result(
            url="https://careers.acmeanalytics.com/jobs/123",
            provider="generic_ats",
            search_title="Data Architect",
            snippet="Data Architect at Acme Analytics",
            query_used="data architect",
            client=client,
        )
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert res.status_code == 200
        assert listing is not None
        assert listing.title == "Data Architect"
        assert getattr(listing, "extraction_outcome", None) is None
        assert getattr(listing, "degraded_from", None) is None


@pytest.mark.anyio
async def test_enrich_ats_page_result_404_expired():
    """Test 404 or expired job listing yields ExtractionOutcome.NOT_FOUND and None listing."""
    html = "<html><body><div class='jv-alert'>The job listing no longer exists</div></body></html>"
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=html))
    async with httpx.AsyncClient(transport=transport) as client:
        listing, res = await enrich_ats_page_result(
            url="https://jobs.jobvite.com/acme/job/expired123",
            provider="jobvite",
            search_title="Data Engineer",
            snippet="Data Engineer at Acme",
            query_used="data engineer",
            client=client,
        )
        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert listing is None


@pytest.mark.anyio
async def test_enrich_ats_page_result_degradation_on_http_error():
    """Test 500 server error on page fetch yields retryable_error and visible degradation on fallback."""
    transport = httpx.MockTransport(lambda req: httpx.Response(500, text="Server Error"))
    async with httpx.AsyncClient(transport=transport) as client:
        listing, res = await enrich_ats_page_result(
            url="https://careers.unknown.com/job/fail500",
            provider="unknown",
            search_title="Platform Lead",
            snippet="Platform Lead at Unknown",
            query_used="platform lead",
            client=client,
        )
        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.status_code == 500
        assert res.degraded_from == "page_scrape"
        assert listing is not None
        assert listing.data_source == "snippet"
        assert listing.extraction_outcome == "retryable_error"
        assert listing.degraded_from == "page_scrape"


@pytest.mark.anyio
async def test_enrich_ats_page_result_waf_challenge():
    """Test WAF challenge yields permanent_error and visible degradation."""
    waf_html = "<html><body><div id='challenge-container'>Checking browser...</div></body></html>"
    transport = httpx.MockTransport(lambda req: httpx.Response(202, text=waf_html))
    async with httpx.AsyncClient(transport=transport) as client:
        listing, res = await enrich_ats_page_result(
            url="https://jobs.protected.com/job/waf1",
            provider="protected",
            search_title="DevOps Engineer",
            snippet="DevOps Engineer at Protected",
            query_used="devops",
            client=client,
        )
        assert res.outcome == ExtractionOutcome.PERMANENT_ERROR
        assert res.degraded_from == "page_scrape"
        assert listing is not None
        assert listing.extraction_outcome == "permanent_error"
        assert listing.degraded_from == "page_scrape"

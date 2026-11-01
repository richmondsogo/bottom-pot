"""
Tests for ATS clients fetch_raw_result and fetch_result methods.
Covers outcome classification, error sanitization, attempt counting, and visible degradation.
"""

import httpx
import pytest

from src.project_files.ats_api_client import GreenhouseClient, LeverClient
from src.project_files.ats_url_parser import parse_ats_url
from src.project_files.extraction_outcome import ExtractionOutcome


@pytest.mark.anyio
async def test_greenhouse_fetch_result_success():
    """Test successful Greenhouse API response yields ExtractionOutcome.SUCCESS and usable listing."""
    mock_payload = {
        "title": "Staff Backend Engineer",
        "company_name": "Acme Corp",
        "location": {"name": "Lagos, Nigeria"},
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
        "content": "<p>Build high-reliability distributed systems.</p>",
        "first_published": "2026-03-01T10:00:00Z",
    }

    def handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parsed = parse_ats_url("https://boards.greenhouse.io/acme/jobs/12345")
        assert parsed is not None
        gh = GreenhouseClient()
        listing, res = await gh.fetch_result(parsed, client)

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert res.status_code == 200
        assert res.raw is not None
        assert res.degraded_from is None
        assert listing is not None
        assert listing.title == "Staff Backend Engineer"
        # Invariant: Successful record has no visible degradation markers
        assert getattr(listing, "extraction_outcome", None) is None
        assert getattr(listing, "degraded_from", None) is None


@pytest.mark.anyio
async def test_greenhouse_fetch_result_404_not_found():
    """Test 404 response yields ExtractionOutcome.NOT_FOUND and None listing."""
    def handler(request: httpx.Request):
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parsed = parse_ats_url("https://boards.greenhouse.io/acme/jobs/99999")
        assert parsed is not None
        gh = GreenhouseClient()
        listing, res = await gh.fetch_result(parsed, client)

        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert res.status_code == 404
        assert listing is None


@pytest.mark.anyio
async def test_greenhouse_fetch_result_degradation_on_error():
    """Test 500 server error yields retryable_error and visible degradation on fallback snippet."""
    def handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parsed = parse_ats_url("https://boards.greenhouse.io/acme/jobs/50000")
        assert parsed is not None
        gh = GreenhouseClient()
        listing, res = await gh.fetch_result(parsed, client, fallback_snippet="Backend Lead at Acme")

        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.status_code == 500
        assert res.degraded_from == "api"
        assert listing is not None
        assert listing.data_source == "snippet"
        # Invariant: Visible degradation markers populated on post-failure fallback
        assert listing.extraction_outcome == "retryable_error"
        assert listing.degraded_from == "api"


@pytest.mark.anyio
async def test_lever_fetch_result_success_and_degradation():
    """Test Lever success, 404, and degradation on 502."""
    parsed = parse_ats_url("https://jobs.lever.co/kinsta/caadac8e-381f-42a2-9801-202b351fff28")
    assert parsed is not None
    lever = LeverClient()

    # Success case
    def ok_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "text": "Site Reliability Engineer",
            "company": "Kinsta",
            "categories": {"location": "Remote", "commitment": "Full time"},
            "applyUrl": "https://jobs.lever.co/kinsta/caadac8e-381f-42a2-9801-202b351fff28/apply",
            "description": "<p>Maintain k8s infrastructure.</p>",
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        listing, res = await lever.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        assert listing.title == "Site Reliability Engineer"
        assert getattr(listing, "extraction_outcome", None) is None

    # 404 Not Found case
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        listing, res = await lever.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert listing is None

    # 502 Bad Gateway -> degradation case
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(502))) as client:
        listing, res = await lever.fetch_result(parsed, client, fallback_snippet="SRE at Kinsta")
        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.status_code == 502
        assert res.degraded_from == "api"
        assert listing is not None
        assert listing.extraction_outcome == "retryable_error"
        assert listing.degraded_from == "api"


@pytest.mark.anyio
async def test_ashby_fetch_result_success_and_degradation():
    """Test Ashby success, absent job in board (not_found), and degradation on 500."""
    from src.project_files.ats_api_client import AshbyClient

    parsed = parse_ats_url("https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff")
    assert parsed is not None
    ashby = AshbyClient()

    # Success case
    def ok_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "jobs": [{
                "id": "d3bc1ced-3ce4-4086-a050-555055dbb1ff",
                "title": "Product Engineer",
                "locationName": "Remote, US",
                "jobUrl": "https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff",
                "descriptionHtml": "<p>Craft exceptional user interfaces.</p>",
                "publishedAt": "2026-03-01T12:00:00Z",
            }]
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        listing, res = await ashby.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        assert listing.title == "Product Engineer"
        assert getattr(listing, "extraction_outcome", None) is None

    # Job absent from board list -> not_found
    def empty_handler(request: httpx.Request):
        return httpx.Response(200, json={"jobs": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(empty_handler)) as client:
        listing, res = await ashby.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert listing is None

    # 500 server error -> degradation
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(500))) as client:
        listing, res = await ashby.fetch_result(parsed, client, fallback_snippet="Engineer at Linear")
        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.degraded_from == "api"
        assert listing is not None
        assert listing.extraction_outcome == "retryable_error"
        assert listing.degraded_from == "api"


@pytest.mark.anyio
async def test_smartrecruiters_fetch_result_success_and_degradation():
    """Test SmartRecruiters success, 404, and degradation on 429 rate limit."""
    from src.project_files.ats_api_client import SmartRecruitersClient

    parsed = parse_ats_url("https://jobs.smartrecruiters.com/uber/3743990000051828")
    assert parsed is not None
    sr = SmartRecruitersClient()

    # Success case
    def ok_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "name": "Senior Software Engineer",
            "company": {"name": "Uber"},
            "location": {"city": "Amsterdam", "remote": True, "hybrid": False},
            "ref": "https://jobs.smartrecruiters.com/uber/3743990000051828",
            "jobAd": {"sections": {"jobDescription": {"text": "<p>Build scalable payments.</p>"}}},
            "releasedDate": "2026-03-01T12:00:00Z",
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        listing, res = await sr.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        assert listing.title == "Senior Software Engineer"
        assert getattr(listing, "extraction_outcome", None) is None

    # 404 Not Found
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        listing, res = await sr.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert listing is None

    # 429 Rate Limited -> degradation
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(429))) as client:
        listing, res = await sr.fetch_result(parsed, client, fallback_snippet="Engineer at Uber")
        assert res.outcome == ExtractionOutcome.RATE_LIMITED
        assert res.status_code == 429
        assert res.degraded_from == "api"
        assert listing is not None
        assert listing.extraction_outcome == "rate_limited"
        assert listing.degraded_from == "api"


@pytest.mark.anyio
async def test_workable_fetch_result_success_and_degradation():
    """Test Workable success, 404, and degradation on connection error."""
    from src.project_files.ats_api_client import WorkableClient

    parsed = parse_ats_url("https://apply.workable.com/treq/j/D94DBAF102")
    assert parsed is not None
    workable = WorkableClient()

    # Success case
    def ok_handler(request: httpx.Request):
        return httpx.Response(200, text="# Senior Frontend Engineer\n> Treq · Remote · Full-time · Posted March 1, 2026\n\n**Workplace:** Remote\n**Department:** Engineering\n\nFull description here.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as client:
        listing, res = await workable.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        assert listing.title == "Senior Frontend Engineer"
        assert getattr(listing, "extraction_outcome", None) is None

    # 404 Not Found
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404))) as client:
        listing, res = await workable.fetch_result(parsed, client)
        assert res.outcome == ExtractionOutcome.NOT_FOUND
        assert listing is None

    # 503 Service Unavailable -> degradation
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(503))) as client:
        listing, res = await workable.fetch_result(parsed, client, fallback_snippet="Frontend Engineer at Treq")
        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert res.status_code == 503
        assert res.degraded_from == "api"
        assert listing is not None
        assert listing.extraction_outcome == "retryable_error"
        assert listing.degraded_from == "api"

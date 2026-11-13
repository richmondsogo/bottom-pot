import pytest
import httpx
from datetime import datetime, timezone
from unittest.mock import patch

from src.project_files.direct_board_router import (
    extract_company_slug_candidates,
    probe_greenhouse_board,
    probe_lever_board,
    probe_ashby_board,
    probe_direct_boards,
)
from src.project_files.models import JobListing


def test_extract_company_slug_candidates():
    # Single company query
    assert extract_company_slug_candidates("palantir") == ["palantir"]
    assert extract_company_slug_candidates("Palantir") == ["palantir"]
    assert extract_company_slug_candidates("Ramp") == ["ramp"]
    assert extract_company_slug_candidates("shifttechnology") == ["shifttechnology"]

    # Company with role words stripped
    assert extract_company_slug_candidates("palantir software engineer") == ["palantir"]
    assert extract_company_slug_candidates("senior backend developer reddit") == ["reddit"]
    assert extract_company_slug_candidates("stripe fullstack lead") == ["stripe"]

    # Pure role query without company name returns empty list
    assert extract_company_slug_candidates("software engineer") == []
    assert extract_company_slug_candidates("senior backend developer") == []
    assert extract_company_slug_candidates("frontend react remote") == []
    assert extract_company_slug_candidates("") == []


@pytest.mark.anyio
async def test_probe_greenhouse_board_200():
    sample_payload = {
        "jobs": [
            {
                "id": 101,
                "title": "Software Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                "location": {"name": "Remote, US"},
                "updated_at": "2026-10-15T12:00:00Z",
            }
        ]
    }

    def transport_handler(request: httpx.Request):
        if "boards-api.greenhouse.io/v1/boards/acme/jobs" in str(request.url):
            return httpx.Response(200, json=sample_payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as client:
        jobs = await probe_greenhouse_board("acme", client)

    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, JobListing)
    assert job.provider == "greenhouse"
    assert job.data_source == "api"
    assert job.title == "Software Engineer"
    assert job.company == "Acme"
    assert job.location == "Remote, US"
    assert job.apply_url == "https://boards.greenhouse.io/acme/jobs/101"


@pytest.mark.anyio
async def test_probe_lever_board_200():
    sample_payload = [
        {
            "id": "lev-202",
            "text": "Platform Engineer",
            "hostedUrl": "https://jobs.lever.co/initech/lev-202",
            "applyUrl": "https://jobs.lever.co/initech/lev-202/apply",
            "categories": {
                "location": "New York, NY",
                "commitment": "Full time",
                "team": "Infrastructure",
            },
            "createdAt": 1729000000000,
        }
    ]

    def transport_handler(request: httpx.Request):
        if "api.lever.co/v0/postings/initech" in str(request.url):
            return httpx.Response(200, json=sample_payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as client:
        jobs = await probe_lever_board("initech", client)

    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, JobListing)
    assert job.provider == "lever"
    assert job.data_source == "api"
    assert job.title == "Platform Engineer"
    assert job.company == "Initech"
    assert job.location == "New York, NY"
    assert job.apply_url == "https://jobs.lever.co/initech/lev-202/apply"


@pytest.mark.anyio
async def test_probe_ashby_board_200():
    sample_payload = {
        "jobs": [
            {
                "id": "ash-303",
                "title": "Staff Product Designer",
                "jobUrl": "https://jobs.ashbyhq.com/linear/ash-303",
                "applyUrl": "https://jobs.ashbyhq.com/linear/ash-303/application",
                "location": "San Francisco, CA",
                "publishedAt": "2026-10-10T08:00:00Z",
            }
        ]
    }

    def transport_handler(request: httpx.Request):
        if (
            "api.ashbyhq.com/posting-api/job-board/linear" in str(request.url)
            and request.method == "GET"
            and "includeCompensation=true" in str(request.url)
        ):
            return httpx.Response(200, json=sample_payload)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as client:
        jobs = await probe_ashby_board("linear", client)

    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, JobListing)
    assert job.provider == "ashby"
    assert job.data_source == "api"
    assert job.title == "Staff Product Designer"
    assert job.company == "Linear"
    assert job.location == "San Francisco, CA"
    assert job.apply_url == "https://jobs.ashbyhq.com/linear/ash-303/application"


@pytest.mark.anyio
async def test_probe_boards_404_returns_empty_list():
    """When an ATS board does not exist (404), return empty list without raising."""
    def transport_handler(request: httpx.Request):
        return httpx.Response(404, json={"error": "Not found"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as client:
        assert await probe_greenhouse_board("nonexistent", client) == []
        assert await probe_lever_board("nonexistent", client) == []
        assert await probe_ashby_board("nonexistent", client) == []


@pytest.mark.anyio
async def test_probe_direct_boards_filters_by_platforms():
    """probe_direct_boards respects the platforms list filter."""
    def transport_handler(request: httpx.Request):
        if "boards-api.greenhouse.io" in str(request.url):
            return httpx.Response(200, json={"jobs": [{"id": 1, "title": "GH", "absolute_url": "http://gh/1"}]})
        if "api.lever.co" in str(request.url):
            return httpx.Response(200, json=[{"id": "2", "text": "Lev", "hostedUrl": "http://lev/2"}])
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)) as client:
        # Only probe greenhouse
        jobs = await probe_direct_boards(["company"], client, platforms=["greenhouse"])
        assert len(jobs) == 1
        assert jobs[0].provider == "greenhouse"

        # Only probe lever
        jobs = await probe_direct_boards(["company"], client, platforms=["lever"])
        assert len(jobs) == 1
        assert jobs[0].provider == "lever"

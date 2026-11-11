import httpx
import pytest

from src.project_files.board_adapters import GreenhouseBoardAdapter
from src.project_files.company_board_registry import CompanyBoard


@pytest.mark.anyio
async def test_greenhouse_adapter_with_and_without_authentic_description():
    adapter = GreenhouseBoardAdapter()
    board = CompanyBoard(
        id=1,
        company_name="Stripe",
        company_slug="stripe",
        ats_provider="greenhouse",
        board_token="stripe",
        board_url="https://boards.greenhouse.io/stripe",
        discovery_source="test",
        source_posting_url=None,
        first_discovered_at=1000.0,
        last_discovered_at=1000.0,
        verification_status="candidate",
        monitoring_capability="supported",
    )

    requested_urls: list[str] = []

    gh_payload = {
        "jobs": [
            # Job 1: Authentic description with HTML and requirements
            {
                "id": 101,
                "title": "Senior Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/101",
                "location": {"name": "Remote, US"},
                "updated_at": "2026-10-01T12:00:00Z",
                "content": "&lt;p&gt;Stripe is building the economic infrastructure for the internet. Millions of companies of all sizes use Stripe software and APIs to accept payments, send payouts, and manage their businesses online. We are looking for an experienced Senior Backend Engineer to join our Core Financial Foundation team in Dublin or remotely across the US.&lt;/p&gt;&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;5+ years building and scaling distributed systems in production&lt;/li&gt;&lt;li&gt;Proficiency in Go, Java, or Python&lt;/li&gt;&lt;li&gt;Strong foundation in relational database consistency and high-throughput transaction processing&lt;/li&gt;&lt;/ul&gt;",
            },
            # Job 2: Absent description content
            {
                "id": 102,
                "title": "Product Operations Lead",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/102",
                "location": {"name": "Dublin, Ireland"},
                "updated_at": "2026-10-02T12:00:00Z",
                "content": None,
            },
            # Job 3: Malformed description content (not a string)
            {
                "id": 103,
                "title": "Technical Account Specialist",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/103",
                "location": {"name": "San Francisco, CA"},
                "updated_at": "2026-10-03T12:00:00Z",
                "content": 12345,
            },
        ]
    }

    def handler(req: httpx.Request):
        requested_urls.append(str(req.url))
        return httpx.Response(200, json=gh_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await adapter.check_board(board, client)

    assert res.success is True
    assert len(res.listings) == 3

    # Verify query includes content=true
    assert len(requested_urls) == 1
    assert "content=true" in requested_urls[0]

    # Job 1: Authentic description extracted
    job1 = next(j for j in res.listings if j.id.endswith("101"))
    assert job1.description_ok is True
    assert job1.description is not None
    assert "economic infrastructure" in job1.description
    assert job1.requirements is not None
    assert "distributed systems" in job1.requirements.lower()

    # Job 2: Absent description content -> description_ok is False, no invented description
    job2 = next(j for j in res.listings if j.id.endswith("102"))
    assert job2.description_ok is False
    assert job2.description is None
    assert not job2.requirements

    # Job 3: Malformed description -> description_ok is False, handled gracefully
    job3 = next(j for j in res.listings if j.id.endswith("103"))
    assert job3.description_ok is False
    assert job3.description is None
    assert not job3.requirements

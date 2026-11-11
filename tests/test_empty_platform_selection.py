import pytest
from httpx import AsyncClient, ASGITransport
from src.api.main import app
from src.project_files.models import SearchParams
from src.project_files.query_builder import build_ats_queries, ATS_DOMAINS
from src.project_files.search_pipeline import SearchOrchestrator


def test_build_ats_queries_empty_vs_omitted():
    params = SearchParams(job_title="Backend Engineer")

    # 1. Omitted (None) -> default all domains
    queries_default = build_ats_queries(params, platforms=None)
    assert len(queries_default) == len(ATS_DOMAINS)
    assert "greenhouse" in queries_default

    # 2. Explicit empty list -> 0 domains
    queries_empty = build_ats_queries(params, platforms=[])
    assert queries_empty == {}

    # 3. Specified list -> only specified
    queries_single = build_ats_queries(params, platforms=["greenhouse"])
    assert list(queries_single.keys()) == ["greenhouse"]


@pytest.mark.anyio
async def test_search_orchestrator_explicit_empty_platforms_runs_zero_providers():
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Backend Engineer", include_nigerian_sites=True)

    events = []
    async for event_name, event_data in orchestrator.run(params, platforms=[]):
        events.append((event_name, event_data))

    assert len(events) == 1
    event_name, done_event = events[0]
    assert event_name == "done"
    assert done_event.total == 0
    assert done_event.providers_searched == []
    assert done_event.serper_calls == 0
    assert done_event.pages_fetched == 0


@pytest.mark.anyio
async def test_api_search_endpoint_distinguishes_empty_and_omitted_platforms():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Explicit empty platforms query param (?platforms=)
        resp_empty = await client.get("/search?q=Engineer&platforms=", headers={"Accept": "text/event-stream"})
        assert resp_empty.status_code == 200
        body_empty = resp_empty.text
        assert "event: done" in body_empty
        assert '"total":0' in body_empty or '"total": 0' in body_empty

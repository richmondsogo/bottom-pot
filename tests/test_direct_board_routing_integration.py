import pytest
import httpx
from unittest.mock import patch, AsyncMock
from src.project_files.models import SearchParams
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.models import JobListing
from datetime import datetime, timezone


@pytest.mark.anyio
async def test_search_orchestrator_probes_direct_boards_on_company_query():
    """When a query contains a candidate company name, SearchOrchestrator launches direct board routing."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Palantir Software Engineer")

    mock_direct_job = JobListing(
        id="lever:palantir:101",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Software Engineer, Infrastructure",
        company="Palantir",
        location="New York, NY",
        apply_url="https://jobs.lever.co/palantir/101/apply",
        source_url="https://jobs.lever.co/palantir/101",
        query_used="palantir",
        scraped_at=datetime.now(timezone.utc),
    )

    with patch.object(orchestrator, "_search_direct_boards", new_callable=AsyncMock) as mock_direct, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats, \
         patch.object(orchestrator, "_search_nigerian_scraper", new_callable=AsyncMock) as mock_nig:
        
        mock_direct.return_value = ("direct_board_routing", [mock_direct_job], False)
        mock_ats.return_value = ("greenhouse", [], False)
        mock_nig.return_value = ("jobberman", [], False)

        async with httpx.AsyncClient() as client:
            events = [e async for e in orchestrator.run(params, platforms=["lever"], client=client)]

        # Direct boards were probed
        assert mock_direct.call_count == 1
        # The direct job was streamed
        results_batches = [e[1] for e in events if e[0] == "results"]
        all_streamed = [item for b in results_batches for item in b.batch]
        assert len(all_streamed) == 1
        assert all_streamed[0].id == "lever:palantir:101"
        assert all_streamed[0].company == "Palantir"


@pytest.mark.anyio
async def test_search_orchestrator_skips_direct_boards_on_pure_role_query():
    """When a query has no company candidate (e.g. 'Software Engineer'), direct board routing is skipped."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Software Engineer")

    with patch.object(orchestrator, "_search_direct_boards", new_callable=AsyncMock) as mock_direct, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats:
        
        mock_ats.return_value = ("greenhouse", [], False)

        async with httpx.AsyncClient() as client:
            _ = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=client)]

        assert mock_direct.call_count == 0


@pytest.mark.anyio
async def test_search_orchestrator_deduplicates_direct_board_and_serper_results():
    """Direct board jobs and Serper search jobs for the same posting are deduplicated cleanly."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Palantir")

    direct_job = JobListing(
        id="lever:palantir:101",
        provider="lever",
        data_source="api",
        ats_source="lever",
        title="Software Engineer",
        company="Palantir",
        location="New York, NY",
        apply_url="https://jobs.lever.co/palantir/101/apply",
        source_url="https://jobs.lever.co/palantir/101",
        query_used="palantir",
        scraped_at=datetime.now(timezone.utc),
    )

    serper_duplicate_job = JobListing(
        id="lever:palantir:101",
        provider="lever",
        data_source="snippet",
        ats_source="lever",
        title="Software Engineer",
        company="Palantir",
        location="New York, NY",
        apply_url="https://jobs.lever.co/palantir/101/apply",
        source_url="https://jobs.lever.co/palantir/101",
        query_used="site:jobs.lever.co/palantir",
        scraped_at=datetime.now(timezone.utc),
    )

    with patch.object(orchestrator, "_search_direct_boards", new_callable=AsyncMock) as mock_direct, \
         patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats:
        
        mock_direct.return_value = ("direct_board_routing", [direct_job], False)
        mock_ats.return_value = ("lever", [serper_duplicate_job], False)

        async with httpx.AsyncClient() as client:
            events = [e async for e in orchestrator.run(params, platforms=["lever"], client=client)]

        done_event = next(e[1] for e in events if e[0] == "done")
        # Exactly 1 total job collected at done
        assert done_event.total == 1

        # The final state of the job is the richer API data_source
        results_batches = [e[1] for e in events if e[0] == "results"]
        last_emitted_item = results_batches[-1].batch[0]
        assert last_emitted_item.id == "lever:palantir:101"
        assert last_emitted_item.data_source == "api"


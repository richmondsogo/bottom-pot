import pytest
import httpx
from unittest.mock import patch, AsyncMock
from src.project_files.models import SearchParams
from src.project_files.nigerian_scrapers import NIGERIAN_SCRAPERS
from src.project_files.search_pipeline import SearchOrchestrator


def test_nigerian_scrapers_excludes_retired_ngcareers():
    """ngcareers domain is permanently retired/redirected to jobberman; it must not be in active NIGERIAN_SCRAPERS."""
    site_names = [s.site_name.lower() for s in NIGERIAN_SCRAPERS]
    assert "ngcareers" not in site_names
    assert site_names == ["jobberman", "myjobmag", "hotnigerianjobs"]


@pytest.mark.anyio
async def test_search_orchestrator_platforms_filters_nigerian_scrapers():
    """When platforms is explicitly specified, only matching Nigerian scrapers run."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Software Engineer")

    # Case 1: platforms contains only hotnigerianjobs -> only hotnigerianjobs task launched
    with patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats, \
         patch.object(orchestrator, "_search_nigerian_scraper", new_callable=AsyncMock) as mock_nig:
        mock_nig.return_value = []
        async with httpx.AsyncClient() as client:
            _ = [e async for e in orchestrator.run(params, platforms=["hotnigerianjobs"], client=client)]
        
        # No ATS queries launched
        assert mock_ats.call_count == 0
        # Exactly 1 Nigerian scraper called: hotnigerianjobs
        assert mock_nig.call_count == 1
        called_scraper = mock_nig.call_args[0][0]
        assert called_scraper.site_name.lower() == "hotnigerianjobs"


@pytest.mark.anyio
async def test_search_orchestrator_platforms_excludes_nigerian_scrapers_when_ats_only():
    """When platforms contains only an ATS (e.g. greenhouse), no Nigerian scrapers run."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Software Engineer")

    with patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats, \
         patch.object(orchestrator, "_search_nigerian_scraper", new_callable=AsyncMock) as mock_nig:
        mock_ats.return_value = []
        async with httpx.AsyncClient() as client:
            _ = [e async for e in orchestrator.run(params, platforms=["greenhouse"], client=client)]
        
        assert mock_ats.call_count == 1
        assert mock_nig.call_count == 0


@pytest.mark.anyio
async def test_search_orchestrator_platforms_none_runs_all_active_scrapers():
    """When platforms is None (default), all active Nigerian scrapers run alongside ATS queries."""
    orchestrator = SearchOrchestrator()
    params = SearchParams(job_title="Software Engineer")

    with patch.object(orchestrator, "_search_ats_serper", new_callable=AsyncMock) as mock_ats, \
         patch.object(orchestrator, "_search_nigerian_scraper", new_callable=AsyncMock) as mock_nig:
        mock_ats.return_value = []
        mock_nig.return_value = []
        async with httpx.AsyncClient() as client:
            _ = [e async for e in orchestrator.run(params, platforms=None, client=client)]
        
        # All 3 active Nigerian scrapers are queried
        assert mock_nig.call_count == 3
        called_sites = {call[0][0].site_name.lower() for call in mock_nig.call_args_list}
        assert called_sites == {"jobberman", "myjobmag", "hotnigerianjobs"}

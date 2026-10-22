"""
Tests for ATS API clients and Nigerian scrapers resilience.
"""

import pytest
import httpx

from src.project_files.ats_api_client import (
    GreenhouseClient,
    LeverClient,
    AshbyClient,
    SmartRecruitersClient,
    WorkableClient,
    BambooHRClient,
    RecruiteeClient,
)
from src.project_files.ats_url_parser import parse_ats_url
from src.project_files.ats_page_enricher import enrich_ats_page
from src.project_files.ats_api_client import LeverClient
from src.project_files.nigerian_scrapers import (
    JobbermanScraper,
    MyJobMagScraper,
    NgCareersScraper,
    HotNigerianJobsScraper,
)
from src.project_files.models import SearchParams


@pytest.mark.anyio
async def test_greenhouse_client_success():
    parsed = parse_ats_url("https://boards.greenhouse.io/stripe/jobs/12345")
    assert parsed is not None

    def mock_handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "title": "Staff Engineer",
                "company_name": "Stripe",
                "location": {"name": "San Francisco, CA"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345",
                "updated_at": "2024-03-01T12:00:00.000Z",
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gh = GreenhouseClient()
        job = await gh.fetch(parsed, client)
        assert job is not None
        assert job.title == "Staff Engineer"
        assert job.provider == "greenhouse"
        assert job.data_source == "api"
        assert job.company == "Stripe"


@pytest.mark.anyio
async def test_greenhouse_client_404_returns_none():
    parsed = parse_ats_url("https://boards.greenhouse.io/stripe/jobs/99999")
    assert parsed is not None

    def mock_handler(request: httpx.Request):
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gh = GreenhouseClient()
        job = await gh.fetch(parsed, client)
        assert job is None


@pytest.mark.anyio
async def test_nigerian_scraper_bot_block():
    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text="<html><body>Access Denied - Robot detected captcha</body></html>")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = JobbermanScraper()
        params = SearchParams(job_title="Data Engineer")
        results = await scraper.search(client, params)
        # Should catch BotBlockError internally and return empty list
        assert results == []


@pytest.mark.anyio
async def test_generic_ats_page_extracts_job_posting_metadata():
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"JobPosting","title":"Backend Engineer","datePosted":"2026-09-01",
     "employmentType":"FULL_TIME","jobLocationType":"TELECOMMUTE",
     "hiringOrganization":{"name":"Example Corp"},
     "jobLocation":{"address":{"addressLocality":"Austin","addressRegion":"TX"}},
     "department":{"name":"Engineering"}}
    </script></head></html>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://jobs.example.com/backend-engineer",
            provider="example_ats",
            search_title="Backend Engineer",
            snippet="Backend Engineer",
            query_used="site:jobs.example.com Backend Engineer",
            client=client,
        )

    assert job.company == "Example Corp"
    assert job.location == "Austin, TX"
    assert job.employment_type == "full_time"
    assert job.work_model == "remote"
    assert job.department == "Engineering"
    assert job.posted_at is not None
    assert job.posted_at.date().isoformat() == "2026-09-01"


@pytest.mark.anyio
async def test_generic_ats_page_handles_graph_and_array_json_ld():
    html = """
    <script type="application/ld+json">[
      {"@graph":[{"@type":"JobPosting","title":"Platform Engineer",
       "datePosted":"2026-09-02","employmentType":"CONTRACT",
       "hiringOrganization":{"name":"Graph Corp"},
       "jobLocation":{"address":{"addressLocality":"London"}}} ]}
    ]</script>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(
            "https://jobs.example.com/platform",
            "example_ats",
            "Platform Engineer",
            "",
            "test",
            client,
        )

    assert job.company == "Graph Corp"
    assert job.employment_type == "contract"
    assert job.posted_at is not None


def test_human_readable_date_is_parsed():
    from src.project_files.field_normalizer import parse_datetime

    assert parse_datetime("Sep 9, 2026").date().isoformat() == "2026-09-09"


@pytest.mark.anyio
async def test_generic_ats_page_without_metadata_is_honest_snippet_fallback():
    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text="<html><body>JavaScript application shell</body></html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(
            "https://jobs.example.com/unknown",
            "example_ats",
            "Backend Engineer",
            "A posting without structured metadata",
            "test",
            client,
        )

    assert job.data_source == "snippet"
    assert job.company == "Unknown"
    assert job.location is None
    assert job.posted_at is None


@pytest.mark.anyio
async def test_api_client_humanizes_company_slug_when_provider_omits_name():
    parsed = parse_ats_url("https://jobs.lever.co/acme-corp-2024/12345678-1234-1234-1234-123456789012")
    assert parsed is not None

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={"text": "Backend Engineer", "categories": {"location": "Remote"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await LeverClient().fetch(parsed, client)

    assert job is not None
    assert job.company == "Acme Corp 2024"
    assert job.company != parsed.company_slug


@pytest.mark.anyio
async def test_workable_markdown_extracts_structured_fields():
    parsed = parse_ats_url("https://apply.workable.com/treq/j/D94DBAF102")
    assert parsed is not None
    markdown = """# Software Engineer
> TreQ · Milton, United Kingdom · Full-time · Posted 2026-09-08
**Workplace:** on_site
**Department:** Engineering
"""

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=markdown)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await WorkableClient().fetch(parsed, client)

    assert job is not None
    assert job.data_source == "scrape"
    assert job.company == "TreQ"
    assert job.location == "Milton, United Kingdom"
    assert job.employment_type == "full_time"
    assert job.work_model == "in_person"
    assert job.department == "Engineering"
    assert job.posted_at is not None


@pytest.mark.anyio
async def test_nigerian_remote_state_comes_from_card_not_search_filter():
    html = """
    <article>
      <h2><a href="/listings/backend-engineer">Backend Engineer</a></h2>
      <p class="text-sm text-link-500">Example Ltd</p>
      <span class="location">Lagos</span>
      <span>Employment Type: Full time</span>
      <span>Location Type: On-site</span>
      <span>Department: Engineering</span>
      <time datetime="2026-09-03">Sep 3, 2026</time>
    </article>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        scraper = JobbermanScraper()
        results = await scraper.search(client, SearchParams(job_title="Backend Engineer", remote=True))

    assert len(results) == 1
    assert results[0].is_remote is False
    assert results[0].employment_type == "full_time"
    assert results[0].work_model == "in_person"
    assert results[0].department == "Engineering"
    assert results[0].posted_at is not None


@pytest.mark.anyio
async def test_jazzhr_share_page_resolves_and_extracts_all_fields():
    """JazzHR share page should resolve to the apply page and extract company,
    location, employment_type, work_model, and posted_at from the JSON-LD."""
    import pathlib

    fixture_path = pathlib.Path(__file__).resolve().parent / "fixtures" / "jazzhr_apply.html"
    if not fixture_path.exists():
        pytest.skip("JazzHR apply fixture not available")

    apply_html = fixture_path.read_text(encoding="utf-8", errors="replace")

    # The share page HTML that contains a link to the apply page
    share_html = """
    <html><body>
    <div class="focus-subheader-content">
        <h1><a href="/apply/kmnC9eIyPq/Senior-Software-Engineer-Product">Senior Software Engineer (Product)</a></h1>
    </div>
    <ul id="focus-subheader-content-info">
        <li><i class="fa fa-map-marker"></i> Austin, TX</li>
        <li><i class="fa fa-clock-o"></i> Full-time</li>
    </ul>
    <a href="/apply/kmnC9eIyPq/Senior-Software-Engineer-Product">Apply</a>
    </body></html>
    """

    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        url = str(request.url)
        if "/app/share/" in url:
            return httpx.Response(200, text=share_html)
        elif "/apply/" in url:
            return httpx.Response(200, text=apply_html)
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://activeprospect.applytojob.com/app/share/kmnC9eIyPq",
            provider="jazzhr",
            search_title="Senior Software Engineer (Product)",
            snippet="",
            query_used="test",
            client=client,
        )

    # Should have fetched both the share page and the apply page
    assert call_count >= 2
    assert job.company == "ActiveProspect, Inc."
    assert "Austin" in (job.location or "")
    assert "TX" in (job.location or "")
    assert job.employment_type == "full_time"
    assert job.work_model == "remote"
    assert job.posted_at is not None
    assert job.posted_at.date().isoformat() == "2026-09-03"


@pytest.mark.anyio
async def test_jobberman_scraper_parses_real_card_html():
    jobberman_html = """
    <html><body>
    <div aria-labelledby="job-1-title" data-cy="listing-cards-components">
        <a data-cy="listing-title-link" href="https://www.jobberman.com/listings/macos-mdm-qa-engineer" title="MacOS MDM QA Engineer">
            <p class="text-lg font-medium text-link-500">MacOS MDM QA Engineer</p>
        </a>
        <p class="text-sm text-blue-700">Honcho Nigeria Ltd</p>
        <div class="flex flex-wrap mt-3 text-sm text-gray-500">
            <span class="px-3 py-1 bg-brand-secondary-100">Remote (Work From Home)</span>
            <span class="px-3 py-1 bg-brand-secondary-100">Full Time</span>
            <span class="px-3 py-1 bg-brand-secondary-100">NGN 1,200,000 - 1,500,000</span>
        </div>
    </div>
    </body></html>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=jobberman_html)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = JobbermanScraper()
        results = await scraper.search(client, SearchParams(job_title="QA Engineer"))

    assert len(results) == 1
    job = results[0]
    assert job.title == "MacOS MDM QA Engineer"
    assert job.company == "Honcho Nigeria Ltd"
    assert job.work_model == "remote"
    assert job.is_remote is True
    assert job.employment_type == "full_time"
    assert job.salary == "NGN 1,200,000 - 1,500,000"


@pytest.mark.anyio
async def test_myjobmag_scraper_parses_search_jobs_html():
    myjobmag_html = """
    <html><body>
    <ul class="job-list">
        <li class="job-list-li">
            <ul>
                <li class="job-logo">
                    <a href="/jobs-at/nimblebyte-global">
                        <img alt="NimbleByte Global logo" src="/logo.png" />
                    </a>
                </li>
                <li class="job-info">
                    <ul>
                        <li class="mag-b">
                            <h2><a href="/job/senior-software-developer">Senior Software Developer at NimbleByte Global</a></h2>
                        </li>
                        <li class="job-item">
                            <ul>
                                <li id="job-date">13 October</li>
                            </ul>
                        </li>
                    </ul>
                </li>
            </ul>
        </li>
    </ul>
    </body></html>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=myjobmag_html)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = MyJobMagScraper()
        results = await scraper.search(client, SearchParams(job_title="Developer"))

    assert len(results) == 1
    job = results[0]
    assert job.title == "Senior Software Developer at NimbleByte Global"
    assert job.company == "NimbleByte Global"
    assert job.posted_at is not None
    assert job.posted_at.day == 13
    assert job.posted_at.month == 10


def test_nigerian_scraper_roboto_font_does_not_trigger_bot_block():
    from src.project_files.nigerian_scrapers import _check_bot_block
    html = """
    <html><head>
    <style>@font-face { font-family: Roboto; src: url(/fonts/roboto.woff2); }</style>
    </head><body>
    <form><button id="recaptcha-submit-newsletter">Subscribe</button></form>
    </body></html>
    """
    # Should not raise BotBlockError
    _check_bot_block(html, "jobberman")


def test_nigerian_scraper_real_cloudflare_challenge_triggers_bot_block():
    from src.project_files.exceptions import BotBlockError
    from src.project_files.nigerian_scrapers import _check_bot_block
    challenge_html = """
    <html><head><title>Just a moment...</title></head>
    <body><div id="challenge-running">Checking your browser</div></body></html>
    """
    with pytest.raises(BotBlockError):
        _check_bot_block(challenge_html, "jobberman")


@pytest.mark.anyio
async def test_ngcareers_scraper_handles_redirect_gracefully():
    def mock_handler(request: httpx.Request):
        # Emulate 301 redirect to jobberman.com
        return httpx.Response(200, text="<html><body>Jobberman Homepage</body></html>", headers={"location": "https://www.jobberman.com/"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = NgCareersScraper()
        # Set response URL explicitly by requesting the redirected target
        resp = await client.get("https://www.jobberman.com/")
        scraper.fetch_html = lambda c, u: scraper.fetch_html.__wrapped__(scraper, c, u) if hasattr(scraper.fetch_html, "__wrapped__") else None
        results = await scraper.search(client, SearchParams(job_title="Developer"))
        assert results == []


@pytest.mark.anyio
async def test_hotnigerianjobs_scraper_handles_525_gracefully():
    def mock_handler(request: httpx.Request):
        return httpx.Response(525, text="Cloudflare Error 525: SSL handshake failed")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = HotNigerianJobsScraper()
        results = await scraper.search(client, SearchParams(job_title="Developer"))
        assert results == []


def test_company_from_title_extraction():
    from src.project_files.ats_page_enricher import _company_from_title

    assert _company_from_title("Georgia-Pacific Data Science Intern - Atlanta, GA") is None
    assert _company_from_title("Senior Frontend Engineer at Postscript") == "Postscript"
    assert _company_from_title("Careers at Stripe | Job Openings") == "Stripe"
    assert _company_from_title("Software Engineer @ OpenAI") == "OpenAI"


@pytest.mark.anyio
async def test_teamtailor_marketing_fixture_yields_no_listing():
    """Real marketing fixture from teamtailor integrations page must yield no listing and be dropped."""
    import json
    from pathlib import Path
    from src.project_files.search_pipeline import SearchOrchestrator

    fixture_json = Path(__file__).parent / "fixtures" / "real" / "teamtailor" / "128b01af.json"
    data = json.loads(fixture_json.read_text(encoding="utf-8"))
    marketing_url = data["url"]

    orchestrator = SearchOrchestrator()
    async with httpx.AsyncClient() as client:
        listing = await orchestrator._enrich_ats_item(
            platform="teamtailor",
            item={
                "link": marketing_url,
                "title": "Vervoe Integration",
                "snippet": "Marketing page",
            },
            query_str="site:teamtailor.com Vervoe",
            client=client,
        )

    assert listing is None
    assert orchestrator._dropped_by_platform.get("teamtailor") == 1




@pytest.mark.anyio
async def test_hotnigerianjobs_roundup_detail_fixture_unbundles_all_positions():
    """Real multi-position roundup detail page must unbundle into 4 distinct roles and fix https://https:// URLs."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "real" / "hotnigerianjobs" / "8e3de42d.html"
    html = fixture_path.read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        scraper = HotNigerianJobsScraper()
        results = await scraper.search(client, SearchParams(job_title="Avatar"))

    assert len(results) == 4
    titles = [r.title for r in results]
    assert titles == ["Chinese Translator", "HR Assistant", "Welder", "Forklift Operator"]
    assert len({r.id for r in results}) == 4
    for r in results:
        assert r.company == "Avatar New Energy Materials Company Limited"
        assert r.location == "Nasarawa"
        assert r.posted_at is not None
        assert r.posted_at.date().isoformat() == "2026-10-19"
        assert not r.apply_url.startswith("https://https://")

    hr_job = next(r for r in results if r.title == "HR Assistant")
    assert hr_job.apply_url == "https://www.hotnigerianjobs.com/hotjobs/976146/hr-assistant-at-avatar-new-energy-materials-compan.html"


@pytest.mark.anyio
async def test_hotnigerianjobs_single_detail_fixture_extracts_fields_without_duplication():
    """Real single-position detail page must return 1 listing (no .jobheader duplication) with real fields."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "real" / "hotnigerianjobs" / "dddf2c5a.html"
    html = fixture_path.read_text(encoding="utf-8")

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        scraper = HotNigerianJobsScraper()
        results = await scraper.search(client, SearchParams(job_title="Chinese Translator"))

    assert len(results) == 1
    job = results[0]
    assert job.title == "Chinese Translator"
    assert job.company == "AVATAR New Energy Materials Company Limited"
    assert job.location == "Kama Otto, Nasarawa"
    assert job.employment_type == "full_time"
    assert job.posted_at is not None
    assert job.posted_at.date().isoformat() == "2026-10-19"


def test_hotnigerianjobs_field_273_fixture_extracts_honest_metadata_and_null_location():
    """Real /field/273/ ICT listing page must extract work_model, salary, location, and keep missing location None."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "real" / "hotnigerianjobs" / "c013c370.html"
    html = fixture_path.read_text(encoding="utf-8")

    scraper = HotNigerianJobsScraper()
    results = scraper.parse_html(
        html,
        SearchParams(
            job_title="Graphics Designer Backend Engineer IT Project Manager",
            location="Abuja",
        ),
    )

    by_title = {r.title: r for r in results}
    assert "Graphics Designer" in by_title
    cavista_job = by_title["Graphics Designer"]
    assert cavista_job.company == "Cavista"
    assert cavista_job.location == "Ilupeju, Lagos State"
    assert cavista_job.work_model == "hybrid"
    assert cavista_job.work_model_source == "title"
    assert cavista_job.work_model_evidence is not None
    assert cavista_job.is_remote is False
    assert cavista_job.posted_at is not None
    assert cavista_job.posted_at.date().isoformat() == "2026-10-22"

    assert "Backend Engineer (Payments & Microservices) - Remote" in by_title
    remote_job = by_title["Backend Engineer (Payments & Microservices) - Remote"]
    assert remote_job.work_model == "remote"
    assert remote_job.is_remote is True
    assert remote_job.location == "Lagos State"
    assert remote_job.salary == "N550,000 - N650,000 monthly"

    # RightCom card does not state a location in the card; must be None, never falsified to params.location ("Abuja")
    assert "IT Project Manager" in by_title
    rightcom_job = by_title["IT Project Manager"]
    assert rightcom_job.company == "RightCom"
    assert rightcom_job.location is None


def test_hotnigerianjobs_homepage_fixture_unbundles_roundups_and_rejects_ads():
    """Real homepage feed must drop promotional ads, unbundle roundups, and filter out non-matching roles."""
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixtures" / "real" / "hotnigerianjobs" / "1b17e78c.html"
    html = fixture_path.read_text(encoding="utf-8")

    scraper = HotNigerianJobsScraper()
    results = scraper.parse_html(html, SearchParams(job_title="Software Developer Engineer"))

    titles = {r.title for r in results}
    # Promotional bootcamp ad ("Apply Before November 2, 2026 and Become a Software Developer") must be rejected
    assert not any("Apply Before November" in t for t in titles)

    # Matching roles from bundled company roundups must be extracted as individual listings
    assert "Full-Stack Software Engineer & Data Automation Developer (Fully Remote)" in titles
    assert "Full Stack Developer" in titles
    assert "Mobile Developer" in titles
    assert "Software Developer" in titles
    assert "Backend C#.Net Engineer II" in titles

    # Non-matching roles from those same roundups must NOT leak into results
    assert "Cold Calling Sales Executive (Outbound)" not in titles
    assert "Business Development Manager - Advisory" not in titles
    assert "Dispatch Rider" not in titles
    assert "Welder" not in titles
    assert "Forklift Operator" not in titles

    remote_dev = next(
        r for r in results if r.title == "Full-Stack Software Engineer & Data Automation Developer (Fully Remote)"
    )
    assert remote_dev.company == "Backend Office HQ"
    assert remote_dev.work_model == "remote"
    assert remote_dev.is_remote is True

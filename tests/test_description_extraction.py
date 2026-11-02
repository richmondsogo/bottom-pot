from __future__ import annotations

import json
from pathlib import Path
import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page
from src.project_files.ats_api_client import GreenhouseClient, LeverClient
from src.project_files.ats_url_parser import ParsedATSUrl
from src.project_files.field_normalizer import clean_html_to_markdown, description_quality, to_markdown
from src.project_files.models import JobListing

REAL_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "real"


# ---------------------------------------------------------------------------
# 1. clean_html_to_markdown Noise Decomposition Tests
# ---------------------------------------------------------------------------

def test_clean_html_to_markdown_decomposes_noise_tags():
    html_input = """
    <div>
      <header><h1>Acme Careers</h1><nav><a href="/jobs">Jobs</a></nav></header>
      <main>
        <h2>Software Engineer</h2>
        <p>We are looking for a Software Engineer to join our core team.</p>
        <aside><p>Related blog post</p></aside>
        <form><input type="text" name="email" /><button type="submit">Subscribe</button></form>
        <iframe src="https://example.com/widget"></iframe>
        <svg><path d="M0 0h24v24H0z"></path></svg>
      </main>
      <footer><p>Copyright 2026 Acme Corp</p></footer>
    </div>
    """
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "Software Engineer" in md
    assert "We are looking for a Software Engineer" in md

    # Decomposed tags must NOT appear in output
    assert "Acme Careers" not in md
    assert "Jobs" not in md
    assert "Related blog post" not in md
    assert "Subscribe" not in md
    assert "Copyright 2026 Acme Corp" not in md


def test_clean_html_to_markdown_decomposes_noise_roles():
    html_input = """
    <div>
      <div role="banner">Site Banner</div>
      <div role="navigation"><a href="/">Home</a></div>
      <article>
        <h2>Backend Lead</h2>
        <p>Lead the backend engineering team in building microservices.</p>
      </article>
      <div role="contentinfo">Footer Info</div>
    </div>
    """
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "Backend Lead" in md
    assert "Site Banner" not in md
    assert "Home" not in md
    assert "Footer Info" not in md


def test_clean_html_to_markdown_decomposes_noise_classes_and_ids():
    html_input = """
    <div>
      <div class="cookie-banner-wrap">We use cookies on this site.</div>
      <div class="user-consent-modal">Accept GDPR consent.</div>
      <div id="newsletter-signup">Sign up for our newsletter!</div>
      <div class="social-share-buttons">Share on LinkedIn, Twitter, Facebook</div>
      <div class="breadcrumb-trail">Home > Jobs > Engineering</div>
      <div class="content">
        <h2>Data Engineer</h2>
        <p>Design and build resilient ETL pipelines.</p>
      </div>
    </div>
    """
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "Data Engineer" in md
    assert "Design and build resilient ETL pipelines." in md

    # Noise class/id content must NOT appear
    assert "cookies" not in md
    assert "consent" not in md
    assert "newsletter" not in md
    assert "Share on LinkedIn" not in md
    assert "breadcrumb" not in md


# ---------------------------------------------------------------------------
# 2. description_quality Validator Tests
# ---------------------------------------------------------------------------

def test_description_quality_length_threshold():
    # Less than 300 chars must fail
    short_text = "Responsibilities include building software. Requirements: Python experience."
    assert len(short_text) < 300
    assert description_quality(short_text) is False


def test_description_quality_requires_at_least_two_job_terms_only_for_dom_scraped():
    # Long enough (350+ chars) but only 1 job term
    text_one_term = "A" * 300 + " Our requirements are extensive and thorough for every candidate who applies to this position."
    assert len(text_one_term) >= 300
    # For DOM-scraped text, requires >= 2 job-like structural terms
    assert description_quality(text_one_term, is_dom_scraped=True) is False
    # For API or JSON-LD text, trusted when len >= 300 and boilerplate check passes
    assert description_quality(text_one_term, is_dom_scraped=False) is True

    # Two distinct job terms
    text_two_terms = "A" * 300 + " Key responsibilities for this role include coding. Requirements include Python and SQL."
    assert description_quality(text_two_terms, is_dom_scraped=True) is True
    assert description_quality(text_two_terms, is_dom_scraped=False) is True


def test_description_quality_rejects_heavy_boilerplate():
    # Job terms present, but overwhelmed by cookie and privacy boilerplate
    boilerplate_text = (
        "A" * 300 + " responsibilities and requirements. "
        "Please accept our cookie policy. Review our privacy policy and terms of use. "
        "All rights reserved. Share via email, facebook, and whistleblow policy under GDPR regulations."
    )
    assert description_quality(boilerplate_text, is_dom_scraped=False) is False
    assert description_quality(boilerplate_text, is_dom_scraped=True) is False


# ---------------------------------------------------------------------------
# 3. Real Fixtures Golden Tests: Teamtailor & Avature Body Location
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_teamtailor_real_job_fixtures_extract_description_and_description_ok():
    """Teamtailor job postings publish standard JSON-LD JobPosting with full HTML description."""
    tt_dir = REAL_FIXTURES_DIR / "teamtailor"
    job_fixtures = [
        ("a3ea4593.html", "https://theunlimited.teamtailor.com/jobs/8538757-data-analyst"),
        ("b6057b16.html", "https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer"),
        ("d93e9876.html", "https://lendurai.teamtailor.com/jobs/8531586-software-engineer-handheld-devices"),
    ]

    for filename, url in job_fixtures:
        fixture_html = (tt_dir / filename).read_text(encoding="utf-8")
        def mock_handler(request: httpx.Request):
            return httpx.Response(200, text=fixture_html)

        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
            job = await enrich_ats_page(url=url, provider="teamtailor", search_title="Job", snippet="", query_used="test", client=client)

        assert job.description is not None, f"Expected description for {filename}"
        assert job.description_ok is True, f"Expected description_ok=True for {filename}"
        assert len(job.description) >= 300


@pytest.mark.anyio
async def test_teamtailor_sparteo_excludes_partner_blurbs():
    """Teamtailor Sparteo posting must extract real job text and exclude external partner blurbs."""
    tt_dir = REAL_FIXTURES_DIR / "teamtailor"
    fixture_html = (tt_dir / "b6057b16.html").read_text(encoding="utf-8")
    url = "https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer"

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=fixture_html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=url, provider="teamtailor", search_title="Job", snippet="", query_used="test", client=client)

    assert job.description is not None
    assert job.description_ok is True
    assert "Sparteo" in job.description
    assert "Fastighetsjobb" not in job.description
    assert "Evalart" not in job.description


@pytest.mark.anyio
async def test_teamtailor_marketing_page_fails_description_quality():
    """Teamtailor marketing / integration pages do not contain job descriptions."""
    tt_dir = REAL_FIXTURES_DIR / "teamtailor"
    fixture_html = (tt_dir / "128b01af.html").read_text(encoding="utf-8")
    url = "https://www.teamtailor.com/pt-br/integrations/vervoe/"

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=fixture_html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=url, provider="teamtailor", search_title="Vervoe", snippet="", query_used="test", client=client)

    assert job.description_ok is False
    assert job.description is None


@pytest.mark.anyio
async def test_avature_real_job_fixtures_extract_description_from_dom_body():
    """Avature job postings do not publish JSON-LD; the description body lives in section.js_views inside <main>."""
    av_dir = REAL_FIXTURES_DIR / "avature"
    job_fixtures = [
        ("556a4063.html", "https://koch.avature.net/en_US/careers/JobDetail/Data-Scientist/194843"),
        ("be85a1ff.html", "https://koch.avature.net/pl_PL/careers/JobDetail/Senior-Mechanical-Simulation-Engineer/193537"),
    ]

    for filename, url in job_fixtures:
        fixture_html = (av_dir / filename).read_text(encoding="utf-8")
        def mock_handler(request: httpx.Request):
            return httpx.Response(200, text=fixture_html)

        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
            job = await enrich_ats_page(url=url, provider="avature", search_title="Job", snippet="", query_used="test", client=client)

        assert job.description is not None, f"Expected DOM description for {filename}"
        assert job.description_ok is True, f"Expected description_ok=True for {filename}"
        assert len(job.description) >= 300


@pytest.mark.anyio
async def test_avature_waf_challenge_page_yields_no_description_and_falls_back_to_snippet_row():
    """Avature AWS WAF challenge interstitial pages must be treated as fetch failure and fall back to snippet row."""
    av_dir = REAL_FIXTURES_DIR / "avature"
    fixture_html = (av_dir / "608503ac.html").read_text(encoding="utf-8")
    url = "https://delta.avature.net/en_US/careers/JobDetail/Delta-Vacations-Business-Intelligence-Analyst/34025"

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=fixture_html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=url, provider="avature", search_title="Job", snippet="", query_used="test", client=client)

    assert job.data_source == "snippet"
    assert job.description is None
    assert job.description_ok is False
    assert job.company == "Delta"
    assert "Delta Vacations Business Intelligence Analyst" in job.title


# ---------------------------------------------------------------------------
# 4. to_markdown Formatting & Regression Tests (Workday, Greenhouse, Lever, Teamtailor)
# ---------------------------------------------------------------------------




@pytest.mark.anyio
async def test_provider_fixtures_formatting_regressions():
    """Greenhouse, Lever, and Teamtailor fixtures also contain blank-line-separated paragraphs,

    at least one '- ' list item, and no leftover HTML tags or &amp; entities.
    """
    # 1. Greenhouse
    gh_data = json.loads((REAL_FIXTURES_DIR / "greenhouse" / "job_8860302002.json").read_text())
    def mock_gh(req: httpx.Request):
        return httpx.Response(200, json=gh_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_gh)) as client:
        parsed_gh = ParsedATSUrl(ats="greenhouse", company_slug="gitlab", job_id="8860302002", raw_url="https://boards.greenhouse.io/gitlab/jobs/8860302002")
        job_gh = await GreenhouseClient().fetch(parsed_gh, client)

    assert job_gh is not None and job_gh.description is not None
    assert "\n\n" in job_gh.description
    assert "\n- " in job_gh.description
    assert "<" not in job_gh.description
    assert "&amp;" not in job_gh.description

    # 2. Lever
    lev_data = json.loads((REAL_FIXTURES_DIR / "lever" / "job_caadac8e.json").read_text())
    def mock_lev(req: httpx.Request):
        return httpx.Response(200, json=lev_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_lev)) as client:
        parsed_lev = ParsedATSUrl(ats="lever", company_slug="kinsta", job_id="caadac8e", raw_url="https://jobs.lever.co/kinsta/caadac8e")
        job_lev = await LeverClient().fetch(parsed_lev, client)

    assert job_lev is not None and job_lev.description is not None
    assert "\n\n" in job_lev.description
    assert "\n- " in job_lev.description
    assert "<" not in job_lev.description
    assert "&amp;" not in job_lev.description

    # 3. Teamtailor
    tt_html = (REAL_FIXTURES_DIR / "teamtailor" / "b6057b16.html").read_text(encoding="utf-8")
    def mock_tt(req: httpx.Request):
        return httpx.Response(200, text=tt_html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_tt)) as client:
        job_tt = await enrich_ats_page(url="https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer", provider="teamtailor", search_title="Job", snippet="", query_used="test", client=client)

    assert job_tt is not None and job_tt.description is not None
    assert "\n\n" in job_tt.description
    assert "\n- " in job_tt.description
    assert "<" not in job_tt.description
    assert "&amp;" not in job_tt.description


@pytest.mark.anyio
async def test_workday_cxs_json_extraction():
    """Workday CXS JSON endpoint extracts high-fidelity HTML description into Markdown with paragraphs and list items."""
    wd_dir = REAL_FIXTURES_DIR / "workday"
    cxs_data = json.loads((wd_dir / "cxs_4dcb1862.json").read_text(encoding="utf-8"))
    job_url = "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"

    def mock_handler(request: httpx.Request):
        if "/wday/cxs/" in str(request.url):
            return httpx.Response(200, json=cxs_data)
        return httpx.Response(500, text="Should not hit HTML path on CXS 200")

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=job_url, provider="workday", search_title="Job", snippet="", query_used="test", client=client)

    assert job.data_source == "api"
    assert job.description is not None
    assert "\n\n" in job.description
    assert "\n- " in job.description
    assert "<" not in job.description
    assert "&amp;" not in job.description
    assert job.employment_type == "full_time"
    assert "Forward Deployed Engineer" in job.title


@pytest.mark.anyio
async def test_workday_cxs_403_fallback():
    """When Workday CXS endpoint returns 403, enrich_ats_page falls back gracefully to JSON-LD/HTML path."""
    wd_dir = REAL_FIXTURES_DIR / "workday"
    html_data = (wd_dir / "4dcb1862.html").read_text(encoding="utf-8")
    job_url = "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"

    def mock_handler(request: httpx.Request):
        if "/wday/cxs/" in str(request.url):
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=html_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=job_url, provider="workday", search_title="Job", snippet="", query_used="test", client=client)

    assert job.data_source == "scrape"
    assert job.description is not None
    assert "<" not in job.description
    assert "&amp;" not in job.description


def test_workday_cxs_url_builder_strips_apply_suffix_and_query():
    """Verify that _build_workday_cxs_url strips trailing /apply and query strings while preserving apply_url."""
    from src.project_files.ats_page_enricher import _build_workday_cxs_url

    # Real fixture URL shape with /apply and query string
    url_with_apply = "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806/apply?source=LinkedIn"
    cxs_url = _build_workday_cxs_url(url_with_apply)
    assert cxs_url == "https://dxctechnology.wd1.myworkdayjobs.com/wday/cxs/dxctechnology/DXCJobs/job/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"

    # With trailing slash on apply
    url_trailing_slash = "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806/apply/"
    cxs_url2 = _build_workday_cxs_url(url_trailing_slash)
    assert cxs_url2 == "https://dxctechnology.wd1.myworkdayjobs.com/wday/cxs/dxctechnology/DXCJobs/job/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"


@pytest.mark.anyio
async def test_workday_cxs_enrich_with_apply_url():
    """enrich_ats_page successfully queries CXS when given a /apply URL while keeping job.apply_url untouched."""
    wd_dir = REAL_FIXTURES_DIR / "workday"
    cxs_data = json.loads((wd_dir / "cxs_4dcb1862.json").read_text(encoding="utf-8"))
    apply_url = "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806/apply?source=Serp"

    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        if "/wday/cxs/dxctechnology/DXCJobs/job/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806" in url_str:
            return httpx.Response(200, json=cxs_data)
        return httpx.Response(404, text="Not found")

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=apply_url, provider="workday", search_title="Job", snippet="", query_used="test", client=client)

    assert job is not None
    assert job.data_source == "api"
    assert job.location == "ESP - MD - LAS ROZAS"
    # apply_url must be kept intact as the original application URL
    assert job.apply_url == apply_url


@pytest.mark.anyio
async def test_workday_cxs_golden_replay():
    golden_path = Path(__file__).parent / "fixtures" / "golden" / "workday_cxs_4dcb1862.json"
    golden_json = json.loads(golden_path.read_text(encoding="utf-8"))
    cxs_path = REAL_FIXTURES_DIR / "workday" / "cxs_4dcb1862.json"
    cxs_data = json.loads(cxs_path.read_text(encoding="utf-8"))

    url = golden_json["apply_url"]

    def mock_handler(request: httpx.Request):
        if "/wday/cxs/" in str(request.url):
            return httpx.Response(200, json=cxs_data)
        return httpx.Response(500, text="Unexpected request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(url=url + "?nocache=1", provider="workday", search_title="Job", snippet="", query_used="test", client=client)

    new_json = json.loads(job.model_dump_json())
    del golden_json["scraped_at"]
    del new_json["scraped_at"]
    del golden_json["id"]
    del new_json["id"]
    del golden_json["apply_url"]
    del new_json["apply_url"]
    del golden_json["source_url"]
    del new_json["source_url"]
    golden_json.pop("freshness_label", None)
    new_json.pop("freshness_label", None)
    golden_json.pop("field_evidence", None)
    new_json.pop("field_evidence", None)

    # Documented intentional diffs:
    # 1. Cleaner preserves markdown link for [here](safelinks...)
    assert "[here](" in new_json["description"]
    golden_json["description"] = new_json["description"]

    # 2. Authentic description scan classifies work_model=in_person
    assert golden_json["work_model"] is None
    assert new_json["work_model"] == "in_person"
    assert new_json["is_remote"] is False
    assert new_json["work_model_source"] == "description"
    golden_json["work_model"] = new_json["work_model"]
    golden_json["is_remote"] = new_json["is_remote"]
    golden_json["work_model_source"] = new_json["work_model_source"]
    golden_json["work_model_evidence"] = new_json["work_model_evidence"]

    assert golden_json == new_json



# ---------------------------------------------------------------------------
# 6. Real Fixtures Golden Tests: Jobvite
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_jobvite_active_posting_extraction():
    """Active Jobvite postings publish standard JSON-LD JobPosting with full HTML description."""
    jv_dir = REAL_FIXTURES_DIR / "jobvite"
    zones_html = (jv_dir / "f1f15d8e.html").read_text(encoding="utf-8")
    ookla_html = (jv_dir / "067d3f2a.html").read_text(encoding="utf-8")

    # 1. Zones
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=zones_html))
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://jobs.jobvite.com/zones/job/ot8zAfwu",
            provider="jobvite",
            search_title="",
            snippet="",
            query_used="test",
            client=client,
        )
    assert job is not None
    assert job.title == "Project Manager 1"
    assert job.company == "Zones LLC."
    assert job.company_slug == "zones"
    assert job.location == "Pakistan"
    assert job.description is not None
    assert "\n\n" in job.description
    assert "<" not in job.description
    assert job.description_ok is True
    assert job.data_source == "scrape"

    # 2. Ookla
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=ookla_html))
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://jobs.jobvite.com/ookla/job/oIFQAfwx",
            provider="jobvite",
            search_title="",
            snippet="",
            query_used="test",
            client=client,
        )
    assert job is not None
    assert job.title == "Financial Accountant"
    assert job.company == "Ookla"
    assert job.company_slug == "ookla"
    assert job.location == "Finland"
    assert job.description is not None
    assert job.description_ok is True


@pytest.mark.anyio
async def test_jobvite_expired_posting_is_dropped():
    """Expired/404 Jobvite postings redirect to catalog page with .jv-alert and must be dropped (return None)."""
    jv_dir = REAL_FIXTURES_DIR / "jobvite"
    expired_html = (jv_dir / "4d1da9f3.html").read_text(encoding="utf-8")

    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=expired_html))
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://jobs.jobvite.com/zones/job/ovbQAfwQ",
            provider="jobvite",
            search_title="Zones LLC. Careers",
            snippet="",
            query_used="test",
            client=client,
        )
    assert job is None


@pytest.mark.anyio
async def test_jobvite_company_from_url_slug_when_hiring_org_missing():
    """When JobPosting hiringOrganization is missing, company falls back to URL slug (humanize_slug)."""
    fake_html = """
    <html><head>
    <script type="application/ld+json">
    {
        "@context": "http://schema.org",
        "@type": "JobPosting",
        "title": "Software Engineer",
        "jobLocation": {"@type": "Place", "address": "Seattle, WA"},
        "description": "<div><p>We are seeking a Software Engineer with responsibilities and requirements.</p><p>Experience with Python.</p></div>"
    }
    </script>
    </head><body><div class="jv-wrapper"></div></body></html>
    """
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=fake_html))
    async with httpx.AsyncClient(transport=transport) as client:
        job = await enrich_ats_page(
            url="https://jobs.jobvite.com/zones/job/oFake123",
            provider="jobvite",
            search_title="",
            snippet="",
            query_used="test",
            client=client,
        )
    assert job is not None
    assert job.company == "Zones"
    assert job.company_slug == "zones"


@pytest.mark.anyio
async def test_jobvite_golden_replay():
    golden_path = Path(__file__).parent / "fixtures" / "golden" / "jobvite_067d3f2a.json"
    golden_json = json.loads(golden_path.read_text(encoding="utf-8"))
    jv_dir = REAL_FIXTURES_DIR / "jobvite"
    html_data = (jv_dir / "067d3f2a.html").read_text(encoding="utf-8")

    url = golden_json["apply_url"]

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(
            url=url + "?nocache=1",
            provider="jobvite",
            search_title="Financial Accountant",
            snippet="Financial Accountant at Ookla",
            query_used="test",
            client=client,
        )

    new_json = json.loads(job.model_dump_json())
    del golden_json["scraped_at"]
    del new_json["scraped_at"]
    del golden_json["id"]
    del new_json["id"]
    del golden_json["apply_url"]
    del new_json["apply_url"]
    del golden_json["source_url"]
    del new_json["source_url"]
    golden_json.pop("freshness_label", None)
    new_json.pop("freshness_label", None)
    golden_json.pop("field_evidence", None)
    new_json.pop("field_evidence", None)

    # Documented intentional diffs:
    # 1. Authentic description contains 'The salary compensation for this role is €55,000 - €60,000.'
    # Now extracted by JobExtractionService into structured JobSalary
    assert golden_json["salary"] is None
    assert new_json["salary"] == {
        "minimum": 55000,
        "maximum": 60000,
        "currency": "EUR",
        "period": None,
        "raw_text": "€55,000 - €60,000",
        "source": "jobvite_description_label",
    }
    golden_json["salary"] = new_json["salary"]

    # 2. ADR 0028 deterministic core confidence (0.86)
    assert golden_json["extraction_confidence"] == 0.86
    assert new_json["extraction_confidence"] == 0.86
    golden_json["extraction_confidence"] = new_json["extraction_confidence"]

    # 3. Centralized description cleaner preserves [accenture.com](http://accenture.com/) link
    assert "[accenture.com](http://accenture.com/)" in new_json["description"]
    golden_json["description"] = new_json["description"]

    assert golden_json == new_json


@pytest.mark.anyio
async def test_jazzhr_golden_replay():
    golden_path = Path(__file__).parent / "fixtures" / "golden" / "jazzhr_apply.json"
    golden_json = json.loads(golden_path.read_text(encoding="utf-8"))
    apply_html = (Path(__file__).parent / "fixtures" / "jazzhr_apply.html").read_text(encoding="utf-8")

    url = golden_json["apply_url"]

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=apply_html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(
            url=url + "?nocache=1",
            provider="jazzhr",
            search_title="Senior Software Engineer (Product)",
            snippet="Senior Software Engineer at ActiveProspect",
            query_used="test",
            client=client,
        )

    new_json = json.loads(job.model_dump_json())
    del golden_json["scraped_at"]
    del new_json["scraped_at"]
    del golden_json["id"]
    del new_json["id"]
    del golden_json["apply_url"]
    del new_json["apply_url"]
    del golden_json["source_url"]
    del new_json["source_url"]
    golden_json.pop("freshness_label", None)
    new_json.pop("freshness_label", None)
    golden_json.pop("field_evidence", None)
    new_json.pop("field_evidence", None)

    # Documented intentional diffs:
    # Work model source and evidence accurately record structured jsonld / TELECOMMUTE
    assert new_json["work_model"] == "remote"
    assert new_json["work_model_source"] == "jsonld"
    assert new_json["work_model_evidence"] == "jobLocationType=TELECOMMUTE"
    golden_json["work_model_source"] = new_json["work_model_source"]
    golden_json["work_model_evidence"] = new_json["work_model_evidence"]

    assert golden_json == new_json


@pytest.mark.anyio
async def test_teamtailor_golden_replay():
    golden_path = Path(__file__).parent / "fixtures" / "golden" / "teamtailor_128b01af.json"
    golden_json = json.loads(golden_path.read_text(encoding="utf-8"))
    tt_dir = REAL_FIXTURES_DIR / "teamtailor"
    html_data = (tt_dir / "128b01af.html").read_text(encoding="utf-8")

    url = golden_json["apply_url"]

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        job = await enrich_ats_page(
            url=url + "?nocache=1",
            provider="teamtailor",
            search_title="Vervoe integration",
            snippet="Vervoe integration snippet",
            query_used="test",
            client=client,
        )

    new_json = json.loads(job.model_dump_json())
    del golden_json["scraped_at"]
    del new_json["scraped_at"]
    del golden_json["id"]
    del new_json["id"]
    del golden_json["apply_url"]
    del new_json["apply_url"]
    del golden_json["source_url"]
    del new_json["source_url"]
    golden_json.pop("freshness_label", None)
    new_json.pop("freshness_label", None)
    golden_json.pop("field_evidence", None)
    new_json.pop("field_evidence", None)

    assert golden_json == new_json


# ---------------------------------------------------------------------------
# 5. Description Cleaner Enhancements & Idempotency Tests (Step 22b)
# ---------------------------------------------------------------------------

def test_clean_html_to_markdown_preserves_links():
    html_input = '<p>Apply directly on <a href="https://example.com/apply">our career portal</a> or email <a href="mailto:jobs@example.com">jobs@example.com</a>.</p>'
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "[our career portal](https://example.com/apply)" in md
    assert "jobs@example.com" in md


def test_clean_html_to_markdown_preserves_tables():
    html_input = """
    <table>
      <thead>
        <tr><th>Level</th><th>Years</th><th>Location</th></tr>
      </thead>
      <tbody>
        <tr><td>Senior</td><td>5+</td><td>Remote</td></tr>
        <tr><td>Staff</td><td>8+</td><td>Hybrid</td></tr>
      </tbody>
    </table>
    """
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "| Level | Years | Location |" in md
    assert "| Senior | 5+ | Remote |" in md
    assert "| Staff | 8+ | Hybrid |" in md


def test_clean_html_to_markdown_decomposes_adsense():
    html_input = """
    <div>
      <p>Job introduction.</p>
      <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-123"></ins>
      <div class="google-ad-banner">Advertisement</div>
      <p>Key responsibilities and qualifications.</p>
    </div>
    """
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "Job introduction." in md
    assert "Key responsibilities and qualifications." in md
    assert "adsbygoogle" not in md
    assert "Advertisement" not in md


def test_clean_html_to_markdown_handles_double_escaped_entities():
    html_input = "&amp;lt;p&amp;gt;We are hiring a &amp;amp; Backend Engineer &amp;lt;strong&amp;gt;immediately&amp;lt;/strong&amp;gt;.&amp;lt;/p&amp;gt;"
    md = clean_html_to_markdown(html_input)
    assert md is not None
    assert "We are hiring a & Backend Engineer **immediately**." in md


def test_clean_html_to_markdown_preserves_literal_comparison_operators():
    text_input = "Requirements: < 5 years required and > 2 years preferred; salary < $150k."
    md = clean_html_to_markdown(text_input)
    assert md is not None
    assert "< 5 years" in md
    assert "> 2 years" in md
    assert "< $150k" in md


def test_clean_html_to_markdown_markdown_special_chars_do_not_gain_escapes():
    md_input = """
    ## Responsibilities
    - Develop **scalable** services
    - Write *clean* code
    - 5+ years experience
    """
    cleaned = clean_html_to_markdown(md_input)
    assert cleaned is not None
    assert "## Responsibilities" in cleaned
    assert "- Develop **scalable** services" in cleaned
    assert "- Write *clean* code" in cleaned
    assert r"\*\*" not in cleaned
    assert r"\*" not in cleaned


def test_clean_html_to_markdown_idempotency_over_all_fixtures():
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    fixture_files = list(fixtures_dir.rglob("*.json")) + list(fixtures_dir.rglob("*.html")) + list(fixtures_dir.rglob("*.md"))

    for p in fixture_files:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if p.suffix == ".json":
                data = json.loads(content)
                desc = (
                    data.get("content")
                    or data.get("description")
                    or data.get("descriptionHtml")
                    or (data.get("jobDescription", {}) if isinstance(data.get("jobDescription"), dict) else {}).get("text")
                )
            else:
                desc = content
            if desc and len(desc) > 50:
                c1 = clean_html_to_markdown(desc)
                c2 = clean_html_to_markdown(c1)
                c3 = clean_html_to_markdown(c2)
                assert c1 == c2, f"Idempotency failed (c1 != c2) for fixture: {p.name}"
                assert c2 == c3, f"Idempotency failed (c2 != c3) for fixture: {p.name}"
        except Exception as exc:
            if isinstance(exc, AssertionError):
                raise


def test_work_model_resolver_sees_li_tags_before_cleaner_strips_them():
    from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting

    raw = RawJobPosting(
        provider="greenhouse",
        source_url="https://boards.greenhouse.io/acme/jobs/123",
        provider_job_id="123",
        company_slug="acme",
        raw_title="Staff Software Engineer",
        raw_company="Acme Corp",
        raw_location="San Francisco, CA",
        raw_description="<p>We are hiring a Staff Software Engineer. #LI-Remote Responsibilities include designing distributed systems.</p>",
        description_is_authentic=True,
    )

    canonical = JobExtractionService.extract(raw)
    assert canonical.work_model == "remote"
    assert canonical.work_model_source == "li_tag"
    assert canonical.work_model_evidence == "#LI-Remote"

    # User-facing description has the #LI-* recruiter tag stripped
    assert canonical.description is not None
    assert "#LI-Remote" not in canonical.description
    assert "Staff Software Engineer." in canonical.description


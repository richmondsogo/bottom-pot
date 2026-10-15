from __future__ import annotations

import json
from pathlib import Path
import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page
from src.project_files.field_normalizer import clean_html_to_markdown, description_quality
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

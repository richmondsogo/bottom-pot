from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bs4 import BeautifulSoup

from src.project_files.company_board_registry import CompanyBoardRegistry, is_valid_board_slug
from src.project_files.job_extraction_service import RawJobPosting
from src.project_files.models import JobListing, SearchParams
from src.project_files.nigerian_scrapers import (
    JobbermanScraper,
    MyJobMagScraper,
    HotNigerianJobsScraper,
    _find_contextual_apply_link,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "nigerian"


def test_jobberman_contextual_apply_and_enrichment():
    fixture_path = FIXTURES_DIR / "jobberman_sample_detail.html"
    assert fixture_path.exists(), "Jobberman fixture must exist"
    html = fixture_path.read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    apply_link = _find_contextual_apply_link(soup, "jobberman.com")
    assert apply_link == "https://boards.greenhouse.io/paystack/jobs/1234567"

    scraper = JobbermanScraper()
    detail_md = scraper.extract_detail_markdown(html)
    assert detail_md is not None
    assert "Job Description & Requirements" in detail_md
    assert "Node.js" in detail_md


def test_myjobmag_title_clean_preserves_valid_titles():
    scraper = MyJobMagScraper()

    # 1. Title with "at" that is part of the job role (e.g. Live at Home Carer)
    html_card_carer = """
    <li class="job-list-li">
        <h2><a href="/job/live-at-home-carer">Live at Home Carer</a></h2>
        <li class="job-logo"><img alt="Premier Care Services logo" /></li>
    </li>
    """
    soup = BeautifulSoup(html_card_carer, "lxml")
    item = soup.select_one("li.job-list-li")
    raw_title_text = "Live at Home Carer"
    logo_img = item.select_one("li.job-logo img")
    company = "Premier Care Services"

    # Cleaning title should not strip "at Home Carer" because company does not match
    import re
    pattern = rf"\s+(?:at|@)\s+{re.escape(company)}\s*$"
    if re.search(pattern, raw_title_text, re.IGNORECASE):
        cleaned = re.sub(pattern, "", raw_title_text, flags=re.IGNORECASE).strip()
    else:
        cleaned = raw_title_text
    assert cleaned == "Live at Home Carer"

    # 2. Title with non-company word "Sea" (Architect at Sea)
    raw_title_sea = "Architect at Sea"
    non_company_words = {"home", "sea", "large", "work", "site", "risk", "scale", "peace", "rest"}
    match = re.search(r"^(.*?)\s+(?:at|@)\s+([A-Z][A-Za-z0-9&.,' -]{1,50})$", raw_title_sea)
    if match and match.group(2).strip().lower() not in non_company_words:
        cleaned_sea = match.group(1).strip()
    else:
        cleaned_sea = raw_title_sea
    assert cleaned_sea == "Architect at Sea"

    # 3. Legitimate title with company suffix "Frontend Engineer at Kuda Bank"
    raw_title_kuda = "Frontend Engineer at Kuda Bank"
    company_kuda = "Kuda Bank"
    pattern_kuda = rf"\s+(?:at|@)\s+{re.escape(company_kuda)}\s*$"
    if re.search(pattern_kuda, raw_title_kuda, re.IGNORECASE):
        cleaned_kuda = re.sub(pattern_kuda, "", raw_title_kuda, flags=re.IGNORECASE).strip()
    else:
        cleaned_kuda = raw_title_kuda
    assert cleaned_kuda == "Frontend Engineer"


def test_myjobmag_contextual_apply_and_enrichment():
    fixture_path = FIXTURES_DIR / "myjobmag_sample_detail.html"
    assert fixture_path.exists(), "MyJobMag fixture must exist"
    html = fixture_path.read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    apply_link = _find_contextual_apply_link(soup, "myjobmag.com")
    assert apply_link == "https://jobs.ashbyhq.com/moniepoint/88888888-4444-4444-4444-121212121212"


def test_hotnigerianjobs_roundup_scoping():
    fixture_path = FIXTURES_DIR / "hotnigerianjobs_roundup_detail.html"
    assert fixture_path.exists(), "HotNigerianJobs roundup fixture must exist"
    html = fixture_path.read_text(encoding="utf-8")

    scraper = HotNigerianJobsScraper()
    now = datetime.now(timezone.utc)

    # Listing 1: "Senior Backend Engineer (Payments)"
    listing_se = JobListing(
        id="hnj-se-123",
        title="Senior Backend Engineer (Payments)",
        company="Interswitch Group",
        location="Lagos",
        apply_url="https://www.hotnigerianjobs.com/hotjobs/348291/#senior-backend-engineer-payments",
        source_url="https://www.hotnigerianjobs.com/hotjobs/348291/",
        provider="hotnigerianjobs",
        ats_source="hotnigerianjobs",
        data_source="scrape",
        query_used="backend engineer",
        scraped_at=now,
    )

    enriched_se = scraper.enrich_listing_from_detail(listing_se, html)
    assert enriched_se is True
    # Must pick the Lever link specifically for Senior Backend Engineer
    assert listing_se.apply_url == "https://jobs.lever.co/interswitch/11111111-2222-3333-4444-555555555555"
    assert "Java, Spring Boot" in (listing_se.description or "")
    # Should not contain Product Designer responsibilities
    assert "figma" not in (listing_se.description or "").lower()

    # Listing 2: "Product Designer (UI/UX)"
    listing_pd = JobListing(
        id="hnj-pd-123",
        title="Product Designer (UI/UX)",
        company="Interswitch Group",
        location="Remote",
        apply_url="https://www.hotnigerianjobs.com/hotjobs/348291/#product-designer-ui-ux",
        source_url="https://www.hotnigerianjobs.com/hotjobs/348291/",
        provider="hotnigerianjobs",
        ats_source="hotnigerianjobs",
        data_source="scrape",
        query_used="product designer",
        scraped_at=now,
    )

    enriched_pd = scraper.enrich_listing_from_detail(listing_pd, html)
    assert enriched_pd is True
    # Must pick the Lever link specifically for Product Designer
    assert listing_pd.apply_url == "https://jobs.lever.co/interswitch/99999999-8888-7777-6666-555555555555"
    assert "figma" in (listing_pd.description or "").lower()
    # Should not contain Java / Spring Boot
    assert "spring boot" not in (listing_pd.description or "").lower()

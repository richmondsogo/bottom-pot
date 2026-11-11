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
    cleaned, company = scraper.clean_title("Live at Home Carer", company="Premier Care Services")
    assert cleaned == "Live at Home Carer"
    assert company == "Premier Care Services"

    # Also with Unknown Company, "Home" should be recognized as a non-company word
    cleaned_unknown, company_unknown = scraper.clean_title("Live at Home Carer", company="Unknown Company")
    assert cleaned_unknown == "Live at Home Carer"

    # 2. Title with non-company word "Sea" (Architect at Sea)
    cleaned_sea, company_sea = scraper.clean_title("Architect at Sea", company="Unknown Company")
    assert cleaned_sea == "Architect at Sea"

    # 3. Legitimate title with company suffix "Frontend Engineer at Kuda Bank"
    cleaned_kuda, company_kuda = scraper.clean_title("Frontend Engineer at Kuda Bank", company="Kuda Bank")
    assert cleaned_kuda == "Frontend Engineer"
    assert company_kuda == "Kuda Bank"

    # When company was Unknown Company initially, extracts the company
    cleaned_extracted, company_extracted = scraper.clean_title("Senior Product Designer at Paystack", company="Unknown Company")
    assert cleaned_extracted == "Senior Product Designer"
    assert company_extracted == "Paystack"


def test_contextual_apply_link_ignores_unrelated_chrome_links():
    html_with_chrome = """
    <html>
      <header>
        <a href="https://boards.greenhouse.io/other-co/jobs/999" class="apply-btn">Apply Now</a>
      </header>
      <nav>
        <a href="https://jobs.ashbyhq.com/navigation-co/456" class="btn-apply">Quick Apply</a>
      </nav>
      <main>
        <div class="job-description">
          <p>We are hiring an engineer.</p>
        </div>
        <div class="apply-section">
          <a href="https://jobs.lever.co/target-company/12345678-abcd" class="apply-btn">Apply for this role</a>
        </div>
      </main>
      <aside class="related-jobs">
        <h3>Related Jobs</h3>
        <a href="https://apply.workable.com/other/j/123" class="apply-btn">Apply Now</a>
      </aside>
      <footer>
        <a href="https://jobs.lever.co/footer-co/789" class="apply-btn">Apply on Lever</a>
      </footer>
    </html>
    """
    soup = BeautifulSoup(html_with_chrome, "lxml")
    apply_url = _find_contextual_apply_link(soup, "nigeriansite.com")
    assert apply_url == "https://jobs.lever.co/target-company/12345678-abcd"


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

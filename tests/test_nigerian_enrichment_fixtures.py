from datetime import datetime, timezone
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.models import JobListing
from src.discovery.nigerian_scrapers import (
    HotNigerianJobsScraper,
    JobbermanScraper,
    MyJobMagScraper,
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


@pytest.mark.anyio
async def test_nigerian_verified_logos_and_post_enrichment_domain_refresh():
    import asyncio

    import httpx

    from src.core.models import SearchParams
    from src.discovery.nigerian_scrapers import _extract_jobposting_jsonld
    from src.extraction.job_extraction_service import RawJobPosting
    from src.extraction.logo_extractor import (
        extract_company_logo_for_provider,
        extract_jobposting_jsonld_from_soup,
    )

    # 1. Jobberman extracts i.roamcdn.net/kazi/... verified logo and rejects default SVGs/ads
    real_jobberman_with_logo = Path(__file__).parent / "fixtures" / "real" / "jobberman" / "03dbf68a.html"
    real_jobberman_anon = Path(__file__).parent / "fixtures" / "real" / "jobberman" / "38371977.html"
    real_jobberman_default = Path(__file__).parent / "fixtures" / "real" / "jobberman" / "a3b49d05.html"

    if real_jobberman_with_logo.exists():
        s_logo = BeautifulSoup(real_jobberman_with_logo.read_text(encoding="utf-8", errors="ignore"), "lxml")
        res = extract_company_logo_for_provider(
            "jobberman", json_ld_doc=extract_jobposting_jsonld_from_soup(s_logo), soup=s_logo
        )
        assert res.verified is True
        assert res.url is not None and "i.roamcdn.net/kazi/" in res.url
        assert "sdc-bn" not in res.url

    if real_jobberman_anon.exists():
        s_anon = BeautifulSoup(real_jobberman_anon.read_text(encoding="utf-8", errors="ignore"), "lxml")
        res_anon = extract_company_logo_for_provider(
            "jobberman", json_ld_doc=extract_jobposting_jsonld_from_soup(s_anon), soup=s_anon
        )
        assert res_anon.url is None

    if real_jobberman_default.exists():
        s_def = BeautifulSoup(real_jobberman_default.read_text(encoding="utf-8", errors="ignore"), "lxml")
        res_def = extract_company_logo_for_provider(
            "jobberman", json_ld_doc=extract_jobposting_jsonld_from_soup(s_def), soup=s_def
        )
        assert res_def.url is None

    # 2. Jobberman detail enrichment refreshes company_domain when apply_url resolves to curated ATS board
    detail_html = (FIXTURES_DIR / "jobberman_sample_detail.html").read_text(encoding="utf-8").replace(
        "https://boards.greenhouse.io/paystack/jobs/1234567",
        "https://jobs.ashbyhq.com/supabase/88888888-4444-4444-4444-121212121212",
    )
    now = datetime.now(timezone.utc)
    jb_listing = JobListing(
        id="jb-supabase-1",
        provider="jobberman",
        ats_source="jobberman",
        data_source="scrape",
        title="Backend Engineer",
        company="Supabase",
        apply_url="https://www.jobberman.com/listings/backend-engineer-supabase-1",
        source_url="https://www.jobberman.com/listings/backend-engineer-supabase-1",
        scraped_at=now,
        query_used="backend",
    )
    assert jb_listing.company_domain is None

    assert _extract_jobposting_jsonld(BeautifulSoup("<div></div>", "lxml")) is None

    raw_jb = RawJobPosting(
        provider="jobberman",
        source_url=jb_listing.source_url,
        apply_url=jb_listing.apply_url,
        raw_title=jb_listing.title,
        raw_company=jb_listing.company,
        scraped_at=now,
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, text=detail_html))
    ) as client:
        await JobbermanScraper()._enrich_detail(client, jb_listing, raw_jb, asyncio.Semaphore(1))
    assert jb_listing.apply_url == "https://jobs.ashbyhq.com/supabase/88888888-4444-4444-4444-121212121212"
    assert jb_listing.company_domain == "supabase.com"
    assert jb_listing.company_domain_source == "catalog_verified"

    # 3. MyJobMag li.job-logo img extracts verified employer logo & rejects placeholder
    mjm_card = BeautifulSoup(
        '<ul><li class="job-list-li"><li class="job-logo"><img src="https://cdn.moniepoint.com/logo.png" alt="Moniepoint logo"></li></li></ul>',
        "lxml",
    )
    mjm_res = extract_company_logo_for_provider("myjobmag", soup=mjm_card)
    assert mjm_res.url == "https://cdn.moniepoint.com/logo.png"
    assert mjm_res.verified is True

    mjm_default = BeautifulSoup(
        '<li class="job-logo"><img src="/assets/images/logo.png" alt="MyJobMag logo"></li>',
        "lxml",
    )
    assert extract_company_logo_for_provider("myjobmag", soup=mjm_default).url is None

    # 4. HotNigerianJobs corporate mailto resolves domain while freemail mailto stays None
    hnj_html = """
    <html><body>
      <div class="mycase">
        <h2><a href="https://www.hotnigerianjobs.com/hotjobs/99901/qa-engineer-at-avtne/">QA Engineer at Avtne</a></h2>
        <div class="mycase4">Send CV to <a href="mailto:hr@avtne.com">hr@avtne.com</a></div>
      </div>
      <div class="mycase">
        <h2><a href="https://www.hotnigerianjobs.com/hotjobs/99902/sales-rep-at-localbiz/">Sales Rep at LocalBiz</a></h2>
        <div class="mycase4">Send CV to <a href="mailto:jobs@gmail.com">jobs@gmail.com</a></div>
      </div>
    </body></html>
    """
    hnj_items = HotNigerianJobsScraper().parse_html(hnj_html, SearchParams(job_title="Engineer Sales"))
    by_id = {it.title: it for it in hnj_items}
    assert by_id["QA Engineer"].company_domain == "avtne.com"
    assert by_id["QA Engineer"].company_domain_source == "mailto_corporate_domain"
    assert by_id["Sales Rep"].company_domain is None


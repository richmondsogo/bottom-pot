"""Tests for verified company_domain extraction, priority rules, and offline logo coverage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.logo_coverage import compute_logo_coverage, format_coverage_report
from src.api.allowlist import ADMIN_JOB_FIELDS, USER_JOB_FIELDS, serialize_event_for_user
from src.core.models import CanonicalJob, JobListing, ResultsBatch
from src.core.settings import ATS_PLATFORMS
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.domain_extractor import (
    extract_registrable_domain,
    lookup_curated_company_domain,
    resolve_company_domain,
)
from src.monitoring.employer_board_catalog import (
    VERIFIED_EMPLOYER_BOARDS,
    preview_catalog_activation,
)


def test_extract_registrable_domain_rejects_all_ats_and_invalid_hosts():
    for cfg in ATS_PLATFORMS:
        host = cfg.site_operator.split("/")[0]
        assert extract_registrable_domain(f"https://{host}/acme/jobs/1") is None
        assert extract_registrable_domain(f"https://jobs.{host}/acme/1") is None

    for denied in (
        "https://acme.jobs.personio.de/job/123",
        "https://acme.personio.co.uk/job/123",
        "https://wd3.myworkdaysite.com/recruiting/acme/123",
        "https://jobberman.com/listings/swe",
        "https://www.linkedin.com/jobs/view/123",
        "https://bit.ly/3abc123",
        "https://127.0.0.1/jobs",
        "http://[::1]:8000/jobs",
        "http://localhost:8000/jobs",
        "javascript:alert(1)",
        "mailto:jobs@stripe.com",
        "",
        None,
        "singlelabel",
        "https://notarealhost.invalidtld99/job",
    ):
        assert extract_registrable_domain(denied) is None, f"Expected None for {denied!r}"


def test_extract_registrable_domain_reduces_employer_hosts_and_multipart_tlds():
    assert extract_registrable_domain("https://careers.stripe.com/jobs/search") == "stripe.com"
    assert extract_registrable_domain("https://apply.engineering.monzo.co.uk/role/1") == "monzo.co.uk"
    assert extract_registrable_domain("https://jobs.paystack.com.ng/apply") == "paystack.com.ng"
    assert extract_registrable_domain("https://careers.electrum.co.za/vacancies") == "electrum.co.za"
    assert extract_registrable_domain("https://jobs.nubank.com.br/role") == "nubank.com.br"
    assert extract_registrable_domain("https://careers.canva.com.au/jobs") == "canva.com.au"


def test_resolve_company_domain_priority_and_catalog_completeness():
    # Priority (a): catalog_verified overrides apply_url host
    dom, src = resolve_company_domain(
        provider="ashby",
        company_slug="supabase",
        apply_url="https://jobs.ashbyhq.com/supabase/123",
    )
    assert dom == "supabase.com"
    assert src == "catalog_verified"

    dom_override, src_override = resolve_company_domain(
        provider="greenhouse",
        company_slug="other",
        apply_url="https://otherco.io/jobs/1",
        catalog_domain="verified-override.com",
    )
    assert dom_override == "verified-override.com"
    assert src_override == "catalog_verified"

    # Priority (b): employer-owned apply_url host when not in catalog
    dom_host, src_host = resolve_company_domain(
        provider="custom",
        company_slug="linear",
        apply_url="https://careers.linear.app/jobs/1",
    )
    assert dom_host == "linear.app"
    assert src_host == "apply_url_host"

    # Priority (c): ATS apply URL without catalog entry -> (None, None)
    assert resolve_company_domain(
        provider="greenhouse",
        company_slug="unknownco",
        apply_url="https://boards.greenhouse.io/unknownco/jobs/123",
    ) == (None, None)

    # All 28 catalog boards carry valid non-ATS curated domains and appear in preview
    preview = preview_catalog_activation()
    assert len(preview) == 28 == len(VERIFIED_EMPLOYER_BOARDS)
    for entry, item in zip(VERIFIED_EMPLOYER_BOARDS, preview):
        assert entry.company_domain
        assert item["company_domain"] == entry.company_domain
        assert extract_registrable_domain(entry.company_domain) == entry.company_domain
        assert lookup_curated_company_domain(entry.ats_provider, entry.board_token) == entry.company_domain


def test_joblisting_canonical_and_allowlist_exposure_for_company_domain():
    now = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
    listing = JobListing(
        id="ashby:supabase:1",
        provider="ashby",
        data_source="api",
        title="Backend Engineer",
        company="Supabase",
        company_slug="supabase",
        apply_url="https://jobs.ashbyhq.com/supabase/1",
        source_url="https://jobs.ashbyhq.com/supabase/1",
        scraped_at=now,
        query_used="engineer",
        ats_source="ashby",
    )
    assert listing.company_domain == "supabase.com"
    assert listing.company_domain_source == "catalog_verified"

    # Canonical adapter round-trip preserves company_domain & source
    canonical: CanonicalJob = CanonicalJobAdapter.from_listing(listing)
    assert canonical.company_domain == "supabase.com"
    assert canonical.company_domain_source == "catalog_verified"
    round_trip = CanonicalJobAdapter.to_listing(canonical)
    assert round_trip.company_domain == "supabase.com"
    assert round_trip.company_domain_source == "catalog_verified"

    # Allowlist exposes company_domain to anonymous callers while hiding internal source
    assert "company_domain" in USER_JOB_FIELDS
    assert "company_domain_source" in ADMIN_JOB_FIELDS
    assert (USER_JOB_FIELDS & ADMIN_JOB_FIELDS) == set()
    assert (USER_JOB_FIELDS | ADMIN_JOB_FIELDS) == set(JobListing.model_fields.keys())

    payload_str = serialize_event_for_user("results", ResultsBatch(batch=[listing], total_so_far=1))
    assert payload_str is not None
    item = json.loads(payload_str)["batch"][0]
    assert item["company_domain"] == "supabase.com"
    assert "company_domain_source" not in item


def test_logo_coverage_offline_three_buckets(tmp_path: Path):
    ashby_dir = tmp_path / "ashby"
    ashby_dir.mkdir()
    (ashby_dir / "unknown.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "1",
                        "title": "Own Verified",
                        "company_logo_url": "https://cdn.example.test/logo.png",
                        "company_logo_verified": True,
                        "applyUrl": "https://jobs.ashbyhq.com/x/1",
                    },
                    {
                        "id": "2",
                        "title": "Employer Apply Host",
                        "applyUrl": "https://careers.linear.app/jobs/2",
                    },
                    {
                        "id": "3",
                        "title": "ATS Host Only",
                        "applyUrl": "https://jobs.ashbyhq.com/unknown/3",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = compute_logo_coverage(tmp_path)
    cat = summary["catalog_boards"]
    assert cat["total"] == 28
    assert cat["own_verified_logo"] + cat["logo_dev_fallback_only"] + cat["neither_monogram"] == 28

    fix = summary["fixture_postings"]
    assert fix == {
        "total": 3,
        "own_verified_logo": 1,
        "logo_dev_fallback_only": 1,
        "neither_monogram": 1,
    }
    report_txt = format_coverage_report(summary)
    assert "Own verified logo" in report_txt
    assert "Logo.dev fallback only" in report_txt
    assert "Neither (monogram)" in report_txt

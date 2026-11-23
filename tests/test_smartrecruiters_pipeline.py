from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest

from src.ats.ats_api_client import ParsedATSUrl, SmartRecruitersClient
from src.core.models import JobSalary
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.job_extraction_service import JobExtractionService

FIXTURE_DIR = Path("tests/fixtures/real/smartrecruiters")


def _extract_from_fixture(filename: str):
    path = FIXTURE_DIR / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    client = SmartRecruitersClient()
    parsed = ParsedATSUrl(
        ats="smartrecruiters",
        company_slug=data.get("company", {}).get("identifier", "test_slug"),
        job_id=str(data.get("id", "123")),
        raw_url=data.get("postingUrl") or f"https://jobs.smartrecruiters.com/test/{data.get('id')}",
    )
    raw = client._parse_raw_payload(data, parsed, query_used="test query")
    job = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(job)
    return raw, job, listing


def test_smartrecruiters_description_section_completeness():
    # 744000155825759.json has all 4 sections in jobAd.sections
    raw, job, listing = _extract_from_fixture("744000155825759.json")

    assert listing.description is not None
    desc = listing.description

    # Assert all 4 authentic sections are present and distinguishable
    assert "Company Description" in desc
    assert "Job Description" in desc
    assert "Qualifications" in desc
    assert "Additional Information" in desc

    # Description length must represent the full text (not truncated to 900 chars)
    assert len(desc) >= 2000


def test_smartrecruiters_dedicated_requirements_extraction():
    # Qualifications must populate listing.requirements without data loss
    raw, job, listing = _extract_from_fixture("744000155825759.json")

    assert listing.requirements is not None
    assert "verbal and written communication" in listing.requirements.lower()
    assert "bilingual" in listing.requirements.lower()


def test_smartrecruiters_full_location_preservation():
    # fullLocation must be preserved rather than degraded to city-only
    _, _, listing_sutherland = _extract_from_fixture("744000155825759.json")
    assert listing_sutherland.location == "Virginia Beach, VA, United States"

    _, _, listing_wise = _extract_from_fixture("744000155937924.json")
    # Clean up excess spaces in "London, , United Kingdom"
    assert "London" in listing_wise.location
    assert "United Kingdom" in listing_wise.location

    _, _, listing_conti = _extract_from_fixture("744000155969710.json")
    assert listing_conti.location == "Camaçari, BA, Brazil"


def test_smartrecruiters_structured_compensation():
    # 744000155937924.json has structured compensation in GBP
    raw, job, listing = _extract_from_fixture("744000155937924.json")

    assert listing.salary is not None
    assert isinstance(listing.salary, JobSalary)
    assert listing.salary.minimum == 135000
    assert listing.salary.maximum == 175000
    assert listing.salary.currency == "GBP"
    assert listing.salary.period == "year"


def test_smartrecruiters_work_model_semantics_and_uncertainty():
    # Sutherland: remote=True, hybrid=False -> remote
    _, _, listing_remote = _extract_from_fixture("744000155825759.json")
    assert listing_remote.work_model == "remote"
    assert listing_remote.work_model_source == "api_enum"

    # Wise: remote=False, hybrid=True -> hybrid
    _, _, listing_hybrid = _extract_from_fixture("744000155937924.json")
    assert listing_hybrid.work_model == "hybrid"
    assert listing_hybrid.work_model_source == "api_enum"

    # Continental: remote=False, hybrid=False -> must NOT guess in_person purely from address
    # If no explicit work-model statement in text, it must remain None (unknown beats wrong)
    _, _, listing_uncertain = _extract_from_fixture("744000155969710.json")
    assert listing_uncertain.work_model is None


# ---------------------------------------------------------------------------
# Step 45: URL Parsing, Identity Normalization & Board-Root Registration
# ---------------------------------------------------------------------------


class TestSmartRecruitersUrlAndIdentity:
    def test_parse_ats_url_normalizes_company_slug_and_preserves_numeric_id(self):
        from src.ats.ats_url_parser import parse_ats_url

        p_upper = parse_ats_url(
            "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales?oga=true"
        )
        p_lower = parse_ats_url("https://jobs.smartrecruiters.com/wise/744000161639339")
        p_careers = parse_ats_url("https://careers.smartrecruiters.com/Nearmap/744000161158698-ae")

        assert p_upper is not None
        assert p_upper.ats == "smartrecruiters"
        assert p_upper.company_slug == "wise"
        assert p_upper.job_id == "744000161639339"

        assert p_lower is not None
        assert p_lower.company_slug == "wise"
        assert p_lower.job_id == "744000161639339"

        assert p_careers is not None
        assert p_careers.ats == "smartrecruiters"
        assert p_careers.company_slug == "nearmap"
        assert p_careers.job_id == "744000161158698"

    def test_board_root_recognition_and_reserved_path_rejection(self):
        from src.ats.ats_url_parser import (
            parse_ats_url,
            parse_smartrecruiters_board_root_url,
        )

        assert parse_smartrecruiters_board_root_url("https://jobs.smartrecruiters.com/Wise") == "wise"
        assert parse_smartrecruiters_board_root_url("https://jobs.smartrecruiters.com/Nearmap/") == "nearmap"
        assert parse_smartrecruiters_board_root_url("https://careers.smartrecruiters.com/ScalableGmbH?utm_source=x") == "scalablegmbh"

        # Job page must NOT be mistaken for a board root
        assert (
            parse_smartrecruiters_board_root_url(
                "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst"
            )
            is None
        )
        assert parse_smartrecruiters_board_root_url("https://jobs.smartrecruiters.com/Wise/744000161639339") is None

        # Reserved paths & placeholders rejected for both board roots and job URLs
        for bad in (
            "https://jobs.smartrecruiters.com/search",
            "https://jobs.smartrecruiters.com/jobs",
            "https://jobs.smartrecruiters.com/careers",
            "https://jobs.smartrecruiters.com/api",
            "https://jobs.smartrecruiters.com/favicon.ico",
            "https://jobs.smartrecruiters.com/smartrecruiters",
            "https://jobs.smartrecruiters.com/company1",
            "https://example.com/Wise",
        ):
            assert parse_smartrecruiters_board_root_url(bad) is None
        assert parse_ats_url("https://jobs.smartrecruiters.com/search/744000161639339") is None
        assert parse_ats_url("https://jobs.smartrecruiters.com/external-referrals/company/Wise/publication/abc") is None

    def test_canonical_url_and_apply_url_separation_and_case_dedupe(self):
        from src.extraction.url_normalizer import (
            build_id_match_key,
            build_url_match_key,
            canonicalize_smartrecruiters_posting_url,
            normalize_job_url,
            url_carries_job_identifier,
        )

        posting = "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst?utm_source=serper"
        apply_u = "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst?oga=true"
        lower_u = "http://jobs.smartrecruiters.com/wise/744000161639339-lead-data-analyst/"

        # Preserves customer-facing casing and keeps apply destination (?oga=true) distinct from posting
        assert (
            normalize_job_url(posting, "smartrecruiters")
            == "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst"
        )
        assert (
            normalize_job_url(apply_u, "smartrecruiters")
            == "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst?oga=true"
        )
        assert normalize_job_url(apply_u, "smartrecruiters") != normalize_job_url(posting, "smartrecruiters")

        # Match keys collapse case variations (Wise vs wise) and ?oga=true
        assert (
            canonicalize_smartrecruiters_posting_url(apply_u)
            == "https://jobs.smartrecruiters.com/wise/744000161639339-lead-data-analyst"
        )
        assert (
            build_url_match_key(apply_u, "smartrecruiters")
            == build_url_match_key(posting, "smartrecruiters")
            == build_url_match_key(lower_u, "smartrecruiters")
        )
        assert (
            build_id_match_key("smartrecruiters", "Wise", "744000161639339")
            == build_id_match_key("smartrecruiters", "wise", "744000161639339")
        )
        assert url_carries_job_identifier(posting, "smartrecruiters") is True
        assert url_carries_job_identifier("https://jobs.smartrecruiters.com/Wise", "smartrecruiters") is False

    def test_dedupe_between_parsed_posting_and_monitored_listing(self):
        from datetime import datetime, timezone

        from src.core.models import JobListing
        from src.extraction.deduplicator import listings_match

        now = datetime.now(timezone.utc)
        parsed_job = JobListing(
            id="smartrecruiters:wise:744000161639339",
            provider="smartrecruiters",
            data_source="api",
            ats_source="smartrecruiters",
            company_slug="wise",
            title="Lead Data Analyst",
            company="Wise",
            source_url="https://jobs.smartrecruiters.com/Wise/744000161639339-lead",
            apply_url="https://jobs.smartrecruiters.com/Wise/744000161639339-lead?oga=true",
            scraped_at=now,
            query_used="wise",
        )
        monitored_job = JobListing(
            id="smartrecruiters:wise:744000161639339",
            provider="smartrecruiters",
            data_source="api",
            ats_source="smartrecruiters",
            company_slug="wise",
            title="Lead Data Analyst - Wise Business",
            company="Wise",
            source_url="https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales",
            apply_url="https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales?oga=true",
            scraped_at=now,
            query_used="wise",
        )
        assert listings_match(parsed_job, monitored_job) is True

    @pytest.mark.anyio
    async def test_search_pipeline_registers_smartrecruiters_board_root_lowercase(self, tmp_path, monkeypatch):
        from src.discovery import search_pipeline
        from src.discovery.search_pipeline import SearchOrchestrator
        from src.storage import company_board_registry as reg_mod
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_root.sqlite"))
        monkeypatch.setattr(search_pipeline, "company_board_registry", reg)
        monkeypatch.setattr(reg_mod, "company_board_registry", reg)

        orch = SearchOrchestrator()
        async with httpx.AsyncClient() as client:
            res = await orch._enrich_ats_item(
                "smartrecruiters",
                {"link": "https://jobs.smartrecruiters.com/Wise", "title": "Wise Careers", "snippet": ""},
                "wise",
                client,
            )
        assert res is None
        board = reg.get_board("smartrecruiters", "wise")
        assert board is not None
        assert board.board_token == "wise"
        assert board.company_slug == "wise"
        assert board.board_url == "https://jobs.smartrecruiters.com/wise"
        assert board.source_posting_url == "https://jobs.smartrecruiters.com/Wise"


# ---------------------------------------------------------------------------
# Step 45: Shared Converter, Quality Extraction, URL Bugfix & Ref Validation
# ---------------------------------------------------------------------------


class TestSmartRecruitersConverterAndQuality:
    def test_smartrecruiters_payload_to_raw_fixes_apply_url_and_source_url_never_uses_ref(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = json.loads((FIXTURE_DIR / "wise_744000161639339_detail.json").read_text(encoding="utf-8"))
        # Inject an API ref field to ensure ref is NEVER surfaced as apply_url or source_url
        detail["ref"] = "https://api.smartrecruiters.com/v1/companies/Wise/postings/744000161639339"

        raw = smartrecruiters_payload_to_raw(detail, company_slug="Wise", query_used="wise")
        assert raw is not None
        assert raw.company_slug == "wise"
        assert raw.provider_job_id == "744000161639339"
        assert raw.raw_company == "Wise"
        assert (
            raw.source_url
            == "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales"
        )
        assert (
            raw.apply_url
            == "https://jobs.smartrecruiters.com/Wise/744000161639339-lead-data-analyst-wise-business-commercial-sales?oga=true"
        )
        assert "api.smartrecruiters.com" not in raw.apply_url
        assert "api.smartrecruiters.com" not in raw.source_url

        canonical = JobExtractionService.extract(raw)
        listing = CanonicalJobAdapter.to_listing(canonical)
        assert listing.id == "smartrecruiters:wise:744000161639339"
        assert listing.company == "Wise"
        assert listing.company_slug == "wise"
        assert listing.salary is not None
        assert listing.salary.minimum == 75000
        assert listing.salary.maximum == 115000
        assert listing.salary.currency == "GBP"
        assert listing.salary.period == "year"
        assert listing.eligibility is not None
        assert listing.eligibility.physical_location_country == "United Kingdom"

    def test_apply_url_falls_back_to_posting_url_never_api_ref(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        detail.pop("applyUrl", None)
        detail["ref"] = "https://api.smartrecruiters.com/v1/companies/Nearmap/postings/744000161158698"

        raw = smartrecruiters_payload_to_raw(detail, company_slug="Nearmap")
        assert raw is not None
        assert (
            raw.source_url
            == "https://jobs.smartrecruiters.com/Nearmap/744000161158698-enterprise-account-executive-commercial-aec-"
        )
        assert raw.apply_url == raw.source_url
        assert "api.smartrecruiters.com" not in raw.apply_url

    def test_conflicting_remote_and_hybrid_flags_stay_unknown(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        detail["location"]["remote"] = True
        detail["location"]["hybrid"] = True
        detail["jobAd"]["sections"] = {
            "jobDescription": {"title": "Job Description", "text": "<p>Join our engineering team.</p>"}
        }

        raw = smartrecruiters_payload_to_raw(detail, company_slug="Nearmap")
        assert raw is not None
        canonical = JobExtractionService.extract(raw)
        listing = CanonicalJobAdapter.to_listing(canonical)
        assert listing.work_model is None
        assert listing.is_remote is None

    def test_eligibility_and_requirements_fallback_with_qualifications_priority(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        # 1. Sutherland has explicit qualifications + Virginia residency requirement
        suth = json.loads((FIXTURE_DIR / "744000155825759.json").read_text(encoding="utf-8"))
        raw_suth = smartrecruiters_payload_to_raw(suth, company_slug="Sutherland")
        assert raw_suth is not None
        listing_suth = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw_suth))
        assert listing_suth.requirements is not None
        assert "bilingual" in listing_suth.requirements.lower()
        assert listing_suth.eligibility is not None
        assert listing_suth.eligibility.physical_location_country == "United States"
        assert listing_suth.eligibility.nigeria_eligible is None or listing_suth.eligibility.nigeria_eligible is False

        # 2. When qualifications is absent, requirements falls back to description
        no_qual = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        no_qual["jobAd"]["sections"].pop("qualifications", None)
        no_qual["jobAd"]["sections"]["jobDescription"]["text"] = (
            "<p>Role overview</p><h3>Requirements</h3><ul><li>5+ years Python experience</li></ul>"
        )
        raw_nq = smartrecruiters_payload_to_raw(no_qual, company_slug="Nearmap")
        assert raw_nq is not None
        assert raw_nq.raw_requirements is None
        listing_nq = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw_nq))
        assert listing_nq.requirements is not None
        assert "5+ years Python experience" in listing_nq.requirements

        # 3. Never infer Nigeria eligibility from company location or job title alone
        ng_loc = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        ng_loc["name"] = "Remote Nigeria Sales Lead"
        ng_loc["location"] = {"city": "Lagos", "country": "ng", "remote": False, "hybrid": False, "fullLocation": "Lagos, Nigeria"}
        ng_loc["jobAd"]["sections"] = {"jobDescription": {"title": "Job Description", "text": "<p>Great role in Lagos.</p>"}}
        raw_ng = smartrecruiters_payload_to_raw(ng_loc, company_slug="Nearmap")
        listing_ng = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw_ng))
        assert listing_ng.eligibility is not None
        assert listing_ng.eligibility.physical_location_country == "Nigeria"
        assert listing_ng.eligibility.nigeria_eligible is None

    def test_validate_smartrecruiters_ref_url_rejects_untrusted_hosts_and_mismatches(self):
        from src.ats.ats_api_client import validate_smartrecruiters_ref_url

        valid_ref = "https://api.smartrecruiters.com/v1/companies/Nearmap/postings/744000161158698"
        assert (
            validate_smartrecruiters_ref_url(
                valid_ref, expected_company_slug="nearmap", expected_job_id="744000161158698"
            )
            == valid_ref
        )

        for bad in (
            "http://api.smartrecruiters.com/v1/companies/Nearmap/postings/744000161158698",
            "https://evil.example.com/v1/companies/Nearmap/postings/744000161158698",
            "https://127.0.0.1/v1/companies/Nearmap/postings/744000161158698",
            "https://api.smartrecruiters.com/v1/companies/Other/postings/744000161158698",
            "https://api.smartrecruiters.com/v1/companies/Nearmap/postings/999",
            "https://api.smartrecruiters.com/v2/companies/Nearmap/postings/744000161158698",
            "https://api.smartrecruiters.com/v1/companies/Nearmap/postings/744000161158698?redirect=https://evil.com",
        ):
            assert (
                validate_smartrecruiters_ref_url(
                    bad, expected_company_slug="nearmap", expected_job_id="744000161158698"
                )
                is None
            )


# ---------------------------------------------------------------------------
# Step 45: Verified Company Logo Extraction & Cached Enrichment
# ---------------------------------------------------------------------------


class TestSmartRecruitersLogoExtraction:
    def test_real_html_logo_accepted_and_wordmarks_or_invalid_hosts_rejected(self):
        from bs4 import BeautifulSoup

        from src.extraction.logo_extractor import extract_company_logo_for_provider

        nearmap_html = (FIXTURE_DIR / "nearmap_slug_posting.html").read_text(encoding="utf-8")
        wise_html = (FIXTURE_DIR / "wise_slug_posting.html").read_text(encoding="utf-8")

        res_near = extract_company_logo_for_provider(
            "smartrecruiters",
            soup=BeautifulSoup(nearmap_html, "html.parser"),
            company_name="Nearmap",
        )
        assert res_near.verified is True
        assert res_near.source == "smartrecruiters_header_logo"
        assert res_near.url is not None
        assert res_near.url.startswith("https://c.smartrecruiters.com/sr-company-logo-prod-")

        res_wise = extract_company_logo_for_provider(
            "smartrecruiters",
            soup=BeautifulSoup(wise_html, "html.parser"),
            company_name="Wise",
        )
        assert res_wise.verified is True
        assert res_wise.url is not None
        assert res_wise.url.startswith("https://c.smartrecruiters.com/sr-company-logo-prod-")

        # Platform wordmark, generic assets, and invalid hosts must be rejected
        wordmark_html = """
        <html><head>
          <meta itemprop="logo" content="https://av-www.smartrecruiters.com/sr-logo/1.0.19/winston/apple-touch-icon.png"/>
        </head><body>
          <span class="header-logo logo"><a href="/"><img src="https://av-www.smartrecruiters.com/sr-logo/1.0.19/wordmark.svg" alt="SmartRecruiters"/></a></span>
          <img src="https://evil.example.com/logo.png" alt="Evil"/>
          <img src="https://c.smartrecruiters.com/sr-company-images-prod-aws-dc5/abc/default_social_logo/300x300" alt="Banner"/>
        </body></html>
        """
        res_bad = extract_company_logo_for_provider(
            "smartrecruiters",
            soup=BeautifulSoup(wordmark_html, "html.parser"),
        )
        assert res_bad.verified is False
        assert res_bad.url is None

    @pytest.mark.anyio
    async def test_logo_enrichment_caches_positive_negative_and_preserves_verified_precedence(
        self, tmp_path
    ):
        from src.ats.ats_api_client import enrich_smartrecruiters_board_identity
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_logo.sqlite"))
        nearmap_html = (FIXTURE_DIR / "nearmap_slug_posting.html").read_text(encoding="utf-8")
        fetch_count = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal fetch_count
            fetch_count += 1
            if "Nearmap/744000161158698" in str(req.url):
                return httpx.Response(200, text=nearmap_html, headers={"content-type": "text/html"})
            return httpx.Response(200, text="<html><body>No logo</body></html>", headers={"content-type": "text/html"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Positive enrichment & cache hit
            _, logo1 = await enrich_smartrecruiters_board_identity(
                "nearmap",
                client,
                registry=reg,
                posting_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698-ae",
                company_name="Nearmap",
            )
            assert logo1.verified is True
            assert fetch_count == 1

            _, logo2 = await enrich_smartrecruiters_board_identity(
                "nearmap",
                client,
                registry=reg,
                posting_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698-ae",
                company_name="Nearmap",
            )
            assert logo2.verified is True
            assert logo2.url == logo1.url
            assert fetch_count == 1  # cached!

            # Verified logo precedence: cannot be overwritten by empty/unverified update
            assert (
                reg.upsert_company_logo(
                    ats_provider="smartrecruiters",
                    board_token="nearmap",
                    logo_url="https://example.com/unverified.png",
                    source="guess",
                    verified=False,
                )
                is False
            )
            assert reg.get_board("smartrecruiters", "nearmap").company_logo_url == logo1.url

            # Negative enrichment & cache hit
            _, neg1 = await enrich_smartrecruiters_board_identity(
                "nologoco",
                client,
                registry=reg,
                posting_url="https://jobs.smartrecruiters.com/nologoco/123456",
                company_name="NoLogoCo",
            )
            assert neg1.verified is False
            assert fetch_count == 2

            _, neg2 = await enrich_smartrecruiters_board_identity(
                "nologoco",
                client,
                registry=reg,
                posting_url="https://jobs.smartrecruiters.com/nologoco/123456",
                company_name="NoLogoCo",
            )
            assert neg2.verified is False
            assert fetch_count == 2  # negative cached!


# ---------------------------------------------------------------------------
# Helpers for Step 45 Pagination, Hydration, Reconciliation & Routing Tests
# ---------------------------------------------------------------------------


def _make_sr_listing_item(
    job_id: str,
    title: str = "Software Engineer",
    *,
    company_ident: str = "TestCo",
    company_name: str = "TestCo",
    released_date: str = "2026-11-10T12:00:00.000Z",
    visibility: str = "PUBLIC",
    remote: bool = False,
    hybrid: bool = False,
    ref_override: str | None = None,
) -> dict:
    return {
        "id": str(job_id),
        "name": title,
        "uuid": f"00000000-0000-4000-8000-{int(job_id) % 10**12:012d}" if str(job_id).isdigit() else "00000000-0000-4000-8000-000000000001",
        "jobAdId": "11111111-1111-4111-8111-111111111111",
        "defaultJobAd": True,
        "refNumber": f"REF{job_id}",
        "company": {"identifier": company_ident, "name": company_name},
        "releasedDate": released_date,
        "location": {
            "city": "London",
            "country": "gb",
            "remote": remote,
            "hybrid": hybrid,
            "fullLocation": "London, United Kingdom",
        },
        "department": {"id": "10", "label": "Engineering"},
        "typeOfEmployment": {"id": "permanent", "label": "Full-time"},
        "visibility": visibility,
        "ref": ref_override
        if ref_override is not None
        else f"https://api.smartrecruiters.com/v1/companies/{company_ident}/postings/{job_id}",
    }


def _make_sr_detail_item(
    job_id: str,
    title: str = "Software Engineer",
    *,
    company_ident: str = "TestCo",
    company_name: str = "TestCo",
    released_date: str = "2026-11-10T12:00:00.000Z",
    remote: bool = False,
    hybrid: bool = False,
    description_html: str = "<p>Full authentic role description with rich details for candidates.</p>",
    qualifications_html: str = "<ul><li>5+ years Python</li></ul>",
    compensation: dict | None = None,
) -> dict:
    slug_title = "-".join(title.lower().split())
    posting_url = f"https://jobs.smartrecruiters.com/{company_ident}/{job_id}-{slug_title}"
    payload = {
        "id": str(job_id),
        "name": title,
        "uuid": f"00000000-0000-4000-8000-{int(job_id) % 10**12:012d}" if str(job_id).isdigit() else "00000000-0000-4000-8000-000000000001",
        "company": {"identifier": company_ident, "name": company_name},
        "releasedDate": released_date,
        "location": {
            "city": "London",
            "country": "gb",
            "remote": remote,
            "hybrid": hybrid,
            "fullLocation": "London, United Kingdom",
        },
        "department": {"id": 10, "label": "Engineering"},
        "typeOfEmployment": {"id": "permanent", "label": "Full-time"},
        "postingUrl": posting_url,
        "applyUrl": f"{posting_url}?oga=true",
        "jobAd": {
            "sections": {
                "companyDescription": {"title": "Company Description", "text": "<p>About TestCo.</p>"},
                "jobDescription": {"title": "Job Description", "text": description_html},
                "qualifications": {"title": "Qualifications", "text": qualifications_html},
                "additionalInformation": {"title": "Additional Information", "text": "<p>Benefits.</p>"},
            }
        },
        "active": True,
        "visibility": "PUBLIC",
    }
    if compensation is not None:
        payload["compensation"] = compensation
    return payload


def _make_sr_board(
    reg,
    *,
    token: str = "testco",
    company_name: str = "TestCo",
    logo_checked_at: float = 1.0,
):
    board = reg.register_candidate(
        company_name=company_name,
        ats_provider="smartrecruiters",
        board_token=token,
        source_url=f"https://jobs.smartrecruiters.com/{company_name}",
    )
    assert board is not None
    if logo_checked_at is not None:
        with reg._get_connection() as conn:
            conn.execute(
                "UPDATE company_boards SET company_logo_checked_at = ? WHERE id = ?",
                (logo_checked_at, board.id),
            )
            conn.commit()
        board = reg.get_board("smartrecruiters", token)
    return board


# ---------------------------------------------------------------------------
# Step 45: Sequential Pagination & Atomic Snapshot Validation
# ---------------------------------------------------------------------------


class TestSmartRecruitersPaginationAndSnapshot:
    @pytest.mark.anyio
    async def test_single_page_board_and_multi_page_board_drain_all_pages(self, tmp_path):
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_pages.sqlite"))

        # 1. Single-page real fixture: Nearmap (36 postings)
        near_postings = json.loads((FIXTURE_DIR / "nearmap_postings.json").read_text(encoding="utf-8"))
        near_detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        near_board = _make_sr_board(reg, token="nearmap", company_name="Nearmap")

        requested_urls: list[str] = []

        def near_handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            requested_urls.append(u)
            if "/postings?" in u:
                assert "destination=PUBLIC" in u
                assert "limit=100" in u
                assert "offset=0" in u
                return httpx.Response(200, json=near_postings)
            if u.endswith("/postings/744000161158698"):
                return httpx.Response(200, json=near_detail)
            pid = u.rsplit("/", 1)[-1]
            return httpx.Response(200, json=_make_sr_detail_item(pid, f"Role {pid}", company_ident="Nearmap", company_name="Nearmap"))

        adapter = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=50)
        async with httpx.AsyncClient(transport=httpx.MockTransport(near_handler)) as client:
            res_near = await adapter.check_board(
                near_board,
                client,
                known_monitored_jobs={},
                known_detail_states={},
                registry=reg,
            )
        assert res_near.success is True
        assert res_near.not_modified is False
        assert len(res_near.listings) == 36
        assert any(j.id == "smartrecruiters:nearmap:744000161158698" for j in res_near.listings)

        # 2. Multi-page real fixture: ScalableGmbH (109 postings across page 0 + page 1)
        p0 = json.loads((FIXTURE_DIR / "scalable_postings_p0.json").read_text(encoding="utf-8"))
        p1 = json.loads((FIXTURE_DIR / "scalable_postings_p1.json").read_text(encoding="utf-8"))
        scal_board = _make_sr_board(reg, token="scalablegmbh", company_name="Scalable GmbH")

        page_offsets: list[str] = []

        def scal_handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                if "offset=0" in u:
                    page_offsets.append("0")
                    return httpx.Response(200, json=p0)
                if "offset=100" in u:
                    page_offsets.append("100")
                    return httpx.Response(200, json=p1)
                return httpx.Response(404)
            pid = u.rsplit("/", 1)[-1]
            return httpx.Response(200, json=_make_sr_detail_item(pid, f"Scalable Role {pid}", company_ident="ScalableGmbH", company_name="Scalable GmbH"))

        adapter_scal = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=5)
        async with httpx.AsyncClient(transport=httpx.MockTransport(scal_handler)) as client:
            res_scal = await adapter_scal.check_board(
                scal_board,
                client,
                known_monitored_jobs={},
                known_detail_states={},
                registry=reg,
            )
        assert res_scal.success is True
        assert page_offsets == ["0", "100"]
        assert len(res_scal.listings) == 109
        assert len({j.id for j in res_scal.listings}) == 109

    @pytest.mark.anyio
    async def test_more_than_100_jobs_drains_320_jobs_across_4_pages_without_cap(self, tmp_path):
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_320.sqlite"))
        board = _make_sr_board(reg, token="bigcorp", company_name="BigCorp")

        all_items = [_make_sr_listing_item(str(10000 + i), f"Role {i}", company_ident="BigCorp", company_name="BigCorp") for i in range(320)]

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                off = int(req.url.params["offset"])
                return httpx.Response(
                    200,
                    json={"offset": off, "limit": 100, "totalFound": 320, "content": all_items[off : off + 100]},
                )
            pid = u.rsplit("/", 1)[-1]
            return httpx.Response(200, json=_make_sr_detail_item(pid, f"Role {pid}", company_ident="BigCorp", company_name="BigCorp"))

        adapter = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=5)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            res = await adapter.check_board(board, client, known_monitored_jobs={}, known_detail_states={}, registry=reg)
        assert res.success is True
        assert len(res.listings) == 320
        assert len({j.id for j in res.listings}) == 320

    @pytest.mark.anyio
    async def test_atomic_snapshot_rejects_malformed_inconsistent_duplicate_or_partial_pages(self, tmp_path):
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_invalid.sqlite"))
        board = _make_sr_board(reg, token="scalablegmbh", company_name="Scalable GmbH")
        p0 = json.loads((FIXTURE_DIR / "scalable_postings_p0.json").read_text(encoding="utf-8"))
        p1 = json.loads((FIXTURE_DIR / "scalable_postings_p1.json").read_text(encoding="utf-8"))

        bad_scenarios: list[tuple[str, object]] = [
            (
                "inconsistent_totals",
                lambda u: httpx.Response(200, json=p0)
                if "offset=0" in u
                else httpx.Response(200, json={**p1, "totalFound": 110}),
            ),
            (
                "incorrect_offset",
                lambda u: httpx.Response(200, json=p0)
                if "offset=0" in u
                else httpx.Response(200, json={**p1, "offset": 0}),
            ),
            (
                "invalid_limit_over_100",
                lambda u: httpx.Response(200, json={**p0, "limit": 200}),
            ),
            (
                "duplicate_ids_across_pages",
                lambda u: httpx.Response(200, json=p0)
                if "offset=0" in u
                else httpx.Response(200, json={**p1, "content": [p0["content"][0]] + p1["content"][1:]}),
            ),
            (
                "repeated_page_0_on_offset_100",
                lambda u: httpx.Response(200, json=p0)
                if "offset=0" in u
                else httpx.Response(200, json={**p0, "offset": 100}),
            ),
            (
                "premature_empty_page",
                lambda u: httpx.Response(200, json=p0)
                if "offset=0" in u
                else httpx.Response(200, json={"offset": 100, "limit": 100, "totalFound": 109, "content": []}),
            ),
            (
                "short_non_final_page",
                lambda u: httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 109, "content": p0["content"][:50]}),
            ),
            (
                "malformed_entry_missing_title",
                lambda u: httpx.Response(
                    200,
                    json={"offset": 0, "limit": 100, "totalFound": 1, "content": [{"id": "123", "visibility": "PUBLIC"}]},
                ),
            ),
            (
                "non_public_visibility",
                lambda u: httpx.Response(
                    200,
                    json={"offset": 0, "limit": 100, "totalFound": 1, "content": [_make_sr_listing_item("123", visibility="INTERNAL")]},
                ),
            ),
            (
                "http_304_on_multi_page_board",
                lambda u: httpx.Response(304),
            ),
            (
                "partial_page_500_on_page_1",
                lambda u: httpx.Response(200, json=p0) if "offset=0" in u else httpx.Response(500),
            ),
        ]

        def _raise_connect(u):
            raise httpx.ConnectError("mid-pagination interruption")

        bad_scenarios.append(
            (
                "mid_pagination_interruption",
                lambda u: httpx.Response(200, json=p0) if "offset=0" in u else _raise_connect(u),
            )
        )

        adapter = SmartRecruitersBoardAdapter()
        board.active_job_count = 109
        board.etag = '"some-etag"'
        board.content_fingerprint = "fp-109"
        for name, responder in bad_scenarios:
            def handler(req: httpx.Request, _resp=responder) -> httpx.Response:
                return _resp(str(req.url))

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res = await adapter.check_board(board, client, known_monitored_jobs={}, known_detail_states={}, registry=reg)
            assert res.success is False, f"{name} must fail entire snapshot"
            assert res.not_modified is False, f"{name} must not return not_modified=True"
            assert res.listings == [], f"{name} must return zero partial listings"


# ---------------------------------------------------------------------------
# Step 45: Detail Hydration, Backlog Fairness, 404/Transient Preservation
# ---------------------------------------------------------------------------


class TestSmartRecruitersDetailHydrationAndFairness:
    @pytest.mark.anyio
    async def test_untrusted_ref_is_never_fetched_and_detail_404_never_closes_listed_job(self, tmp_path):
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_404.sqlite"))
        board = _make_sr_board(reg, token="nearmap", company_name="Nearmap")

        err_404 = json.loads((FIXTURE_DIR / "nearmap_posting_404.json").read_text(encoding="utf-8"))
        evil_calls: list[str] = []
        items = [
            _make_sr_listing_item("744000161158698", "Role 404", company_ident="Nearmap", company_name="Nearmap"),
            _make_sr_listing_item(
                "744000160739739",
                "Evil Ref Role",
                company_ident="Nearmap",
                company_name="Nearmap",
                ref_override="https://evil.attacker.example/steal",
            ),
        ]

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "evil.attacker.example" in u:
                evil_calls.append(u)
                return httpx.Response(200, json={})
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 2, "content": items})
            if u.endswith("/744000161158698"):
                return httpx.Response(404, json=err_404)
            return httpx.Response(404)

        adapter = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=10)
        monitor = BoardMonitor(registry=reg)
        from src.monitoring import board_monitor as bm_mod
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res = await monitor.check_single_board(board, client)
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter

        assert res.success is True
        assert evil_calls == []
        stored_404 = reg.get_monitored_job("smartrecruiters:nearmap:744000161158698")
        assert stored_404 is not None
        assert stored_404.source_url == "https://jobs.smartrecruiters.com/Nearmap/744000161158698"
        states = reg.get_monitored_job_detail_states(board.id)
        assert states["smartrecruiters:nearmap:744000161158698"].detail_status == "detail_404"
        assert states["smartrecruiters:nearmap:744000161158698"].detail_next_retry_at is not None
        assert states["smartrecruiters:nearmap:744000160739739"].detail_status == "invalid_detail"

    @pytest.mark.anyio
    async def test_initial_backlog_drains_fairly_without_starving_old_pending_or_stale_ttl(self, tmp_path):
        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry
        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_fair.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")

        # Poll 1: 5 initial jobs with budget max_new=2 -> 2 hydrated, 3 pending
        initial_items = [
            _make_sr_listing_item(str(100 + i), f"Initial {i}", company_ident="Wise", company_name="Wise")
            for i in range(5)
        ]
        detail_calls: list[str] = []

        def make_handler(current_items):
            def handler(req: httpx.Request) -> httpx.Response:
                u = str(req.url)
                if "/postings?" in u:
                    return httpx.Response(
                        200,
                        json={"offset": 0, "limit": 100, "totalFound": len(current_items), "content": current_items},
                    )
                pid = u.rsplit("/", 1)[-1]
                detail_calls.append(pid)
                return httpx.Response(200, json=_make_sr_detail_item(pid, f"Role {pid}", company_ident="Wise", company_name="Wise"))
            return handler

        adapter = SmartRecruitersBoardAdapter(
            detail_revalidate_ttl_seconds=60.0,
            max_new_hydrations_per_poll=2,
            max_revalidations_per_poll=1,
        )
        monitor = BoardMonitor(registry=reg)
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(make_handler(initial_items))) as client:
                await monitor.check_single_board(reg.get_board("smartrecruiters", "wise"), client)

            assert detail_calls == ["100", "101"]
            states_1 = reg.get_monitored_job_detail_states(board.id)
            assert states_1["smartrecruiters:wise:100"].detail_status == "hydrated"
            assert states_1["smartrecruiters:wise:101"].detail_status == "hydrated"
            assert states_1["smartrecruiters:wise:102"].detail_status == "pending_hydration"
            assert states_1["smartrecruiters:wise:103"].detail_status == "pending_hydration"
            assert states_1["smartrecruiters:wise:104"].detail_status == "pending_hydration"

            # Poll 2: 3 brand-new jobs arrive at top of listing, AND job 100 is stale (TTL expired)
            with reg._get_connection() as conn:
                conn.execute(
                    "UPDATE monitored_jobs SET last_checked_at = ? WHERE job_id = ?",
                    (time.time() - 120.0, "smartrecruiters:wise:100"),
                )
                conn.commit()

            poll2_items = [
                _make_sr_listing_item("200", "Brand New 0", company_ident="Wise", company_name="Wise"),
                _make_sr_listing_item("201", "Brand New 1", company_ident="Wise", company_name="Wise"),
                _make_sr_listing_item("202", "Brand New 2", company_ident="Wise", company_name="Wise"),
            ] + initial_items
            detail_calls.clear()

            # Simulate restart by instantiating a fresh BoardMonitor on same SQLite file
            reg_restarted = CompanyBoardRegistry(db_path=str(tmp_path / "sr_fair.sqlite"))
            monitor2 = BoardMonitor(registry=reg_restarted)
            async with httpx.AsyncClient(transport=httpx.MockTransport(make_handler(poll2_items))) as client:
                await monitor2.check_single_board(reg_restarted.get_board("smartrecruiters", "wise"), client)

            # Old pending jobs (102, 103) must NOT starve behind brand-new (200, 201, 202),
            # AND stale hydrated job 100 gets its separate 1-slot TTL revalidation!
            assert set(detail_calls) == {"102", "103", "100"}
            states_2 = reg_restarted.get_monitored_job_detail_states(board.id)
            assert states_2["smartrecruiters:wise:102"].detail_status == "hydrated"
            assert states_2["smartrecruiters:wise:103"].detail_status == "hydrated"
            assert states_2["smartrecruiters:wise:200"].detail_status == "pending_hydration"
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter

    @pytest.mark.anyio
    async def test_failed_refresh_preserves_rich_cached_description_and_metadata(self, tmp_path):
        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry
        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_rich_keep.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")

        listing_item = _make_sr_listing_item("744000161639339", "Lead Data Analyst", company_ident="Wise", company_name="Wise")
        detail_item = json.loads((FIXTURE_DIR / "wise_744000161639339_detail.json").read_text(encoding="utf-8"))
        fail_detail = False

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 1, "content": [listing_item]})
            if fail_detail:
                return httpx.Response(503)
            return httpx.Response(200, json=detail_item)

        adapter = SmartRecruitersBoardAdapter(detail_revalidate_ttl_seconds=60.0)
        monitor = BoardMonitor(registry=reg)
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await monitor.check_single_board(board, client)

            rich = reg.get_monitored_job("smartrecruiters:wise:744000161639339")
            assert rich is not None
            assert rich.salary is not None and rich.salary.minimum == 75000
            assert rich.requirements is not None
            assert rich.apply_url.endswith("?oga=true")

            # Force TTL expiry and simulate 503 on detail refresh
            with reg._get_connection() as conn:
                conn.execute(
                    "UPDATE monitored_jobs SET last_checked_at = ? WHERE job_id = ?",
                    (time.time() - 120.0, "smartrecruiters:wise:744000161639339"),
                )
                conn.commit()
            fail_detail = True

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await monitor.check_single_board(reg.get_board("smartrecruiters", "wise"), client)

            preserved = reg.get_monitored_job("smartrecruiters:wise:744000161639339")
            assert preserved is not None
            assert preserved.description == rich.description
            assert preserved.requirements == rich.requirements
            assert preserved.salary == rich.salary
            assert preserved.apply_url == rich.apply_url
            states = reg.get_monitored_job_detail_states(board.id)
            assert states["smartrecruiters:wise:744000161639339"].detail_status == "transient_error"
            assert states["smartrecruiters:wise:744000161639339"].detail_retry_count == 1
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter


# ---------------------------------------------------------------------------
# Step 45: Persistent 2-Snapshot Missing-Job Confirmation Policy
# ---------------------------------------------------------------------------


class TestSmartRecruitersSnapshotReconciliation:
    @pytest.mark.anyio
    async def test_two_snapshot_absence_confirmation_reappearance_reset_empty_board_and_failure_safety(
        self, tmp_path
    ):
        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry
        db_path = str(tmp_path / "sr_reconcile.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        board = _make_sr_board(reg, token="nearmap", company_name="Nearmap")

        item_a = _make_sr_listing_item("1001", "Role A", company_ident="Nearmap", company_name="Nearmap")
        item_b = _make_sr_listing_item("1002", "Role B", company_ident="Nearmap", company_name="Nearmap")
        mode = "ab"

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                if mode == "ab":
                    return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 2, "content": [item_a, item_b]})
                if mode == "a_only":
                    return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 1, "content": [item_a]})
                if mode == "empty":
                    return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 0, "content": []})
                return httpx.Response(500)
            pid = u.rsplit("/", 1)[-1]
            return httpx.Response(200, json=_make_sr_detail_item(pid, f"Role {pid}", company_ident="Nearmap", company_name="Nearmap"))

        adapter = SmartRecruitersBoardAdapter()
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            # 1. Initial complete snapshot: A and B active
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg).check_single_board(board, client)
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 2

            # 2. Poll with B missing -> B remains ACTIVE as missing candidate (count=1), survives restart!
            mode = "a_only"
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "nearmap"), client)
            reg_restarted = CompanyBoardRegistry(db_path=db_path)
            assert "smartrecruiters:nearmap:1002" in reg_restarted.get_monitored_jobs_for_board(board.id)
            assert reg_restarted.get_monitored_job_detail_states(board.id)["smartrecruiters:nearmap:1002"].missing_confirmation_count == 1

            # 3. Failed scan must NEVER increment missing_confirmation_count or close B!
            mode = "fail_500"
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res_fail = await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert res_fail.success is False
            assert reg_restarted.get_monitored_job_detail_states(board.id)["smartrecruiters:nearmap:1002"].missing_confirmation_count == 1

            # 4. B reappears -> resets missing_confirmation_count to 0!
            mode = "ab"
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert reg_restarted.get_monitored_job_detail_states(board.id)["smartrecruiters:nearmap:1002"].missing_confirmation_count == 0

            # 5. B missing on two independent complete scans -> B is closed on 2nd scan!
            mode = "a_only"
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert "smartrecruiters:nearmap:1002" in reg_restarted.get_monitored_jobs_for_board(board.id)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert "smartrecruiters:nearmap:1002" not in reg_restarted.get_monitored_jobs_for_board(board.id)
            assert "smartrecruiters:nearmap:1001" in reg_restarted.get_monitored_jobs_for_board(board.id)

            # 6. Valid empty snapshot on established verified board ALSO requires 2 consecutive empty snapshots!
            mode = "empty"
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert "smartrecruiters:nearmap:1001" in reg_restarted.get_monitored_jobs_for_board(board.id)
            assert reg_restarted.get_monitored_job_detail_states(board.id)["smartrecruiters:nearmap:1001"].missing_confirmation_count == 1

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert reg_restarted.get_monitored_jobs_for_board(board.id) == {}

            # 7. Subsequent empty snapshot now returns not_modified=True cleanly
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res_empty_stable = await BoardMonitor(registry=reg_restarted).check_single_board(
                    reg_restarted.get_board("smartrecruiters", "nearmap"), client
                )
            assert res_empty_stable.success is True
            assert res_empty_stable.not_modified is True
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter


# ---------------------------------------------------------------------------
# Step 45: Registry Promotion, Direct-Board Routing & Auto-Registration
# ---------------------------------------------------------------------------


class TestSmartRecruitersRegistryAndDirectRouting:
    def test_smartrecruiters_promoted_to_monitorable_and_adapter_registered(self):
        from src.providers.board_adapters import BOARD_ADAPTERS, SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import (
            MONITORABLE_PROVIDERS,
            PROVISIONAL_PROVIDERS,
        )

        assert "smartrecruiters" in MONITORABLE_PROVIDERS
        assert "smartrecruiters" not in PROVISIONAL_PROVIDERS
        assert isinstance(BOARD_ADAPTERS.get("smartrecruiters"), SmartRecruitersBoardAdapter)

    @pytest.mark.anyio
    async def test_direct_probe_respects_detail_cap_rejects_empty_and_partial_and_registers_valid(
        self, tmp_path, monkeypatch
    ):
        from src.ats import ats_api_client
        from src.ats.direct_board_router import probe_direct_boards, probe_smartrecruiters_board
        from src.core.models import SearchParams
        from src.discovery import search_pipeline
        from src.discovery.search_pipeline import SearchOrchestrator
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_direct.sqlite"))
        monkeypatch.setattr(search_pipeline, "company_board_registry", reg)
        monkeypatch.setattr(ats_api_client, "company_board_registry", reg)

        empty_resp = json.loads((FIXTURE_DIR / "nonexistent_company_postings.json").read_text(encoding="utf-8"))
        near_postings = json.loads((FIXTURE_DIR / "nearmap_postings.json").read_text(encoding="utf-8"))
        near_detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        near_html = (FIXTURE_DIR / "nearmap_slug_posting.html").read_text(encoding="utf-8")

        detail_fetches: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "nonexistent-bottom-pot-probe-99999/postings" in u:
                return httpx.Response(200, json=empty_resp)
            if "partialfail/postings?limit=100&offset=0" in u:
                return httpx.Response(
                    200,
                    json={
                        "offset": 0,
                        "limit": 100,
                        "totalFound": 109,
                        "content": [_make_sr_listing_item(str(i), f"Job {i}") for i in range(100)],
                    },
                )
            if "partialfail/postings?limit=100&offset=100" in u:
                return httpx.Response(503)
            if "Nearmap/postings?" in u or "nearmap/postings?" in u:
                return httpx.Response(200, json=near_postings)
            if "/postings/" in u:
                pid = u.rsplit("/", 1)[-1]
                detail_fetches.append(pid)
                if pid == "744000161158698":
                    return httpx.Response(200, json=near_detail)
                return httpx.Response(200, json=_make_sr_detail_item(pid, f"Nearmap {pid}", company_ident="Nearmap", company_name="Nearmap"))
            if "jobs.smartrecruiters.com/Nearmap/" in u:
                return httpx.Response(200, text=near_html, headers={"content-type": "text/html"})
            return httpx.Response(404)

        orch = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # 1. Unknown 200-empty company must NOT register
            _, empty_res, _ = await orch._search_direct_boards(
                slugs=["nonexistent-bottom-pot-probe-99999"],
                params=SearchParams(job_title="nonexistent-bottom-pot-probe-99999"),
                platforms=["smartrecruiters"],
                client=client,
            )
            assert empty_res == []
            assert reg.get_board("smartrecruiters", "nonexistent-bottom-pot-probe-99999") is None

            # 2. Failed/incomplete multi-page snapshot must NOT register
            _, partial_res, _ = await orch._search_direct_boards(
                slugs=["partialfail"],
                params=SearchParams(job_title="partialfail"),
                platforms=["smartrecruiters"],
                client=client,
            )
            assert partial_res == []
            assert reg.get_board("smartrecruiters", "partialfail") is None

            # 3. Direct probe respects max_detail_fetches cap and emits verified URLs
            capped = await probe_smartrecruiters_board("Nearmap", client, max_detail_fetches=5)
            assert len(capped) == 36
            assert len(detail_fetches) == 5
            first_job = next(j for j in capped if j.id == "smartrecruiters:nearmap:744000161158698")
            assert first_job.apply_url.endswith("?oga=true")
            assert first_job.source_url != first_job.apply_url
            assert all("api.smartrecruiters.com" not in (j.apply_url or "") for j in capped)
            assert all(j.source_url.startswith("https://jobs.smartrecruiters.com/Nearmap/") for j in capped)

            # 4. Successful probe via SearchOrchestrator registers verified board + logo
            detail_fetches.clear()
            _, near_res, _ = await orch._search_direct_boards(
                slugs=["nearmap"],
                params=SearchParams(job_title="nearmap"),
                platforms=["smartrecruiters"],
                client=client,
            )
            assert len(near_res) == 36
            assert len(detail_fetches) == 15  # default max_detail_fetches=15
            board = reg.get_board("smartrecruiters", "nearmap")
            assert board is not None
            assert board.board_token == "nearmap"
            assert board.company_name == "Nearmap"
            assert board.verification_status == "verified"
            assert board.monitoring_capability == "supported"
            assert board.active_job_count == 36
            assert board.company_logo_verified is True
            assert (board.company_logo_url or "").startswith("https://c.smartrecruiters.com/sr-company-logo-prod-")

            # 5. probe_direct_boards honors platforms=["smartrecruiters"]
            wired = await probe_direct_boards(["nearmap"], client, platforms=["smartrecruiters"])
            assert len(wired) == 36


class TestSmartRecruitersAdditionalCoverage:
    @pytest.mark.anyio
    async def test_numeric_id_and_uuid_preserve_canonical_numeric_provider_job_id(self):
        from src.ats.ats_api_client import ParsedATSUrl, SmartRecruitersClient

        detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        uuid_val = detail["uuid"]
        numeric_id = detail["id"]

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=detail)

        client_inst = SmartRecruitersClient()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            by_num, _ = await client_inst.fetch_result(
                ParsedATSUrl(
                    ats="smartrecruiters",
                    company_slug="nearmap",
                    job_id=numeric_id,
                    raw_url=f"https://jobs.smartrecruiters.com/Nearmap/{numeric_id}",
                ),
                client,
            )
            by_uuid, _ = await client_inst.fetch_result(
                ParsedATSUrl(
                    ats="smartrecruiters",
                    company_slug="nearmap",
                    job_id=uuid_val,
                    raw_url=f"https://jobs.smartrecruiters.com/Nearmap/{numeric_id}",
                ),
                client,
            )
        assert by_num is not None and by_uuid is not None
        assert by_num.id == f"smartrecruiters:nearmap:{numeric_id}"
        assert by_uuid.id == f"smartrecruiters:nearmap:{numeric_id}"

    @pytest.mark.anyio
    async def test_retry_backoff_prevents_immediate_rehammer_and_listing_change_rehydrates(self, tmp_path):
        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_backoff.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")
        item = _make_sr_listing_item("7001", "Initial Title", company_ident="Wise", company_name="Wise")
        detail_calls = 0
        fail_detail = True

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal detail_calls
            u = str(req.url)
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 1, "content": [item]})
            detail_calls += 1
            if fail_detail:
                return httpx.Response(503)
            return httpx.Response(200, json=_make_sr_detail_item("7001", item["name"], company_ident="Wise", company_name="Wise"))

        adapter = SmartRecruitersBoardAdapter(detail_revalidate_ttl_seconds=21600.0)
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                # Poll 1: detail 503 -> transient_error backoff (~300s)
                await BoardMonitor(registry=reg).check_single_board(board, client)
                assert detail_calls == 1
                st1 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:7001"]
                assert st1.detail_status == "transient_error"
                assert st1.detail_next_retry_at is not None and st1.detail_next_retry_at > time.time()

                # Poll 2 immediately: within backoff -> NOT retried
                res2 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                assert res2.not_modified is True
                assert detail_calls == 1

                # Poll 3 after backoff expires -> retried and hydrated
                with reg._get_connection() as conn:
                    conn.execute("UPDATE monitored_jobs SET detail_next_retry_at = ? WHERE board_id = ?", (time.time() - 5.0, board.id))
                    conn.commit()
                fail_detail = False
                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                assert detail_calls == 2
                st3 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:7001"]
                assert st3.detail_status == "hydrated"

                # Poll 4: listing payload changes before 6h TTL -> rehydrates immediately!
                item["name"] = "Updated Staff Title"
                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                assert detail_calls == 3
                updated = reg.get_monitored_job("smartrecruiters:wise:7001")
                assert updated is not None and updated.title == "Updated Staff Title"
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter

    @pytest.mark.anyio
    async def test_shared_host_concurrency_cap_and_partial_pagination_never_increments_missing(self, tmp_path):
        import asyncio

        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_conc.sqlite"))
        board = _make_sr_board(reg, token="scalablegmbh", company_name="Scalable GmbH")

        p0_items = [_make_sr_listing_item(str(5000 + i), f"Role {i}", company_ident="ScalableGmbH", company_name="Scalable GmbH") for i in range(100)]
        p1_items = [_make_sr_listing_item(str(5100 + i), f"Role {100 + i}", company_ident="ScalableGmbH", company_name="Scalable GmbH") for i in range(5)]

        inflight = 0
        max_inflight = 0
        fail_p1 = False

        async def handler(req: httpx.Request) -> httpx.Response:
            nonlocal inflight, max_inflight
            u = str(req.url)
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            try:
                await asyncio.sleep(0.01)
                if "/postings?" in u:
                    if "offset=0" in u:
                        return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 105, "content": p0_items})
                    if fail_p1:
                        return httpx.Response(503)
                    return httpx.Response(200, json={"offset": 100, "limit": 100, "totalFound": 105, "content": p1_items})
                pid = u.rsplit("/", 1)[-1]
                return httpx.Response(200, json=_make_sr_detail_item(pid, f"Role {pid}", company_ident="ScalableGmbH", company_name="Scalable GmbH"))
            finally:
                inflight -= 1

        adapter = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=12)
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res1 = await BoardMonitor(registry=reg).check_single_board(board, client)
                assert res1.success is True
                assert max_inflight <= 3
                assert len(reg.get_monitored_jobs_for_board(board.id)) == 105

                # Partial pagination failure on page 1 must NEVER close jobs or increment missing count
                fail_p1 = True
                res2 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "scalablegmbh"), client)
                assert res2.success is False
                assert len(reg.get_monitored_jobs_for_board(board.id)) == 105
                states = reg.get_monitored_job_detail_states(board.id)
                assert all(st.missing_confirmation_count == 0 for st in states.values())
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter

    @pytest.mark.anyio
    async def test_single_flight_logo_coalescing(self, tmp_path):
        import asyncio

        from src.ats.ats_api_client import enrich_smartrecruiters_board_identity
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_coalesce.sqlite"))
        nearmap_html = (FIXTURE_DIR / "nearmap_slug_posting.html").read_text(encoding="utf-8")
        calls = 0

        async def handler(req: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.02)
            return httpx.Response(200, text=nearmap_html, headers={"content-type": "text/html"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            r1, r2, r3 = await asyncio.gather(
                enrich_smartrecruiters_board_identity(
                    "nearmap",
                    client,
                    registry=reg,
                    posting_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698-ae",
                ),
                enrich_smartrecruiters_board_identity(
                    "nearmap",
                    client,
                    registry=reg,
                    posting_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698-ae",
                ),
                enrich_smartrecruiters_board_identity(
                    "nearmap",
                    client,
                    registry=reg,
                    posting_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698-ae",
                ),
            )
        assert calls == 1
        assert r1[1].verified is True and r2[1].verified is True and r3[1].verified is True
        assert r1[1].url == r2[1].url == r3[1].url


class TestSmartRecruitersIdentityValidation:
    """PR #42 correction tests for company.identifier and candidate-facing posting URL validation."""

    def test_company_identifier_case_insensitive_match_accepted(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw
        from src.providers.board_adapters import validate_smartrecruiters_page

        item = _make_sr_listing_item("744000161639339", "Lead Data Analyst", company_ident="Wise", company_name="Wise")
        items, _, total, err = validate_smartrecruiters_page(
            {"offset": 0, "limit": 100, "totalFound": 1, "content": [item]},
            requested_offset=0,
            expected_total=None,
            seen_ids=set(),
            collected_count=0,
            expected_company_slug="wise",
        )
        assert err is None and total == 1 and items is not None and len(items) == 1

        detail = _make_sr_detail_item("744000161639339", "Lead Data Analyst", company_ident="Wise", company_name="Wise")
        raw = smartrecruiters_payload_to_raw(detail, company_slug="wise")
        assert raw is not None
        assert raw.company_slug == "wise"
        assert raw.provider_job_id == "744000161639339"

    def test_company_identifier_mismatch_rejected_in_snapshot_and_converter(self):
        from src.ats.ats_api_client import (
            ExtractionOutcome,
            SmartRecruitersClient,
            smartrecruiters_payload_to_raw,
        )
        from src.ats.ats_url_parser import parse_ats_url
        from src.providers.board_adapters import validate_smartrecruiters_page

        foreign_item = _make_sr_listing_item(
            "744000161639339",
            "Lead Data Analyst",
            company_ident="OtherCompany",
            company_name="Other Company",
        )
        items, _, _, err = validate_smartrecruiters_page(
            {"offset": 0, "limit": 100, "totalFound": 1, "content": [foreign_item]},
            requested_offset=0,
            expected_total=None,
            seen_ids=set(),
            collected_count=0,
            expected_company_slug="wise",
        )
        assert items is None and err is not None and "identifier" in err.lower()

        detail = _make_sr_detail_item(
            "744000161639339",
            "Lead Data Analyst",
            company_ident="OtherCompany",
            company_name="Other Company",
        )
        assert smartrecruiters_payload_to_raw(detail, company_slug="wise") is None

        parsed = parse_ats_url("https://jobs.smartrecruiters.com/Wise/744000161639339")
        assert parsed is not None
        import asyncio

        async def _check_client():
            def handler(req: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json=detail)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await SmartRecruitersClient().fetch_raw_result(parsed, client)

        res = asyncio.run(_check_client())
        assert res.outcome == ExtractionOutcome.PARSE_ERROR
        assert res.raw is None

    def test_correct_posting_url_and_job_id_and_legitimate_external_url_preserved(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item(
            "744000161639339",
            "Lead Data Analyst",
            company_ident="Wise",
            company_name="Wise",
        )
        detail["postingUrl"] = "https://careers.smartrecruiters.com/Wise/744000161639339-lead-data-analyst"
        detail["applyUrl"] = "https://careers.wise.com/apply/744000161639339"
        raw = smartrecruiters_payload_to_raw(detail, company_slug="wise")
        assert raw is not None
        assert raw.source_url == "https://careers.smartrecruiters.com/Wise/744000161639339-lead-data-analyst"
        assert raw.apply_url == "https://careers.wise.com/apply/744000161639339"

    def test_posting_url_belonging_to_another_company_rejected(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item(
            "744000161639339",
            "Lead Data Analyst",
            company_ident="Wise",
            company_name="Wise",
        )
        detail["postingUrl"] = "https://jobs.smartrecruiters.com/OtherCompany/744000161639339-lead-data-analyst"
        detail["applyUrl"] = "https://careers.smartrecruiters.com/OtherCompany/744000161639339?oga=true"
        raw = smartrecruiters_payload_to_raw(
            detail,
            company_slug="wise",
            fallback_source_url="https://jobs.smartrecruiters.com/OtherCompany/744000161639339",
        )
        assert raw is not None
        assert "OtherCompany" not in raw.source_url
        assert "OtherCompany" not in raw.apply_url
        assert raw.source_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"
        assert raw.apply_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"

    def test_posting_url_belonging_to_another_job_rejected(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item(
            "744000161639339",
            "Lead Data Analyst",
            company_ident="Wise",
            company_name="Wise",
        )
        detail["postingUrl"] = "https://jobs.smartrecruiters.com/Wise/999999999999999-wrong-role"
        detail["applyUrl"] = "https://jobs.smartrecruiters.com/Wise/999999999999999-wrong-role?oga=true"
        raw = smartrecruiters_payload_to_raw(
            detail,
            company_slug="wise",
            fallback_source_url="https://jobs.smartrecruiters.com/Wise/888888888888888",
        )
        assert raw is not None
        assert "999999999999999" not in raw.source_url
        assert "888888888888888" not in raw.source_url
        assert "999999999999999" not in raw.apply_url
        assert raw.source_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"
        assert raw.apply_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"

    def test_missing_company_identifier_uses_validated_board_slug_fallback(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw
        from src.providers.board_adapters import validate_smartrecruiters_page

        item = _make_sr_listing_item("744000161639339", "Lead Data Analyst", company_ident="Wise", company_name="Wise")
        item["company"] = {"name": "Wise"}
        items, _, total, err = validate_smartrecruiters_page(
            {"offset": 0, "limit": 100, "totalFound": 1, "content": [item]},
            requested_offset=0,
            expected_total=None,
            seen_ids=set(),
            collected_count=0,
            expected_company_slug="wise",
        )
        assert err is None and total == 1 and items is not None and len(items) == 1

        detail = _make_sr_detail_item("744000161639339", "Lead Data Analyst", company_ident="Wise", company_name="Wise")
        detail["company"] = {"name": "Wise"}
        raw = smartrecruiters_payload_to_raw(detail, company_slug="wise")
        assert raw is not None
        assert raw.company_slug == "wise"
        assert raw.raw_company == "Wise"
        assert raw.source_url.startswith("https://jobs.smartrecruiters.com/Wise/744000161639339")


class TestMissingJobReconciliationFailureVisibility:
    """PR #42 correction tests for making missing-job reconciliation DB failures visible."""

    @pytest.mark.anyio
    async def test_reconciliation_db_failure_marks_poll_failed_and_later_poll_completes_two_snapshot_policy(self, tmp_path):
        from src.monitoring.board_monitor import BoardMonitor
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_reconcile_fail.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")
        item_a = _make_sr_listing_item("1001", "Role Alpha", company_ident="Wise", company_name="Wise")
        item_b = _make_sr_listing_item("1002", "Role Beta", company_ident="Wise", company_name="Wise")
        current_items = [item_a, item_b]

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": len(current_items), "content": current_items})
            pid = u.rsplit("/", 1)[-1]
            name = next((i["name"] for i in current_items if i["id"] == pid), "Role")
            return httpx.Response(200, json=_make_sr_detail_item(pid, name, company_ident="Wise", company_name="Wise"))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Poll 1: establish both jobs active and record initial content_fingerprint
            res1 = await BoardMonitor(registry=reg).check_single_board(board, client)
            assert res1.success is True
            board_after_1 = reg.get_board("smartrecruiters", "wise")
            assert board_after_1 is not None and board_after_1.content_fingerprint
            fp_poll_1 = board_after_1.content_fingerprint
            last_ok_1 = board_after_1.last_successful_check

            # Poll 2: Role Beta disappears, but reconcile_missing_jobs hits a persistence failure
            current_items = [item_a]
            with reg._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TRIGGER fail_reconcile_update
                    BEFORE UPDATE ON monitored_jobs
                    WHEN NEW.missing_confirmation_count > OLD.missing_confirmation_count
                    BEGIN
                        SELECT RAISE(ABORT, 'simulated sqlite persistence failure');
                    END;
                    """
                )
                conn.commit()

            try:
                res2 = await BoardMonitor(registry=reg).check_single_board(board_after_1, client)
                assert res2.success is False
                assert res2.error and "simulated sqlite persistence failure" in res2.error

                board_after_2 = reg.get_board("smartrecruiters", "wise")
                assert board_after_2 is not None
                assert board_after_2.failure_count == 1
                assert board_after_2.content_fingerprint == fp_poll_1
                assert board_after_2.last_successful_check == last_ok_1

                # Neither job may be closed or left with corrupted candidate count
                assert "smartrecruiters:wise:1002" in reg.get_monitored_jobs_for_board(board.id)
                st_b_2 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:1002"]
                assert st_b_2.missing_confirmation_count == 0
            finally:
                with reg._get_connection() as conn:
                    conn.execute("DROP TRIGGER IF EXISTS fail_reconcile_update")
                    conn.commit()

            # Poll 3 (unchanged {item_a} since failure): fingerprint did NOT advance so poll runs and logs missing 1
            res3 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
            assert res3.success is True
            assert res3.not_modified is False
            assert "smartrecruiters:wise:1002" in reg.get_monitored_jobs_for_board(board.id)
            st_b_3 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:1002"]
            assert st_b_3.missing_confirmation_count == 1

            # Poll 4 (second independent complete snapshot missing Beta): confirms closure
            res4 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
            assert res4.success is True
            assert "smartrecruiters:wise:1002" not in reg.get_monitored_jobs_for_board(board.id)
            with reg._get_connection() as conn:
                row = conn.execute(
                    "SELECT status FROM monitored_jobs WHERE job_id = ?",
                    ("smartrecruiters:wise:1002",),
                ).fetchone()
                assert row is not None and row[0] == "closed"

        # Sanity: non-SmartRecruiters providers keep immediate closure (threshold=1)
        gh_board = reg.register_candidate(
            company_name="TestGH",
            ats_provider="greenhouse",
            board_token="testgh",
            source_url="https://boards.greenhouse.io/testgh",
        )
        assert gh_board is not None
        from src.core.models import JobListing
        reg.upsert_monitored_job(
            JobListing(
                id="greenhouse:testgh:1",
                provider="greenhouse",
                data_source="api",
                title="GH Role",
                company="TestGH",
                company_slug="testgh",
                scraped_at="2026-11-16T00:00:00Z",
                source_url="https://boards.greenhouse.io/testgh/jobs/1",
                apply_url="https://boards.greenhouse.io/testgh/jobs/1",
                query_used="testgh",
                ats_source="greenhouse",
            ),
            board_id=gh_board.id,
        )
        assert reg.reconcile_missing_jobs(gh_board.id, set(), confirm_threshold=1) == (1, 0)
        assert "greenhouse:testgh:1" not in reg.get_monitored_jobs_for_board(gh_board.id)
        with reg._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM monitored_jobs WHERE job_id = ?",
                ("greenhouse:testgh:1",),
            ).fetchone()
            assert row is not None and row[0] == "closed"


class TestRetryBackoffListingChangeRehydration:
    """PR #42 correction tests for listing changes during retry backoff and fallback metadata freshness."""

    @pytest.mark.anyio
    async def test_unhydrated_failed_job_listing_change_rehydrates_immediately_and_unchanged_respects_backoff(self, tmp_path):
        from src.monitoring.board_monitor import BoardMonitor
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_backoff_change.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")
        item = _make_sr_listing_item(
            "8001",
            "Initial Fallback Title",
            company_ident="Wise",
            company_name="Wise",
            remote=False,
        )
        detail_calls = 0
        fail_detail = True

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal detail_calls
            u = str(req.url)
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 1, "content": [item]})
            detail_calls += 1
            if fail_detail:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json=_make_sr_detail_item(
                    "8001",
                    item["name"],
                    company_ident="Wise",
                    company_name="Wise",
                    remote=bool(item.get("location", {}).get("remote")),
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Poll 1: initial detail fails -> unhydrated fallback with retry backoff in future
            res1 = await BoardMonitor(registry=reg).check_single_board(board, client)
            assert res1.success is True
            assert detail_calls == 1
            st1 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:8001"]
            assert st1.detail_status == "transient_error"
            assert st1.detail_last_hydrated_at is None
            assert st1.detail_next_retry_at is not None and st1.detail_next_retry_at > time.time()

            # Poll 2: unchanged listing before retry_at -> still respects backoff
            res2 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
            assert res2.success is True
            assert res2.not_modified is True
            assert detail_calls == 1

            # Poll 3: BEFORE retry_at, listing payload changes -> triggers immediate rehydration!
            item["name"] = "Updated Staff Engineer"
            item["location"] = {"city": "Tallinn", "country": "ee", "remote": True, "hybrid": False}
            fail_detail = False

            res3 = await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
            assert res3.success is True
            assert res3.not_modified is False
            assert detail_calls == 2

            st3 = reg.get_monitored_job_detail_states(board.id)["smartrecruiters:wise:8001"]
            assert st3.detail_status == "hydrated"
            assert st3.detail_last_hydrated_at is not None
            updated = reg.get_monitored_job("smartrecruiters:wise:8001")
            assert updated is not None
            assert updated.title == "Updated Staff Engineer"
            assert updated.work_model == "remote"

    @pytest.mark.anyio
    async def test_changed_listing_updates_fallback_metadata_and_preserves_backoff_and_budgets(self, tmp_path):
        from src.monitoring import board_monitor as bm_mod
        from src.monitoring.board_monitor import BoardMonitor
        from src.providers.board_adapters import SmartRecruitersBoardAdapter
        from src.storage.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "sr_fallback_fresh.sqlite"))
        board = _make_sr_board(reg, token="wise", company_name="Wise")
        item_1 = _make_sr_listing_item(
            "8001",
            "Old Due Job",
            company_ident="Wise",
            company_name="Wise",
            remote=False,
        )
        item_2 = _make_sr_listing_item(
            "8002",
            "Initial Failed Title",
            company_ident="Wise",
            company_name="Wise",
            remote=False,
        )
        item_2["location"] = {"city": "Berlin", "country": "de", "remote": False, "hybrid": False}
        items = [item_1, item_2]
        detail_calls: list[str] = []
        fail_8002 = True

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "/postings?" in u:
                return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": len(items), "content": items})
            pid = u.rsplit("/", 1)[-1]
            detail_calls.append(pid)
            if pid == "8002" and fail_8002:
                return httpx.Response(503)
            cur = next(i for i in items if i["id"] == pid)
            return httpx.Response(
                200,
                json=_make_sr_detail_item(pid, cur["name"], company_ident="Wise", company_name="Wise"),
            )

        # Budget = 1 so Poll 1 hydrations leave 8002 deferred, Poll 2 tries 8002 (503), etc.
        adapter = SmartRecruitersBoardAdapter(max_new_hydrations_per_poll=1)
        orig_adapter = bm_mod.BOARD_ADAPTERS.get("smartrecruiters")
        bm_mod.BOARD_ADAPTERS["smartrecruiters"] = adapter
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                # Poll 1: 8001 hydrated, 8002 deferred (pending_hydration fallback)
                await BoardMonitor(registry=reg).check_single_board(board, client)
                assert detail_calls == ["8001"]

                # Update 8002 while deferred by budget -> fallback metadata updates immediately, still queues next
                item_2["name"] = "Fresh Deferred Title"
                item_2["location"] = {"city": "Tallinn", "country": "ee", "remote": True, "hybrid": False}
                # Wait: Poll 2 has budget 1 -> 8002 is due (`pending_old` / `changed_known`), tries detail -> 503!
                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                assert detail_calls == ["8001", "8002"]

                job_2_after_fail = reg.get_monitored_job("smartrecruiters:wise:8002")
                assert job_2_after_fail is not None
                assert job_2_after_fail.title == "Fresh Deferred Title"
                assert job_2_after_fail.work_model == "remote"

                # Poll 3: Add brand_new 8003, AND 8002's listing changes AGAIN while in retry backoff,
                # with max_new_hydrations_per_poll=1: old unchanged due job (if any) isn't starved,
                # and if we set budget=1 with brand_new 8003 only, changed 8002 runs BEFORE brand_new 8003!
                item_2["name"] = "Changed Again In Backoff"
                item_3 = _make_sr_listing_item("8003", "Brand New Arrival", company_ident="Wise", company_name="Wise")
                items.append(item_3)

                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                # Changed known job 8002 runs BEFORE brand_new 8003 (respecting fairness + budget=1)!
                assert detail_calls == ["8001", "8002", "8002"]
                job_2_after_fail_2 = reg.get_monitored_job("smartrecruiters:wise:8002")
                assert job_2_after_fail_2 is not None
                assert job_2_after_fail_2.title == "Changed Again In Backoff"

                # Poll 4: 8002 unchanged since Poll 3 attempt -> respects retry backoff, so brand_new 8003 gets hydrated!
                await BoardMonitor(registry=reg).check_single_board(reg.get_board("smartrecruiters", "wise"), client)
                assert detail_calls == ["8001", "8002", "8002", "8003"]
        finally:
            if orig_adapter is not None:
                bm_mod.BOARD_ADAPTERS["smartrecruiters"] = orig_adapter


class TestSmartRecruitersStrictNumericIds:
    """PR #42 final review tests enforcing strict numeric SmartRecruiters posting IDs."""

    def test_numeric_string_and_integer_ids_accepted_and_normalized(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail_str = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        raw_str = smartrecruiters_payload_to_raw(detail_str, company_slug="wise")
        assert raw_str is not None
        assert raw_str.provider_job_id == "744000161639339"

        detail_int = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        detail_int["id"] = 744000161639339
        raw_int = smartrecruiters_payload_to_raw(detail_int, company_slug="wise", default_job_id="744000161639339")
        assert raw_int is not None
        assert raw_int.provider_job_id == "744000161639339"

    def test_numeric_expected_id_match_accepted_and_mismatch_rejected(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        matched = smartrecruiters_payload_to_raw(detail, company_slug="wise", default_job_id="744000161639339")
        assert matched is not None
        assert matched.provider_job_id == "744000161639339"

        mismatched = smartrecruiters_payload_to_raw(detail, company_slug="wise", default_job_id="999999999999999")
        assert mismatched is None

    @pytest.mark.parametrize(
        "bad_id",
        [
            None,
            "",
            "   ",
            True,
            False,
            [744000161639339],
            {"id": "744000161639339"},
            "11111111-1111-4111-8111-111111111111",
            "abc123",
            "744000161639339.0",
            123.45,
            -744000161639339,
            "+744000161639339",
            "1e10",
            "²³",
        ],
    )
    def test_invalid_or_non_numeric_payload_ids_rejected_even_with_valid_default_or_external_url(self, bad_id):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        detail["postingUrl"] = "https://careers.wise.com/jobs/744000161639339"
        detail["applyUrl"] = "https://careers.wise.com/apply/744000161639339"
        if bad_id is None:
            detail.pop("id", None)
        else:
            detail["id"] = bad_id

        # Must reject both with numeric default_job_id (no silent substitution) and without default_job_id
        assert smartrecruiters_payload_to_raw(detail, company_slug="wise", default_job_id="744000161639339") is None
        assert smartrecruiters_payload_to_raw(detail, company_slug="wise") is None

    def test_uuid_lookup_preserves_canonical_numeric_id_and_rejects_invalid_payload(self):
        from src.ats.ats_api_client import (
            ExtractionOutcome,
            ParsedATSUrl,
            SmartRecruitersClient,
            smartrecruiters_payload_to_raw,
        )

        uuid_val = "3e9b1111-2222-4333-8444-555566667777"
        detail = json.loads((FIXTURE_DIR / "nearmap_744000161158698_detail.json").read_text(encoding="utf-8"))
        raw = smartrecruiters_payload_to_raw(detail, company_slug="nearmap", default_job_id=uuid_val)
        assert raw is not None
        assert raw.provider_job_id == detail["id"]

        bad_detail = dict(detail)
        bad_detail["id"] = "abc123"
        assert smartrecruiters_payload_to_raw(bad_detail, company_slug="nearmap", default_job_id=uuid_val) is None

        parsed = ParsedATSUrl(
            ats="smartrecruiters",
            company_slug="nearmap",
            job_id="744000161158698",
            raw_url="https://jobs.smartrecruiters.com/Nearmap/744000161158698",
        )
        import asyncio

        async def _call():
            def handler(req: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json=bad_detail)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await SmartRecruitersClient().fetch_raw_result(parsed, client)

        res = asyncio.run(_call())
        assert res.outcome == ExtractionOutcome.PARSE_ERROR
        assert res.raw is None

    def test_valid_external_apply_url_preserved_when_numeric_id_valid_and_mismatched_sr_urls_rejected(self):
        from src.ats.ats_api_client import smartrecruiters_payload_to_raw

        detail = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        detail["applyUrl"] = "https://careers.wise.com/apply/744000161639339"
        raw = smartrecruiters_payload_to_raw(detail, company_slug="wise", default_job_id="744000161639339")
        assert raw is not None
        assert raw.apply_url == "https://careers.wise.com/apply/744000161639339"

        detail_bad_url = _make_sr_detail_item("744000161639339", "Data Engineer", company_ident="Wise", company_name="Wise")
        detail_bad_url["postingUrl"] = "https://jobs.smartrecruiters.com/OtherCo/744000161639339-wrong"
        detail_bad_url["applyUrl"] = "https://careers.smartrecruiters.com/Wise/111111111111111-wrong"
        raw_fixed = smartrecruiters_payload_to_raw(detail_bad_url, company_slug="wise", default_job_id="744000161639339")
        assert raw_fixed is not None
        assert raw_fixed.source_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"
        assert raw_fixed.apply_url == "https://jobs.smartrecruiters.com/Wise/744000161639339"

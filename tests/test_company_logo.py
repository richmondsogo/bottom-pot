"""
Step 35 TDD: Company-Logo Extraction Architecture & End-to-End Propagation Tests.

Covers:
1. Shared SSRF-safe HTTPS URL normalization and rejection of invalid/tracking/share-card/private-IP URLs.
2. Teamtailor-only logo extraction (JSON-LD hiringOrganization.logo primary, header logotype DOM fallback,
   never og:image / body description images / favicons / non-Teamtailor providers).
3. CompanyBoardRegistry persistence and non-overwriting protection for verified logos.
4. CanonicalJob -> JobListing -> GlobalDeduplicator -> API allowlist propagation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from src.api.allowlist import (
    ADMIN_JOB_FIELDS,
    USER_JOB_FIELDS,
    serialize_event_for_user,
)
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import CompanyBoardRegistry
from src.project_files.deduplicator import merge_listings
from src.project_files.logo_extractor import (
    extract_company_logo_for_provider,
    validate_and_normalize_logo_url,
)
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    ExtractionMethod,
    FieldConfidence,
    FieldEvidence,
    JobListing,
    ResultsBatch,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "teamtailor"


def _load_fixture(stem: str) -> tuple[dict, BeautifulSoup]:
    meta = json.loads((FIXTURE_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    html_text = (FIXTURE_DIR / f"{stem}.html").read_text(encoding="utf-8")
    return meta, BeautifulSoup(html_text, "lxml")


def _extract_jsonld(soup: BeautifulSoup) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            doc = json.loads(script.string or script.get_text() or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and doc.get("@type") == "JobPosting":
            return doc
    return {}


class TestValidateAndNormalizeLogoUrl:
    def test_accepts_https_cdn_urls(self):
        svg_url = "https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/image_uploads/0e4469ed/original.svg"
        assert validate_and_normalize_logo_url(svg_url) == svg_url
        png_url = " https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/2ff546e4/original.png "
        assert validate_and_normalize_logo_url(png_url) == png_url.strip()

    @pytest.mark.parametrize(
        "bad_url",
        [
            None,
            "",
            "   ",
            "/logos/company.png",
            "http://images.teamtailor-cdn.com/logo.png",
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            "file:///etc/passwd",
            "https://127.0.0.1/logo.png",
            "https://localhost/logo.png",
            "https://10.0.0.1/logo.png",
            "https://172.16.5.4/logo.png",
            "https://192.168.1.2/logo.png",
            "https://169.254.169.254/latest/meta-data/",
            "https://[::1]/logo.png",
            "https://internal.company.local/logo.png",
            "https://metadata.google.internal/logo.png",
            "https://screenshots.teamtailor-cdn.com/bcf47d78-6711-42d0-9eca-bacc1937a5ff-facebook.png?update=1791",
            "https://www.teamtailor.com/images/og/tt-opengraph.png",
            "https://www.teamtailor.com/logos/teamtailor-logotype.svg",
            "https://www.facebook.com/tr?id=599749577903756&ev=PageView&noscript=1",
        ],
    )
    def test_rejects_unsafe_relative_tracking_or_non_logo_urls(self, bad_url):
        assert validate_and_normalize_logo_url(bad_url) is None


class TestTeamtailorLogoExtraction:
    def test_extracts_jsonld_svg_and_png_from_real_fixtures(self):
        meta_a, soup_a = _load_fixture("a3ea4593")  # The Unlimited (.svg)
        res_a = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc=_extract_jsonld(soup_a),
            soup=soup_a,
            page_url=meta_a["url"],
            company_name="The Unlimited",
        )
        assert res_a.url is not None
        assert res_a.url.endswith(".svg")
        assert res_a.verified is True
        assert res_a.source == "json_ld_hiring_organization_logo"

        meta_b, soup_b = _load_fixture("b6057b16")  # Sparteo (.png)
        res_b = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc=_extract_jsonld(soup_b),
            soup=soup_b,
            page_url=meta_b["url"],
            company_name="Sparteo",
        )
        assert res_b.url is not None
        assert res_b.url.endswith(".png")
        assert res_b.verified is True
        assert res_b.source == "json_ld_hiring_organization_logo"

    def test_returns_null_when_no_company_logo_exists_on_real_fixtures(self):
        # Lendurai (d93e9876): has og:image screenshot, no hiringOrganization.logo, no header img
        meta_d, soup_d = _load_fixture("d93e9876")
        res_d = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc=_extract_jsonld(soup_d),
            soup=soup_d,
            page_url=meta_d["url"],
            company_name="Lendurai",
        )
        assert res_d.url is None
        assert res_d.verified is False

        # Lunar custom domain (df512e48): has recruiter picture, facebook tracking pixel, og:image, no company logo
        meta_l, soup_l = _load_fixture("df512e48")
        res_l = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc=_extract_jsonld(soup_l),
            soup=soup_l,
            page_url=meta_l["url"],
            company_name="Lunar",
        )
        assert res_l.url is None
        assert res_l.verified is False

    def test_dom_header_logotype_fallback_and_body_image_exclusion(self):
        html = """
        <html>
          <head>
            <meta property="og:image" content="https://screenshots.teamtailor-cdn.com/card-facebook.png" />
            <link rel="icon" href="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/favicon-v3/image_uploads/111/original.png" />
          </head>
          <body>
            <header>
              <a class="relative h-[72px] flex items-center justify-center focus-visible-header" href="/">
                <img src="https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/image_uploads/222/original.png" alt="Acme Corp career site" />
              </a>
            </header>
            <main>
              <div class="prose">
                <img src="https://cdn.example.com/team-photo.jpg" alt="Our team in Berlin" />
              </div>
            </main>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        res = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc={},
            soup=soup,
            page_url="https://acme.teamtailor.com/jobs/123-engineer",
            company_name="Acme Corp",
        )
        assert res.url == "https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/image_uploads/222/original.png"
        assert res.source == "dom_header_logotype"
        assert res.verified is True

        # Removing header logotype must NOT fall back to prose body image, og:image, or favicon
        html_no_header = html.replace("<header>", "<header><!--").replace("</header>", "--></header>")
        res_none = extract_company_logo_for_provider(
            "teamtailor",
            json_ld_doc={},
            soup=BeautifulSoup(html_no_header, "lxml"),
            page_url="https://acme.teamtailor.com/jobs/123-engineer",
            company_name="Acme Corp",
        )
        assert res_none.url is None
        assert res_none.verified is False

    @pytest.mark.parametrize("other_provider", ["workday", "smartrecruiters", "greenhouse", "ashby", "jobberman"])
    def test_unenabled_providers_remain_null_until_opted_in(self, other_provider):
        doc = {
            "@type": "JobPosting",
            "hiringOrganization": {
                "@type": "Organization",
                "name": "Example Corp",
                "logo": "https://cdn.example.com/logo.png",
            },
        }
        res = extract_company_logo_for_provider(
            other_provider,
            json_ld_doc=doc,
            soup=None,
            page_url="https://example.com/jobs/1",
            company_name="Example Corp",
        )
        assert res.url is None
        assert res.verified is False


class TestLogoPersistenceDedupAndAllowlist:
    def test_registry_persists_logo_and_never_overwrites_verified_with_unverified(self, tmp_path):
        db_file = str(tmp_path / "boards.sqlite")
        reg = CompanyBoardRegistry(db_path=db_file)
        verified_url = "https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/image_uploads/0e4469ed/original.svg"

        board = reg.register_candidate(
            company_name="The Unlimited",
            ats_provider="teamtailor",
            board_token="theunlimited",
            source_url="https://theunlimited.teamtailor.com/jobs/8538757-data-analyst",
            company_logo_url=verified_url,
            company_logo_source="json_ld_hiring_organization_logo",
            company_logo_verified=True,
        )
        assert board is not None
        assert board.company_logo_url == verified_url
        assert board.company_logo_verified is True

        # Attempting to overwrite verified logo with None or unverified URL must keep verified URL
        reg.register_candidate(
            company_name="The Unlimited",
            ats_provider="teamtailor",
            board_token="theunlimited",
            source_url="https://theunlimited.teamtailor.com/jobs/9999999-other",
            company_logo_url="https://cdn.example.com/unverified.png",
            company_logo_source="dom_header_logotype",
            company_logo_verified=False,
        )
        reg.upsert_company_logo(
            ats_provider="teamtailor",
            board_token="theunlimited",
            logo_url=None,
            source=None,
            verified=False,
        )

        # Reconnect to confirm durability
        reg2 = CompanyBoardRegistry(db_path=db_file)
        loaded = reg2.get_board("teamtailor", "theunlimited")
        assert loaded is not None
        assert loaded.company_logo_url == verified_url
        assert loaded.company_logo_verified is True

    def test_canonical_adapter_dedup_and_api_allowlist(self):
        verified_url = "https://images.teamtailor-cdn.com/images/s3/teamtailor-production/logotype-v3/2ff546e4/original.png"
        canonical = CanonicalJob(
            id="teamtailor:sparteo:8467816",
            source="teamtailor",
            source_url="https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer",
            application_url="https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer",
            title="Chief Data Officer",
            company="Sparteo",
            company_slug="sparteo",
            company_logo_url=verified_url,
            company_logo_source="json_ld_hiring_organization_logo",
            company_logo_verified=True,
            scraped_at=datetime.now(timezone.utc),
            field_evidence=[
                FieldEvidence(
                    field=CanonicalJobField.COMPANY_LOGO,
                    normalized_value=verified_url,
                    raw_value=verified_url,
                    method=ExtractionMethod.JSON_LD,
                    provider="teamtailor",
                    provider_field_name="hiringOrganization.logo",
                    confidence_score=0.90,
                )
            ],
            field_confidence=[
                FieldConfidence(field=CanonicalJobField.COMPANY_LOGO, score=0.90, reason="Verified JSON-LD logo"),
            ],
        )
        listing = CanonicalJobAdapter.to_listing(canonical)
        assert listing.company_logo_url == verified_url
        assert listing.company_logo_source == "json_ld_hiring_organization_logo"
        assert listing.company_logo_verified is True

        roundtrip = CanonicalJobAdapter.from_listing(listing)
        assert roundtrip.company_logo_url == verified_url
        assert roundtrip.company_logo_verified is True

        # Dedup protection: unverified donor cannot overwrite verified base logo
        unverified_donor = listing.model_copy(
            deep=True,
            update={
                "id": "teamtailor:sparteo:8467816-dup",
                "company_logo_url": "https://example.com/unverified.png",
                "company_logo_source": "dom_fallback",
                "company_logo_verified": False,
                "field_evidence": [],
            },
        )
        merged = merge_listings(listing, unverified_donor)
        assert merged.company_logo_url == verified_url
        assert merged.company_logo_verified is True

        # Verified donor DOES fill missing logo on base
        missing_base = listing.model_copy(
            deep=True,
            update={
                "company_logo_url": None,
                "company_logo_source": None,
                "company_logo_verified": False,
                "field_evidence": [],
            },
        )
        merged_fill = merge_listings(missing_base, listing)
        assert merged_fill.company_logo_url == verified_url
        assert merged_fill.company_logo_verified is True

        # Allowlist exposure vs admin redaction
        assert "company_logo_url" in USER_JOB_FIELDS
        assert "company_logo_source" in ADMIN_JOB_FIELDS
        assert "company_logo_verified" in ADMIN_JOB_FIELDS

        batch = ResultsBatch(batch=[listing], total_so_far=1)
        user_payload = json.loads(serialize_event_for_user("results", batch) or "{}")
        user_job = user_payload["batch"][0]
        assert user_job["company_logo_url"] == verified_url
        assert "company_logo_source" not in user_job
        assert "company_logo_verified" not in user_job

    def test_job_extraction_service_logo_provenance_confidence_mapping(self):
        from src.project_files.confidence_policy import (
            BASE_CONFIDENCE_TABLE,
            EvidenceType,
        )
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting

        base_raw_kwargs = dict(
            provider="teamtailor",
            source_url="https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer",
            apply_url="https://sparteo.teamtailor.com/jobs/8467816-chief-data-officer",
            raw_title="Chief Data Officer",
            raw_company="Sparteo",
            raw_location="Paris, France",
            raw_description="Lead data strategy across all products and engineering teams.",
            extraction_method=ExtractionMethod.DOM,
        )

        # 1. JSON-LD hiringOrganization.logo -> TYPED_ENUM (0.90) + JSON_LD + verified=True
        raw_jsonld = RawJobPosting(
            **base_raw_kwargs,
            raw_fields={
                "company_logo_url": "https://cdn.example.com/jsonld-logo.png",
                "company_logo_source": "json_ld_hiring_organization_logo",
                "company_logo_verified": True,
            },
        )
        job_jsonld = JobExtractionService.extract(raw_jsonld)
        ev_jsonld = [e for e in job_jsonld.field_evidence if e.field == CanonicalJobField.COMPANY_LOGO]
        assert len(ev_jsonld) == 1
        assert ev_jsonld[0].confidence_score == pytest.approx(
            BASE_CONFIDENCE_TABLE[(CanonicalJobField.COMPANY_LOGO, EvidenceType.TYPED_ENUM)]
        )
        assert ev_jsonld[0].confidence_score == pytest.approx(0.90)
        assert ev_jsonld[0].method == ExtractionMethod.JSON_LD
        assert job_jsonld.company_logo_verified is True

        # 2. DOM header logotype -> STRUCTURED_FREE_TEXT (0.80) + DOM + verified=True
        raw_logotype = RawJobPosting(
            **base_raw_kwargs,
            raw_fields={
                "company_logo_url": "https://cdn.example.com/logotype.png",
                "company_logo_source": "dom_header_logotype",
                "company_logo_verified": True,
            },
        )
        job_logotype = JobExtractionService.extract(raw_logotype)
        ev_logotype = [e for e in job_logotype.field_evidence if e.field == CanonicalJobField.COMPANY_LOGO]
        assert len(ev_logotype) == 1
        assert ev_logotype[0].confidence_score == pytest.approx(
            BASE_CONFIDENCE_TABLE[(CanonicalJobField.COMPANY_LOGO, EvidenceType.STRUCTURED_FREE_TEXT)]
        )
        assert ev_logotype[0].confidence_score == pytest.approx(0.80)
        assert ev_logotype[0].method == ExtractionMethod.DOM
        assert job_logotype.company_logo_verified is True

        # 3. Unverified DOM alt img -> EXPLICIT_LABEL (0.65) + DOM + verified=False
        raw_alt = RawJobPosting(
            **base_raw_kwargs,
            raw_fields={
                "company_logo_url": "https://cdn.example.com/header-alt.png",
                "company_logo_source": "dom_header_alt_img",
                "company_logo_verified": False,
            },
        )
        job_alt = JobExtractionService.extract(raw_alt)
        ev_alt = [e for e in job_alt.field_evidence if e.field == CanonicalJobField.COMPANY_LOGO]
        assert len(ev_alt) == 1
        assert ev_alt[0].confidence_score == pytest.approx(
            BASE_CONFIDENCE_TABLE[(CanonicalJobField.COMPANY_LOGO, EvidenceType.EXPLICIT_LABEL)]
        )
        assert ev_alt[0].confidence_score == pytest.approx(0.65)
        assert ev_alt[0].method == ExtractionMethod.DOM
        assert job_alt.company_logo_verified is False

        # Verify verified-over-unverified dedup protection holds for extracted listings
        listing_verified = CanonicalJobAdapter.to_listing(job_logotype)
        listing_unverified = CanonicalJobAdapter.to_listing(job_alt)
        merged = merge_listings(listing_verified, listing_unverified)
        assert merged.company_logo_url == "https://cdn.example.com/logotype.png"
        assert merged.company_logo_verified is True

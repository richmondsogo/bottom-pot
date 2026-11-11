from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.project_files.ats_api_client import ParsedATSUrl, SmartRecruitersClient
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.models import JobSalary


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

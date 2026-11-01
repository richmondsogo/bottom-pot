from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.project_files.job_extraction_service import (
    JobExtractionService,
    RawJobPosting,
    parse_tz_aware_date,
)
from src.project_files.models import (
    CanonicalJobField,
    ExtractionMethod,
)


def test_json_ld_telecommute_structured_remote():
    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/1",
        raw_title="Senior Python Engineer",
        raw_company="Acme Corp",
        raw_fields={"jobLocationType": "TELECOMMUTE"},
    )
    job = JobExtractionService.extract(raw)
    assert job.work_model == "remote"
    assert job.work_model_source == "jsonld"
    assert job.work_model_evidence == "jobLocationType=TELECOMMUTE"


def test_json_ld_restricted_region_remote():
    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/2",
        raw_title="Frontend Developer",
        raw_company="Acme Corp",
        raw_fields={
            "jobLocationType": "TELECOMMUTE",
            "applicantLocationRequirements": {"@type": "Country", "name": "Nigeria"},
        },
    )
    job = JobExtractionService.extract(raw)
    assert job.work_model == "remote"
    assert job.location == "Nigeria (Remote)"
    # Evidence preserves applicantLocationRequirements restriction
    loc_ev = [e for e in job.field_evidence if e.field == CanonicalJobField.LOCATION]
    assert any("applicantLocationRequirements: Nigeria" in str(e.raw_value) for e in loc_ev)


def test_json_ld_conflicting_work_model_preserves_evidence():
    # Structured JSON-LD says TELECOMMUTE, description says on-site role
    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/3",
        raw_title="Staff Engineer",
        raw_company="Acme Corp",
        raw_description="This is an on-site role in our London headquarters.",
        description_is_authentic=True,
        raw_fields={"jobLocationType": "TELECOMMUTE"},
    )
    job = JobExtractionService.extract(raw)
    # Structured data wins
    assert job.work_model == "remote"
    # But conflict is preserved in field_evidence
    wm_ev = [e for e in job.field_evidence if e.field == CanonicalJobField.WORK_MODEL]
    assert any("TELECOMMUTE" in str(e.raw_value) for e in wm_ev)
    assert any("description_conflict:" in str(e.raw_value) for e in wm_ev)


def test_json_ld_base_salary_extraction():
    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/4",
        raw_title="Data Scientist",
        raw_company="Acme Corp",
        raw_fields={
            "baseSalary": {
                "@type": "MonetaryAmount",
                "currency": "USD",
                "value": {
                    "@type": "QuantitativeValue",
                    "minValue": 130000,
                    "maxValue": 160000,
                    "unitText": "YEAR",
                },
            }
        },
    )
    job = JobExtractionService.extract(raw)
    assert job.salary is not None
    assert job.salary.minimum == 130000
    assert job.salary.maximum == 160000
    assert job.salary.currency == "USD"
    assert job.salary.period == "year"


def test_json_ld_base_salary_rejects_zero_and_placeholders():
    # Zero values
    raw_zero = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/5",
        raw_title="Engineer",
        raw_company="Acme Corp",
        raw_fields={
            "baseSalary": {
                "currency": "USD",
                "value": {"minValue": 0, "maxValue": 0, "unitText": "YEAR"},
            }
        },
    )
    job_zero = JobExtractionService.extract(raw_zero)
    assert job_zero.salary is None


def test_json_ld_base_salary_currency_from_structured_field_only():
    # When baseSalary has no currency, it must NOT infer from location or description
    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/6",
        raw_title="Accountant",
        raw_company="Acme Corp",
        raw_location="New York, NY",
        raw_fields={
            "baseSalary": {
                "value": {"minValue": 80000, "maxValue": 100000, "unitText": "YEAR"},
            }
        },
    )
    job = JobExtractionService.extract(raw)
    assert job.salary is not None
    assert job.salary.minimum == 80000
    assert job.salary.maximum == 100000
    assert job.salary.currency is None  # Never inferred from location hint!


def test_snippet_authenticity_guards():
    # Snippet-only record (description_is_authentic=False)
    raw = RawJobPosting(
        provider="snippet_fallback",
        source_url="https://example.com/job/7",
        raw_title="Security Analyst",
        raw_company="Acme Corp",
        raw_description="Job summary: Salary: $120,000 - $140,000 per year. Fully remote role based anywhere.",
        description_is_authentic=False,
    )
    job = JobExtractionService.extract(raw)
    # 1. No salary extraction from snippets
    assert job.salary is None
    # 2. No work model description scan from snippets
    assert job.work_model is None

"""Tests for Nigerian job board applicant eligibility (ADR 0037)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.core.models import ExtractionMethod, JobEligibility, JobListing
from src.discovery.nigerian_scrapers import NIGERIAN_SCRAPERS
from src.extraction.eligibility_extractor import (
    NIGERIAN_BOARD_PROVIDERS,
    apply_applicant_country_assessment,
    evaluate_eligibility_for_country,
    extract_eligibility,
)


def test_nigerian_board_providers_matches_active_scrapers():
    active_names = {s.site_name.lower() for s in NIGERIAN_SCRAPERS}
    assert active_names == {"jobberman", "myjobmag", "hotnigerianjobs"}
    assert NIGERIAN_BOARD_PROVIDERS == active_names


@pytest.mark.parametrize("provider", ["jobberman", "myjobmag", "hotnigerianjobs", "hotnigerianJobs"])
def test_nigerian_boards_ng_eligible_when_eligibility_is_none_or_generic(provider: str):
    # 1. None eligibility + missing location + unknown work_model
    res_none = evaluate_eligibility_for_country(None, "NG", provider=provider)
    assert res_none.status == "eligible"
    assert res_none.reason == "Listed on a Nigerian job board (workable from Nigeria)."
    assert res_none.summary_label == "Nigeria eligible"
    assert "unverified" not in (res_none.summary_label or "").lower()
    assert "restricted" not in (res_none.summary_label or "").lower()

    # 2. Generic remote with None eligibility
    res_remote_none = evaluate_eligibility_for_country(
        None, "NG", work_model="remote", location=None, provider=provider
    )
    assert res_remote_none.status == "eligible"
    assert res_remote_none.reason == "Listed on a Nigerian job board (workable from Nigeria)."
    assert res_remote_none.summary_label == "Remote · Nigeria eligible"

    # 3. Generic unknown JobEligibility metadata
    generic_elig = JobEligibility(classification="unknown")
    res_generic = evaluate_eligibility_for_country(
        generic_elig, "NG", work_model="remote", location="Remote", provider=provider
    )
    assert res_generic.status == "eligible"
    assert res_generic.reason == "Listed on a Nigerian job board (workable from Nigeria)."
    assert res_generic.summary_label == "Remote · Nigeria eligible"

    # 4. Onsite / hybrid with local Nigerian city
    res_onsite = evaluate_eligibility_for_country(
        generic_elig, "NG", work_model="onsite", location="Lagos", provider=provider
    )
    assert res_onsite.status == "eligible"
    assert res_onsite.summary_label == "Onsite · Lagos"


@pytest.mark.parametrize("provider", ["jobberman", "myjobmag", "hotnigerianjobs"])
def test_nigerian_boards_explicit_ng_exclusion_overrides_to_restricted(provider: str):
    excl_country = JobEligibility(
        classification="unknown",
        excluded_residence_countries=["Nigeria"],
        excluded_country_codes=["NG"],
    )
    res_country = evaluate_eligibility_for_country(
        excl_country, "NG", work_model="remote", location="Remote", provider=provider
    )
    assert res_country.status == "restricted"
    assert "excludes applicants residing in Nigeria" in (res_country.reason or "")

    excl_region = JobEligibility(
        classification="unknown",
        excluded_residence_countries=["Africa"],
        excluded_regions=["Africa"],
    )
    res_region = evaluate_eligibility_for_country(
        excl_region, "NG", work_model="remote", location="Remote", provider=provider
    )
    assert res_region.status == "restricted"
    assert "excludes applicants in Africa" in (res_region.reason or "")

    # Also via extract_eligibility end-to-end
    extracted = extract_eligibility(
        provider=provider,
        work_model="remote",
        location="Remote",
        description="Remote software role. Note: we are unable to hire candidates in Nigeria at this time.",
        description_is_authentic=True,
        method=ExtractionMethod.SCRAPE,
    )
    assert extracted is not None
    assert extracted.nigeria_eligible is False
    assert "excludes" in (extracted.nigeria_eligibility_reason or "").lower()


@pytest.mark.parametrize("applicant_cc", ["US", "GB", "GH", "KE", "DE"])
@pytest.mark.parametrize("provider", ["jobberman", "myjobmag", "hotnigerianjobs"])
def test_nigerian_boards_non_ng_applicants_unchanged(applicant_cc: str, provider: str):
    res_none = evaluate_eligibility_for_country(
        None, applicant_cc, work_model="remote", location="Remote", provider=provider
    )
    assert res_none.status == "unknown"
    assert res_none.summary_label == "Remote · Eligibility unverified"

    res_generic = evaluate_eligibility_for_country(
        JobEligibility(classification="unknown"),
        applicant_cc,
        work_model="remote",
        location="Remote",
        provider=provider,
    )
    assert res_generic.status == "unknown"
    assert res_generic.summary_label == "Remote · Eligibility unverified"


@pytest.mark.parametrize("provider", ["greenhouse", "lever", "ashby", "workable", "ngcareers", None])
def test_non_nigerian_boards_for_ng_unchanged(provider: str | None):
    res_none = evaluate_eligibility_for_country(
        None, "NG", work_model="remote", location="Remote", provider=provider
    )
    assert res_none.status == "unknown"
    assert res_none.summary_label == "Remote · Eligibility unverified"

    res_generic = evaluate_eligibility_for_country(
        JobEligibility(classification="unknown"),
        "NG",
        work_model="remote",
        location="Remote",
        provider=provider,
    )
    assert res_generic.status == "unknown"
    assert res_generic.summary_label == "Remote · Eligibility unverified"


def test_apply_applicant_country_assessment_and_extract_eligibility_pass_provider():
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    listing_none_elig = JobListing(
        id="myjobmag:test-1",
        title="Backend Engineer",
        company="Example Ltd",
        apply_url="https://www.myjobmag.com/job/backend-engineer",
        source_url="https://www.myjobmag.com/job/backend-engineer",
        provider="myjobmag",
        ats_source="myjobmag",
        data_source="scrape",
        query_used="backend",
        scraped_at=now,
        eligibility=None,
    )
    ng_copy = apply_applicant_country_assessment(listing_none_elig, "NG")
    assert ng_copy.eligibility is not None
    assert ng_copy.eligibility.applicant_assessment is not None
    assert ng_copy.eligibility.applicant_assessment.status == "eligible"
    assert ng_copy.eligibility.applicant_assessment.reason == "Listed on a Nigerian job board (workable from Nigeria)."

    # Fallback to ats_source when provider is empty string
    listing_ats_fallback = listing_none_elig.model_copy(update={"provider": "", "ats_source": "hotnigerianJobs"})
    ng_fallback = apply_applicant_country_assessment(listing_ats_fallback, "NG")
    assert ng_fallback.eligibility is not None
    assert ng_fallback.eligibility.applicant_assessment is not None
    assert ng_fallback.eligibility.applicant_assessment.status == "eligible"

    # Non-NG country remains unknown
    us_copy = apply_applicant_country_assessment(listing_none_elig, "US")
    assert us_copy.eligibility is not None
    assert us_copy.eligibility.applicant_assessment is not None
    assert us_copy.eligibility.applicant_assessment.status == "unknown"

    # extract_eligibility sets nigeria_eligible=True for Nigerian board even with generic remote text
    extracted = extract_eligibility(
        provider="jobberman",
        work_model="remote",
        location="Remote",
        description="Hiring a backend engineer to build APIs.",
        description_is_authentic=True,
        method=ExtractionMethod.SCRAPE,
    )
    assert extracted is not None
    assert extracted.nigeria_eligible is True
    assert extracted.nigeria_eligibility_reason == "Listed on a Nigerian job board (workable from Nigeria)."

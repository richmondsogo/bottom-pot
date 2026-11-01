from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.job_extraction_service import (
    JobExtractionService,
    RawJobPosting,
    parse_tz_aware_date,
)
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    ExtractionMethod,
    FieldConfidence,
    FieldEvidence,
    FieldValidation,
    JobListing,
    JobSalary,
    SearchParams,
    ValidationStatus,
)
from src.project_files.observability import (
    SourceKind,
    SourceOutcome,
    SourceTelemetry,
    SourceTelemetryEvent,
    source_telemetry,
)
from src.project_files.search_pipeline import SearchOrchestrator, _cache


def _listing() -> JobListing:
    return JobListing(
        id="greenhouse:acme:1",
        provider="greenhouse",
        data_source="api",
        title="Backend Engineer",
        company="Acme",
        scraped_at=datetime.now(timezone.utc),
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        query_used="test",
        ats_source="greenhouse",
    )


def test_canonical_job_contract_retains_field_provenance() -> None:
    job = CanonicalJob(
        source="greenhouse",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        application_url="https://boards.greenhouse.io/acme/jobs/1",
        title="Backend Engineer",
        company="Acme",
        salary=JobSalary(minimum=120_000, maximum=150_000, currency="USD", period="year"),
        field_evidence=[
            FieldEvidence(
                field=CanonicalJobField.SALARY,
                raw_value="$120,000-$150,000 annually",
                method=ExtractionMethod.ATS_API,
                source_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs/1",
            )
        ],
        field_validations=[
            FieldValidation(
                field=CanonicalJobField.SALARY,
                status=ValidationStatus.ACCEPTED,
            )
        ],
        field_confidence=[
            FieldConfidence(field=CanonicalJobField.SALARY, score=0.95, reason="Source API range")
        ],
    )

    assert job.salary is not None
    assert job.salary.maximum == 150_000
    assert job.field_evidence[0].method is ExtractionMethod.ATS_API


@pytest.mark.anyio
async def test_authentic_api_fixtures_have_non_uniform_field_confidence() -> None:
    """ADR 0028: Source reliability and field confidence are separate.
    Authentic API fixtures must not receive uniform confidence across all fields.
    """
    import httpx
    from pathlib import Path
    from src.project_files.ats_api_client import GreenhouseClient
    from src.project_files.ats_url_parser import parse_ats_url

    real_dir = Path(__file__).resolve().parent / "fixtures" / "real"

    gh_bytes = (real_dir / "greenhouse" / "job_8860302002.json").read_bytes()
    gh_parsed = parse_ats_url("https://boards.greenhouse.io/gitlab/jobs/8860302002")
    assert gh_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=gh_bytes))) as client:
        gh_raw = await GreenhouseClient().fetch_raw(gh_parsed, client)
    assert gh_raw is not None
    gh_job = JobExtractionService.extract(gh_raw)

    scores = [c.score for c in gh_job.field_confidence]
    assert len(scores) >= 5
    # Distinct scores exist (e.g. 0.90 for title/company/description/date vs 0.70 for location vs 0.50 for work_model)
    assert len(set(scores)) > 1
    # Check specific fields
    conf_by_field = {c.field: c.score for c in gh_job.field_confidence}
    assert conf_by_field[CanonicalJobField.TITLE] == 0.90
    assert conf_by_field[CanonicalJobField.LOCATION] == 0.70
    assert conf_by_field[CanonicalJobField.WORK_MODEL] == 0.50
    # Missing fields have no confidence (None), not a low number
    assert CanonicalJobField.SALARY not in conf_by_field


def test_canonical_job_adapter_roundtrip_golden_serialization() -> None:
    from pathlib import Path
    import json

    golden_dir = Path(__file__).resolve().parent / "fixtures" / "golden"
    assert golden_dir.exists()
    golden_files = list(golden_dir.glob("*.json"))
    assert len(golden_files) >= 10

    for fixture_file in golden_files:
        raw_json = fixture_file.read_text(encoding="utf-8")
        orig_listing = JobListing.model_validate_json(raw_json)
        canonical = CanonicalJobAdapter.from_listing(orig_listing)
        roundtrip_listing = CanonicalJobAdapter.to_listing(canonical)

        orig_dict = json.loads(orig_listing.model_dump_json())
        roundtrip_dict = json.loads(roundtrip_listing.model_dump_json())
        orig_dict.pop("field_evidence", None)
        roundtrip_dict.pop("field_evidence", None)

        if isinstance(orig_listing.salary, str):
            # Pre-Step 22b legacy baseline fixtures contained raw string salaries.
            # CanonicalJobAdapter canonicalizes them into structured JobSalary objects.
            assert roundtrip_listing.salary is not None
            roundtrip_dict["salary"] = orig_dict["salary"]
            roundtrip_dict["extraction_confidence"] = orig_dict["extraction_confidence"]

        assert orig_dict == roundtrip_dict, f"Serialization mismatch for {fixture_file.name}"


def test_job_extraction_service_extracts_canonical_job() -> None:
    raw = RawJobPosting(
        provider="greenhouse",
        source_url="https://boards.greenhouse.io/acme/jobs/1",
        provider_job_id="1",
        company_slug="acme",
        raw_title="Senior Backend Engineer",
        raw_company="Acme Corp",
        raw_location="Remote, US",
        raw_description="<p>We are hiring a 100% remote engineer. Salary: $120,000 - $150,000 per year</p>",
        raw_date="2026-10-01T12:00:00Z",
    )
    canonical = JobExtractionService.extract(raw)
    assert canonical.id == "greenhouse:acme:1"
    assert canonical.title == "Senior Backend Engineer"
    assert canonical.company == "Acme Corp"
    assert canonical.work_model == "remote"
    assert canonical.work_model_source == "location"
    assert canonical.salary is not None
    assert canonical.salary.minimum == 120_000
    assert canonical.salary.maximum == 150_000
    assert canonical.salary.currency == "USD"
    assert canonical.salary.period == "year"
    assert canonical.posted_at == datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Convert to JobListing via CanonicalJobAdapter
    listing = CanonicalJobAdapter.to_listing(canonical)
    assert listing.id == "greenhouse:acme:1"
    assert listing.is_remote is True
    assert listing.work_model == "remote"


def test_parse_tz_aware_date_handles_iso_and_epoch() -> None:
    # ISO string with Z
    dt1 = parse_tz_aware_date("2026-05-15T09:30:00Z")
    assert dt1 == datetime(2026, 5, 15, 9, 30, tzinfo=timezone.utc)

    # Epoch ms (e.g. Lever)
    dt2 = parse_tz_aware_date(1715765400000)
    assert dt2 == datetime(2024, 5, 15, 9, 30, tzinfo=timezone.utc)

    # Epoch seconds
    dt3 = parse_tz_aware_date(1715765400)
    assert dt3 == datetime(2024, 5, 15, 9, 30, tzinfo=timezone.utc)

    # None and invalid string
    assert parse_tz_aware_date(None) is None
    assert parse_tz_aware_date("invalid-date") is None


def test_jobsalary_defaults_are_none_not_invented():
    # BUG-02: currency and period must default to None, never USD or year
    salary = JobSalary(minimum=100_000)
    assert salary.currency is None
    assert salary.period is None


@pytest.mark.parametrize(
    "salary",
    [
        {},
        {"minimum": 150_000, "maximum": 120_000},
        {"minimum": -1},
    ],
)
def test_salary_contract_rejects_invalid_ranges(salary: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        JobSalary(**salary)


def test_source_telemetry_aggregates_and_resets() -> None:
    telemetry = SourceTelemetry()
    telemetry.record(
        SourceTelemetryEvent(
            source="greenhouse",
            kind=SourceKind.ATS,
            outcome=SourceOutcome.SUCCESS,
            duration_ms=12,
            result_count=3,
        )
    )
    telemetry.record(
        SourceTelemetryEvent(
            source="greenhouse",
            kind=SourceKind.ATS,
            outcome=SourceOutcome.FAILURE,
            duration_ms=8,
            result_count=0,
        )
    )

    summary = telemetry.snapshot()
    assert len(summary) == 1
    assert summary[0].runs == 2
    assert summary[0].successful_runs == 1
    assert summary[0].failed_runs == 1
    assert summary[0].result_count == 3
    assert summary[0].total_duration_ms == 20

    telemetry.reset()
    assert telemetry.snapshot() == []


@pytest.mark.anyio
async def test_orchestrator_records_successful_source_telemetry() -> None:
    _cache.clear()
    source_telemetry.reset()
    orchestrator = SearchOrchestrator()

    async def successful_search(platform, query, params, client):
        return platform, [_listing()], True

    orchestrator._search_ats_serper = successful_search
    params = SearchParams(job_title="Telemetry Success", include_nigerian_sites=False)
    events = [event async for event in orchestrator.run(params, platforms=["greenhouse"])]

    assert [event[0] for event in events] == ["results", "done"]
    summary = source_telemetry.snapshot()
    assert len(summary) == 1
    assert summary[0].source == "greenhouse"
    assert summary[0].kind is SourceKind.ATS
    assert summary[0].successful_runs == 1
    assert summary[0].result_count == 1


@pytest.mark.anyio
async def test_orchestrator_records_failed_source_telemetry() -> None:
    _cache.clear()
    source_telemetry.reset()
    orchestrator = SearchOrchestrator()

    async def failed_search(platform, query, params, client):
        raise RuntimeError("source unavailable")

    orchestrator._search_ats_serper = failed_search
    params = SearchParams(job_title="Telemetry Failure", include_nigerian_sites=False)
    events = [event async for event in orchestrator.run(params, platforms=["greenhouse"])]

    assert [event[0] for event in events] == ["done"]
    summary = source_telemetry.snapshot()
    assert len(summary) == 1
    assert summary[0].failed_runs == 1
    assert summary[0].result_count == 0


@pytest.mark.anyio
async def test_orchestrator_scopes_nigerian_scrapers_by_platforms() -> None:
    _cache.clear()
    source_telemetry.reset()
    orchestrator = SearchOrchestrator()

    async def successful_ats_search(platform, query, params, client):
        return platform, [_listing()], True

    scraped_sites: list[str] = []

    async def mock_ng_scraper(scraper, params, client):
        scraped_sites.append(scraper.site_name)
        return scraper.site_name, [], False

    orchestrator._search_ats_serper = successful_ats_search
    orchestrator._search_nigerian_scraper = mock_ng_scraper

    # 1. Only greenhouse requested -> 0 Nigerian scrapers should run even with include_nigerian_sites=True
    params = SearchParams(job_title="Platform Filter Test", include_nigerian_sites=True)
    _ = [event async for event in orchestrator.run(params, platforms=["greenhouse"])]
    assert scraped_sites == []

    # 2. Only jobberman requested -> only jobberman runs
    scraped_sites.clear()
    _ = [event async for event in orchestrator.run(params, platforms=["jobberman"])]
    assert scraped_sites == ["jobberman"]


def test_freshness_label_naive_and_aware_posted_at_timezones() -> None:
    from datetime import datetime, timezone, timedelta
    import warnings
    
    # 1. Naive datetime must compute freshness_label without raising TypeError
    naive_dt = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None)
    assert naive_dt.tzinfo is None
    job_naive = _listing()
    job_naive.posted_at = naive_dt
    assert job_naive.freshness_label == "2 days ago"

    # 2. Aware UTC datetime must compute freshness_label accurately
    aware_dt = datetime.now(timezone.utc) - timedelta(days=1)
    job_aware = _listing()
    job_aware.posted_at = aware_dt
    assert job_aware.freshness_label == "Yesterday"

    # 3. No utcnow deprecation warnings emitted
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        _ = job_aware.freshness_label
        _ = job_naive.freshness_label
    utcnow_warnings = [w for w in recorded if "datetime.datetime.utcnow" in str(w.message)]
    assert len(utcnow_warnings) == 0


def test_old_cached_listing_without_field_evidence_loads_safely() -> None:
    """Amendment 4: Test that an old cached row without the field_evidence key still loads."""
    old_cached_json = """{
        "id": "greenhouse:acme:1",
        "provider": "greenhouse",
        "data_source": "api",
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Lagos, Nigeria",
        "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
        "source_url": "https://boards.greenhouse.io/acme/jobs/1",
        "query_used": "test",
        "ats_source": "greenhouse",
        "scraped_at": "2026-10-01T12:00:00Z"
    }"""
    listing = JobListing.model_validate_json(old_cached_json)
    assert listing.id == "greenhouse:acme:1"
    assert listing.title == "Backend Engineer"
    assert listing.field_evidence is None
    assert listing.extraction_confidence is not None
    assert listing.extraction_confidence > 0.0


def test_adding_populated_core_field_never_lowers_scalar_confidence() -> None:
    """Amendment 3 Property Test: Adding a populated core field never lowers the scalar.
    Tests all 2^5 = 32 combinations of core fields.
    """
    from itertools import combinations
    from src.project_files.confidence_policy import (
        CORE_FIELD_WEIGHTS,
        compute_legacy_scalar_confidence,
    )

    core_fields = list(CORE_FIELD_WEIGHTS.keys())
    assert len(core_fields) == 5

    # Fixed representative scores for populated fields
    score_samples = [0.30, 0.50, 0.70, 0.86, 0.90, 0.95]

    for k in range(len(core_fields)):
        for subset in combinations(core_fields, k):
            base_scores = {f: 0.80 for f in subset}
            base_scalar = compute_legacy_scalar_confidence(base_scores)

            unpopulated = [f for f in core_fields if f not in subset]
            for field_to_add in unpopulated:
                for sample_score in score_samples:
                    augmented_scores = dict(base_scores)
                    augmented_scores[field_to_add] = sample_score
                    augmented_scalar = compute_legacy_scalar_confidence(augmented_scores)
                    assert (
                        augmented_scalar >= base_scalar
                    ), f"Adding {field_to_add}={sample_score} lowered scalar from {base_scalar} to {augmented_scalar}"


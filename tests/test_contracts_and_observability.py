from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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

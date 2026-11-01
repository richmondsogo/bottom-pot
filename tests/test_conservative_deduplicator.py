"""
Tests for conservative order-independent deduplication (Step 23 & ADR 0028).

TDD: These tests verify conservative matching, progressive field-level merging,
and strict order-independence:
1. Order-independence: [Snippet, API] vs [API, Snippet] produces identical merged output.
2. Distinct city separation: Same company + title, different locations -> stays separate.
3. Tracking parameter merge: Same URL with different UTM/tracking params -> single merged job.
4. Distinct job IDs on same host: Different gh_jid -> stays separate.
5. Work-model conflict preservation.
"""

from datetime import datetime, timezone
import pytest

from src.project_files.models import (
    CanonicalJobField,
    ExtractionMethod,
    FieldEvidence,
    JobListing,
    JobSalary,
    ValidationStatus,
)
from src.project_files.search_pipeline import GlobalDeduplicator


def _make_listing(
    id_: str,
    provider: str,
    company: str,
    title: str,
    apply_url: str,
    data_source: str = "api",
    location: str | None = None,
    work_model: str | None = None,
    salary: JobSalary | None = None,
    description: str | None = None,
    extraction_confidence: float | None = None,
    field_evidence: list[FieldEvidence] | None = None,
) -> JobListing:
    return JobListing(
        id=id_,
        provider=provider,
        data_source=data_source,
        title=title,
        company=company,
        company_slug=company.lower(),
        apply_url=apply_url,
        source_url=apply_url,
        location=location,
        work_model=work_model,
        salary=salary,
        description=description,
        description_ok=bool(description and len(description) > 50),
        extraction_confidence=extraction_confidence,
        field_evidence=field_evidence or [],
        scraped_at=datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc),
        query_used="python developer",
        ats_source=provider,
    )


class TestConservativeDeduplicator:
    def test_order_independence_snippet_and_api(self):
        """[Snippet, API] vs [API, Snippet] must yield identical merged output."""
        snippet_item = _make_listing(
            id_="generic:snippet123",
            provider="generic",
            company="Acme Corp",
            title="Software Engineer",
            apply_url="https://boards.greenhouse.io/acme/jobs/4567890?utm_source=serper",
            data_source="snippet",
            location=None,
            salary=None,
            description=None,
            field_evidence=[
                FieldEvidence(
                    field=CanonicalJobField.TITLE,
                    raw_value="Software Engineer",
                    method=ExtractionMethod.SNIPPET,
                    confidence_score=0.30,
                ),
                FieldEvidence(
                    field=CanonicalJobField.APPLY_URL,
                    raw_value="https://boards.greenhouse.io/acme/jobs/4567890?utm_source=serper",
                    method=ExtractionMethod.SNIPPET,
                    confidence_score=0.70,
                ),
            ],
        )

        api_item = _make_listing(
            id_="greenhouse:acme:4567890",
            provider="greenhouse",
            company="Acme Corp",
            title="Senior Software Engineer",
            apply_url="https://boards.greenhouse.io/acme/jobs/4567890",
            data_source="api",
            location="Remote, Nigeria",
            work_model="remote",
            salary=JobSalary(minimum=120_000, maximum=160_000, currency="USD", period="year"),
            description="Full authentic job description with comprehensive requirements...",
            field_evidence=[
                FieldEvidence(
                    field=CanonicalJobField.TITLE,
                    raw_value="Senior Software Engineer",
                    method=ExtractionMethod.ATS_API,
                    confidence_score=0.90,
                ),
                FieldEvidence(
                    field=CanonicalJobField.SALARY,
                    raw_value="$120k - $160k",
                    method=ExtractionMethod.ATS_API,
                    confidence_score=0.90,
                ),
            ],
        )

        # Run 1: Snippet first, then API
        dedup_1 = GlobalDeduplicator()
        res_1 = dedup_1.deduplicate([snippet_item, api_item])
        assert len(res_1) == 1
        merged_1 = res_1[0]

        # Run 2: API first, then Snippet
        dedup_2 = GlobalDeduplicator()
        res_2 = dedup_2.deduplicate([api_item, snippet_item])
        assert len(res_2) == 1
        merged_2 = res_2[0]

        # In both runs:
        # - Surviving ID must be the authentic API id
        assert merged_1.id == "greenhouse:acme:4567890"
        assert merged_2.id == "greenhouse:acme:4567890"

        # - Losing snippet ID must be kept in aliases
        assert "generic:snippet123" in merged_1.aliases
        assert "generic:snippet123" in merged_2.aliases

        # - Stronger API title and salary must win
        assert merged_1.title == "Senior Software Engineer"
        assert merged_2.title == "Senior Software Engineer"
        assert merged_1.salary == api_item.salary
        assert merged_2.salary == api_item.salary

        # - Both results must be completely identical
        assert merged_1.model_dump(exclude={"field_evidence"}) == merged_2.model_dump(exclude={"field_evidence"})

    def test_distinct_city_separation(self):
        """Same company + title in different cities must stay separate."""
        job_lagos = _make_listing(
            id_="greenhouse:stripe:101",
            provider="greenhouse",
            company="Stripe",
            title="Backend Engineer",
            apply_url="https://boards.greenhouse.io/stripe/jobs/101",
            location="Lagos, Nigeria",
        )
        job_london = _make_listing(
            id_="greenhouse:stripe:102",
            provider="greenhouse",
            company="Stripe",
            title="Backend Engineer",
            apply_url="https://boards.greenhouse.io/stripe/jobs/102",
            location="London, UK",
        )

        dedup = GlobalDeduplicator()
        results = dedup.deduplicate([job_lagos, job_london])
        assert len(results) == 2, "Jobs with different IDs/locations must never merge"

    def test_tracking_parameter_merge(self):
        """Same job URL with different UTM tracking parameters merges into one record."""
        job_utm = _make_listing(
            id_="snippet:1",
            provider="greenhouse",
            company="Stripe",
            title="Staff Engineer",
            apply_url="https://boards.greenhouse.io/stripe/jobs/999?utm_source=twitter&utm_medium=feed",
            data_source="snippet",
        )
        job_clean = _make_listing(
            id_="greenhouse:stripe:999",
            provider="greenhouse",
            company="Stripe",
            title="Staff Engineer",
            apply_url="https://boards.greenhouse.io/stripe/jobs/999#apply",
            data_source="api",
        )

        dedup = GlobalDeduplicator()
        results = dedup.deduplicate([job_utm, job_clean])
        assert len(results) == 1
        assert results[0].id == "greenhouse:stripe:999"

    def test_distinct_job_ids_on_same_host_never_merge(self):
        """Jobs differing only by query ID (gh_jid) stay separate."""
        job_1 = _make_listing(
            id_="host:1",
            provider="generic",
            company="Acme",
            title="Product Designer",
            apply_url="https://careers.acme.com/jobs?gh_jid=1001",
        )
        job_2 = _make_listing(
            id_="host:2",
            provider="generic",
            company="Acme",
            title="Product Designer",
            apply_url="https://careers.acme.com/jobs?gh_jid=1002",
        )

        dedup = GlobalDeduplicator()
        results = dedup.deduplicate([job_1, job_2])
        assert len(results) == 2

    def test_work_model_conflict_preserves_evidence_and_higher_confidence_wins(self):
        """When work-model signals conflict, higher confidence wins and evidence is preserved."""
        job_scrape = _make_listing(
            id_="greenhouse:stripe:777",
            provider="greenhouse",
            company="Stripe",
            title="Systems Architect",
            apply_url="https://boards.greenhouse.io/stripe/jobs/777",
            data_source="scrape",
            work_model="hybrid",
            field_evidence=[
                FieldEvidence(
                    field=CanonicalJobField.WORK_MODEL,
                    raw_value="hybrid flexible policy",
                    method=ExtractionMethod.SCRAPE,
                    confidence_score=0.50,
                )
            ],
        )

        job_api = _make_listing(
            id_="greenhouse:stripe:777",
            provider="greenhouse",
            company="Stripe",
            title="Systems Architect",
            apply_url="https://boards.greenhouse.io/stripe/jobs/777",
            data_source="api",
            work_model="remote",
            field_evidence=[
                FieldEvidence(
                    field=CanonicalJobField.WORK_MODEL,
                    raw_value="remote=True",
                    method=ExtractionMethod.ATS_API,
                    confidence_score=0.90,
                )
            ],
        )

        dedup = GlobalDeduplicator()
        merged = dedup.deduplicate([job_scrape, job_api])[0]
        assert merged.work_model == "remote"

        # Both evidence observations preserved
        wm_evs = [ev for ev in merged.field_evidence if ev.field == CanonicalJobField.WORK_MODEL]
        assert len(wm_evs) >= 2

    def test_streaming_filter_merges_across_batches_without_duplicate_emission(self):
        """Amendment 8: Dedup merges before emission without duplicate SSE emission."""
        dedup = GlobalDeduplicator()

        snippet = _make_listing(
            id_="generic:snip1",
            provider="generic",
            company="Wise",
            title="Lead Engineer",
            apply_url="https://jobs.smartrecruiters.com/Wise/744000155937924",
            data_source="snippet",
        )
        api = _make_listing(
            id_="smartrecruiters:wise:744000155937924",
            provider="smartrecruiters",
            company="Wise",
            title="Lead Software Engineer",
            apply_url="https://jobs.smartrecruiters.com/Wise/744000155937924",
            data_source="api",
        )
        distinct_job = _make_listing(
            id_="smartrecruiters:uber:999",
            provider="smartrecruiters",
            company="Uber",
            title="Android Engineer",
            apply_url="https://jobs.smartrecruiters.com/uber/999",
            data_source="api",
        )

        # Batch 1 emits snippet
        emitted_1 = dedup.filter([snippet])
        assert len(emitted_1) == 1
        assert emitted_1[0].id == "generic:snip1"

        # Batch 2 contains api (which matches snippet) and distinct_job
        emitted_2 = dedup.filter([api, distinct_job])
        # api is merged internally into emitted record state, NOT re-emitted as duplicate SSE event
        assert len(emitted_2) == 1
        assert emitted_2[0].id == "smartrecruiters:uber:999"

        # Internal state contains the merged record with updated API title
        merged_wise = next(r for r in dedup._emitted if "744000155937924" in r.id)
        assert merged_wise.title == "Lead Software Engineer"
        assert "generic:snip1" in merged_wise.aliases


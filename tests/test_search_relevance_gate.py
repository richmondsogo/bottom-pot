from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.project_files.models import JobListing
from src.project_files.relevance_classifier import RelevanceLevel, classify_relevance
from src.project_files.search_pipeline import SearchOrchestrator, SearchParams


def _make_listing(id: str, title: str, company: str, desc: str) -> JobListing:
    return JobListing(
        id=id,
        title=title,
        company=company,
        location="Remote",
        apply_url=f"https://jobs.smartrecruiters.com/{id}",
        source_url=f"https://jobs.smartrecruiters.com/{id}",
        provider="smartrecruiters",
        ats_source="smartrecruiters",
        data_source="api",
        description=desc,
        query_used="Full-Stack Developer",
        scraped_at=datetime.now(timezone.utc),
    )


def test_relevance_gate_filters_irrelevant_jobs():
    query = "Full-Stack Developer"

    relevant_job = _make_listing(
        "smartrecruiters:acme:1",
        "Senior Full Stack Engineer",
        "Acme Corp",
        "Build full stack web apps with React and Node.",
    )

    related_job = _make_listing(
        "smartrecruiters:acme:2",
        "Backend Software Engineer",
        "Acme Corp",
        "Design backend APIs and database schemas.",
    )

    irrelevant_job = _make_listing(
        "smartrecruiters:tire:3",
        "Tire Development Engineer II - TLD REPLACEMENT AMERICAS",
        "Continental",
        "Oversee tire compound durability and mechanical tests.",
    )

    # Validate individual relevance classifications
    assert classify_relevance(query, relevant_job.title, responsibilities=relevant_job.description).level == RelevanceLevel.STRONG
    assert classify_relevance(query, related_job.title, responsibilities=related_job.description).level == RelevanceLevel.RELATED
    assert classify_relevance(query, irrelevant_job.title, responsibilities=irrelevant_job.description).level == RelevanceLevel.IRRELEVANT

    # Test orchestrator relevance filter method
    orchestrator = SearchOrchestrator()
    filtered = orchestrator._filter_by_relevance(query, [relevant_job, related_job, irrelevant_job])
    filtered_ids = [j.id for j in filtered]

    assert "smartrecruiters:acme:1" in filtered_ids
    assert "smartrecruiters:acme:2" in filtered_ids
    assert "smartrecruiters:tire:3" not in filtered_ids

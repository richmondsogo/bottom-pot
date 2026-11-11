from __future__ import annotations

import pytest

from src.project_files.relevance_classifier import (
    RelevanceLevel,
    RelevanceResult,
    classify_relevance,
)


def test_relevance_classifier_exact_and_strong_matches():
    # Exact or near-exact title matches
    res1 = classify_relevance(
        query="Full-Stack Developer",
        title="Full Stack Developer",
        department="Engineering",
        responsibilities="Build web applications using Python and React.",
    )
    assert res1.level == RelevanceLevel.STRONG
    assert res1.score >= 0.85

    res2 = classify_relevance(
        query="Full-Stack Developer",
        title="Senior Full-Stack Engineer",
        department="Software Development",
        responsibilities="Design full stack systems.",
    )
    assert res2.level == RelevanceLevel.STRONG
    assert res2.score >= 0.85


def test_relevance_classifier_legitimate_related_roles():
    # Legitimate related specializations within the domain
    res_front = classify_relevance(
        query="Full-Stack Developer",
        title="Senior Frontend Engineer",
        department="Engineering",
        responsibilities="Build React user interfaces and integrate backend APIs.",
    )
    assert res_front.level == RelevanceLevel.RELATED
    assert 0.5 <= res_front.score < 0.85

    res_back = classify_relevance(
        query="Full-Stack Developer",
        title="Backend Software Engineer",
        department="Core Platform",
        responsibilities="Develop distributed services in Go and PostgreSQL.",
    )
    assert res_back.level == RelevanceLevel.RELATED
    assert 0.5 <= res_back.score < 0.85

    res_ml = classify_relevance(
        query="Machine Learning Engineer",
        title="Computer Vision Engineer",
        department="AI Research",
        responsibilities="Train deep learning models for image processing.",
    )
    assert res_ml.level == RelevanceLevel.RELATED


def test_relevance_classifier_irrelevant_cross_domain_roles():
    # Real false positives observed in production search results for "Full-Stack Developer"
    negatives = [
        ("Tire Development Engineer II - TLD REPLACEMENT AMERICAS", "R&D"),
        ("Financial Crime Reporting Specialist (Bahasa Indonesia speaker)", "Operations"),
        ("Vulnerability Manager", "Information Security"),
        ("Lead Quant Analyst- Power Trading (m/f/d)", "Trading"),
        ("Aviation Planning Intern", "Aviation"),
        ("Associate-CS Phone", "Customer Service"),
    ]
    for title, dept in negatives:
        res = classify_relevance(
            query="Full-Stack Developer",
            title=title,
            department=dept,
            responsibilities="Oversee tire compound testing and manufacturing.",
        )
        assert res.level == RelevanceLevel.IRRELEVANT, f"Expected IRRELEVANT for {title}, got {res.level} ({res.reason})"
        assert res.score < 0.35


def test_relevance_classifier_excludes_company_marketing_text():
    # A non-tech role at a software company that describes itself as a full-stack platform
    company_marketing = "Acme Corp is the leading full-stack developer platform for enterprise cloud."
    res = classify_relevance(
        query="Full-Stack Developer",
        title="Aviation Planning Intern",
        department="Operations",
        company_description=company_marketing,  # Must be ignored as role evidence
        responsibilities="Assist with airport gate scheduling and passenger flow analysis.",
    )
    assert res.level == RelevanceLevel.IRRELEVANT
    assert "marketing" not in res.matched_tokens

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.models import JobListing
from src.extraction.relevance_classifier import (
    RelevanceLevel,
    classify_relevance,
    filter_and_rank_by_relevance,
    relevance_tier,
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


def test_relevance_classifier_blocks_body_only_mentions():
    # Body-only mention must never make an unrelated title match
    res_tech_trap = classify_relevance(
        query="Backend",
        title="Technical Account Manager I",
        responsibilities="Partner with backend engineering teams on API troubleshooting.",
        qualifications="Familiarity with backend services and REST APIs.",
    )
    assert res_tech_trap.level == RelevanceLevel.IRRELEVANT

    res_nontech_trap = classify_relevance(
        query="Accountant",
        title="Operations Associate",
        responsibilities="Coordinate invoices with the senior accountant and payroll team.",
    )
    assert res_nontech_trap.level == RelevanceLevel.IRRELEVANT

    # Single-word query must not expand via related cluster to unrelated title
    res_single = classify_relevance(
        query="Backend",
        title="Frontend Software Engineer",
        responsibilities="Collaborate closely with backend engineers.",
    )
    assert res_single.level == RelevanceLevel.IRRELEVANT


def test_relevance_classifier_domain_agnostic_normalization_and_nontech():
    # Hyphen/space/compound, Unicode NFKC, punctuation, plural, suffix, and filler words
    cases = [
        ("Backend", "Senior Backend Engineer", None),
        ("Back-end Developer", "Backend Developer (.NET)", None),
        ("Back end developer", "Back\u2010end Developer", None),
        ("Ｂａｃｋｅｎｄ jobs", "Senior Backend Engineer", None),
        ("Marketing Manager role", "Marketing Manager", None),
        ("Marketing Managers", "Senior Product Marketing Manager (US)", None),
        ("Senior Accountant position", "Senior Accountant ", None),
        ("Accountants", "Accountant-ERP", None),
        ("Fraud Analyst", "Senior Fraud Analyst", None),
        ("Vulnerability Manager", "Vulnerability Manager", None),
        ("Civil Engineering", "Senior Civil Engineer", None),
        ("Aviation Planning opening", "Aviation Planning Intern", None),
        ("Stripe", "Technical Sourcer", "Stripe"),
    ]
    for query, title, company in cases:
        tier, res = relevance_tier(query, title, company=company)
        assert tier == 1, f"Expected Tier 1 for query={query!r}, title={title!r}, got tier={tier} ({res.reason})"
        assert res.level == RelevanceLevel.STRONG


def test_relevance_classifier_whole_word_boundaries_prevent_substring_leaks():
    # "ai" must not match "email"/"retail", "ml" must not match "aml", "developer" != "development"
    assert classify_relevance("Data Scientist", "Email Marketing Manager").level == RelevanceLevel.IRRELEVANT
    assert classify_relevance("AI Engineer", "Retail Operations Manager").level == RelevanceLevel.IRRELEVANT
    assert classify_relevance("ML Engineer", "AML Compliance Analyst").level == RelevanceLevel.IRRELEVANT
    assert classify_relevance("Web Developer", "Business Development Representative").level == RelevanceLevel.IRRELEVANT


def test_filter_and_rank_orders_tier1_before_tier2_with_freshness_tiebreak():
    now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    def _job(jid: str, title: str, days_old: int, desc: str = "") -> JobListing:
        return JobListing(
            id=jid,
            provider="greenhouse",
            data_source="api",
            ats_source="greenhouse",
            title=title,
            company="Acme",
            apply_url=f"https://boards.greenhouse.io/acme/jobs/{jid}",
            source_url=f"https://boards.greenhouse.io/acme/jobs/{jid}",
            description=desc,
            posted_at=now - timedelta(days=days_old),
            scraped_at=now,
            query_used="Full-Stack Developer",
        )

    tier1_older = _job("t1-older", "Full Stack Developer", days_old=20)
    tier1_newer = _job("t1-newer", "Senior Full-Stack Developer", days_old=2)
    tier2_newest = _job("t2-newest", "Senior Full-Stack Engineer", days_old=1)
    tier2_related = _job("t2-related", "Backend Software Engineer", days_old=5)
    body_only = _job("drop-body", "Technical Account Manager I", days_old=0, desc="Full-Stack Developer background")

    ranked = filter_and_rank_by_relevance(
        "Full-Stack Developer",
        [body_only, tier2_related, tier1_older, tier2_newest, tier1_newer],
        mode="filter",
    )
    assert [j.id for j in ranked] == ["t1-newer", "t1-older", "t2-newest", "t2-related"]

    unfiltered = filter_and_rank_by_relevance(
        "Full-Stack Developer",
        [body_only, tier2_related, tier1_older, tier2_newest, tier1_newer],
        mode="off",
    )
    assert [j.id for j in unfiltered] == ["drop-body", "t2-related", "t1-older", "t2-newest", "t1-newer"]

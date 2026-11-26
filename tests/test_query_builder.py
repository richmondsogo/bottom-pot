"""
Tests for Query Builder (Step 7).
"""

from src.core.models import SearchParams
from src.discovery.query_builder import ATS_DOMAINS, build_ats_queries, build_ats_query


def test_ats_domains_defined():
    assert "greenhouse" in ATS_DOMAINS
    assert "lever" in ATS_DOMAINS
    assert "ashby" in ATS_DOMAINS
    assert ATS_DOMAINS["ashby"] == "jobs.ashbyhq.com"
    assert "smartrecruiters" in ATS_DOMAINS
    assert "workable" in ATS_DOMAINS
    assert "pinpointhq" in ATS_DOMAINS
    assert "recruitee" in ATS_DOMAINS
    assert "bamboohr" not in ATS_DOMAINS


def test_basic_query():
    params = SearchParams(job_title="Data Analyst")
    q = build_ats_query("boards.greenhouse.io", params)
    # Query text is canonicalized (casefolded) by shared search_canonicalizer
    assert q == 'site:boards.greenhouse.io "data analyst"'


def test_remote_true_query():
    params = SearchParams(job_title="Backend Engineer", remote=True)
    q = build_ats_query("jobs.lever.co", params)
    assert q == 'site:jobs.lever.co "backend engineer" "remote"'


def test_remote_false_query():
    params = SearchParams(job_title="Backend Engineer", remote=False)
    q = build_ats_query("jobs.lever.co", params)
    assert q == 'site:jobs.lever.co "backend engineer" -"remote"'


def test_single_word_location():
    params = SearchParams(job_title="Frontend Engineer", location="London")
    q = build_ats_query("jobs.ashbyhq.com", params)
    assert q == 'site:jobs.ashbyhq.com "frontend engineer" london'


def test_multi_word_location():
    params = SearchParams(job_title="Frontend Engineer", location="New York")
    q = build_ats_query("jobs.ashbyhq.com", params)
    assert q == 'site:jobs.ashbyhq.com "frontend engineer" "new york"'


def test_exclude_keywords():
    params = SearchParams(
        job_title="Software Engineer",
        exclude_keywords=["intern", "contract"],
    )
    q = build_ats_query("apply.workable.com", params)
    # exclude_keywords are canonicalized and sorted alphabetically
    assert q == 'site:apply.workable.com "software engineer" -"contract" -"intern"'


def test_build_ats_queries_all():
    params = SearchParams(job_title="DevOps Engineer")
    queries = build_ats_queries(params)
    assert len(queries) == 10
    assert "breezy" not in queries
    assert "bamboohr" not in queries
    assert "pinpointhq" in queries
    assert "greenhouse" in queries
    assert 'site:greenhouse.io "devops engineer"' == queries["greenhouse"]


def test_build_ats_queries_filtered():
    params = SearchParams(job_title="DevOps Engineer")
    queries = build_ats_queries(params, platforms=["greenhouse", "lever", "ashby"])
    assert len(queries) == 3
    assert "greenhouse" in queries
    assert "lever" in queries
    assert "ashby" in queries
    assert queries["ashby"] == 'site:jobs.ashbyhq.com "devops engineer"'


def test_teamtailor_query_excludes_marketing_subdomain():
    params = SearchParams(job_title="Software Engineer")
    q = build_ats_query("teamtailor.com", params, platform="teamtailor")
    assert "-site:www.teamtailor.com" in q
    assert "-site:support.teamtailor.com" in q
    assert 'site:teamtailor.com -site:www.teamtailor.com -site:support.teamtailor.com "software engineer"' == q

    # Also verify build_ats_queries automatically includes exclusion
    queries = build_ats_queries(params, platforms=["teamtailor"])
    assert queries["teamtailor"] == 'site:teamtailor.com -site:www.teamtailor.com -site:support.teamtailor.com "software engineer"'


def test_pinpoint_query_excludes_marketing_subdomains():
    params = SearchParams(job_title="Software Engineer")
    queries = build_ats_queries(params, platforms=["pinpointhq"])
    assert (
        queries["pinpointhq"]
        == 'site:pinpointhq.com -site:www.pinpointhq.com -site:developers.pinpointhq.com -site:app.pinpointhq.com "software engineer"'
    )


def test_nigerian_location_relaxed_for_ats_queries():
    """Nigerian locations relax ATS queries to ('Nigeria' OR 'Lagos' OR 'Remote' OR 'EMEA') unless remote=False."""
    # 1. Nigeria with remote not specified -> relaxed
    p1 = SearchParams(job_title="Software Engineer", location="Nigeria")
    q1 = build_ats_query("boards.greenhouse.io", p1)
    assert q1 == 'site:boards.greenhouse.io "software engineer" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 2. Lagos with remote=True -> relaxed and includes "remote"
    p2 = SearchParams(job_title="Backend Engineer", location="Lagos", remote=True)
    q2 = build_ats_query("jobs.lever.co", p2)
    assert q2 == 'site:jobs.lever.co "backend engineer" "remote" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 3. Abuja with remote=False (strict on-site) -> exact location preserved, NOT relaxed
    p3 = SearchParams(job_title="Frontend Engineer", location="Abuja", remote=False)
    q3 = build_ats_query("jobs.ashbyhq.com", p3)
    assert q3 == 'site:jobs.ashbyhq.com "frontend engineer" -"remote" abuja'

    # 4. Port Harcourt -> relaxed
    p4 = SearchParams(job_title="DevOps Engineer", location="Port Harcourt")
    q4 = build_ats_query("apply.workable.com", p4)
    assert q4 == 'site:apply.workable.com "devops engineer" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 5. Non-Nigerian location (London) -> exact location preserved
    p5 = SearchParams(job_title="Data Scientist", location="London")
    q5 = build_ats_query("jobs.ashbyhq.com", p5)
    assert q5 == 'site:jobs.ashbyhq.com "data scientist" london'


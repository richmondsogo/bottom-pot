"""
Tests for Query Builder (Step 7).
"""

from src.project_files.models import SearchParams
from src.project_files.query_builder import ATS_DOMAINS, build_ats_queries, build_ats_query


def test_ats_domains_defined():
    assert "greenhouse" in ATS_DOMAINS
    assert "lever" in ATS_DOMAINS
    assert "ashby" in ATS_DOMAINS
    assert "smartrecruiters" in ATS_DOMAINS
    assert "workable" in ATS_DOMAINS
    assert "bamboohr" in ATS_DOMAINS
    assert "recruitee" in ATS_DOMAINS


def test_basic_query():
    params = SearchParams(job_title="Data Analyst")
    q = build_ats_query("boards.greenhouse.io", params)
    assert q == 'site:boards.greenhouse.io "Data Analyst"'


def test_remote_true_query():
    params = SearchParams(job_title="Backend Engineer", remote=True)
    q = build_ats_query("jobs.lever.co", params)
    assert q == 'site:jobs.lever.co "Backend Engineer" "remote"'


def test_remote_false_query():
    params = SearchParams(job_title="Backend Engineer", remote=False)
    q = build_ats_query("jobs.lever.co", params)
    assert q == 'site:jobs.lever.co "Backend Engineer" -"remote"'


def test_single_word_location():
    params = SearchParams(job_title="Frontend Engineer", location="London")
    q = build_ats_query("jobs.ashbyhq.com", params)
    assert q == 'site:jobs.ashbyhq.com "Frontend Engineer" London'


def test_multi_word_location():
    params = SearchParams(job_title="Frontend Engineer", location="New York")
    q = build_ats_query("jobs.ashbyhq.com", params)
    assert q == 'site:jobs.ashbyhq.com "Frontend Engineer" "New York"'


def test_exclude_keywords():
    params = SearchParams(
        job_title="Software Engineer",
        exclude_keywords=["intern", "contract"],
    )
    q = build_ats_query("apply.workable.com", params)
    assert q == 'site:apply.workable.com "Software Engineer" -"intern" -"contract"'


def test_build_ats_queries_all():
    params = SearchParams(job_title="DevOps Engineer")
    queries = build_ats_queries(params)
    assert len(queries) == 18
    assert "greenhouse" in queries
    assert 'site:greenhouse.io "DevOps Engineer"' == queries["greenhouse"]


def test_build_ats_queries_filtered():
    params = SearchParams(job_title="DevOps Engineer")
    queries = build_ats_queries(params, platforms=["greenhouse", "lever"])
    assert len(queries) == 2
    assert "greenhouse" in queries
    assert "lever" in queries


def test_teamtailor_query_excludes_marketing_subdomain():
    params = SearchParams(job_title="Software Engineer")
    q = build_ats_query("teamtailor.com", params, platform="teamtailor")
    assert "-site:www.teamtailor.com" in q
    assert 'site:teamtailor.com -site:www.teamtailor.com "Software Engineer"' == q

    # Also verify build_ats_queries automatically includes exclusion
    queries = build_ats_queries(params, platforms=["teamtailor"])
    assert queries["teamtailor"] == 'site:teamtailor.com -site:www.teamtailor.com "Software Engineer"'


def test_nigerian_location_relaxed_for_ats_queries():
    """Nigerian locations relax ATS queries to ('Nigeria' OR 'Lagos' OR 'Remote' OR 'EMEA') unless remote=False."""
    # 1. Nigeria with remote not specified -> relaxed
    p1 = SearchParams(job_title="Software Engineer", location="Nigeria")
    q1 = build_ats_query("boards.greenhouse.io", p1)
    assert q1 == 'site:boards.greenhouse.io "Software Engineer" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 2. Lagos with remote=True -> relaxed and includes "remote"
    p2 = SearchParams(job_title="Backend Engineer", location="Lagos", remote=True)
    q2 = build_ats_query("jobs.lever.co", p2)
    assert q2 == 'site:jobs.lever.co "Backend Engineer" "remote" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 3. Abuja with remote=False (strict on-site) -> exact location preserved, NOT relaxed
    p3 = SearchParams(job_title="Frontend Engineer", location="Abuja", remote=False)
    q3 = build_ats_query("jobs.ashbyhq.com", p3)
    assert q3 == 'site:jobs.ashbyhq.com "Frontend Engineer" -"remote" Abuja'

    # 4. Port Harcourt -> relaxed
    p4 = SearchParams(job_title="DevOps Engineer", location="Port Harcourt")
    q4 = build_ats_query("apply.workable.com", p4)
    assert q4 == 'site:apply.workable.com "DevOps Engineer" ("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'

    # 5. Non-Nigerian location (London) -> exact location preserved
    p5 = SearchParams(job_title="Data Scientist", location="London")
    q5 = build_ats_query("jobs.ashbyhq.com", p5)
    assert q5 == 'site:jobs.ashbyhq.com "Data Scientist" London'


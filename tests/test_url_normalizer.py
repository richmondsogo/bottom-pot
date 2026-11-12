"""
Unit tests for src/project_files/url_normalizer.py

Covers:
- Lowercase hostnames and schemes
- Trailing slash stripping
- Tracking parameter stripping (utm_*, gclid, fbclid, msclkid, mc_cid, mc_eid, gh_src, lever-source, lever-origin)
- Non-tracking parameter retention (ref, source, etc.) and deterministic sorting
- Fragment handling: anchor stripping (#apply, #content) vs SPA routing fragment retention (#/jobs/123)
- Identifier preservation: gh_jid, jobId, reqId, etc.
- Provider identifier registry
- url_carries_job_identifier truth table (bare boards, listing pages, jobs)
- Strong-match identity keys: (provider, company, provider_job_id)
- Negative separation: same numeric ID under different companies stays separate;
  records sharing a listing page stay separate.
"""

import pytest

from src.project_files.url_normalizer import (
    build_id_match_key,
    build_url_match_key,
    normalize_job_url,
    url_carries_job_identifier,
)


class TestUrlNormalizer:
    def test_lowercase_scheme_and_hostname(self):
        url = "HTTPS://BOARDS.GREENHOUSE.IO/Stripe/jobs/12345"
        assert normalize_job_url(url) == "https://boards.greenhouse.io/Stripe/jobs/12345"

    def test_strip_trailing_slash(self):
        url = "https://jobs.lever.co/anthropic/d1e9b6e2-4c1a-4f7e-b3e9-1a2b3c4d5e6f/"
        assert normalize_job_url(url) == "https://jobs.lever.co/anthropic/d1e9b6e2-4c1a-4f7e-b3e9-1a2b3c4d5e6f"

    def test_strip_all_known_tracking_params(self):
        url = (
            "https://jobs.lever.co/kinsta/caadac8e/apply?"
            "utm_source=google&utm_medium=cpc&utm_campaign=summer&utm_content=text&utm_term=dev&"
            "gclid=12345&fbclid=67890&msclkid=abcde&mc_cid=fghij&mc_eid=klmno&"
            "gh_src=ghref&lever-source=levsrc&lever-origin=levorig"
        )
        assert normalize_job_url(url) == "https://jobs.lever.co/kinsta/caadac8e/apply"

    def test_preserve_non_tracking_params_and_sort_deterministically(self):
        url = "https://example.com/jobs/detail?source=linkedin&ref=engineering_newsletter&z_param=last&a_param=first"
        norm = normalize_job_url(url)
        assert norm == "https://example.com/jobs/detail?a_param=first&ref=engineering_newsletter&source=linkedin&z_param=last"

    def test_strip_known_anchors_and_preserve_routing_fragments(self):
        # Known anchors are stripped
        assert normalize_job_url("https://example.com/job/123#apply") == "https://example.com/job/123"
        assert normalize_job_url("https://example.com/job/123#content") == "https://example.com/job/123"
        assert normalize_job_url("https://example.com/job/123#overview") == "https://example.com/job/123"

        # SPA routing fragments are preserved
        assert normalize_job_url("https://example.com/portal#/jobs/456") == "https://example.com/portal#/jobs/456"
        assert normalize_job_url("https://example.com/portal#!job-789") == "https://example.com/portal#!job-789"

    def test_preserve_job_identifier_params(self):
        url = "https://careers.acme.com/view?gh_jid=998877&utm_medium=feed"
        assert normalize_job_url(url) == "https://careers.acme.com/view?gh_jid=998877"

        url2 = "https://careers.delta.com/JobDetail?jobId=34732&utm_source=jobboard"
        assert normalize_job_url(url2) == "https://careers.delta.com/JobDetail?jobId=34732"


class TestUrlCarriesJobIdentifier:
    @pytest.mark.parametrize(
        "url,expected",
        [
            # Valid known ATS job URLs
            ("https://boards.greenhouse.io/stripe/jobs/4567890", True),
            ("https://jobs.lever.co/anthropic/d1e9b6e2-4c1a-4f7e-b3e9-1a2b3c4d5e6f", True),
            ("https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff", True),
            ("https://jobs.smartrecruiters.com/uber/3743990000051828", True),
            ("https://deel.bamboohr.com/careers/15", True),
            # Embedded / query-based job URLs
            ("https://company.com/careers?gh_jid=12345", True),
            ("https://company.com/apply?jobId=67890", True),
            ("https://company.taleo.net/careersection/ex/jobdetail.ftl?job=112233", True),
            # Nigerian job postings
            ("https://www.jobberman.com/listings/senior-frontend-developer-2kgrpe", True),
            ("https://www.myjobmag.com/job/lead-architect", True),
            ("https://www.hotnigerianjobs.com/hotjobs/979610/engineer.html", True),
            ("https://ngcareers.com/job/cloud-devops", True),
            # Bare ATS board roots & listing pages (must be rejected)
            ("https://boards.greenhouse.io/stripe", False),
            ("https://boards.greenhouse.io/stripe/jobs", False),
            ("https://jobs.lever.co/anthropic", False),
            ("https://jobs.ashbyhq.com/figme", False),
            # Generic listing/apply pages
            ("https://acme.com/careers", False),
            ("https://acme.com/jobs", False),
            ("https://acme.com/apply", False),
            ("https://acme.com/jobs/apply", False),
            ("https://acme.com/search", False),
            ("https://acme.com/", False),
            ("", False),
        ],
    )
    def test_job_identifier_presence(self, url, expected):
        assert url_carries_job_identifier(url) == expected


class TestMatchKeysAndNegativeSeparation:
    def test_strong_id_match_key(self):
        key = build_id_match_key("greenhouse", "Stripe", "4567890")
        assert key == ("greenhouse", "stripe", "4567890")

    def test_same_numeric_id_under_different_companies_stays_separate(self):
        key_stripe = build_id_match_key("greenhouse", "stripe", "12345")
        key_openai = build_id_match_key("greenhouse", "openai", "12345")
        assert key_stripe != key_openai, "Same job ID under different companies must never match"

    def test_missing_or_unknown_company_yields_no_id_match_key(self):
        assert build_id_match_key("greenhouse", "Unknown", "12345") is None
        assert build_id_match_key("greenhouse", None, "12345") is None
        assert build_id_match_key(None, "stripe", "12345") is None
        assert build_id_match_key("greenhouse", "stripe", None) is None

    def test_two_records_sharing_a_listing_page_url_stay_separate(self):
        listing_url = "https://boards.greenhouse.io/stripe/jobs"
        match_key = build_url_match_key(listing_url)
        assert match_key is None, "Listing page URLs must never produce a URL match key"

    def test_verified_job_url_produces_url_match_key(self):
        job_url_1 = "https://boards.greenhouse.io/stripe/jobs/4567890?utm_source=twitter"
        job_url_2 = "https://boards.greenhouse.io/stripe/jobs/4567890#apply"

        key1 = build_url_match_key(job_url_1)
        key2 = build_url_match_key(job_url_2)

        assert key1 == "https://boards.greenhouse.io/stripe/jobs/4567890"
        assert key2 == "https://boards.greenhouse.io/stripe/jobs/4567890"
        assert key1 == key2

    def test_greenhouse_http_normalized_to_https_without_generalizing_other_domains(self):
        assert (
            normalize_job_url("http://job-boards.eu.greenhouse.io/bybit/jobs/4974271101")
            == "https://job-boards.eu.greenhouse.io/bybit/jobs/4974271101"
        )
        assert (
            normalize_job_url("http://job-boards.greenhouse.io/discord/jobs/8910013002?gh_src=x")
            == "https://job-boards.greenhouse.io/discord/jobs/8910013002"
        )
        # Arbitrary non-Greenhouse domains remain http://
        assert normalize_job_url("http://example.com/jobs/12345") == "http://example.com/jobs/12345"

    def test_redundant_gh_jid_stripped_when_matching_path_id_and_retained_otherwise(self):
        assert (
            normalize_job_url("https://job-boards.greenhouse.io/figma/jobs/6238015004?gh_jid=6238015004")
            == "https://job-boards.greenhouse.io/figma/jobs/6238015004"
        )
        assert (
            normalize_job_url("https://boards.greenhouse.io/spacex/jobs/8769729002?gh_jid=8769729002")
            == "https://boards.greenhouse.io/spacex/jobs/8769729002"
        )
        # When gh_jid is the only identifier on a custom/embed path, retain it
        assert (
            normalize_job_url("https://databricks.com/company/careers/open-positions/job?gh_jid=8923831002")
            == "https://databricks.com/company/careers/open-positions/job?gh_jid=8923831002"
        )
        assert (
            normalize_job_url("https://boards.greenhouse.io/embed/job_app?gh_jid=12345")
            == "https://boards.greenhouse.io/embed/job_app?gh_jid=12345"
        )

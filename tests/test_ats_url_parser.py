"""
Tests for src/project_files/ats_url_parser.py

Covers:
 All 7 ATS platforms with valid URLs
 - URL variants (e.g., boards.greenhouse.io vs job-boards.greenhouse.io)
- URL variants (e.g., boards.greenhouse.io vs job-boards.greenhouse.io)
- Rejection of homepages, search pages, blog posts, partial paths
- Edge cases: None, empty string, malformed URL
"""

import pytest

from src.project_files.ats_url_parser import ParsedATSUrl, parse_ats_url


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------

class TestGreenhouse:
    def test_boards_greenhouse_io(self):
        url = "https://boards.greenhouse.io/stripe/jobs/4567890"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "greenhouse"
        assert result.company_slug == "stripe"
        assert result.job_id == "4567890"
        assert result.raw_url == url

    def test_job_boards_greenhouse_io(self):
        url = "https://job-boards.greenhouse.io/openai/jobs/1234567"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "greenhouse"
        assert result.company_slug == "openai"
        assert result.job_id == "1234567"

    def test_greenhouse_homepage_rejected(self):
        assert parse_ats_url("https://boards.greenhouse.io/stripe") is None

    def test_greenhouse_jobs_root_rejected(self):
        # /jobs without a numeric ID at the end
        assert parse_ats_url("https://boards.greenhouse.io/stripe/jobs") is None

    def test_greenhouse_non_numeric_job_id_rejected(self):
        # The spec requires a numeric job ID for Greenhouse
        assert parse_ats_url("https://boards.greenhouse.io/stripe/jobs/abc-def") is None

    def test_greenhouse_trailing_slash(self):
        url = "https://boards.greenhouse.io/stripe/jobs/9999999/"
        result = parse_ats_url(url)
        assert result is not None
        assert result.job_id == "9999999"

    def test_greenhouse_with_query_string(self):
        # Query strings should be stripped; core path must still match
        url = "https://boards.greenhouse.io/stripe/jobs/4567890?utm_source=linkedin"
        result = parse_ats_url(url)
        assert result is not None
        assert result.job_id == "4567890"


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------

class TestLever:
    VALID = "https://jobs.lever.co/anthropic/d1e9b6e2-4c1a-4f7e-b3e9-1a2b3c4d5e6f"

    def test_valid_lever_url(self):
        result = parse_ats_url(self.VALID)
        assert result is not None
        assert result.ats == "lever"
        assert result.company_slug == "anthropic"
        assert result.job_id == "d1e9b6e2-4c1a-4f7e-b3e9-1a2b3c4d5e6f"

    def test_lever_homepage_rejected(self):
        assert parse_ats_url("https://jobs.lever.co/anthropic") is None

    def test_lever_non_uuid_rejected(self):
        assert parse_ats_url("https://jobs.lever.co/anthropic/software-engineer") is None

    def test_lever_trailing_slash(self):
        url = self.VALID + "/"
        result = parse_ats_url(url)
        assert result is not None


# ---------------------------------------------------------------------------
# Ashby
# ---------------------------------------------------------------------------

class TestAshby:
    VALID = "https://jobs.ashbyhq.com/figma/a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_valid_ashby_url(self):
        result = parse_ats_url(self.VALID)
        assert result is not None
        assert result.ats == "ashby"
        assert result.company_slug == "figma"

    def test_ashby_application_url_accepted(self):
        result = parse_ats_url("https://jobs.ashbyhq.com/figma/a1b2c3d4-e5f6-7890-abcd-ef1234567890/application")
        assert result is not None
        assert result.ats == "ashby"
        assert result.company_slug == "figma"
        assert result.job_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_ashby_homepage_rejected(self):
        assert parse_ats_url("https://jobs.ashbyhq.com/figma") is None

    def test_ashby_non_uuid_rejected(self):
        assert parse_ats_url("https://jobs.ashbyhq.com/figma/design-engineer") is None

    def test_ashby_other_suffix_rejected(self):
        assert parse_ats_url("https://jobs.ashbyhq.com/figma/a1b2c3d4-e5f6-7890-abcd-ef1234567890/settings") is None



# ---------------------------------------------------------------------------
# SmartRecruiters
# ---------------------------------------------------------------------------

class TestSmartRecruiters:
    VALID = "https://jobs.smartrecruiters.com/Spotify/743999800573774"

    def test_valid_smartrecruiters_url(self):
        result = parse_ats_url(self.VALID)
        assert result is not None
        assert result.ats == "smartrecruiters"
        assert result.company_slug == "Spotify"
        assert result.job_id == "743999800573774"

    def test_smartrecruiters_homepage_rejected(self):
        assert parse_ats_url("https://jobs.smartrecruiters.com/Spotify") is None

    def test_smartrecruiters_non_numeric_job_id_rejected(self):
        assert parse_ats_url("https://jobs.smartrecruiters.com/Spotify/data-engineer") is None


# ---------------------------------------------------------------------------
# Workable
# ---------------------------------------------------------------------------

class TestWorkable:
    def test_subdomain_variant(self):
        url = "https://acme.workable.com/jobs/ABC123"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "workable"
        assert result.company_slug == "acme"
        assert result.job_id == "ABC123"

    def test_apply_variant(self):
        url = "https://apply.workable.com/acme/j/DEF456"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "workable"
        assert result.company_slug == "acme"
        assert result.job_id == "DEF456"

    def test_workable_homepage_rejected(self):
        assert parse_ats_url("https://acme.workable.com") is None

    def test_workable_apply_homepage_rejected(self):
        assert parse_ats_url("https://apply.workable.com/acme") is None


# ---------------------------------------------------------------------------
# BambooHR
# ---------------------------------------------------------------------------

class TestBambooHR:
    def test_valid_bamboohr_url(self):
        url = "https://techcorp.bamboohr.com/careers/42"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "bamboohr"
        assert result.company_slug == "techcorp"
        assert result.job_id == "42"

    def test_bamboohr_homepage_rejected(self):
        assert parse_ats_url("https://techcorp.bamboohr.com") is None

    def test_bamboohr_careers_root_rejected(self):
        assert parse_ats_url("https://techcorp.bamboohr.com/careers") is None


# ---------------------------------------------------------------------------
# Recruitee
# ---------------------------------------------------------------------------

class TestRecruitee:
    def test_valid_recruitee_url(self):
        url = "https://mycompany.recruitee.com/o/1234567-senior-python-engineer"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "recruitee"
        assert result.company_slug == "mycompany"
        assert result.job_id == "1234567"

    def test_recruitee_homepage_rejected(self):
        assert parse_ats_url("https://mycompany.recruitee.com") is None

    def test_recruitee_no_numeric_id_rejected(self):
        # No numeric prefix before the dash
        assert parse_ats_url("https://mycompany.recruitee.com/o/senior-python-engineer") is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_none_input(self):
        assert parse_ats_url(None) is None  # type: ignore[arg-type]

    def test_empty_string(self):
        assert parse_ats_url("") is None

    def test_totally_unrelated_url(self):
        assert parse_ats_url("https://www.linkedin.com/jobs/view/12345") is None

    def test_http_scheme_also_works(self):
        url = "http://boards.greenhouse.io/stripe/jobs/4567890"
        result = parse_ats_url(url)
        assert result is not None
        assert result.ats == "greenhouse"

    def test_malformed_url_does_not_raise(self):
        # Should return None, not raise
        result = parse_ats_url("not-a-url-at-all-:::###")
        assert result is None

class TestAdditionalATS:
    @pytest.mark.parametrize(
        "url,ats",
        [
            ("https://jobs.jobvite.com/acme/job/abc123", "jobvite"),
            ("https://acme.teamtailor.com/jobs/12345-backend-engineer", "teamtailor"),
            ("https://jobs.personio.com/job/backend-engineer-12345", "personio"),
            ("https://jobs.icims.com/jobs/12345/backend-engineer", "icims"),
            ("https://apply.breezy.hr/p/abc123/backend-engineer", "breezy"),
            ("https://applytojob.com/apply/abc123", "jazzhr"),
            ("https://activeprospect.applytojob.com/app/share/kmnC9eIyPq", "jazzhr"),
            ("https://jobs.sap.com/job/12345/backend-engineer", "successfactors"),
        ],
    )
    def test_supported_additional_job_urls(self, url, ats):
        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == ats

    @pytest.mark.parametrize(
        "url",
        [
            "https://jobs.jobvite.com/acme",
            "https://acme.teamtailor.com/jobs",
            "https://jobs.icims.com/jobs/not-a-number/backend-engineer",
            "https://apply.breezy.hr/p/abc123",
        ],
    )
    def test_additional_homepages_and_malformed_urls_are_rejected(self, url):
        assert parse_ats_url(url) is None

    @pytest.mark.parametrize(
        "url",
        [
            "https://jobs.smartrecruiters.com/NBCUniversal3/744000148820824-sr-software-engineer",
            "https://jobs.smartrecruiters.com/Canva/6000000001393822-staff-software-engineer-video-performance-bay-area-only-",
        ],
    )
    def test_smartrecruiters_title_slug_is_supported(self, url):
        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == "smartrecruiters"
        assert parsed.job_id.isdigit()


class TestSlugValidationAndTenantExtraction:
    def test_is_valid_board_slug_accepts_legitimate_slugs(self):
        from src.project_files.ats_url_parser import is_valid_board_slug
        assert is_valid_board_slug("greenhouse", "stripe") is True
        assert is_valid_board_slug("lever", "anthropic") is True
        assert is_valid_board_slug("ashby", "figma") is True
        assert is_valid_board_slug("personio", "getflow") is True

    def test_is_valid_board_slug_rejects_stopwords_and_placeholders(self):
        from src.project_files.ats_url_parser import is_valid_board_slug
        assert is_valid_board_slug("greenhouse", "greenhouse") is False
        assert is_valid_board_slug("personio", "personio") is False
        assert is_valid_board_slug("icims", "icims") is False
        assert is_valid_board_slug("breezy", "breezy") is False
        assert is_valid_board_slug("jazzhr", "jazzhr") is False
        assert is_valid_board_slug("workday", "jobs") is False
        assert is_valid_board_slug("workday", "careers") is False
        assert is_valid_board_slug("workday", "apply") is False
        assert is_valid_board_slug("workday", "") is False
        assert is_valid_board_slug("workday", None) is False

    def test_tenant_subdomain_extraction_across_providers(self):
        # Workday tenant subdomain
        p1 = parse_ats_url("https://nvidia.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Senior-Architect_JR198")
        assert p1 is not None
        assert p1.company_slug == "nvidia"

        # Taleo tenant subdomain
        p2 = parse_ats_url("https://acme.taleo.net/careersection/2/jobdetail.ftl?job=12345")
        assert p2 is not None
        assert p2.company_slug == "acme"

        # Personio tenant subdomain
        p3 = parse_ats_url("https://acme.jobs.personio.de/job/12345")
        assert p3 is not None
        assert p3.company_slug == "acme"

        # Breezy tenant subdomain
        p4 = parse_ats_url("https://acme.breezy.hr/p/12345-engineer")
        assert p4 is not None
        assert p4.company_slug == "acme"

        # JazzHR tenant subdomain
        p5 = parse_ats_url("https://activeprospect.applytojob.com/apply/abc123")
        assert p5 is not None
        assert p5.company_slug == "activeprospect"


# ---------------------------------------------------------------------------
# Avature
# ---------------------------------------------------------------------------

class TestAvature:
    @pytest.mark.parametrize(
        "url,expected_slug,expected_id",
        [
            (
                "https://koch.avature.net/en_US/careers/JobDetail/Data-Scientist/194843",
                "koch",
                "194843",
            ),
            (
                "https://delta.avature.net/en_US/careers/JobDetail/Director-Materials-Strategy/34732?jobId=34732",
                "delta",
                "34732",
            ),
            (
                "https://delta.avature.net/en_US/careers/JobDetail/Delta-Vacations-Business-Intelligence-Analyst/34025?jobId=34025",
                "delta",
                "34025",
            ),
            (
                "https://koch.avature.net/pl_PL/careers/JobDetail/Senior-Mechanical-Simulation-Engineer/193537",
                "koch",
                "193537",
            ),
            (
                "https://acme.avature.net/careers/job/12345/senior-dev",
                "acme",
                "12345",
            ),
            (
                "https://acme.avature.net/careers/job/12345/",
                "acme",
                "12345",
            ),
        ],
    )
    def test_valid_avature_urls(self, url, expected_slug, expected_id):
        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == "avature"
        assert parsed.company_slug == expected_slug
        assert parsed.job_id == expected_id

    @pytest.mark.parametrize(
        "url",
        [
            "https://koch.avature.net/careers",
            "https://koch.avature.net/careers/SearchJobs",
            "https://koch.avature.net/en_US/careers/Login",
            "https://koch.avature.net/internalcareers",
            "https://koch.avature.net/portal/4/images/logo.svg",
        ],
    )
    def test_avature_non_job_urls_rejected(self, url):
        assert parse_ats_url(url) is None

    def test_parse_ats_url_exception_logs_warning(self, monkeypatch):
        from loguru import logger
        from src.project_files import ats_url_parser

        logged: list[str] = []
        handler_id = logger.add(lambda msg: logged.append(str(msg)), level="WARNING")
        try:
            class FaultyPattern:
                def match(self, _):
                    raise RuntimeError("Simulated error")

            monkeypatch.setattr(ats_url_parser, "_GH_BOARDS", FaultyPattern())
            result = ats_url_parser.parse_ats_url("https://boards.greenhouse.io/stripe/jobs/12345")
            assert result is None
            assert any("Error parsing ATS URL" in msg and "Simulated error" in msg for msg in logged)
        finally:
            logger.remove(handler_id)


# ---------------------------------------------------------------------------
# Step 23: URL Normalization & Identifier Preservation Negative Tests
# ---------------------------------------------------------------------------

class TestUrlNormalizationAndIdentifierIntegrity:
    """
    Verify that URL normalization preserves job identifiers and never merges distinct jobs.
    """

    def test_distinct_jobs_differing_only_by_gh_jid_never_normalize_to_same_url(self):
        from src.project_files.url_normalizer import normalize_job_url

        url1 = "https://careers.acme.com/jobs?gh_jid=12345&utm_source=linkedin"
        url2 = "https://careers.acme.com/jobs?gh_jid=67890&utm_source=linkedin"

        norm1 = normalize_job_url(url1)
        norm2 = normalize_job_url(url2)

        assert norm1 == "https://careers.acme.com/jobs?gh_jid=12345"
        assert norm2 == "https://careers.acme.com/jobs?gh_jid=67890"
        assert norm1 != norm2, "Distinct gh_jid jobs must never normalize to the same URL"

    def test_distinct_jobs_differing_only_by_query_job_id_never_normalize_to_same_url(self):
        from src.project_files.url_normalizer import normalize_job_url

        url1 = "https://jobs.example.com/apply?jobId=A101&gclid=test1234"
        url2 = "https://jobs.example.com/apply?jobId=B202&gclid=test5678"

        norm1 = normalize_job_url(url1)
        norm2 = normalize_job_url(url2)

        assert norm1 == "https://jobs.example.com/apply?jobId=A101"
        assert norm2 == "https://jobs.example.com/apply?jobId=B202"
        assert norm1 != norm2, "Distinct query jobId values must never normalize to the same URL"

    def test_same_job_with_different_tracking_params_normalizes_identically(self):
        from src.project_files.url_normalizer import normalize_job_url

        url_a = "https://boards.greenhouse.io/stripe/jobs/4567890/?utm_source=twitter&utm_medium=social&gh_src=share"
        url_b = "https://BOARDS.GREENHOUSE.IO/stripe/jobs/4567890#apply"

        assert normalize_job_url(url_a) == "https://boards.greenhouse.io/stripe/jobs/4567890"
        assert normalize_job_url(url_b) == "https://boards.greenhouse.io/stripe/jobs/4567890"
        assert normalize_job_url(url_a) == normalize_job_url(url_b)


class TestGreenhouseStep37UrlSupport:
    def test_eu_greenhouse_host_parsed(self):
        url = "https://job-boards.eu.greenhouse.io/cognite/jobs/5016416101"
        res = parse_ats_url(url)
        assert res is not None
        assert res.ats == "greenhouse"
        assert res.company_slug == "cognite"
        assert res.job_id == "5016416101"

    @pytest.mark.parametrize(
        "http_url,expected_https,expected_slug,expected_id",
        [
            (
                "http://job-boards.eu.greenhouse.io/bybit/jobs/4974271101",
                "https://job-boards.eu.greenhouse.io/bybit/jobs/4974271101",
                "bybit",
                "4974271101",
            ),
            (
                "http://job-boards.greenhouse.io/discord/jobs/8910013002",
                "https://job-boards.greenhouse.io/discord/jobs/8910013002",
                "discord",
                "8910013002",
            ),
            (
                "http://boards.greenhouse.io/stripe/jobs/4567890",
                "https://boards.greenhouse.io/stripe/jobs/4567890",
                "stripe",
                "4567890",
            ),
        ],
    )
    def test_http_recognized_greenhouse_hosts_canonicalized_to_https(
        self, http_url, expected_https, expected_slug, expected_id
    ):
        from src.project_files.ats_url_parser import canonicalize_recognized_greenhouse_url

        canonical = canonicalize_recognized_greenhouse_url(http_url)
        assert canonical == expected_https
        res = parse_ats_url(http_url)
        assert res is not None
        assert res.ats == "greenhouse"
        assert res.company_slug == expected_slug
        assert res.job_id == expected_id
        assert res.raw_url == expected_https

    def test_arbitrary_http_domain_not_upgraded(self):
        from src.project_files.ats_url_parser import canonicalize_recognized_greenhouse_url

        assert canonicalize_recognized_greenhouse_url("http://example.com/jobs/12345") == "http://example.com/jobs/12345"

    def test_hyphenated_job_id_preserved_and_non_numeric_rejected(self):
        url = "https://job-boards.greenhouse.io/corasps/jobs/5131342007-8"
        res = parse_ats_url(url)
        assert res is not None
        assert res.ats == "greenhouse"
        assert res.company_slug == "corasps"
        assert res.job_id == "5131342007-8"
        assert parse_ats_url("https://boards.greenhouse.io/corasps/jobs/abc-def") is None

    def test_gh_jid_handling_recognized_vs_arbitrary_custom_domain(self):
        res_dup = parse_ats_url("https://job-boards.greenhouse.io/cloudflare/jobs/8328914?gh_jid=8328914")
        assert res_dup is not None
        assert res_dup.company_slug == "cloudflare"
        assert res_dup.job_id == "8328914"

        res_board_q = parse_ats_url("https://boards.greenhouse.io/stripe?gh_jid=4567890")
        assert res_board_q is not None
        assert res_board_q.ats == "greenhouse"
        assert res_board_q.company_slug == "stripe"
        assert res_board_q.job_id == "4567890"

        res_embed = parse_ats_url("https://boards.greenhouse.io/embed/job_app?for=stripe&token=4567890")
        assert res_embed is not None
        assert res_embed.ats == "greenhouse"
        assert res_embed.company_slug == "stripe"
        assert res_embed.job_id == "4567890"

        # Unverified arbitrary custom domains with ?gh_jid= must NOT parse into GreenhouseClient
        assert parse_ats_url("https://arbitrary-custom.example.com/careers?gh_jid=8140140") is None

    def test_parse_greenhouse_board_root_url(self):
        from src.project_files.ats_url_parser import parse_greenhouse_board_root_url

        assert parse_greenhouse_board_root_url("https://boards.greenhouse.io/stripe") == "stripe"
        assert parse_greenhouse_board_root_url("https://job-boards.greenhouse.io/stripe/jobs") == "stripe"
        assert parse_greenhouse_board_root_url("http://job-boards.eu.greenhouse.io/cognite?gh_src=ref") == "cognite"
        assert parse_greenhouse_board_root_url("https://boards.greenhouse.io/stripe/jobs/4567890") is None
        assert parse_greenhouse_board_root_url("https://boards.greenhouse.io/embed") is None
        assert parse_greenhouse_board_root_url("https://boards.greenhouse.io/stripe?gh_jid=4567890") is None

    def test_all_81_genuine_greenhouse_serper_urls_parse_to_https(self):
        import json
        from pathlib import Path

        fixture = Path(__file__).parent / "fixtures" / "real" / "greenhouse" / "serper_urls_81.json"
        urls = json.loads(fixture.read_text(encoding="utf-8"))
        assert len(urls) == 81
        parsed_results = [parse_ats_url(u) for u in urls]
        failed = [u for u, p in zip(urls, parsed_results) if p is None or p.ats != "greenhouse"]
        assert failed == [], f"Expected all 81 genuine Greenhouse URLs to parse, failed: {failed}"
        assert all(p.raw_url.startswith("https://") for p in parsed_results if p is not None)

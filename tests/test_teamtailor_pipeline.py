"""
Step 35 TDD: Teamtailor Quality Pipeline End-to-End Tests.

Covers:
1. Query builder exclusion of support.teamtailor.com & www.teamtailor.com.
2. URL discovery/parsing across multi-label regional (.na.), localized (/sv/jobs/), slugless (/jobs/{id}),
   and rejection of integration/support/people/marketing URLs.
3. SSRF-safe URL validation, Google redirect unwrapping, and verified custom-domain detection.
4. Expired (404/410/closed banner even with lingering JSON-LD) vs retryable/WAF fallback preservation.
5. Canonical Teamtailor identity & deduplication across slugless/locale/redirect variants.
6. Structured extraction (<dl>, section.block-cover, JSON-LD, requirements, work_model, salary, eligibility, logo)
   verified directly against captured real Teamtailor HTML fixtures.
7. Shared extractor improvements (requirements curly apostrophes/headings, EU-scoped WFA & Malaysia/EMEA/hybrid/visa
   eligibility rules, Spanish/Swedish/French work_model, European trailing € & dot-thousands salary parsing).
8. Post-relevance board registration in SearchOrchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.ats_url_parser import (
    is_safe_public_https_url,
    parse_ats_url,
)
from src.project_files.company_board_registry import CompanyBoardRegistry, build_canonical_board_url
from src.project_files.deduplicator import GlobalDeduplicator
from src.project_files.eligibility_extractor import extract_eligibility
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.job_extraction_service import extract_requirements
from src.project_files.models import SearchParams
from src.project_files.query_builder import ATS_EXCLUDED_SUBDOMAINS, build_ats_query
from src.project_files.salary_parser import extract_salary, parse_text_salary
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.work_model import resolve_work_model

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "teamtailor"


def _read_fixture(stem: str) -> tuple[dict, str]:
    meta = json.loads((FIXTURE_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    html = (FIXTURE_DIR / f"{stem}.html").read_text(encoding="utf-8")
    return meta, html


def _fixture_transport(url_map: dict[str, tuple[int, str]]):
    def handler(request: httpx.Request) -> httpx.Response:
        req_url = str(request.url)
        if req_url in url_map:
            code, body = url_map[req_url]
            return httpx.Response(code, text=body, request=request)
        return httpx.Response(404, text="Not found", request=request)

    return httpx.MockTransport(handler)


class TestTeamtailorDiscoveryAndUrlParsing:
    def test_query_builder_excludes_marketing_and_support_subdomains(self):
        excl = ATS_EXCLUDED_SUBDOMAINS["teamtailor"]
        assert "www.teamtailor.com" in excl
        assert "support.teamtailor.com" in excl
        q = build_ats_query("teamtailor.com", SearchParams(job_title="Software Engineer"), platform="teamtailor")
        assert "-site:www.teamtailor.com" in q
        assert "-site:support.teamtailor.com" in q

    @pytest.mark.parametrize(
        ("url", "expected_slug", "expected_id"),
        [
            ("https://qtech.teamtailor.com/jobs/8029561-java-developer", "qtech", "8029561"),
            ("https://rooftop.na.teamtailor.com/jobs/724276-frontend-architect-lead", "rooftop.na", "724276"),
            ("https://cc-jobs-jobsity.na.teamtailor.com/jobs/726924-fullstack-go-engineer", "cc-jobs-jobsity.na", "726924"),
            ("https://schibsted.teamtailor.com/sv/jobs/8657817-fullstack-developer-advertising-technology", "schibsted", "8657817"),
            ("https://acme.teamtailor.com/pt-BR/jobs/123456-desenvolvedor-backend", "acme", "123456"),
            ("https://knowmadmood.teamtailor.com/jobs/8519313", "knowmadmood", "8519313"),
            ("https://twinharbour.teamtailor.com/jobs/8531346", "twinharbour", "8531346"),
            ("https://baconsultingsrl-1749809296.teamtailor.com/jobs/8641048-full-stack-developer-net-angular", "baconsultingsrl-1749809296", "8641048"),
        ],
    )
    def test_parses_observed_valid_teamtailor_variants(self, url, expected_slug, expected_id):
        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == "teamtailor"
        assert parsed.company_slug == expected_slug
        assert parsed.job_id == expected_id

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://www.teamtailor.com/pt/integrations/",
            "https://www.teamtailor.com/pt-br/integrations/vervoe/",
            "https://support.teamtailor.com/sv/articles/1558532-skapa-ett-nytt-jobb",
            "https://support.teamtailor.com/jobs/12345-fake",
            "https://horse.teamtailor.com/pt-BR/people/3297430-claudio-martins",
            "https://career.teamtailor.com/jobs/12345-demo",
            "https://acme.teamtailor.com/jobs",
            "https://acme.teamtailor.com/departments/engineering",
            "https://www.teamtailor.com/en/",
        ],
    )
    def test_rejects_non_job_and_excluded_teamtailor_urls(self, bad_url):
        assert parse_ats_url(bad_url) is None

    def test_canonical_board_url_supports_multilabel_na_tenants(self):
        assert build_canonical_board_url("teamtailor", "rooftop.na") == "https://rooftop.na.teamtailor.com"

    def test_ssrf_safety_blocks_private_loopback_metadata_and_http(self):
        assert is_safe_public_https_url("https://jobs.lunar.app/jobs/8614059-backend-engineer", resolve_dns=False) is True
        for unsafe in (
            "http://jobs.lunar.app/jobs/8614059-backend-engineer",
            "https://127.0.0.1/jobs/1",
            "https://localhost/jobs/1",
            "https://10.0.0.5/jobs/1",
            "https://192.168.1.10/jobs/1",
            "https://172.16.0.1/jobs/1",
            "https://169.254.169.254/latest/meta-data/",
            "https://[::1]/jobs/1",
            "https://metadata.google.internal/computeMetadata/v1/",
            "https://careers.internal.local/jobs/1",
        ):
            assert is_safe_public_https_url(unsafe, resolve_dns=False) is False

    def test_canonical_identity_and_dedup_across_url_variants(self):
        meta_slugless, html_slugless = _read_fixture("49a602c1")  # knowmadmood/8519313
        listing_a = httpx.AsyncClient
        import asyncio

        async def _run():
            u1 = "https://knowmadmood.teamtailor.com/jobs/8519313"
            u2 = "https://knowmadmood.teamtailor.com/es/jobs/8519313-software-developer-java-backend-a-coruna"
            transport = _fixture_transport({u1: (200, html_slugless), u2: (200, html_slugless)})
            async with httpx.AsyncClient(transport=transport) as client:
                j1, r1 = await enrich_ats_page_result(u1, "teamtailor", "", "", "java", client)
                j2, r2 = await enrich_ats_page_result(u2, "teamtailor", "", "", "java", client)
            return j1, r1, j2, r2

        j1, r1, j2, r2 = asyncio.run(_run())
        assert r1.outcome == ExtractionOutcome.SUCCESS
        assert r2.outcome == ExtractionOutcome.SUCCESS
        assert j1 is not None and j2 is not None
        assert j1.id == "teamtailor:knowmadmood:8519313"
        assert j2.id == "teamtailor:knowmadmood:8519313"

        dedup = GlobalDeduplicator()
        emissions = dedup.filter([j1, j2])
        assert len(emissions) == 1


class TestTeamtailorCustomDomainsAndGoogleRedirect:
    @pytest.mark.anyio
    async def test_google_goto_unwrapped_safely_and_custom_domain_accepted(self, monkeypatch):
        from src.project_files.ats_url_parser import parse_teamtailor_custom_domain_url

        _, lunar_expired_html = _read_fixture("df512e48")
        _, active_tt_html = _read_fixture("bb5a2c67")
        goto_expired = "https://www.google.com/goto?url=CAES_LUNAR_EXPIRED"
        lunar_url = "https://jobs.lunar.app/jobs/8614059-backend-engineer"
        goto_active = "https://www.google.com/goto?url=CAES_ACTIVE_CUSTOM"
        custom_active_url = "https://careers.smartestenergy-custom.com/jobs/8564842-quantitative-portfolio-manager"
        monkeypatch.setattr("src.project_files.ats_url_parser.is_safe_public_https_url", lambda u, resolve_dns=True: u.startswith("https://") and "169.254" not in u and "127.0.0.1" not in u)

        # Real custom domain Lunar HTML verifies as Teamtailor custom domain
        parsed_lunar = parse_teamtailor_custom_domain_url(lunar_url, html_text=lunar_expired_html, final_url=lunar_url)
        assert parsed_lunar is not None
        assert parsed_lunar.ats == "teamtailor"
        assert parsed_lunar.company_slug == "lunar"
        assert parsed_lunar.job_id == "8614059"

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u == goto_expired:
                return httpx.Response(302, headers={"Location": lunar_url}, request=request)
            if u == lunar_url:
                return httpx.Response(200, text=lunar_expired_html, request=request)
            if u == goto_active:
                return httpx.Response(302, headers={"Location": custom_active_url}, request=request)
            if u == custom_active_url:
                return httpx.Response(200, text=active_tt_html, request=request)
            return httpx.Response(404, text="Not found", request=request)

        orch = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
            # Expired HTTP-200 Lunar custom-domain page ("This position is no longer active") is dropped cleanly
            expired_listing = await orch._enrich_ats_item(
                "teamtailor",
                {"link": goto_expired, "title": "Moonrise FCP Risk & Requirements Officer", "snippet": "Lunar"},
                "Risk Officer",
                client,
            )
            assert expired_listing is None

            # Active custom-domain Teamtailor posting via Google /goto unwraps and extracts cleanly
            active_listing = await orch._enrich_ats_item(
                "teamtailor",
                {"link": goto_active, "title": "Quantitative Portfolio Manager", "snippet": "SmartestEnergy"},
                "Quantitative Portfolio Manager",
                client,
            )
        assert active_listing is not None
        assert active_listing.provider == "teamtailor"
        assert active_listing.company == "SmartestEnergy"
        assert active_listing.work_model == "hybrid"
        assert active_listing.company_logo_url and "logotype-v3" in active_listing.company_logo_url

    @pytest.mark.anyio
    async def test_google_goto_to_non_teamtailor_or_ssrf_target_rejected(self, monkeypatch):
        goto_ssrf = "https://www.google.com/goto?url=SSRF"
        goto_non_tt = "https://www.google.com/goto?url=NON_TT"

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u == goto_ssrf:
                return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data/"}, request=request)
            if u == goto_non_tt:
                return httpx.Response(302, headers={"Location": "https://careers.randomcorp.com/jobs/123"}, request=request)
            if u == "https://careers.randomcorp.com/jobs/123":
                return httpx.Response(200, text="<html><body><h1>Engineer</h1><p>No teamtailor here</p></body></html>", request=request)
            return httpx.Response(404, text="Not found", request=request)

        orch = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
            res_ssrf = await orch._enrich_ats_item("teamtailor", {"link": goto_ssrf, "title": "X", "snippet": ""}, "eng", client)
            res_non_tt = await orch._enrich_ats_item("teamtailor", {"link": goto_non_tt, "title": "X", "snippet": ""}, "eng", client)
        assert res_ssrf is None
        assert res_non_tt is None

    @pytest.mark.anyio
    async def test_non_teamtailor_page_and_expired_410_rejected_while_500_degrades(self):
        _, html_410 = _read_fixture("f6a01abc")
        _, html_integ = _read_fixture("7fc22ed2")
        _, html_support = _read_fixture("0bbe167e")
        _, html_people = _read_fixture("f0020ea3")

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "726882" in u:
                return httpx.Response(410, text=html_410, request=request)
            if "404job" in u:
                return httpx.Response(404, text="<html><body>Page not found</body></html>", request=request)
            if "500job" in u:
                return httpx.Response(500, text="Internal Server Error", request=request)
            if "integ" in u:
                return httpx.Response(200, text=html_integ, request=request)
            if "support" in u:
                return httpx.Response(200, text=html_support, request=request)
            if "people" in u:
                return httpx.Response(200, text=html_people, request=request)
            return httpx.Response(404, text="Not found", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            j410, r410 = await enrich_ats_page_result(
                "https://cc-jobs-jobsity.na.teamtailor.com/jobs/726882-senior-react-developer",
                "teamtailor",
                "Senior React",
                "expired job",
                "react",
                client,
            )
            assert j410 is None
            assert r410.outcome == ExtractionOutcome.NOT_FOUND

            j404, r404 = await enrich_ats_page_result(
                "https://acme.teamtailor.com/jobs/404job-gone",
                "teamtailor",
                "Python Dev",
                "gone",
                "python",
                client,
            )
            assert j404 is None
            assert r404.outcome == ExtractionOutcome.NOT_FOUND

            for bad_url, html_label in (
                ("https://www.teamtailor.com/pt/integrations/?x=integ", "integ"),
                ("https://support.teamtailor.com/sv/articles/1558532?x=support", "support"),
                ("https://horse.teamtailor.com/pt-BR/people/3297430?x=people", "people"),
            ):
                j_bad, r_bad = await enrich_ats_page_result(bad_url, "teamtailor", html_label, "", "python", client)
                assert j_bad is None
                assert r_bad.outcome == ExtractionOutcome.NOT_FOUND

            # Retryable 500 still preserves snippet fallback + outcome
            j500, r500 = await enrich_ats_page_result(
                "https://acme.teamtailor.com/jobs/500job-backend",
                "teamtailor",
                "Backend Engineer - Acme",
                "Build APIs",
                "backend",
                client,
            )
            assert j500 is not None
            assert j500.data_source == "snippet"
            assert r500.outcome == ExtractionOutcome.RETRYABLE_ERROR


class TestTeamtailorStructuredRealFixtures:
    @pytest.mark.anyio
    async def test_qtech_spanish_dl_salary_work_model_and_logo(self):
        meta, html = _read_fixture("110bfa03")
        url = meta["url"]
        async with httpx.AsyncClient(transport=_fixture_transport({url: (200, html)})) as client:
            job, res = await enrich_ats_page_result(url, "teamtailor", "", "", "java developer", client)
        assert res.outcome == ExtractionOutcome.SUCCESS
        assert job is not None
        assert job.id == "teamtailor:qtech:8029561"
        assert job.company == "Q-Tech"
        assert job.department == "Backend"
        assert job.work_model == "hybrid"
        assert job.employment_type == "full_time"
        assert job.location and "Barcelona" in job.location
        assert job.salary is not None
        assert job.salary.minimum == 45000
        assert job.salary.maximum == 50000
        assert job.salary.currency == "EUR"
        assert job.salary.period == "year"
        assert job.company_logo_url and "logotype-v3" in job.company_logo_url
        assert job.description and "Already working at" not in job.description
        assert job.requirements

    @pytest.mark.anyio
    async def test_rooftop_na_schibsted_iqm_luminor_keypath_twinharbour_smartest_multiverse(self):
        specs = [
            ("41deef68", "rooftop.na", "724276"),
            ("9090494c", "schibsted", "8657817"),
            ("481151bd", "iqm", "8522248"),
            ("b08a7101", "luminorbank", "8656160"),
            ("0624475a", "keypatheducation", "8685870"),
            ("d22cffd5", "twinharbour", "8531346"),
            ("bb5a2c67", "smartestenergy", "8564842"),
            ("cfd24a93", "multiversecomputing", "8689068"),
        ]
        url_map = {}
        metas = {}
        for stem, _, _ in specs:
            meta, html = _read_fixture(stem)
            url_map[meta["url"]] = (200, html)
            metas[stem] = meta

        async with httpx.AsyncClient(transport=_fixture_transport(url_map)) as client:
            results = {}
            for stem, _, _ in specs:
                u = metas[stem]["url"]
                job, _ = await enrich_ats_page_result(u, "teamtailor", "", "", "engineer", client)
                results[stem] = job

        # rooftop.na (.na. + Spanish <dl> + requirements)
        j_roof = results["41deef68"]
        assert j_roof.id == "teamtailor:rooftop.na:724276"
        assert j_roof.employment_type == "full_time"
        assert j_roof.location and "Argentina" in j_roof.location
        assert j_roof.requirements

        # schibsted (/sv/jobs/ + Swedish <dl> + requirements)
        j_sch = results["9090494c"]
        assert j_sch.id == "teamtailor:schibsted:8657817"
        assert j_sch.department == "Schibsted"
        assert j_sch.work_model == "in_person"
        assert j_sch.employment_type == "full_time"
        assert j_sch.requirements

        # iqm (trailing euro + monthly prefix + curly apostrophe requirements)
        j_iqm = results["481151bd"]
        assert j_iqm.salary is not None
        assert j_iqm.salary.minimum == 5000
        assert j_iqm.salary.maximum == 5833
        assert j_iqm.salary.currency == "EUR"
        assert j_iqm.salary.period == "month"
        assert j_iqm.requirements

        # luminorbank (EU-scoped "work from anywhere in the EU..." != global remote, 1160 EUR/month)
        j_lum = results["b08a7101"]
        assert j_lum.salary is not None
        assert j_lum.salary.minimum == 1160
        assert j_lum.salary.currency == "EUR"
        assert j_lum.salary.period == "month"
        assert j_lum.eligibility is not None
        assert j_lum.eligibility.global_remote_explicit is not True
        assert j_lum.eligibility.nigeria_eligible is not True
        assert j_lum.requirements

        # keypatheducation ("residing in Malaysia" -> Malaysia captured + Australia in JSON-LD -> nigeria_eligible=False)
        j_key = results["0624475a"]
        assert j_key.work_model == "remote"
        assert j_key.eligibility is not None
        assert "Malaysia" in (j_key.eligibility.allowed_residence_countries or [])
        assert j_key.eligibility.nigeria_eligible is False

        # twinharbour (slugless URL + compact multi-location <= 80 chars + raw_location preserved)
        j_twin = results["d22cffd5"]
        assert j_twin.id == "teamtailor:twinharbour:8531346"
        assert j_twin.work_model == "hybrid"
        assert j_twin.location and len(j_twin.location) <= 80
        assert j_twin.raw_location

        # smartestenergy (NYC 3 days/week hybrid attendance -> nigeria_eligible=False + salary)
        j_smart = results["bb5a2c67"]
        assert j_smart.salary is not None
        assert j_smart.salary.minimum == 165000
        assert j_smart.eligibility is not None
        assert j_smart.eligibility.nigeria_eligible is False

        # multiversecomputing (work visa sponsorship available + compact 2-city location)
        j_multi = results["cfd24a93"]
        assert j_multi.work_model == "hybrid"
        assert j_multi.location and len(j_multi.location) <= 80
        assert j_multi.eligibility is not None
        assert j_multi.eligibility.visa_sponsorship_status == "available"


class TestSharedExtractorsAndPostRelevanceRegistration:
    def test_requirements_extraction_handles_curly_apostrophe_bold_atx_and_headers(self):
        md1 = "##### **What you’ll need**\n- Python 3.11\n- SQL\n\n##### **Benefits**\n- PTO"
        req1 = extract_requirements(md1)
        assert req1 and "Python 3.11" in req1 and "PTO" not in req1

        md2 = "## Required Experience\n- 5 years Go\n\n## Perks\n- Remote budget"
        req2 = extract_requirements(md2)
        assert req2 and "5 years Go" in req2 and "Remote budget" not in req2

        md3 = "#### **What Makes You a Great Fit:**\n- Strong communication\n#### **Why You Will Love Working Here:**\n- Bonus"
        req3 = extract_requirements(md3)
        assert req3 and "Strong communication" in req3 and "Bonus" not in req3

    def test_eligibility_eu_wfa_bulgaria_thailand_emea_and_work_auth_neutrality(self):
        el_eu = extract_eligibility(
            provider="teamtailor",
            work_model="hybrid",
            location="Baltics",
            description="Flexibility. Hybrid work, and the possibility to work from anywhere in the EU, Iceland, Switzerland, and the UK.",
            description_is_authentic=True,
        )
        assert el_eu is not None
        assert el_eu.global_remote_explicit is not True
        assert el_eu.nigeria_eligible is not True

        el_bg = extract_eligibility(
            provider="teamtailor",
            work_model="remote",
            location="Sofia",
            description="This remote role is open to candidates based in Bulgaria only.",
            description_is_authentic=True,
        )
        assert el_bg is not None
        assert el_bg.allowed_residence_countries == ["Bulgaria"]
        assert el_bg.nigeria_eligible is False

        el_th = extract_eligibility(
            provider="teamtailor",
            work_model="in_person",
            location="Bangkok, Thailand",
            description="Join our Bangkok engineering hub.",
            description_is_authentic=True,
        )
        assert el_th is not None
        assert el_th.physical_location_country == "Thailand"
        assert el_th.nigeria_eligible is False

        el_emea = extract_eligibility(
            provider="teamtailor",
            work_model="remote",
            location="EMEA",
            description="Remote in EMEA. Join our distributed team.",
            description_is_authentic=True,
        )
        assert el_emea is not None
        assert el_emea.nigeria_eligible is None

        el_auth_contractor = extract_eligibility(
            provider="teamtailor",
            work_model="remote",
            location="London, United Kingdom",
            description="Independent contractor arrangement available. Right to work in the United Kingdom required.",
            description_is_authentic=True,
        )
        assert el_auth_contractor is not None
        assert el_auth_contractor.nigeria_eligible is None

    def test_multilingual_work_model_tokens(self):
        assert resolve_work_model(workplace_type="Híbrido").value == "hybrid"
        assert resolve_work_model(workplace_type="Télétravail").value == "remote"
        assert resolve_work_model(workplace_type="På plats").value == "in_person"
        assert resolve_work_model(workplace_type="Distans").value == "remote"

    def test_european_salary_formats(self):
        s1 = parse_text_salary("45.000 € - 50.000 €/año", source="teamtailor_salary")
        assert s1 is not None and s1.minimum == 45000 and s1.maximum == 50000 and s1.currency == "EUR" and s1.period == "year"

        s2 = extract_salary("teamtailor", {}, description="- **Gross monthly salary range:** 5000 € - 5833 €.")
        assert s2 is not None and s2.minimum == 5000 and s2.maximum == 5833 and s2.currency == "EUR" and s2.period == "month"

        s3 = extract_salary("teamtailor", {}, description="- **Gross salary.** 1160 EUR/month, which is determined by experience.")
        assert s3 is not None and s3.minimum == 1160 and s3.maximum == 1160 and s3.currency == "EUR" and s3.period == "month"

    @pytest.mark.anyio
    async def test_irrelevant_teamtailor_jobs_are_not_registered_to_board_registry(self, tmp_path, monkeypatch):
        from src.project_files import cache_store as cs_mod
        from src.project_files import search_pipeline as sp_mod

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "reg.sqlite"))
        monkeypatch.setattr(sp_mod, "company_board_registry", reg)
        # Isolate url cache cleanly in tmp_path
        tmp_cache = cs_mod.CacheStore(db_path=str(tmp_path / "cache.sqlite"))
        monkeypatch.setattr(sp_mod, "cache_store", tmp_cache)
        monkeypatch.setattr("src.project_files.ats_page_enricher.cache_store", tmp_cache)

        _, html_good = _read_fixture("110bfa03")  # Q-Tech Java Developer
        html_irrel = html_good.replace("Java Developer", "Senior Associate Audit")
        serper_resp = {
            "organic": [
                {"link": "https://qtech.teamtailor.com/jobs/8029561-java-developer", "title": "Java Developer", "snippet": ""},
                {"link": "https://gravita.teamtailor.com/jobs/8550942-senior-associate-audit", "title": "Senior Associate Audit", "snippet": ""},
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "serper.dev" in u:
                return httpx.Response(200, json=serper_resp, request=request)
            if "qtech.teamtailor.com" in u:
                return httpx.Response(200, text=html_good, request=request)
            if "gravita.teamtailor.com" in u:
                return httpx.Response(200, text=html_irrel, request=request)
            return httpx.Response(404, text="", request=request)

        monkeypatch.setattr("src.project_files.search_pipeline.settings.serper_api_key", "test-key")
        monkeypatch.setattr("src.project_files.search_pipeline.settings.serper_mode", "live")
        orch = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            plat, jobs, _ = await orch._search_ats_serper(
                "teamtailor",
                "site:teamtailor.com java developer",
                SearchParams(job_title="Java Developer"),
                client,
            )
        assert plat == "teamtailor"
        assert len(jobs) == 1
        assert jobs[0].company == "Q-Tech"
        assert reg.get_board("teamtailor", "qtech") is not None
        assert reg.get_board("teamtailor", "qtech").company_logo_url is not None
        assert reg.get_board("teamtailor", "gravita") is None

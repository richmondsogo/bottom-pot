"""Tests for Step 41 Workable Quality Pipeline."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from src.project_files.ats_url_parser import parse_ats_url


WORKABLE_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "workable"


class TestWorkableUrlParsingAndCanonicalization:
    def test_parses_all_real_url_shapes_including_apply_suffix(self):
        cases = [
            ("https://apply.workable.com/arabicai/j/321EBFED35/apply/", "arabicai", "321EBFED35"),
            ("https://apply.workable.com/globaldevgroup/j/39B6DB6679/apply", "globaldevgroup", "39B6DB6679"),
            ("https://apply.workable.com/treq/j/D94DBAF102/", "treq", "D94DBAF102"),
            ("https://acme.workable.com/jobs/ABC123", "acme", "ABC123"),
            ("https://acme.workable.com/jobs/ABC123/apply/", "acme", "ABC123"),
            ("https://apply.workable.com/testtrick-testing/j/07A169962E/", "testtrick-testing", "07A169962E"),
        ]
        for url, exp_slug, exp_id in cases:
            parsed = parse_ats_url(url)
            assert parsed is not None, f"Failed to parse {url}"
            assert parsed.ats == "workable"
            assert parsed.company_slug == exp_slug
            assert parsed.job_id == exp_id

    def test_rejects_reserved_paths_synthetic_slugs_and_bare_apply_paths(self):
        invalid_urls = [
            "https://apply.workable.com/j/A8DB68FCC3",
            "https://apply.workable.com/acme/apply",
            "https://apply.workable.com/acme/apply/",
            "https://apply.workable.com/api/v1/accounts/treq",
            "https://apply.workable.com/assets/j/123456",
            "https://apply.workable.com/widget/j/123456",
            "https://www.workable.com/jobs/123456",
            "https://jobs.workable.com/jobs/123456",
            "https://apply.workable.com/test-company/j/123456",
            "https://apply.workable.com/fake-company/j/123456",
        ]
        for url in invalid_urls:
            assert parse_ats_url(url) is None, f"Should not parse {url}"

    def test_board_root_parser_valid_vs_invalid(self):
        from src.project_files.ats_url_parser import parse_workable_board_root_url

        assert parse_workable_board_root_url("https://apply.workable.com/verneek") == "verneek"
        assert parse_workable_board_root_url("https://apply.workable.com/verneek/") == "verneek"
        assert parse_workable_board_root_url("https://verneek.workable.com") == "verneek"
        assert parse_workable_board_root_url("https://verneek.workable.com/") == "verneek"
        assert parse_workable_board_root_url("https://apply.workable.com/verneek/j/3DBA754691") is None
        assert parse_workable_board_root_url("https://apply.workable.com/verneek/apply") is None
        assert parse_workable_board_root_url("https://apply.workable.com/assets") is None
        assert parse_workable_board_root_url("https://www.workable.com") is None
        assert parse_workable_board_root_url("https://apply.workable.com/test-company") is None

    def test_normalizer_canonicalizes_apply_subdomain_and_tracking_preserving_meaningful_params(self):
        from src.project_files.url_normalizer import (
            normalize_job_url,
            url_carries_job_identifier,
        )

        canon = "https://apply.workable.com/globaldevgroup/j/39B6DB6679"
        assert normalize_job_url("https://apply.workable.com/globaldevgroup/j/39B6DB6679/apply/", "workable") == canon
        assert normalize_job_url("http://GlobalDevGroup.workable.com/jobs/39B6DB6679/", "workable") == canon
        assert (
            normalize_job_url(
                "https://apply.workable.com/globaldevgroup/j/39B6DB6679/?utm_source=getro&gh_src=board#apply",
                "workable",
            )
            == canon
        )
        assert (
            normalize_job_url(
                "https://apply.workable.com/globaldevgroup/j/39B6DB6679?lang=en&utm_medium=social",
                "workable",
            )
            == "https://apply.workable.com/globaldevgroup/j/39B6DB6679?lang=en"
        )
        assert url_carries_job_identifier("https://apply.workable.com/globaldevgroup/j/39B6DB6679/apply", "workable") is True
        assert url_carries_job_identifier("https://apply.workable.com/globaldevgroup", "workable") is False
        assert url_carries_job_identifier("https://apply.workable.com/globaldevgroup/apply", "workable") is False

    def test_serper_inventory_64_urls_reconcile_to_60_unique_jobs_across_54_slugs(self):
        from src.project_files.url_normalizer import normalize_job_url

        urls = json.loads((WORKABLE_FIXTURE_DIR / "serper_urls_78.json").read_text(encoding="utf-8"))
        assert len(urls) == 64
        unique_jobs: set[tuple[str, str]] = set()
        canon_urls: set[str] = set()
        slugs: set[str] = set()
        for url in urls:
            parsed = parse_ats_url(url)
            assert parsed is not None, f"Unparsed genuine serper URL: {url}"
            assert parsed.ats == "workable"
            unique_jobs.add((parsed.company_slug.lower(), parsed.job_id.upper()))
            slugs.add(parsed.company_slug.lower())
            canon_urls.add(normalize_job_url(url, "workable"))
        assert len(unique_jobs) == 60
        assert len(canon_urls) == 60
        assert len(slugs) == 54

    @pytest.mark.anyio
    async def test_search_pipeline_registers_workable_board_root_before_dropping(self, tmp_path):
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.search_pipeline import SearchOrchestrator

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        orch = SearchOrchestrator()
        with patch("src.project_files.search_pipeline.company_board_registry", reg):
            async with httpx.AsyncClient() as client:
                out = await orch._enrich_ats_item(
                    "workable",
                    {"link": "https://apply.workable.com/verneek/", "title": "Verneek Jobs", "snippet": "..."},
                    "ml engineer",
                    client,
                )
        assert out is None
        board = reg.get_board("workable", "verneek")
        assert board is not None
        assert board.board_url == "https://apply.workable.com/verneek"


class TestWorkableSalaryAndExtraction:
    def test_structured_workable_salary_extracts_inr_jod_and_bounds(self):
        from src.project_files.salary_parser import extract_salary

        learnrush = json.loads((WORKABLE_FIXTURE_DIR / "job_learnrush_64801AA613.json").read_text(encoding="utf-8"))
        sal_in = extract_salary("workable", learnrush, location_hint="India")
        assert sal_in is not None
        assert sal_in.minimum == 800000
        assert sal_in.maximum == 1500000
        assert sal_in.currency == "INR"
        assert sal_in.period == "year"
        assert sal_in.source == "workable_structured"

        bm = json.loads((WORKABLE_FIXTURE_DIR / "job_99brightminds_63E0790AD5.json").read_text(encoding="utf-8"))
        sal_jo = extract_salary("workable", bm, location_hint="Amman, Jordan")
        assert sal_jo is not None
        assert sal_jo.minimum == 800
        assert sal_jo.maximum == 900
        assert sal_jo.currency == "JOD"
        assert sal_jo.period == "year"
        assert sal_jo.source == "workable_structured"

        sal_single_to = extract_salary(
            "workable",
            {"salary_from": None, "salary_to": 6000, "salary_currency_iso_code": "USD", "salary_frequency": "month"},
        )
        assert sal_single_to is not None
        assert sal_single_to.minimum is None
        assert sal_single_to.maximum == 6000
        assert sal_single_to.currency == "USD"
        assert sal_single_to.period == "month"

        assert extract_salary(
            "workable",
            {"salary_from": 0, "salary_to": 0, "salary_currency_iso_code": "USD", "salary_frequency": "year"},
        ) is None

    def test_text_salary_handles_inr_rupee_markdown_link_and_standalone_hourly_bullet(self):
        from src.project_files.salary_parser import extract_salary

        sal_inr = extract_salary("workable", {}, description="**Salary:** INR 800,000–1,500,000", location_hint="India (Remote)")
        assert sal_inr is not None
        assert sal_inr.currency == "INR"
        assert sal_inr.minimum == 800000
        assert sal_inr.maximum == 1500000
        assert sal_inr.period is None

        sal_rupee = extract_salary("workable", {}, description="Salary: ₹800,000 - ₹1,500,000 per year", location_hint="India")
        assert sal_rupee is not None
        assert sal_rupee.currency == "INR"
        assert sal_rupee.period == "year"

        sal_verneek = extract_salary(
            "workable",
            {},
            description="**Annual Salary Range**: $40K-$200K[](https://apply.workable.com/verneek/j/0532863EFD/apply/)",
            location_hint="New York, United States",
        )
        assert sal_verneek is not None
        assert sal_verneek.minimum == 40000
        assert sal_verneek.maximum == 200000
        assert sal_verneek.currency == "USD"
        assert sal_verneek.period == "year"
        assert "http" not in (sal_verneek.raw_text or "")
        assert "](" not in (sal_verneek.raw_text or "")

        sal_hr = extract_salary(
            "workable",
            {},
            description="## Description\n\nAustin, TX\n- In office\n- $30/hr\n\nPart-time (20+ hrs/week)",
            location_hint="Austin, United States",
        )
        assert sal_hr is not None
        assert sal_hr.minimum == 30
        assert sal_hr.maximum == 30
        assert sal_hr.currency == "USD"
        assert sal_hr.period == "hour"

        assert extract_salary("workable", {}, description="- $150/month wellness allowance") is None

    def test_job_extraction_service_extracts_workable_requirements_eligibility_and_logo(self):
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
        from src.project_files.models import ExtractionMethod

        raw = RawJobPosting(
            provider="workable",
            source_url="https://apply.workable.com/99brightminds/j/63E0790AD5",
            provider_job_id="63E0790AD5",
            company_slug="99brightminds",
            apply_url="https://apply.workable.com/99brightminds/j/63E0790AD5/apply",
            extraction_method=ExtractionMethod.ATS_API,
            raw_title="Backend Engineer-JAVA",
            raw_company="99BrightMinds",
            raw_location="Amman, Jordan",
            raw_workplace_type="remote",
            raw_employment_type="Full-time",
            raw_description="We are looking for a Backend Engineer with 3-5 years of experience in Java.",
            raw_requirements="- 3-5 years of experience in Backend Development.\n- Strong expertise in Java, Spring Boot.",
            description_is_authentic=True,
            raw_fields={
                "salary_from": 800,
                "salary_to": 900,
                "salary_currency_iso_code": "JOD",
                "salary_frequency": "year",
                "company_logo_url": "https://workablehr.s3.amazonaws.com/uploads/account/logo/745898/logo",
                "company_logo_source": "workable_account_logo",
                "company_logo_verified": True,
            },
        )
        canonical = JobExtractionService.extract(raw)
        assert canonical.salary is not None and canonical.salary.currency == "JOD"
        assert canonical.requirements is not None
        assert "Spring Boot" in canonical.requirements
        assert canonical.eligibility is not None
        assert canonical.eligibility.physical_location_country == "Jordan"
        assert canonical.company_logo_url == "https://workablehr.s3.amazonaws.com/uploads/account/logo/745898/logo"
        assert canonical.company_logo_source == "workable_account_logo"
        assert canonical.company_logo_verified is True


class TestWorkableClientAndLogos:
    def test_logo_extractor_accepts_account_logo_and_rejects_og_banner_and_facebook_preview(self):
        from src.project_files.logo_extractor import extract_company_logo_for_provider

        res_ok = extract_company_logo_for_provider(
            "workable",
            workable_account_logo="https://workablehr.s3.amazonaws.com/uploads/account/logo/456770/logo",
            company_name="Verneek",
        )
        assert res_ok.verified is True
        assert res_ok.url == "https://workablehr.s3.amazonaws.com/uploads/account/logo/456770/logo"
        assert res_ok.source == "workable_account_logo"

        res_og = extract_company_logo_for_provider(
            "workable",
            workable_account_logo="https://workablehr.s3.amazonaws.com/uploads/account/open_graph_logo/456770/social?1764034086000",
            company_name="Verneek",
        )
        assert res_og.verified is False
        assert res_og.url is None

        res_fb = extract_company_logo_for_provider(
            "workable",
            workable_account_logo="https://www.workable.com/assets/facebook-preview.png",
            company_name="Learnrush",
        )
        assert res_fb.verified is False
        assert res_fb.url is None

        assert extract_company_logo_for_provider("workable", workable_account_logo=None, company_name="Learnrush").verified is False

    def test_workable_payload_to_raw_maps_all_structured_fields_and_avoids_chrome(self):
        from src.project_files.ats_api_client import workable_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        bm = json.loads((WORKABLE_FIXTURE_DIR / "job_99brightminds_63E0790AD5.json").read_text(encoding="utf-8"))
        raw = workable_payload_to_raw(
            bm,
            company_slug="99brightminds",
            source_url="https://apply.workable.com/99brightminds/j/63E0790AD5/apply/",
            default_company_name="99BrightMinds",
            company_logo_url="https://workablehr.s3.amazonaws.com/uploads/account/logo/745898/logo",
            company_logo_source="workable_account_logo",
            company_logo_verified=True,
        )
        assert raw is not None
        assert raw.source_url == "https://apply.workable.com/99brightminds/j/63E0790AD5"
        assert raw.apply_url == "https://apply.workable.com/99brightminds/j/63E0790AD5/apply"
        assert raw.provider_job_id == "63E0790AD5"
        assert raw.raw_company == "99BrightMinds"
        assert raw.raw_location == "Amman, Jordan"
        assert raw.raw_workplace_type == "remote"
        assert raw.raw_employment_type == "Full-time"
        assert raw.raw_date == "2026-10-25T00:00:00.000Z"
        assert raw.raw_requirements is not None and "Spring Boot" in raw.raw_requirements
        assert "Powered by" not in (raw.raw_description or "")
        assert "Apply at" not in (raw.raw_description or "")
        # Should not double-prefix "### Requirements" with a second "## Requirements"
        assert (raw.raw_description or "").lower().count("### requirements") <= 1

        canonical = JobExtractionService.extract(raw)
        assert canonical.salary is not None and canonical.salary.currency == "JOD"
        assert canonical.salary.minimum == 800 and canonical.salary.maximum == 900
        assert canonical.salary.period == "year"
        assert canonical.work_model == "remote"
        assert canonical.employment_type == "full_time"
        assert canonical.requirements is not None
        assert canonical.eligibility is not None and canonical.eligibility.physical_location_country == "Jordan"

        # Multi-location visible vs hidden handling + hybrid + department list
        multi_payload = {
            **bm,
            "workplace": "hybrid",
            "remote": False,
            "department": ["Engineering", "Platform"],
            "location": {"city": "London", "country": "United Kingdom", "countryCode": "GB", "region": "England"},
            "locations": [
                {"city": "London", "country": "United Kingdom", "countryCode": "GB", "region": "England", "hidden": False},
                {"city": "Berlin", "country": "Germany", "countryCode": "DE", "region": "Berlin", "hidden": False},
                {"city": "Secret", "country": "Narnia", "countryCode": "XX", "region": None, "hidden": True},
            ],
        }
        raw_multi = workable_payload_to_raw(multi_payload, company_slug="acme")
        assert raw_multi is not None
        assert raw_multi.raw_location == "London, United Kingdom | Berlin, Germany"
        assert "Secret" not in (raw_multi.raw_location or "")
        assert raw_multi.raw_workplace_type == "hybrid"
        assert raw_multi.raw_department == "Engineering, Platform"

    @pytest.mark.anyio
    async def test_workable_client_prefers_api_v2_and_enriches_identity_and_handles_404(self, tmp_path):
        from src.project_files.ats_api_client import WorkableClient, enrich_workable_board_identity
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.extraction_outcome import ExtractionOutcome

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        job_json = (WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8")
        acct_json = (WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8")
        learnrush_acct = (WORKABLE_FIXTURE_DIR / "account_learnrush.json").read_text(encoding="utf-8")
        seen_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            seen_urls.append(u)
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                return httpx.Response(200, json=json.loads(job_json))
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=json.loads(acct_json))
            if "/api/v1/accounts/learnrush" in u:
                return httpx.Response(200, json=json.loads(learnrush_acct))
            if "/api/v2/accounts/treq/jobs/D94DBAF102" in u:
                return httpx.Response(404, json={"error": "Not found"})
            return httpx.Response(500)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg):
                parsed = parse_ats_url("https://apply.workable.com/verneek/j/3DBA754691/")
                listing, res = await WorkableClient().fetch_result(parsed, client)
                assert res.outcome == ExtractionOutcome.SUCCESS
                assert listing is not None
                assert listing.data_source == "api"
                assert listing.company == "Verneek"
                assert listing.work_model == "in_person"
                assert listing.salary is not None
                assert listing.salary.minimum == 40000 and listing.salary.maximum == 200000
                assert listing.salary.currency == "USD" and listing.salary.period == "year"
                assert listing.requirements is not None and "PyTorch" in listing.requirements
                assert listing.apply_url == "https://apply.workable.com/verneek/j/3DBA754691/apply"
                assert listing.source_url == "https://apply.workable.com/verneek/j/3DBA754691"
                assert listing.company_logo_verified is True
                assert listing.company_logo_url == "https://workablehr.s3.amazonaws.com/uploads/account/logo/456770/logo"

                # 404 returns NOT_FOUND immediately without hitting .md fallback
                parsed_404 = parse_ats_url("https://apply.workable.com/treq/j/D94DBAF102")
                listing_404, res_404 = await WorkableClient().fetch_result(parsed_404, client)
                assert listing_404 is None
                assert res_404.outcome == ExtractionOutcome.NOT_FOUND
                assert not any(u.endswith(".md") for u in seen_urls)

                # Learnrush negative-cached cleanly (logo=null, second call hits cache)
                n1, l1 = await enrich_workable_board_identity("learnrush", client, registry=reg)
                assert n1 == "Learnrush" and l1.verified is False and l1.url is None
                acct_hits_before = sum(1 for u in seen_urls if "/api/v1/accounts/learnrush" in u)
                n2, l2 = await enrich_workable_board_identity("learnrush", client, registry=reg)
                acct_hits_after = sum(1 for u in seen_urls if "/api/v1/accounts/learnrush" in u)
                assert acct_hits_before == 1 and acct_hits_after == 1
                assert n2 == "Learnrush" and l2.verified is False

    @pytest.mark.anyio
    async def test_workable_markdown_fallback_strips_chrome_and_preserves_body(self):
        from src.project_files.ats_api_client import WorkableClient

        md_text = (WORKABLE_FIXTURE_DIR / "job_D94DBAF102.md").read_text(encoding="utf-8")
        parsed = parse_ats_url("https://apply.workable.com/treq/j/D94DBAF102")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=md_text))
        ) as client:
            job = await WorkableClient().fetch(parsed, client)
        assert job is not None
        assert job.company == "TreQ"
        assert job.apply_url == "https://apply.workable.com/treq/j/D94DBAF102/apply"
        assert job.source_url == "https://apply.workable.com/treq/j/D94DBAF102"
        assert "Powered by" not in (job.description or "")
        assert "[Apply at TreQ]" not in (job.description or "")
        assert "**Workplace:**" not in (job.description or "")
        assert "35 days annual leave" in (job.description or "")
        assert job.requirements is not None
        assert job.eligibility is not None and job.eligibility.physical_location_country == "United Kingdom"


class TestWorkableBoardMonitoringAndDirectRouter:
    def test_workable_promoted_to_monitorable_and_adapter_registered(self):
        from src.project_files.board_adapters import BOARD_ADAPTERS, WorkableBoardAdapter
        from src.project_files.company_board_registry import (
            MONITORABLE_PROVIDERS,
            PROVISIONAL_PROVIDERS,
        )

        assert "workable" in MONITORABLE_PROVIDERS
        assert "workable" not in PROVISIONAL_PROVIDERS
        assert "workable" in BOARD_ADAPTERS
        assert isinstance(BOARD_ADAPTERS["workable"], WorkableBoardAdapter)

    @pytest.mark.anyio
    async def test_workable_board_monitor_lifecycle_rotating_refresh_and_safety(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "monitor.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None
        assert board.monitoring_capability == "supported"

        job_v1 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        job_v2 = {
            **job_v1,
            "shortcode": "0DB6C4CE39",
            "title": "Motion Marketing Designer (Remote)",
            "workplace": "remote",
            "remote": True,
        }
        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_two = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] in {"3DBA754691", "0DB6C4CE39"}],
        }

        mode = {"phase": "initial", "v2_calls": []}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                if mode["phase"] == "transient_500":
                    return httpx.Response(500)
                if mode["phase"] == "removed_second":
                    return httpx.Response(
                        200,
                        json={
                            **widget_two,
                            "jobs": [j for j in widget_two["jobs"] if j["shortcode"] == "3DBA754691"],
                        },
                    )
                return httpx.Response(200, json=widget_two)
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                mode["v2_calls"].append("3DBA754691")
                if mode["phase"] == "detail_transient_503":
                    return httpx.Response(503)
                if mode["phase"] == "rotated_salary":
                    return httpx.Response(
                        200,
                        json={
                            **job_v1,
                            "salary_from": 160000,
                            "salary_to": 210000,
                            "salary_currency_iso_code": "USD",
                            "salary_frequency": "year",
                        },
                    )
                return httpx.Response(200, json=job_v1)
            if "/api/v2/accounts/verneek/jobs/0DB6C4CE39" in u:
                mode["v2_calls"].append("0DB6C4CE39")
                if mode["phase"] == "detail_transient_503":
                    return httpx.Response(503)
                return httpx.Response(200, json=job_v2)
            return httpx.Response(404)

        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=3600, max_revalidations_per_poll=1)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ):
                # 1. Initial check hydrates both jobs + company logo
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True and res1.not_modified is False
                assert len(res1.listings) == 2
                assert set(mode["v2_calls"]) == {"3DBA754691", "0DB6C4CE39"}
                j_ml = reg.get_monitored_job("workable:verneek:3DBA754691")
                assert j_ml is not None and j_ml.company_logo_verified is True and j_ml.requirements is not None

                # 2. Immediate repeat poll -> unchanged (not_modified=True, 0 new v2 calls)
                mode["v2_calls"].clear()
                b2 = reg.get_board("workable", "verneek")
                res2 = await monitor.check_single_board(b2, client, cache_store=cache)
                assert res2.success is True and res2.not_modified is True
                assert mode["v2_calls"] == []

                # 3. Age ONLY 3DBA754691 past TTL -> rotating refresh picks 1 stale job and updates structured salary
                import time

                with reg._get_connection() as conn:
                    conn.execute(
                        "UPDATE monitored_jobs SET last_checked_at = ? WHERE job_id = ?",
                        (time.time() - 7200, "workable:verneek:3DBA754691"),
                    )
                    conn.commit()
                mode["phase"] = "rotated_salary"
                res3 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res3.success is True and res3.not_modified is False
                assert mode["v2_calls"] == ["3DBA754691"]
                j_ml_updated = reg.get_monitored_job("workable:verneek:3DBA754691")
                assert j_ml_updated is not None and j_ml_updated.salary is not None
                assert j_ml_updated.salary.minimum == 160000

                # 4. Transient widget 500 does NOT close active monitored jobs
                mode["phase"] = "transient_500"
                res_err = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_err.success is False
                with reg._get_connection() as conn:
                    active_cnt = conn.execute(
                        "SELECT COUNT(*) FROM monitored_jobs WHERE board_id = ? AND status = 'active'",
                        (board.id,),
                    ).fetchone()[0]
                assert active_cnt == 2

                # 5. Valid 200 widget missing 0DB6C4CE39 closes only the removed job
                mode["phase"] = "removed_second"
                res_rem = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_rem.success is True
                assert len(res_rem.listings) == 1
                with reg._get_connection() as conn:
                    rows = dict(
                        conn.execute(
                            "SELECT job_id, status FROM monitored_jobs WHERE board_id = ?",
                            (board.id,),
                        ).fetchall()
                    )
                assert rows["workable:verneek:3DBA754691"] == "active"
                assert rows["workable:verneek:0DB6C4CE39"] == "closed"

    def test_workable_widget_diff_covers_all_meaningful_fields_and_ignores_missing(self):
        from src.project_files.ats_api_client import workable_payload_to_raw
        from src.project_files.board_adapters import _workable_widget_differs_from_listing
        from src.project_files.canonical_job_adapter import CanonicalJobAdapter
        from src.project_files.job_extraction_service import JobExtractionService

        job_v2 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_verneek = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_item = next(j for j in widget_verneek["jobs"] if j["shortcode"] == "3DBA754691")

        raw = workable_payload_to_raw(job_v2, company_slug="verneek", default_company_name="Verneek")
        assert raw is not None
        existing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw))

        # Unchanged widget metadata must not differ
        assert _workable_widget_differs_from_listing(widget_item, existing) is False

        # Missing or blank optional widget fields must not be treated as removal
        assert _workable_widget_differs_from_listing(
            {
                "shortcode": "3DBA754691",
                "title": widget_item["title"],
                "country": "United States",
                "employment_type": "",
                "department": None,
            },
            existing,
        ) is False

        # Hybrid api/v2 job with widget telecommuting=False (real Mercari fixture) must not differ
        mercari_v2 = json.loads((WORKABLE_FIXTURE_DIR / "job_mercari_4D1D2BE55C.json").read_text(encoding="utf-8"))
        mercari_widget = json.loads((WORKABLE_FIXTURE_DIR / "widget_mercari.json").read_text(encoding="utf-8"))
        mercari_w_item = next(j for j in mercari_widget["jobs"] if j["shortcode"] == "4D1D2BE55C")
        mercari_raw = workable_payload_to_raw(mercari_v2, company_slug="mercari", default_company_name="Mercari")
        assert mercari_raw is not None
        mercari_existing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(mercari_raw))
        assert mercari_existing.work_model == "hybrid"
        assert _workable_widget_differs_from_listing(mercari_w_item, mercari_existing) is False

        # Changing each meaningful field triggers diff
        assert _workable_widget_differs_from_listing({**widget_item, "title": "Staff ML Engineer"}, existing) is True
        assert _workable_widget_differs_from_listing({**widget_item, "published_on": "2026-11-10"}, existing) is True
        assert _workable_widget_differs_from_listing({**widget_item, "employment_type": "Contract"}, existing) is True
        assert _workable_widget_differs_from_listing({**widget_item, "department": "Platform"}, existing) is True
        assert _workable_widget_differs_from_listing({**widget_item, "telecommuting": True}, existing) is True
        assert _workable_widget_differs_from_listing(
            {
                **widget_item,
                "city": "San Francisco",
                "locations": [
                    {
                        "country": "United States",
                        "countryCode": "US",
                        "city": "San Francisco",
                        "region": "New York",
                        "hidden": False,
                    }
                ],
            },
            existing,
        ) is True
        assert _workable_widget_differs_from_listing(
            {
                **widget_item,
                "country": "Canada",
                "city": "Toronto",
                "state": "Ontario",
                "locations": [
                    {
                        "country": "Canada",
                        "countryCode": "CA",
                        "city": "Toronto",
                        "region": "Ontario",
                        "hidden": False,
                    }
                ],
            },
            existing,
        ) is True
        assert _workable_widget_differs_from_listing(
            {
                **widget_item,
                "locations": [
                    *widget_item["locations"],
                    {
                        "country": "United Kingdom",
                        "countryCode": "GB",
                        "city": "London",
                        "region": "England",
                        "hidden": False,
                    },
                ],
            },
            existing,
        ) is True

        # State-only change when city is absent
        state_raw = workable_payload_to_raw(
            {
                **job_v2,
                "location": {"city": "", "region": "England", "country": "United Kingdom", "countryCode": "GB"},
                "locations": [{"city": "", "region": "England", "country": "United Kingdom", "countryCode": "GB", "hidden": False}],
            },
            company_slug="verneek",
        )
        assert state_raw is not None
        state_existing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(state_raw))
        assert _workable_widget_differs_from_listing(
            {
                **widget_item,
                "city": "",
                "state": "Scotland",
                "country": "United Kingdom",
                "locations": [{"city": "", "region": "Scotland", "country": "United Kingdom", "hidden": False}],
            },
            state_existing,
        ) is True

    @pytest.mark.anyio
    async def test_workable_monitor_immediate_rehydration_on_every_widget_field_change(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "field_changes.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        base_v2 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        base_w = next(j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691")

        # Start with Portland, Oregon, US so even a state-only change (Oregon -> Maine) with identical city/country is exercised
        cur_w = {
            **base_w,
            "city": "Portland",
            "state": "Oregon",
            "country": "United States",
            "locations": [
                {
                    "country": "United States",
                    "countryCode": "US",
                    "city": "Portland",
                    "region": "Oregon",
                    "hidden": False,
                }
            ],
        }
        cur_v2 = {
            **base_v2,
            "location": {"city": "Portland", "region": "Oregon", "country": "United States", "countryCode": "US"},
            "locations": [
                {
                    "city": "Portland",
                    "region": "Oregon",
                    "country": "United States",
                    "countryCode": "US",
                    "hidden": False,
                }
            ],
        }
        state = {"widget_job": cur_w, "v2_job": cur_v2, "v2_calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json={**widget_full, "jobs": [state["widget_job"]]})
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                state["v2_calls"] += 1
                return httpx.Response(200, json=state["v2_job"])
            return httpx.Response(404)

        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=1)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ):
                # Poll 1: initial hydration
                res0 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res0.success is True and state["v2_calls"] == 1

                # Poll 2: unchanged -> 0 v2 calls
                state["v2_calls"] = 0
                res_unchanged = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_unchanged.not_modified is True and state["v2_calls"] == 0

                mutations = [
                    (
                        "employment_type",
                        {**cur_w, "employment_type": "Part-time"},
                        {**cur_v2, "type": "part"},
                        lambda j: j.employment_type == "part_time",
                    ),
                    (
                        "department",
                        {**cur_w, "employment_type": "Part-time", "department": "Applied Research"},
                        {**cur_v2, "type": "part", "department": ["Applied Research"]},
                        lambda j: j.department == "Applied Research",
                    ),
                    (
                        "telecommuting_true",
                        {**cur_w, "employment_type": "Part-time", "department": "Applied Research", "telecommuting": True},
                        {**cur_v2, "type": "part", "department": ["Applied Research"], "workplace": "remote", "remote": True},
                        lambda j: j.work_model == "remote",
                    ),
                    (
                        "telecommuting_false",
                        {**cur_w, "employment_type": "Part-time", "department": "Applied Research", "telecommuting": False},
                        {**cur_v2, "type": "part", "department": ["Applied Research"], "workplace": "on_site", "remote": False},
                        lambda j: j.work_model == "in_person",
                    ),
                    (
                        "state_only",
                        {
                            **cur_w,
                            "employment_type": "Part-time",
                            "department": "Applied Research",
                            "telecommuting": False,
                            "state": "Maine",
                            "locations": [
                                {"country": "United States", "countryCode": "US", "city": "Portland", "region": "Maine", "hidden": False}
                            ],
                        },
                        {
                            **cur_v2,
                            "type": "part",
                            "department": ["Applied Research"],
                            "workplace": "on_site",
                            "remote": False,
                            "location": {"city": "Portland", "region": "Maine", "country": "United States", "countryCode": "US"},
                            "locations": [
                                {"city": "Portland", "region": "Maine", "country": "United States", "countryCode": "US", "hidden": False}
                            ],
                        },
                        lambda j: j.eligibility is not None and j.eligibility.physical_location_country == "United States",
                    ),
                    (
                        "city_and_country",
                        {
                            **cur_w,
                            "employment_type": "Part-time",
                            "department": "Applied Research",
                            "telecommuting": False,
                            "city": "Toronto",
                            "state": "Ontario",
                            "country": "Canada",
                            "locations": [
                                {"country": "Canada", "countryCode": "CA", "city": "Toronto", "region": "Ontario", "hidden": False}
                            ],
                        },
                        {
                            **cur_v2,
                            "type": "part",
                            "department": ["Applied Research"],
                            "workplace": "on_site",
                            "remote": False,
                            "location": {"city": "Toronto", "region": "Ontario", "country": "Canada", "countryCode": "CA"},
                            "locations": [
                                {"city": "Toronto", "region": "Ontario", "country": "Canada", "countryCode": "CA", "hidden": False}
                            ],
                        },
                        lambda j: j.location == "Toronto, Canada",
                    ),
                    (
                        "multi_locations",
                        {
                            **cur_w,
                            "employment_type": "Part-time",
                            "department": "Applied Research",
                            "telecommuting": False,
                            "city": "Toronto",
                            "state": "Ontario",
                            "country": "Canada",
                            "locations": [
                                {"country": "Canada", "countryCode": "CA", "city": "Toronto", "region": "Ontario", "hidden": False},
                                {"country": "United Kingdom", "countryCode": "GB", "city": "London", "region": "England", "hidden": False},
                            ],
                        },
                        {
                            **cur_v2,
                            "type": "part",
                            "department": ["Applied Research"],
                            "workplace": "on_site",
                            "remote": False,
                            "location": {"city": "Toronto", "region": "Ontario", "country": "Canada", "countryCode": "CA"},
                            "locations": [
                                {"city": "Toronto", "region": "Ontario", "country": "Canada", "countryCode": "CA", "hidden": False},
                                {"city": "London", "region": "England", "country": "United Kingdom", "countryCode": "GB", "hidden": False},
                            ],
                        },
                        lambda j: j.location == "Toronto, Canada | London, United Kingdom"
                        and j.raw_location == "Toronto, Canada | London, United Kingdom",
                    ),
                ]

                for label, w_next, v2_next, assertion in mutations:
                    state["widget_job"] = w_next
                    state["v2_job"] = v2_next
                    state["v2_calls"] = 0
                    res_m = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                    assert res_m.success is True and res_m.not_modified is False, f"Failed not_modified on {label}"
                    assert state["v2_calls"] == 1, f"Expected immediate api/v2 call on {label}"
                    stored = reg.get_monitored_job("workable:verneek:3DBA754691")
                    assert stored is not None and assertion(stored), f"Assertion failed after {label}: {stored}"

                # Immediate repeat after final mutation -> 0 v2 calls
                state["v2_calls"] = 0
                res_after = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_after.not_modified is True and state["v2_calls"] == 0

    @pytest.mark.anyio
    async def test_workable_widget_fallback_on_503_and_invalid_200_retries_before_6h_and_survives_restart(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "retry_503.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_v2 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        w_ml = next(j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691")
        w_fe = next(j for j in widget_full["jobs"] if j["shortcode"] == "A61D4585B3")
        job_fe_v2 = {
            **job_v2,
            "shortcode": "A61D4585B3",
            "title": "Frontend Engineer",
            "department": ["Front-end"],
        }

        mode = {"ml": "503", "fe": "invalid_200", "v2_calls": []}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json={**widget_full, "jobs": [w_ml, w_fe]})
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                mode["v2_calls"].append("3DBA754691")
                if mode["ml"] == "503":
                    return httpx.Response(503)
                return httpx.Response(200, json=job_v2)
            if "/api/v2/accounts/verneek/jobs/A61D4585B3" in u:
                mode["v2_calls"].append("A61D4585B3")
                if mode["fe"] == "invalid_200":
                    return httpx.Response(200, json={"shortcode": "A61D4585B3", "title": "Frontend Engineer", "description": ""})
                return httpx.Response(200, json=job_fe_v2)
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                # Poll 1: 503 for 3DBA754691, incomplete 200 for A61D4585B3 -> widget fallback, NOT marked detail-refreshed
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True and res1.not_modified is False
                assert len(res1.listings) == 2
                assert res1.refreshed_job_ids == set()

                stored_ml = reg.get_monitored_job("workable:verneek:3DBA754691")
                assert stored_ml is not None
                assert stored_ml.title == "Machine Learning Engineer"
                assert stored_ml.description is None
                assert stored_ml.company_logo_verified is True

                states1 = reg.get_monitored_job_detail_states(board.id)
                assert states1["workable:verneek:3DBA754691"].detail_status == "transient_error"
                assert states1["workable:verneek:3DBA754691"].detail_last_hydrated_at is None
                assert states1["workable:verneek:3DBA754691"].detail_retry_count == 1
                assert states1["workable:verneek:A61D4585B3"].detail_status == "invalid_detail"
                assert states1["workable:verneek:A61D4585B3"].detail_last_hydrated_at is None

                with reg._get_connection() as conn:
                    checked_map = dict(
                        conn.execute(
                            "SELECT job_id, last_checked_at FROM monitored_jobs WHERE board_id = ?",
                            (board.id,),
                        ).fetchall()
                    )
                assert checked_map["workable:verneek:3DBA754691"] == 0.0
                assert checked_map["workable:verneek:A61D4585B3"] == 0.0

                # Immediate poll 30s later (inside backoff): must NOT hammer api/v2
                clock["now"] += 30.0
                mode["v2_calls"].clear()
                res_backoff = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_backoff.success is True and res_backoff.not_modified is True
                assert mode["v2_calls"] == []

            # Simulate application restart 30 minutes later (still << 6 hours TTL!)
            clock["now"] += 1800.0
            mode["ml"] = "200"
            mode["fe"] = "200"
            mode["v2_calls"].clear()

            reg_restarted = CompanyBoardRegistry(db_path=db_path)
            cache_restarted = CacheStore(db_path=db_path)
            adapter_restarted = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=5)
            monitor_restarted = BoardMonitor(registry=reg_restarted, cache=cache_restarted)

            with patch("src.project_files.ats_api_client.company_board_registry", reg_restarted), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter_restarted}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                res2 = await monitor_restarted.check_single_board(
                    reg_restarted.get_board("workable", "verneek"),
                    client,
                    cache_store=cache_restarted,
                )
                assert res2.success is True and res2.not_modified is False
                assert set(mode["v2_calls"]) == {"3DBA754691", "A61D4585B3"}
                assert res2.refreshed_job_ids == {
                    "workable:verneek:3DBA754691",
                    "workable:verneek:A61D4585B3",
                }
                healed_ml = reg_restarted.get_monitored_job("workable:verneek:3DBA754691")
                assert healed_ml is not None
                assert healed_ml.description_ok is True
                assert healed_ml.requirements is not None
                assert healed_ml.salary is not None

                states2 = reg_restarted.get_monitored_job_detail_states(board.id)
                assert states2["workable:verneek:3DBA754691"].detail_status == "hydrated"
                assert states2["workable:verneek:3DBA754691"].detail_retry_count == 0
                assert states2["workable:verneek:3DBA754691"].detail_last_hydrated_at == clock["now"]

    @pytest.mark.anyio
    async def test_workable_detail_404_does_not_close_job_present_in_widget_and_closes_when_removed(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "detail_404.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_v1 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        job_v2 = {**job_v1, "shortcode": "0DB6C4CE39", "title": "Motion Marketing Designer (Remote)", "workplace": "remote", "remote": True}
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_two = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] in {"3DBA754691", "0DB6C4CE39"}],
        }
        widget_one = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691"],
        }

        mode = {"widget": "two", "v2_0DB": "200", "v2_calls": []}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json=widget_two if mode["widget"] == "two" else widget_one)
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                mode["v2_calls"].append("3DBA754691")
                return httpx.Response(200, json=job_v1)
            if "/api/v2/accounts/verneek/jobs/0DB6C4CE39" in u:
                mode["v2_calls"].append("0DB6C4CE39")
                if mode["v2_0DB"] == "404":
                    return httpx.Response(404, json={"error": "Not found"})
                return httpx.Response(200, json=job_v2)
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=3600, max_revalidations_per_poll=1)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                # 1. Initial hydration of both jobs
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True and len(res1.listings) == 2

                # 2. Age 0DB6C4CE39 past TTL (3DBA754691 remains fresh at +1800s < 3600s); api/v2 now returns 404 while widget still lists 0DB6C4CE39
                clock["now"] += 1800.0
                with reg._get_connection() as conn:
                    conn.execute(
                        "UPDATE monitored_jobs SET last_checked_at = ? WHERE job_id = ?",
                        (clock["now"] - 7200.0, "workable:verneek:0DB6C4CE39"),
                    )
                    conn.commit()
                mode["v2_0DB"] = "404"
                mode["v2_calls"].clear()

                res2 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res2.success is True
                assert mode["v2_calls"] == ["0DB6C4CE39"]
                assert "workable:verneek:0DB6C4CE39" not in (res2.refreshed_job_ids or set())
                assert len(res2.listings) == 2

                # Case A: Job MUST remain active and preserve its rich cached listing
                preserved = reg.get_monitored_job("workable:verneek:0DB6C4CE39")
                assert preserved is not None
                assert preserved.description_ok is True
                assert preserved.requirements is not None
                with reg._get_connection() as conn:
                    statuses = dict(
                        conn.execute(
                            "SELECT job_id, status FROM monitored_jobs WHERE board_id = ?",
                            (board.id,),
                        ).fetchall()
                    )
                assert statuses["workable:verneek:0DB6C4CE39"] == "active"

                states = reg.get_monitored_job_detail_states(board.id)
                assert states["workable:verneek:0DB6C4CE39"].detail_status == "detail_404"
                assert states["workable:verneek:0DB6C4CE39"].detail_retry_count == 1
                assert states["workable:verneek:0DB6C4CE39"].detail_next_retry_at > clock["now"]

                # Immediate repeat poll (before 404 backoff expires) must NOT hammer api/v2
                clock["now"] += 60.0
                mode["v2_calls"].clear()
                res_no_hammer = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_no_hammer.success is True and res_no_hammer.not_modified is True
                assert mode["v2_calls"] == []

                # Case B: Later successful widget response removes 0DB6C4CE39 -> closed cleanly
                clock["now"] += 60.0
                mode["widget"] = "one"
                res3 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res3.success is True and len(res3.listings) == 1
                with reg._get_connection() as conn:
                    statuses_after = dict(
                        conn.execute(
                            "SELECT job_id, status FROM monitored_jobs WHERE board_id = ?",
                            (board.id,),
                        ).fetchall()
                    )
                assert statuses_after["workable:verneek:3DBA754691"] == "active"
                assert statuses_after["workable:verneek:0DB6C4CE39"] == "closed"

    @pytest.mark.anyio
    async def test_workable_new_job_detail_404_uses_conservative_fallback_and_backs_off(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "new_404.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_one = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691"],
        }
        widget_empty = {**widget_full, "jobs": []}
        state = {"widget": widget_one, "v2_calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json=state["widget"])
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                state["v2_calls"] += 1
                return httpx.Response(404, json={"error": "Not found"})
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True and len(res1.listings) == 1
                assert res1.refreshed_job_ids == set()
                states1 = reg.get_monitored_job_detail_states(board.id)
                st1 = states1["workable:verneek:3DBA754691"]
                assert st1.detail_status == "detail_404"
                assert st1.detail_last_hydrated_at is None
                assert st1.detail_retry_count == 1
                assert st1.detail_next_retry_at == clock["now"] + 3600.0

                # Before 1h backoff expires, poll must not hammer api/v2
                clock["now"] += 1800.0
                res2 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res2.success is True and res2.not_modified is True
                assert state["v2_calls"] == 1

                # Once 1h backoff elapses, one retry occurs with doubled backoff (2h)
                clock["now"] += 1860.0
                res3 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res3.success is True
                assert state["v2_calls"] == 2
                st3 = reg.get_monitored_job_detail_states(board.id)["workable:verneek:3DBA754691"]
                assert st3.detail_retry_count == 2
                assert st3.detail_next_retry_at == clock["now"] + 7200.0

                # Removing from widget closes it even while detail was 404
                state["widget"] = widget_empty
                res4 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res4.success is True and len(res4.listings) == 0
                with reg._get_connection() as conn:
                    status_row = conn.execute(
                        "SELECT status FROM monitored_jobs WHERE job_id = ?",
                        ("workable:verneek:3DBA754691",),
                    ).fetchone()
                assert status_row is not None and status_row[0] == "closed"

    @pytest.mark.anyio
    async def test_workable_existing_rich_job_preserves_cache_and_hydrated_ts_on_503(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry

        db_path = str(tmp_path / "preserve_rich.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_v1 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_one = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691"],
        }
        mode = {"status": 200, "v2_calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json=widget_one)
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                mode["v2_calls"] += 1
                if mode["status"] == 503:
                    return httpx.Response(503)
                return httpx.Response(200, json=job_v1)
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        t0 = clock["now"]
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True
                assert res1.refreshed_job_ids == {"workable:verneek:3DBA754691"}

                # 6h later, stale revalidation hits 503 -> must keep rich listing + t0 detail_last_hydrated_at
                clock["now"] += 22000.0
                mode["status"] = 503
                res2 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res2.success is True
                assert res2.refreshed_job_ids == set()
                preserved = reg.get_monitored_job("workable:verneek:3DBA754691")
                assert preserved is not None
                assert preserved.description_ok is True
                assert preserved.requirements is not None
                st2 = reg.get_monitored_job_detail_states(board.id)["workable:verneek:3DBA754691"]
                assert st2.detail_status == "transient_error"
                assert st2.detail_last_hydrated_at == t0
                assert st2.detail_retry_count == 1
                assert st2.detail_next_retry_at == clock["now"] + 300.0

    @pytest.mark.anyio
    async def test_direct_board_router_probes_workable(self, tmp_path):
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.direct_board_router import probe_direct_boards

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "router.sqlite"))
        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_99brightminds.json").read_text(encoding="utf-8"))
        widget_json = json.loads((WORKABLE_FIXTURE_DIR / "widget_99brightminds.json").read_text(encoding="utf-8"))
        job_json = json.loads((WORKABLE_FIXTURE_DIR / "job_99brightminds_63E0790AD5.json").read_text(encoding="utf-8"))

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/widget/accounts/99brightminds" in u:
                return httpx.Response(200, json=widget_json)
            if "/api/v1/accounts/99brightminds" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v2/accounts/99brightminds/jobs/63E0790AD5" in u:
                return httpx.Response(200, json=job_json)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg):
                listings = await probe_direct_boards(["99brightminds"], client, platforms=["workable"])
        assert len(listings) >= 1
        target = next((j for j in listings if j.id == "workable:99brightminds:63E0790AD5"), None)
        assert target is not None
        assert target.company == acct_json["name"]
        assert target.salary is not None and target.salary.currency == "JOD"
        assert target.company_logo_verified is True
        assert target.apply_url == "https://apply.workable.com/99brightminds/j/63E0790AD5/apply"

    @pytest.mark.anyio
    async def test_workable_monitoring_and_direct_probe_respect_shared_host_concurrency_limit(self, tmp_path):
        from src.config import settings
        from src.project_files.board_adapters import BOARD_ADAPTERS, WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.direct_board_router import probe_workable_board
        from src.project_files.http_resilience import resilience_manager

        resilience_manager.reset()
        db_path = str(tmp_path / "shared_host_limit.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)

        base_v2 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_tpl = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        acct_tpl = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        base_w = next(j for j in widget_tpl["jobs"] if j["shortcode"] == "3DBA754691")

        # Register 5 Workable boards, each with 5 jobs (up to 25 unthrottled detail requests concurrently)
        slugs = [f"acme-{i}" for i in range(5)]
        for i, slug in enumerate(slugs):
            b = reg.register_candidate(
                ats_provider="workable",
                board_token=slug,
                company_name=f"Acme {i}",
                source_url=f"https://apply.workable.com/{slug}/j/JOB0",
            )
            assert b is not None

        metrics = {"in_flight": 0, "peak": 0, "total_requests": 0, "account_calls": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            metrics["total_requests"] += 1
            metrics["in_flight"] += 1
            metrics["peak"] = max(metrics["peak"], metrics["in_flight"])
            try:
                await asyncio.sleep(0.025)
                if "/api/v1/accounts/" in u:
                    metrics["account_calls"] += 1
                    return httpx.Response(200, json=acct_tpl)
                if "/api/v1/widget/accounts/" in u:
                    slug = u.rsplit("/", 1)[-1]
                    jobs = [{**base_w, "shortcode": f"JOB{k}"} for k in range(5)]
                    return httpx.Response(200, json={**widget_tpl, "name": slug, "jobs": jobs})
                if "/api/v2/accounts/" in u:
                    parts = u.split("/")
                    sc = parts[-1]
                    return httpx.Response(200, json={**base_v2, "shortcode": sc})
                return httpx.Response(404)
            finally:
                metrics["in_flight"] -= 1

        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=21600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ):
                results = await asyncio.gather(
                    monitor.poll_due_boards(max_boards=5, client=client, cache_store=cache),
                    probe_workable_board("acme-direct", client),
                )

        monitored_jobs, probed_jobs = results
        assert len(monitored_jobs) == 25
        assert len(probed_jobs) == 5
        assert metrics["account_calls"] >= 5
        assert metrics["total_requests"] >= 35
        assert metrics["peak"] <= settings.per_host_concurrency_limit
        assert metrics["peak"] >= 2  # Still concurrent up to the shared host limit
        assert resilience_manager._host_failures.get("apply.workable.com", 0) == 0

    @pytest.mark.anyio
    async def test_workable_429_circuit_breaker_network_and_5xx_preserve_active_jobs(self, tmp_path):
        from src.config import settings
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.direct_board_router import probe_workable_board
        from src.project_files.http_resilience import CircuitBreakerOpenError, resilience_manager

        resilience_manager.reset()
        db_path = str(tmp_path / "resilience_outcomes.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_v1 = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))
        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_one = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691"],
        }

        mode = {"widget": "200", "v2": "200", "widget_calls": 0, "v2_calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v1/widget/accounts/verneek" in u:
                mode["widget_calls"] += 1
                if mode["widget"] == "429":
                    return httpx.Response(429, headers={"Retry-After": "12"})
                if mode["widget"] == "503":
                    return httpx.Response(503)
                if mode["widget"] == "timeout":
                    raise httpx.ReadTimeout("timed out", request=request)
                if mode["widget"] == "connect_err":
                    raise httpx.ConnectError("connection refused", request=request)
                return httpx.Response(200, json=widget_one)
            if "/api/v2/accounts/verneek/jobs/3DBA754691" in u:
                mode["v2_calls"] += 1
                if mode["v2"] == "429":
                    return httpx.Response(429, headers={"Retry-After": "9"})
                if mode["v2"] == "503":
                    return httpx.Response(503)
                if mode["v2"] == "404":
                    return httpx.Response(404, json={"error": "Not found"})
                return httpx.Response(200, json=job_v1)
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=3600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        def _active_statuses() -> dict[str, str]:
            with reg._get_connection() as conn:
                return dict(
                    conn.execute(
                        "SELECT job_id, status FROM monitored_jobs WHERE board_id = ?",
                        (board.id,),
                    ).fetchall()
                )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                # 1. Initial successful hydration
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True and len(res1.listings) == 1
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                # 2. Detail 429 honors Retry-After=9 on apply.workable.com, preserves active listing
                clock["now"] += 4000.0
                mode["v2"] = "429"
                res2 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res2.success is True and len(res2.listings) == 1
                assert resilience_manager.is_host_rate_limited("apply.workable.com") is True
                assert resilience_manager._host_rate_limit_backoff["apply.workable.com"] == 9.0
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                # While in 429 backoff (now + 3s < 9s), widget GET and direct probe are skipped locally
                clock["now"] += 3.0
                calls_before_backoff = mode["widget_calls"]
                res2b = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res2b.success is False
                assert "rate limited" in (res2b.error or "").lower()
                assert mode["widget_calls"] == calls_before_backoff
                assert await probe_workable_board("verneek", client) == []
                assert mode["widget_calls"] == calls_before_backoff
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                # 3. After Retry-After expires, widget 429 sets Retry-After=12 and does not close jobs
                clock["now"] += 10.0
                mode["widget"] = "429"
                mode["v2"] = "200"
                res3 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res3.success is False
                assert resilience_manager.is_host_rate_limited("apply.workable.com") is True
                assert resilience_manager._host_rate_limit_backoff["apply.workable.com"] == 12.0
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                # 4. Detail 404 still does NOT trip circuit breaker (treated as healthy HTTP response) and does not close job
                clock["now"] += 400.0  # past both 12s rate-limit backoff and 300s detail transient retry
                mode["widget"] = "200"
                mode["v2"] = "404"
                res4 = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res4.success is True and len(res4.listings) == 1
                assert resilience_manager.is_host_open("apply.workable.com") is True
                assert resilience_manager._host_failures.get("apply.workable.com", 0) == 0
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                # 5. Consecutive 503 + network errors (timeout / connect_err) trip circuit breaker and preserve active job
                mode["v2"] = "200"
                modes_seq = ["503", "timeout", "connect_err", "503", "timeout"]
                for idx in range(settings.circuit_breaker_failure_threshold):
                    clock["now"] += 1.0
                    mode["widget"] = modes_seq[idx % len(modes_seq)]
                    fail_res = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                    assert fail_res.success is False
                    assert _active_statuses()["workable:verneek:3DBA754691"] == "active"

                assert resilience_manager.is_host_open("apply.workable.com") is False
                calls_when_open = mode["widget_calls"]
                res_cb = await monitor.check_single_board(reg.get_board("workable", "verneek"), client, cache_store=cache)
                assert res_cb.success is False
                assert "Circuit breaker" in (res_cb.error or "")
                assert mode["widget_calls"] == calls_when_open  # no outbound HTTP call while breaker OPEN
                assert _active_statuses()["workable:verneek:3DBA754691"] == "active"
                preserved = reg.get_monitored_job("workable:verneek:3DBA754691")
                assert preserved is not None and preserved.description_ok is True

                # Direct board probe also handles open circuit breaker gracefully
                assert await probe_workable_board("verneek", client) == []

    @pytest.mark.anyio
    async def test_workable_search_client_identity_enrichment_does_not_deadlock_under_throttle(self, tmp_path):
        from src.project_files.ats_api_client import WorkableClient
        from src.project_files.ats_url_parser import parse_ats_url
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.http_resilience import resilience_manager

        resilience_manager.reset()
        reg = CompanyBoardRegistry(db_path=str(tmp_path / "search_nodl.sqlite"))
        acct_json = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_json = json.loads((WORKABLE_FIXTURE_DIR / "job_verneek_3DBA754691.json").read_text(encoding="utf-8"))

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/accounts/" in u:
                return httpx.Response(200, json=acct_json)
            if "/api/v2/accounts/" in u:
                return httpx.Response(200, json=job_json)
            return httpx.Response(404)

        client_wrapper = WorkableClient()

        async def _throttled_item(idx: int, http_client: httpx.AsyncClient):
            url = f"https://apply.workable.com/verneek{idx}/j/3DBA754691"
            parsed = parse_ats_url(url)
            assert parsed is not None
            async with resilience_manager.throttle(url):
                return await asyncio.wait_for(
                    client_wrapper.fetch_result(parsed, http_client),
                    timeout=2.0,
                )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg):
                # Fill all 3 host semaphore slots concurrently — would deadlock if identity enrichment re-acquired throttle
                outcomes = await asyncio.gather(
                    *(_throttled_item(i, http_client) for i in range(4))
                )
        assert len(outcomes) == 4
        assert all(listing is not None and listing.company_logo_verified for listing, _ in outcomes)

    @pytest.mark.anyio
    async def test_workable_account_identity_429_records_backoff_and_preserves_jobs(self, tmp_path):
        from src.project_files.board_adapters import WorkableBoardAdapter
        from src.project_files.board_monitor import BoardMonitor
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.http_resilience import resilience_manager

        resilience_manager.reset()
        db_path = str(tmp_path / "acct_429.sqlite")
        reg = CompanyBoardRegistry(db_path=db_path)
        cache = CacheStore(db_path=db_path)
        board = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek/j/3DBA754691",
        )
        assert board is not None

        widget_full = json.loads((WORKABLE_FIXTURE_DIR / "widget_verneek.json").read_text(encoding="utf-8"))
        widget_one = {
            **widget_full,
            "jobs": [j for j in widget_full["jobs"] if j["shortcode"] == "3DBA754691"],
        }
        v2_calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if "/api/v1/widget/accounts/verneek" in u:
                return httpx.Response(200, json=widget_one)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(429, headers={"Retry-After": "7"})
            if "/api/v2/accounts/verneek/jobs/" in u:
                v2_calls["count"] += 1
                return httpx.Response(200, json={})
            return httpx.Response(404)

        clock = {"now": 1_700_000_000.0}
        adapter = WorkableBoardAdapter(detail_revalidate_ttl_seconds=3600, max_revalidations_per_poll=5)
        monitor = BoardMonitor(registry=reg, cache=cache)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.project_files.ats_api_client.company_board_registry", reg), patch.dict(
                "src.project_files.board_monitor.BOARD_ADAPTERS", {"workable": adapter}
            ), patch("time.time", side_effect=lambda: clock["now"]):
                res = await monitor.check_single_board(board, client, cache_store=cache)
                assert res.success is True and len(res.listings) == 1
                assert res.refreshed_job_ids == set()
                assert v2_calls["count"] == 0  # Account 429 prevented subsequent api/v2 call during backoff
                assert resilience_manager.is_host_rate_limited("apply.workable.com") is True
                assert resilience_manager._host_rate_limit_backoff["apply.workable.com"] == 7.0
                st = reg.get_monitored_job_detail_states(board.id)["workable:verneek:3DBA754691"]
                assert st.detail_status == "transient_error"
                assert st.detail_last_error == "host_rate_limited"


class TestWorkableCacheRepair:
    @pytest.mark.anyio
    async def test_workable_cache_repair_dry_run_canonicalizes_merges_and_is_idempotent(self, tmp_path):
        from datetime import datetime, timezone
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.models import JobListing, JobSalary
        from src.project_files.workable_cache_repair import repair_workable_cache

        db_path = str(tmp_path / "repair.sqlite")
        cache = CacheStore(db_path=db_path)
        reg = CompanyBoardRegistry(db_path=db_path)

        now = datetime.now(timezone.utc)
        now_ts = time.time()
        # 1. Seed degraded alias URL (trailing slash + tracking query) for 99brightminds
        # using direct SQL to simulate legacy pre-Step-41 unnormalized keys in url_cache
        alias_url = "https://apply.workable.com/99brightminds/j/63E0790AD5/?utm_source=serper"
        canon_99 = "https://apply.workable.com/99brightminds/j/63E0790AD5"
        alias_listing = JobListing(
            id="workable:99brightminds:63E0790AD5",
            provider="workable",
            ats_source="workable",
            company="99brightminds",
            company_slug="99brightminds",
            provider_job_id="63E0790AD5",
            title="Sales Account Manager - Amman",
            source_url=alias_url,
            apply_url=alias_url,
            scraped_at=now,
            query_used="sales",
            data_source="api",
        )
        # Also seed pre-existing richer canonical row with existing posted_at to verify completeness merge
        canon_listing = JobListing(
            id="workable:99brightminds:63E0790AD5",
            provider="workable",
            ats_source="workable",
            company="99brightminds",
            company_slug="99brightminds",
            provider_job_id="63E0790AD5",
            title="Sales Account Manager - Amman",
            source_url=canon_99,
            apply_url=canon_99,
            posted_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            scraped_at=now,
            query_used="sales",
            data_source="api",
        )

        # 2. Seed learnrush /apply URL with degraded INR salary (missing currency)
        apply_alias_learn = "https://apply.workable.com/learnrush/j/64801AA613/apply"
        learn_listing = JobListing(
            id="workable:learnrush:64801AA613",
            provider="workable",
            ats_source="workable",
            company="Learnrush",
            company_slug="learnrush",
            provider_job_id="64801AA613",
            title="Data Scientist (AI & ML)",
            source_url=apply_alias_learn,
            apply_url=apply_alias_learn,
            salary=JobSalary(minimum=400000, maximum=800000, raw_text="4,00,000 - 8,00,000"),
            scraped_at=now,
            query_used="data scientist",
            data_source="api",
        )
        with cache._get_connection() as conn:
            for raw_u, item_l in (
                (alias_url, alias_listing),
                (canon_99, canon_listing),
                (apply_alias_learn, learn_listing),
            ):
                conn.execute(
                    "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (raw_u, item_l.model_dump_json(), now_ts, now_ts + 86400),
                )
            conn.commit()

        # 3. Seed expired 404 treq URL + active monitored_jobs row
        treq_url = "https://apply.workable.com/treq/j/D94DBAF102"
        treq_listing = JobListing(
            id="workable:treq:D94DBAF102",
            provider="workable",
            ats_source="workable",
            company="TReq",
            company_slug="treq",
            provider_job_id="D94DBAF102",
            title="Fullstack Engineer",
            description="Historical cached description must be preserved on 404.",
            source_url=treq_url,
            apply_url=treq_url,
            scraped_at=now,
            query_used="fullstack",
            data_source="api",
        )
        cache.set_url_cache(treq_url, treq_listing)
        board_treq = reg.register_candidate(ats_provider="workable", board_token="treq", company_name="TReq", source_url=treq_url)
        reg.upsert_monitored_job(treq_listing, board_id=board_treq.id)

        # 4. Seed synthetic row (must be skipped)
        syn_url = "https://example.com/workable/company0/j/DEAD1234"
        cache.set_url_cache(
            syn_url,
            JobListing(
                id="workable:company0:DEAD1234",
                provider="workable",
                ats_source="workable",
                company="TestCompany",
                title="Dummy Role",
                source_url=syn_url,
                apply_url=syn_url,
                scraped_at=now,
                query_used="dummy",
                data_source="api",
            ),
        )

        # 5. Seed provisional board record for verneek awaiting promotion + logo
        board_vern = reg.register_candidate(
            ats_provider="workable",
            board_token="verneek",
            company_name="Verneek",
            source_url="https://apply.workable.com/verneek",
        )
        with reg._get_connection() as conn:
            conn.execute(
                "UPDATE company_boards SET monitoring_capability = 'provisional' WHERE id = ?",
                (board_vern.id,),
            )
            conn.commit()

        acct_99 = json.loads((WORKABLE_FIXTURE_DIR / "account_99brightminds.json").read_text(encoding="utf-8"))
        job_99 = json.loads((WORKABLE_FIXTURE_DIR / "job_99brightminds_63E0790AD5.json").read_text(encoding="utf-8"))
        acct_lr = json.loads((WORKABLE_FIXTURE_DIR / "account_learnrush.json").read_text(encoding="utf-8"))
        job_lr = json.loads((WORKABLE_FIXTURE_DIR / "job_learnrush_64801AA613.json").read_text(encoding="utf-8"))
        acct_treq = json.loads((WORKABLE_FIXTURE_DIR / "account_treq.json").read_text(encoding="utf-8"))
        acct_vern = json.loads((WORKABLE_FIXTURE_DIR / "account_verneek.json").read_text(encoding="utf-8"))
        job_treq_404 = json.loads((WORKABLE_FIXTURE_DIR / "job_treq_D94DBAF102_404.json").read_text(encoding="utf-8"))

        requested_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            requested_urls.append(u)
            if "/api/v1/accounts/99brightminds" in u:
                return httpx.Response(200, json=acct_99)
            if "/api/v2/accounts/99brightminds/jobs/63E0790AD5" in u:
                return httpx.Response(200, json=job_99)
            if "/api/v1/accounts/learnrush" in u:
                return httpx.Response(200, json=acct_lr)
            if "/api/v2/accounts/learnrush/jobs/64801AA613" in u:
                return httpx.Response(200, json=job_lr)
            if "/api/v1/accounts/treq" in u:
                return httpx.Response(200, json=acct_treq)
            if "/api/v2/accounts/treq/jobs/D94DBAF102" in u:
                return httpx.Response(404, json=job_treq_404)
            if "/api/v1/accounts/verneek" in u:
                return httpx.Response(200, json=acct_vern)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Step 1: Dry run must not mutate SQLite
            dry_report = await repair_workable_cache(cache=cache, registry=reg, client=client, dry_run=True)
            assert dry_report.dry_run is True
            assert dry_report.serper_calls_used == 0
            assert dry_report.skipped_synthetic >= 1
            with cache._get_connection() as conn:
                raw_urls = {r[0] for r in conn.execute("SELECT url FROM url_cache").fetchall()}
            assert alias_url in raw_urls
            with reg._get_connection() as conn:
                cap = conn.execute(
                    "SELECT monitoring_capability FROM company_boards WHERE ats_provider='workable' AND board_token='verneek'"
                ).fetchone()[0]
                assert cap == "provisional"

            # Step 2: Live repair pass
            rep1 = await repair_workable_cache(cache=cache, registry=reg, client=client, dry_run=False)
            assert rep1.dry_run is False
            assert rep1.serper_calls_used == 0
            assert rep1.canonicalized_urls >= 2
            assert rep1.expired_or_unavailable == 1
            assert rep1.monitored_jobs_closed == 1
            assert rep1.boards_reconciled >= 1

            # Raw SQLite alias keys removed after durable canonical write
            with cache._get_connection() as conn:
                raw_urls_after = {r[0] for r in conn.execute("SELECT url FROM url_cache").fetchall()}
            assert alias_url not in raw_urls_after
            assert apply_alias_learn not in raw_urls_after
            assert canon_99 in raw_urls_after
            assert "https://apply.workable.com/learnrush/j/64801AA613" in raw_urls_after

            fixed_99 = cache.get_url_cache(canon_99)
            assert fixed_99 is not None
            assert fixed_99.company == acct_99["name"]
            assert fixed_99.salary is not None and fixed_99.salary.currency == "JOD"
            assert fixed_99.requirements is not None
            assert fixed_99.eligibility is not None
            assert fixed_99.company_logo_verified is True
            assert fixed_99.apply_url == "https://apply.workable.com/99brightminds/j/63E0790AD5/apply"

            fixed_lr = cache.get_url_cache("https://apply.workable.com/learnrush/j/64801AA613")
            assert fixed_lr is not None
            assert fixed_lr.salary is not None and fixed_lr.salary.currency == "INR"
            assert fixed_lr.salary.period == "year"
            assert fixed_lr.requirements is not None
            assert fixed_lr.company_logo_verified is False
            assert fixed_lr.company_logo_url is None

            # Historical cached 404 row preserved, monitored_job marked closed
            preserved_treq = cache.get_url_cache(treq_url)
            assert preserved_treq is not None
            assert "Historical cached description" in (preserved_treq.description or "")
            with reg._get_connection() as conn:
                treq_status = conn.execute(
                    "SELECT status FROM monitored_jobs WHERE job_id = ?",
                    ("workable:treq:D94DBAF102",),
                ).fetchone()[0]
                assert treq_status == "closed"
                vern_row = conn.execute(
                    "SELECT monitoring_capability, company_logo_verified FROM company_boards WHERE ats_provider='workable' AND board_token='verneek'"
                ).fetchone()
                assert vern_row[0] == "supported"
                assert vern_row[1] == 1

            # Step 3: Pass 2 idempotency (zero v2 detail calls)
            requested_urls.clear()
            rep2 = await repair_workable_cache(cache=cache, registry=reg, client=client, dry_run=False)
            assert rep2.serper_calls_used == 0
            assert rep2.skipped_already_repaired >= 3
            assert not [u for u in requested_urls if "/api/v2/" in u]





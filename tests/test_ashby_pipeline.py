"""
Step 39 TDD: Ashby Quality Pipeline End-to-End Tests.

Covers real captured Ashby fixtures (zero synthetic postings, zero live HTTP):
- Slice 2: Shared `ashby_payload_to_raw`, GET API, location + secondaryLocations, ADR 0002 work_model.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from src.project_files.ats_api_client import AshbyClient
from src.project_files.ats_url_parser import parse_ats_url
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.work_model import resolve_work_model

ASHBY_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "ashby"


def _load_board(filename: str) -> dict:
    return json.loads((ASHBY_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _find_job(board: dict, job_id: str) -> dict:
    for j in board.get("jobs", []):
        if str(j.get("id", "")).lower() == job_id.lower():
            return j
    raise KeyError(f"Job {job_id} not found in fixture")


class TestAshbyPayloadAndApiClient:
    def test_shared_payload_builder_extracts_location_secondary_workplace_and_apply_url(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw

        plaid = _load_board("plaid_board_sample.json")
        # Job with workplaceType="Hybrid" AND isRemote=True + location="San Francisco HQ"
        sf_job = _find_job(plaid, "5d8abedc-018a-4b42-ae1f-0e70b34f2007")
        raw = ashby_payload_to_raw(
            sf_job,
            company_slug="plaid",
            default_company_name="Plaid",
        )
        assert raw is not None
        assert raw.provider == "ashby"
        assert raw.raw_company == "Plaid"
        assert raw.raw_location == "San Francisco HQ"
        assert raw.raw_workplace_type == "Hybrid"
        assert raw.source_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007"
        assert raw.apply_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007/application"

        canonical = JobExtractionService.extract(raw)
        assert canonical.location == "San Francisco HQ"
        # ADR 0002: workplaceType="Hybrid" must NOT be overridden by isRemote=True
        assert canonical.work_model == "hybrid"
        assert canonical.work_model_source == "api_enum"
        assert canonical.application_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007/application"
        assert canonical.source_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007"
        listing = CanonicalJobAdapter.to_listing(canonical)
        assert listing.apply_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007/application"
        assert listing.source_url == "https://jobs.ashbyhq.com/plaid/5d8abedc-018a-4b42-ae1f-0e70b34f2007"

    def test_shared_payload_builder_preserves_distinct_secondary_locations(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw

        linear = _load_board("linear_board.json")
        eu_job = _find_job(linear, "d3bc1ced-3ce4-4086-a050-555055dbb1ff")
        raw_dup = ashby_payload_to_raw(eu_job, company_slug="linear")
        assert raw_dup is not None
        # Europe appears in both location and secondaryLocations -> deduplicated
        assert raw_dup.raw_location == "Europe"

        # Distinct secondaryLocations should be retained in location string
        multi = dict(eu_job)
        multi["location"] = "San Francisco"
        multi["secondaryLocations"] = [
            {"location": "New York"},
            {"location": "san francisco"},
            {"location": "London"},
        ]
        raw_multi = ashby_payload_to_raw(multi, company_slug="linear")
        assert raw_multi is not None
        assert raw_multi.raw_location == "San Francisco; New York; London"

    def test_ashby_client_uses_get_with_percent_encoded_slug_and_compensation(self):
        board = _load_board("applied_compute_board.json")
        job_url = "https://jobs.ashbyhq.com/Applied%20Compute/4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba"
        parsed = parse_ats_url(job_url)
        assert parsed is not None
        assert parsed.company_slug == "Applied Compute"

        called_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            assert request.method == "GET"
            return httpx.Response(200, json=board)

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await AshbyClient().fetch_raw_result(parsed, client)

        res = asyncio.run(_run())

        assert res.raw is not None
        assert called_urls == [
            "https://api.ashbyhq.com/posting-api/job-board/Applied%20Compute?includeCompensation=true"
        ]
        assert res.raw.raw_location == "San Francisco"
        canonical = JobExtractionService.extract(res.raw)
        assert canonical.work_model == "in_person"
        assert canonical.work_model_source == "api_enum"


class TestAshbyWorkModelLadder:
    def test_is_remote_true_never_overrides_missing_workplace_type_as_api_enum(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw

        linear = _load_board("linear_board.json")
        hybrid_job = dict(_find_job(linear, "d3bc1ced-3ce4-4086-a050-555055dbb1ff"))
        hybrid_job["workplaceType"] = "Hybrid"
        hybrid_job["isRemote"] = True
        raw_hybrid = ashby_payload_to_raw(hybrid_job, company_slug="linear")
        assert raw_hybrid is not None
        c_hybrid = JobExtractionService.extract(raw_hybrid)
        assert c_hybrid.work_model == "hybrid"

        # When workplaceType is omitted even though isRemote=True, never synthesize api_enum="remote"
        no_enum_job = dict(hybrid_job)
        no_enum_job.pop("workplaceType", None)
        no_enum_job["isRemote"] = True
        raw_no_enum = ashby_payload_to_raw(no_enum_job, company_slug="linear")
        assert raw_no_enum is not None
        assert raw_no_enum.raw_workplace_type is None

    def test_text_fallback_handles_real_in_person_internship_and_fully_remotely(self):
        in_person = resolve_work_model(
            description="This is an in-person internship based in our Burbank hangar.",
        )
        assert in_person.value == "in_person"
        assert in_person.source == "description"

        fully_remotely = resolve_work_model(
            description="We are happy for you to work fully remotely from within Europe.",
        )
        assert fully_remotely.value == "remote"
        assert fully_remotely.source == "description"

        undisclosed = resolve_work_model(
            location="San Francisco, CA",
            description="Build identity verification pipelines with modern Go and TypeScript.",
        )
        assert undisclosed.value is None


class TestAshbyRequirementsEligibilityAndSalary:
    def test_requirements_extracted_for_quora_wayve_and_linear(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw

        quora = _load_board("quora_sample.json")["jobs"][0]
        c_quora = JobExtractionService.extract(ashby_payload_to_raw(quora, company_slug="quora"))
        assert c_quora.requirements is not None
        assert "Java" in c_quora.requirements or "years" in c_quora.requirements.lower()

        wayve = _load_board("wayve_sample.json")["jobs"][0]
        c_wayve = JobExtractionService.extract(ashby_payload_to_raw(wayve, company_slug="wayve"))
        assert c_wayve.requirements is not None
        assert len(c_wayve.requirements) > 40

        linear_eu = _find_job(_load_board("linear_board.json"), "d3bc1ced-3ce4-4086-a050-555055dbb1ff")
        c_linear = JobExtractionService.extract(ashby_payload_to_raw(linear_eu, company_slug="linear"))
        assert c_linear.requirements is not None
        assert "5+ years of experience" in c_linear.requirements

    def test_eligibility_treats_european_union_as_regional_never_physical_country(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw
        from src.project_files.eligibility_extractor import extract_eligibility

        linear_eu = _find_job(_load_board("linear_board.json"), "d3bc1ced-3ce4-4086-a050-555055dbb1ff")
        c_linear = JobExtractionService.extract(ashby_payload_to_raw(linear_eu, company_slug="linear"))
        assert c_linear.eligibility is not None
        assert c_linear.eligibility.physical_location_country is None
        assert c_linear.eligibility.allowed_residence_countries == ["North America", "Europe"]
        assert c_linear.eligibility.residence_restriction_confirmed is True
        assert c_linear.eligibility.nigeria_eligible is False

        eu_only_elig = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Europe",
            raw_fields={"address": {"postalAddress": {"addressCountry": "European Union"}}},
        )
        assert eu_only_elig is not None
        assert eu_only_elig.physical_location_country is None
        assert eu_only_elig.allowed_residence_countries == ["EU"]
        assert eu_only_elig.nigeria_eligible is False

        spring = _load_board("spring_health_board_sample.json")
        remote_us = _find_job(spring, "cf97b740-8332-4367-9195-a860a3424abe")
        c_spring = JobExtractionService.extract(
            ashby_payload_to_raw(remote_us, company_slug="deaa6ad2-d184-436b-b69e-17f761da1d94")
        )
        assert c_spring.eligibility is not None
        assert c_spring.eligibility.physical_location_country == "United States"
        assert c_spring.eligibility.nigeria_eligible is None

    def test_salary_period_preserved_vs_omitted_faithfully(self):
        from src.project_files.ats_api_client import ashby_payload_to_raw

        plaid_job = _find_job(_load_board("plaid_board_sample.json"), "5d8abedc-018a-4b42-ae1f-0e70b34f2007")
        c_plaid = JobExtractionService.extract(ashby_payload_to_raw(plaid_job, company_slug="plaid"))
        assert c_plaid.salary is not None
        assert c_plaid.salary.minimum == 189600
        assert c_plaid.salary.maximum == 290400
        assert c_plaid.salary.currency == "USD"
        assert c_plaid.salary.period == "year"

        plug_job = _find_job(_load_board("plugmotors_board.json"), "62316e43-351a-465e-b143-fe30cb5e642c")
        c_plug = JobExtractionService.extract(ashby_payload_to_raw(plug_job, company_slug="plugmotors"))
        assert c_plug.salary is not None
        assert c_plug.salary.minimum == 164000
        assert c_plug.salary.maximum == 200000
        assert c_plug.salary.currency == "USD"
        assert c_plug.salary.period == "year"

        applied_job = _find_job(_load_board("applied_compute_board.json"), "4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba")
        c_applied = JobExtractionService.extract(ashby_payload_to_raw(applied_job, company_slug="Applied Compute"))
        assert c_applied.salary is not None
        assert c_applied.salary.minimum == 175000
        assert c_applied.salary.maximum == 250000
        assert c_applied.salary.currency == "USD"
        assert c_applied.salary.period is None


class TestAshbyBoardIdentityEnrichment:
    def test_enrich_ashby_board_identity_coalesces_and_sets_real_name_and_logo(self, tmp_path):
        from src.project_files.ats_api_client import enrich_ashby_board_identity
        from src.project_files.company_board_registry import CompanyBoardRegistry

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        plug_html = (ASHBY_FIXTURE_DIR / "plugmotors_board.html").read_text(encoding="utf-8")
        sh_html = (ASHBY_FIXTURE_DIR / "spring_health_board.html").read_text(encoding="utf-8")

        fetch_counts: dict[str, int] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            fetch_counts[u] = fetch_counts.get(u, 0) + 1
            if u.endswith("/plugmotors"):
                return httpx.Response(200, text=plug_html, headers={"content-type": "text/html"})
            if u.endswith("/deaa6ad2-d184-436b-b69e-17f761da1d94"):
                return httpx.Response(200, text=sh_html, headers={"content-type": "text/html"})
            return httpx.Response(404)

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                r1, r2 = await asyncio.gather(
                    enrich_ashby_board_identity("plugmotors", client, registry=reg),
                    enrich_ashby_board_identity("plugmotors", client, registry=reg),
                )
                r3 = await enrich_ashby_board_identity("deaa6ad2-d184-436b-b69e-17f761da1d94", client, registry=reg)
                # Cached negative check must avoid redundant second fetch
                r4 = await enrich_ashby_board_identity("deaa6ad2-d184-436b-b69e-17f761da1d94", client, registry=reg)
                return r1, r2, r3, r4

        (name1, logo1), (name2, logo2), (name3, logo3), (name4, logo4) = asyncio.run(_run())
        assert name1 == "Plug Technologies Inc"
        assert name2 == "Plug Technologies Inc"
        assert logo1.verified is True
        assert logo1.url is not None and "/org-theme-logo/" in logo1.url
        assert logo2.url == logo1.url
        assert fetch_counts.get("https://jobs.ashbyhq.com/plugmotors") == 1

        assert name3 == "Spring Health"
        assert logo3.url is None
        assert logo3.verified is False
        assert name4 == "Spring Health"
        assert fetch_counts.get("https://jobs.ashbyhq.com/deaa6ad2-d184-436b-b69e-17f761da1d94") == 1


class TestAshbyBoardAdapterAndDirectRouterParity:
    def test_ashby_board_adapter_uses_get_shared_pipeline_rich_fingerprint_and_identity(self, tmp_path):
        from src.project_files.board_adapters import AshbyBoardAdapter
        from src.project_files.company_board_registry import CompanyBoardRegistry

        plaid_json = _load_board("plaid_board_sample.json")
        plaid_html = (ASHBY_FIXTURE_DIR / "plaid_board.html").read_text(encoding="utf-8")
        reg = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        board = reg.register_candidate(
            ats_provider="ashby",
            board_token="plaid",
            company_name="Plaid",
            source_url="https://jobs.ashbyhq.com/plaid",
        )
        assert board is not None

        seen_requests: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append((request.method, str(request.url)))
            if "api.ashbyhq.com/posting-api/job-board/plaid" in str(request.url):
                return httpx.Response(200, json=plaid_json, headers={"etag": '"e1"'})
            if str(request.url) == "https://jobs.ashbyhq.com/plaid":
                return httpx.Response(200, text=plaid_html, headers={"content-type": "text/html"})
            return httpx.Response(404)

        adapter = AshbyBoardAdapter()

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await adapter.check_board(board, client, registry=reg)

        res = asyncio.run(_run())
        assert res.success is True
        assert res.not_modified is False
        assert res.content_fingerprint is not None
        assert ("GET", "https://api.ashbyhq.com/posting-api/job-board/plaid?includeCompensation=true") in seen_requests
        assert all(m == "GET" for m, _ in seen_requests)

        assert len(res.listings) == 3
        first = res.listings[0]
        assert first.location == "San Francisco HQ"
        assert first.work_model == "hybrid"
        assert first.work_model_source == "api_enum"
        assert first.salary is not None and first.salary.minimum == 189600
        assert first.requirements is not None
        assert first.eligibility is not None
        assert first.company_logo_verified is True
        assert "/org-theme-logo/" in (first.company_logo_url or "")

        # Mutating workplaceType or location must invalidate fingerprint (must NOT short-circuit 304)
        board.content_fingerprint = res.content_fingerprint
        mutated = json.loads(json.dumps(plaid_json))
        mutated["jobs"][0]["workplaceType"] = "OnSite"

        def handler_mut(request: httpx.Request) -> httpx.Response:
            if "api.ashbyhq.com/posting-api/job-board/plaid" in str(request.url):
                return httpx.Response(200, json=mutated)
            return httpx.Response(404)

        async def _run_mut():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler_mut)) as client:
                return await adapter.check_board(board, client, registry=reg)

        res_mut = asyncio.run(_run_mut())
        assert res_mut.success is True
        assert res_mut.not_modified is False
        assert res_mut.content_fingerprint != res.content_fingerprint
        assert res_mut.listings[0].work_model == "in_person"

    def test_probe_ashby_board_achieves_full_parity_with_ashby_client(self, tmp_path):
        from src.project_files.direct_board_router import probe_ashby_board

        plug_json = _load_board("plugmotors_board.json")
        plug_html = (ASHBY_FIXTURE_DIR / "plugmotors_board.html").read_text(encoding="utf-8")

        def handler(request: httpx.Request) -> httpx.Response:
            if "api.ashbyhq.com/posting-api/job-board/plugmotors" in str(request.url):
                assert request.method == "GET"
                assert "includeCompensation=true" in str(request.url)
                return httpx.Response(200, json=plug_json)
            if str(request.url) == "https://jobs.ashbyhq.com/plugmotors":
                return httpx.Response(200, text=plug_html, headers={"content-type": "text/html"})
            return httpx.Response(404)

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                direct_jobs = await probe_ashby_board("plugmotors", client)
                parsed = parse_ats_url("https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c")
                assert parsed is not None
                direct_client_job, _ = await AshbyClient().fetch_result(parsed, client)
                return direct_jobs, direct_client_job

        direct_jobs, client_job = asyncio.run(_run())
        assert client_job is not None
        matched = next(j for j in direct_jobs if "62316e43-351a-465e-b143-fe30cb5e642c" in j.source_url)
        assert matched.title == client_job.title
        assert matched.company == client_job.company == "Plug Technologies Inc"
        assert matched.location == client_job.location == "Los Angeles"
        assert matched.work_model == client_job.work_model == "in_person"
        assert matched.salary == client_job.salary
        assert matched.eligibility == client_job.eligibility
        assert matched.company_logo_url == client_job.company_logo_url
        assert matched.company_logo_verified is True

    def test_ashby_board_adapter_fingerprint_detects_tail_description_secondary_loc_and_compensation_while_preserving_304(
        self, tmp_path
    ):
        from src.project_files.board_adapters import AshbyBoardAdapter
        from src.project_files.company_board_registry import CompanyBoardRegistry

        base_payload = _load_board("plaid_board_sample.json")
        base_payload["jobs"][0]["secondaryLocations"] = [{"location": "New York, NY"}]

        reg = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        board = reg.register_candidate(
            ats_provider="ashby",
            board_token="plaid",
            company_name="Plaid",
            source_url="https://jobs.ashbyhq.com/plaid",
        )
        assert board is not None
        # Pre-seed checked identity so check_board hits only the board API
        reg.set_board_identity(
            ats_provider="ashby",
            board_token="plaid",
            company_name="Plaid",
            logo_url="https://app.ashbyhq.com/api/images/org-theme-logo/plaid.png",
            logo_source="ashby_app_data_square_logo",
            logo_verified=True,
        )
        board = reg.get_board("ashby", "plaid")
        assert board is not None

        adapter = AshbyBoardAdapter()

        async def _check(payload: dict | None, *, status: int = 200, headers: dict | None = None):
            seen_headers: dict[str, str] = {}

            def handler(request: httpx.Request) -> httpx.Response:
                seen_headers.update(dict(request.headers))
                if status == 304:
                    return httpx.Response(304, headers=headers or {})
                return httpx.Response(status, json=payload, headers=headers or {})

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await adapter.check_board(board, client, registry=reg), seen_headers

        # Initial baseline poll
        res0, _ = asyncio.run(_check(base_payload, headers={"etag": '"etag-v1"', "last-modified": "Mon, 01 Jun 2026 00:00:00 GMT"}))
        assert res0.success is True
        assert res0.not_modified is False
        assert res0.content_fingerprint is not None
        assert "New York, NY" in (res0.listings[0].location or "")
        assert res0.listings[0].salary is not None and res0.listings[0].salary.minimum == 189600

        board.content_fingerprint = res0.content_fingerprint
        board.etag = res0.etag
        board.last_modified = res0.last_modified

        # 1) Change description content ONLY after character 200
        desc_mut = json.loads(json.dumps(base_payload))
        assert len(desc_mut["jobs"][0]["descriptionPlain"]) > 200
        assert len(desc_mut["jobs"][0]["descriptionHtml"]) > 200
        desc_mut["jobs"][0]["descriptionHtml"] += "<p>Distributed Go microservices requirement added after char 200.</p>"
        desc_mut["jobs"][0]["descriptionPlain"] += "\nDistributed Go microservices requirement added after char 200."
        res_desc, _ = asyncio.run(_check(desc_mut))
        assert res_desc.success is True
        assert res_desc.not_modified is False
        assert res_desc.content_fingerprint != res0.content_fingerprint
        assert "distributed go microservices" in (res_desc.listings[0].description or "").lower()

        # 2) Change a secondaryLocation while keeping list length == 1 unchanged
        sec_mut = json.loads(json.dumps(base_payload))
        sec_mut["jobs"][0]["secondaryLocations"] = [{"location": "London, UK"}]
        res_sec, _ = asyncio.run(_check(sec_mut))
        assert res_sec.success is True
        assert res_sec.not_modified is False
        assert res_sec.content_fingerprint != res0.content_fingerprint
        assert "London, UK" in (res_sec.listings[0].location or "")
        assert "New York, NY" not in (res_sec.listings[0].location or "")

        # 3) Change compensation while keeping all other fields constant
        comp_mut = json.loads(json.dumps(base_payload))
        comp_mut["jobs"][0]["compensation"]["compensationTiers"][0]["components"][0]["minValue"] = 210000
        comp_mut["jobs"][0]["compensation"]["compensationTiers"][0]["components"][0]["maxValue"] = 320000
        comp_mut["jobs"][0]["compensation"]["compensationTiers"][0]["components"][0]["summary"] = "$210K – $320K"
        comp_mut["jobs"][0]["compensation"]["scrapeableCompensationSalarySummary"] = "$210K - $320K"
        res_comp, _ = asyncio.run(_check(comp_mut))
        assert res_comp.success is True
        assert res_comp.not_modified is False
        assert res_comp.content_fingerprint != res0.content_fingerprint
        assert res_comp.listings[0].salary is not None
        assert res_comp.listings[0].salary.minimum == 210000
        assert res_comp.listings[0].salary.maximum == 320000

        # 4) Change employmentType, department/team, workplaceTypeName, and isRemote fallback (when workplaceType omitted)
        emp_mut = json.loads(json.dumps(base_payload))
        emp_mut["jobs"][0]["employmentType"] = "Contract"
        res_emp, _ = asyncio.run(_check(emp_mut))
        assert res_emp.not_modified is False
        assert res_emp.content_fingerprint != res0.content_fingerprint

        dept_mut = json.loads(json.dumps(base_payload))
        dept_mut["jobs"][0]["department"] = "Platform Engineering"
        res_dept, _ = asyncio.run(_check(dept_mut))
        assert res_dept.not_modified is False
        assert res_dept.content_fingerprint != res0.content_fingerprint

        wtn_mut = json.loads(json.dumps(base_payload))
        wtn_mut["jobs"][0]["workplaceType"] = None
        wtn_mut["jobs"][0]["workplaceTypeName"] = "Remote"
        res_wtn, _ = asyncio.run(_check(wtn_mut))
        assert res_wtn.not_modified is False
        assert res_wtn.listings[0].work_model == "remote"

        # isRemote fallback when workplaceType & workplaceTypeName are absent
        fb_base = json.loads(json.dumps(base_payload))
        fb_base["jobs"][0]["workplaceType"] = None
        fb_base["jobs"][0]["workplaceTypeName"] = None
        fb_base["jobs"][0]["isRemote"] = False
        res_fb_base, _ = asyncio.run(_check(fb_base))
        assert res_fb_base.not_modified is False
        board.content_fingerprint = res_fb_base.content_fingerprint

        fb_mut = json.loads(json.dumps(fb_base))
        fb_mut["jobs"][0]["isRemote"] = True
        res_fb_mut, _ = asyncio.run(_check(fb_mut))
        assert res_fb_mut.not_modified is False
        assert res_fb_mut.content_fingerprint != res_fb_base.content_fingerprint

        # Restore baseline fingerprint & verify transient metadata + key reordering do NOT invalidate it
        board.content_fingerprint = res0.content_fingerprint
        transient_mut = json.loads(json.dumps(base_payload))
        transient_mut["apiVersion"] = "2"
        transient_mut["generatedAt"] = "2026-11-13T16:00:00Z"
        transient_mut["jobs"][0]["transientRequestId"] = "req-999"
        transient_mut["jobs"][0]["isListed"] = False
        # Reorder keys inside compensation
        comp0 = transient_mut["jobs"][0]["compensation"]
        transient_mut["jobs"][0]["compensation"] = dict(reversed(list(comp0.items())))
        res_same, _ = asyncio.run(_check(transient_mut))
        assert res_same.success is True
        assert res_same.not_modified is True
        assert res_same.content_fingerprint == res0.content_fingerprint

        # 5) Preserve HTTP 304 conditional caching behavior
        res_304, req_headers = asyncio.run(_check(None, status=304))
        assert res_304.success is True
        assert res_304.not_modified is True
        assert res_304.etag == '"etag-v1"'
        assert res_304.last_modified == "Mon, 01 Jun 2026 00:00:00 GMT"
        assert res_304.content_fingerprint == res0.content_fingerprint
        assert req_headers.get("if-none-match") == '"etag-v1"'
        assert req_headers.get("if-modified-since") == "Mon, 01 Jun 2026 00:00:00 GMT"

    def test_ashby_job_content_hash_returns_full_64_char_sha256_and_is_key_order_invariant(self):
        import re
        from src.project_files.board_adapters import _ashby_job_content_hash

        base_payload = _load_board("plaid_board_sample.json")
        job0 = base_payload["jobs"][0]

        h1 = _ashby_job_content_hash(job0)
        assert re.fullmatch(r"[0-9a-f]{64}", h1) is not None

        # Identical canonical payload produces identical 64-char digest
        job_copy = json.loads(json.dumps(job0))
        assert _ashby_job_content_hash(job_copy) == h1

        # Reordering dictionary keys (top-level and nested) does not change digest
        reordered = dict(reversed(list(job_copy.items())))
        reordered["address"] = dict(reversed(list(job_copy["address"].items())))
        reordered["address"]["postalAddress"] = dict(
            reversed(list(job_copy["address"]["postalAddress"].items()))
        )
        reordered["compensation"] = dict(reversed(list(job_copy["compensation"].items())))
        assert _ashby_job_content_hash(reordered) == h1

        # Changing a meaningful Ashby posting field changes the 64-char digest
        mutated = json.loads(json.dumps(job0))
        mutated["title"] = "Principal Strategic Initiatives"
        h_mut = _ashby_job_content_hash(mutated)
        assert re.fullmatch(r"[0-9a-f]{64}", h_mut) is not None
        assert h_mut != h1


class TestAshbyCacheRepair:
    """Slice 6: zero-Serper restartable Ashby cache & board identity repair."""

    def test_repair_dry_run_makes_zero_db_mutations_and_skips_synthetic_records(self, tmp_path):
        from src.project_files.ashby_cache_repair import repair_ashby_cache
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.models import JobListing

        plug_json = _load_board("plugmotors_board.json")
        plug_html = (ASHBY_FIXTURE_DIR / "plugmotors_board.html").read_text(encoding="utf-8")

        db_path = str(tmp_path / "cache.sqlite")
        cache = CacheStore(db_path=db_path)
        reg = CompanyBoardRegistry(db_path=db_path)

        degraded = JobListing(
            id="ashby:plugmotors:62316e43-351a-465e-b143-fe30cb5e642c",
            provider="ashby",
            data_source="api",
            ats_source="ashby",
            query_used="plugmotors",
            scraped_at="2026-11-10T00:00:00Z",
            title="Mechanical Engineer",
            company="Plugmotors",
            company_slug="plugmotors",
            provider_job_id="62316e43-351a-465e-b143-fe30cb5e642c",
            source_url="https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c",
            apply_url="https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c/application",
            location=None,
            work_model="in_person",
            description="Old description",
            description_ok=True,
        )
        # Insert raw alias & synthetic URL directly into url_cache to mirror operational anomalies
        with cache._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (
                    "https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c?embed=js",
                    degraded.model_dump_json(),
                    1000.0,
                    9999999999.0,
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (
                    "https://example.com/ashby/job/0",
                    degraded.model_copy(update={"company_slug": "company0"}).model_dump_json(),
                    1000.0,
                    9999999999.0,
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (
                    "https://jobs.ashbyhq.com/company0/00000000-0000-0000-0000-000000000000",
                    degraded.model_copy(update={"company_slug": "company0"}).model_dump_json(),
                    1000.0,
                    9999999999.0,
                ),
            )
            conn.commit()

        reg.register_candidate(
            ats_provider="ashby",
            board_token="plugmotors",
            company_name="Plugmotors",
            source_url="https://jobs.ashbyhq.com/plugmotors",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            assert "serper" not in u.lower()
            if "api.ashbyhq.com/posting-api/job-board/plugmotors" in u:
                assert request.method == "GET"
                assert "includeCompensation=true" in u
                return httpx.Response(200, json=plug_json)
            if u == "https://jobs.ashbyhq.com/plugmotors":
                return httpx.Response(200, text=plug_html, headers={"content-type": "text/html"})
            return httpx.Response(404)

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await repair_ashby_cache(cache=cache, registry=reg, client=client, dry_run=True)

        report = asyncio.run(_run())
        assert report.dry_run is True
        assert report.serper_calls_used == 0
        assert report.skipped_synthetic == 2
        assert report.total_urls == 1
        assert report.repaired_from_board_api == 1
        assert report.canonicalized_urls == 1

        # Dry run must leave SQLite rows untouched
        with cache._get_connection() as conn:
            rows = {r[0] for r in conn.execute("SELECT url FROM url_cache").fetchall()}
            assert "https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c?embed=js" in rows
            assert "https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c" not in rows
            state_tbl = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ashby_repair_state'"
            ).fetchone()
            assert state_tbl is None
        board = reg.get_board("ashby", "plugmotors")
        assert board is not None
        assert board.company_name == "Plugmotors"
        assert board.company_logo_url is None

    def test_repair_live_rekeys_aliases_preserves_404_reconciles_boards_and_is_idempotent(self, tmp_path):
        from src.project_files.ashby_cache_repair import repair_ashby_cache
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.models import JobListing

        plug_json = _load_board("plugmotors_board.json")
        plug_html = (ASHBY_FIXTURE_DIR / "plugmotors_board.html").read_text(encoding="utf-8")
        applied_json = _load_board("applied_compute_board.json")

        db_path = str(tmp_path / "cache.sqlite")
        cache = CacheStore(db_path=db_path)
        reg = CompanyBoardRegistry(db_path=db_path)

        expired_listing = JobListing(
            id="ashby:goneco:11111111-1111-1111-1111-111111111111",
            provider="ashby",
            data_source="api",
            ats_source="ashby",
            query_used="goneco",
            scraped_at="2026-11-10T00:00:00Z",
            title="Archived Role",
            company="GoneCo",
            company_slug="goneco",
            provider_job_id="11111111-1111-1111-1111-111111111111",
            source_url="https://jobs.ashbyhq.com/goneco/11111111-1111-1111-1111-111111111111",
            apply_url="https://jobs.ashbyhq.com/goneco/11111111-1111-1111-1111-111111111111/application",
            description="Authentic cached description that must survive 404.",
            description_ok=True,
        )
        encoded_listing = JobListing(
            id="ashby:Applied%20Compute:4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba",
            provider="ashby",
            data_source="api",
            ats_source="ashby",
            query_used="Applied%20Compute",
            scraped_at="2026-11-10T00:00:00Z",
            title="Member of Technical Staff",
            company="Applied%20Compute",
            company_slug="Applied%20Compute",
            provider_job_id="4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba",
            source_url="https://jobs.ashbyhq.com/Applied%20Compute/4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba",
            apply_url="https://jobs.ashbyhq.com/Applied%20Compute/4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba/application",
            description="Old",
            description_ok=True,
        )
        alias_listing = JobListing(
            id="ashby:plugmotors:62316e43-351a-465e-b143-fe30cb5e642c",
            provider="ashby",
            data_source="api",
            ats_source="ashby",
            query_used="plugmotors",
            scraped_at="2026-11-10T00:00:00Z",
            title="Mechanical Engineer",
            company="Plugmotors",
            company_slug="plugmotors",
            provider_job_id="62316e43-351a-465e-b143-fe30cb5e642c",
            source_url="https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c",
            apply_url="https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c/application",
            description="Old",
            description_ok=True,
        )
        with cache._get_connection() as conn:
            for u, item in [
                ("https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c?csj=senior", alias_listing),
                ("https://jobs.ashbyhq.com/Applied%20Compute/4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba", encoded_listing),
                ("https://jobs.ashbyhq.com/goneco/11111111-1111-1111-1111-111111111111", expired_listing),
            ]:
                conn.execute(
                    "INSERT OR REPLACE INTO url_cache (url, listing_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (u, item.model_dump_json(), 1000.0, 9999999999.0),
                )
            conn.commit()

        # Register candidate board WITHOUT url_cache row (e.g. another slug or matching plugmotors)
        reg.register_candidate(
            ats_provider="ashby",
            board_token="plugmotors",
            company_name="Plugmotors",
            source_url="https://jobs.ashbyhq.com/plugmotors",
        )

        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            calls.append(u)
            if "api.ashbyhq.com/posting-api/job-board/plugmotors" in u:
                return httpx.Response(200, json=plug_json)
            if u == "https://jobs.ashbyhq.com/plugmotors":
                return httpx.Response(200, text=plug_html, headers={"content-type": "text/html"})
            if "api.ashbyhq.com/posting-api/job-board/Applied%20Compute" in u:
                return httpx.Response(200, json=applied_json)
            if u == "https://jobs.ashbyhq.com/Applied%20Compute":
                return httpx.Response(404)
            return httpx.Response(404)

        async def _run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                rep1 = await repair_ashby_cache(cache=cache, registry=reg, client=client)
                calls_after_first = len(calls)
                rep2 = await repair_ashby_cache(cache=cache, registry=reg, client=client)
                return rep1, rep2, calls_after_first, len(calls)

        rep1, rep2, calls1, calls2 = asyncio.run(_run())
        assert rep1.total_urls == 3
        assert rep1.repaired_from_board_api == 2
        assert rep1.canonicalized_urls == 1
        assert rep1.expired_or_unavailable == 1
        assert rep1.boards_identity_enriched == 1
        assert rep1.serper_calls_used == 0

        # Canonical URL written, alias URL removed
        repaired_plug = cache.get_url_cache("https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c")
        assert repaired_plug is not None
        assert repaired_plug.company == "Plug Technologies Inc"
        assert repaired_plug.location == "Los Angeles"
        assert repaired_plug.company_logo_verified is True
        with cache._get_connection() as conn:
            old_row = conn.execute(
                "SELECT 1 FROM url_cache WHERE url = ?",
                ("https://jobs.ashbyhq.com/plugmotors/62316e43-351a-465e-b143-fe30cb5e642c?csj=senior",),
            ).fetchone()
            assert old_row is None

        # %20 legacy company upgraded cleanly
        repaired_applied = cache.get_url_cache("https://jobs.ashbyhq.com/Applied%20Compute/4d3f6ac9-31fe-4dee-b4dc-34a36597d2ba")
        assert repaired_applied is not None
        assert repaired_applied.company == "Applied Compute"
        assert repaired_applied.location == "San Francisco"

        # 404 entry preserved intact
        still_there = cache.get_url_cache("https://jobs.ashbyhq.com/goneco/11111111-1111-1111-1111-111111111111")
        assert still_there is not None
        assert still_there.description == "Authentic cached description that must survive 404."

        # Board identity reconciled
        board = reg.get_board("ashby", "plugmotors")
        assert board is not None
        assert board.company_name == "Plug Technologies Inc"
        assert board.company_logo_verified is True

        # Second pass is 100% idempotent with zero URL HTTP fetches
        assert rep2.skipped_already_repaired == 3
        assert rep2.repaired_from_board_api == 0
        assert rep2.repaired_from_posting_api == 0
        assert rep2.expired_or_unavailable == 0
        assert calls2 == calls1

"""
Step 36 Red-Green TDD: Lever Quality Pipeline End-to-End Tests.

Covers:
1. Genuine captured Lever fixture corpus integrity (keeping job_caadac8e.json untouched).
2. URL discovery, parsing, /apply canonicalisation, board-root discovery, and 104-URL Serper regression.
3. Unified lever_payload_to_raw extraction across LeverClient, LeverBoardAdapter, probe_lever_board,
   plus opening deduplication, lists-only & HTML-only fallback, additional preservation, crisp markdown
   lists, and completeness-aware BoardMonitor/CacheStore persistence.
4. Structured Lever lists[] requirements extraction and prose fallback (separating qualifications from
   responsibilities, perks, benefits, and working conditions).
5. Geographic & eligibility accuracy (Lever country wiring, ", CA" -> US California disambiguation,
   perks "work from anywhere" guard against Latam/country restrictions, unknown/onsite semantics).
6. Salary extraction (structured salaryRange, salaryDescriptionPlain, upper-bound "up to USD 170000",
   bold Markdown "Annual base salary ranging from **CA$160,000 to CA$185,000**", "Starting Base Salary",
   "Pay:", period=None preservation, and rejection of 0/0, per-diem meal allowances, and multi-tier prose).
7. Lever company logo & canonical employer name extraction via JSON-LD / a.main-header-logo / board
   title, rejection of lever-logo-refresh.svg / og:image, bounded board caching, and overwrite protection.
8. Multi-location preservation via categories.allLocations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from bs4 import BeautifulSoup
import httpx
import pytest

from src.project_files.ats_api_client import LeverClient
from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.ats_url_parser import ParsedATSUrl, parse_ats_url
from src.project_files.board_adapters import LeverBoardAdapter
from src.project_files.board_monitor import BoardMonitor
from src.project_files.cache_store import CacheStore
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import CompanyBoard, CompanyBoardRegistry
from src.project_files.deduplicator import GlobalDeduplicator, merge_listings
from src.project_files.direct_board_router import probe_lever_board
from src.project_files.eligibility_extractor import extract_eligibility
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.logo_extractor import extract_company_logo_for_provider
from src.project_files.models import SearchParams
from src.project_files.salary_parser import extract_salary, parse_text_salary
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.url_normalizer import (
    build_url_match_key,
    normalize_job_url,
    url_carries_job_identifier,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "lever"


def _load_api(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_html(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8", errors="ignore")


def _extract_via_client_payload(filename: str):
    data = _load_api(filename)
    from src.project_files.ats_api_client import lever_payload_to_raw

    hosted = data.get("hostedUrl") or ""
    slug = hosted.split("/")[3]
    raw = lever_payload_to_raw(data, company_slug=slug, source_url=hosted)
    assert raw is not None
    job = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(job)
    return raw, job, listing


class TestLeverFixtureCorpus:
    def test_existing_fixture_and_required_evidence_present(self):
        expected = [
            "job_caadac8e.json",
            "api_4775e970.json",
            "api_785989a6.json",
            "api_aeced5e0.json",
            "api_c977b005.json",
            "html_42be630d.html",
            "api_78ddafc0.json",
            "api_624ad7e8.json",
            "api_9176aa65.json",
            "html_9176aa65.html",
            "board_zoox.html",
            "api_1cb2b7f2.json",
            "html_1cb2b7f2.html",
            "board_tpgsi.html",
            "api_9f66e598.json",
            "api_7e9da32d.json",
            "api_925a47b7.json",
            "api_b5b03a21.json",
            "api_faa295da.json",
            "api_8ae01813.json",
            "api_fad6ad02.json",
            "serper_urls_104.json",
        ]
        for fname in expected:
            assert (FIXTURE_DIR / fname).exists(), f"Missing Lever fixture: {fname}"
        caad = _load_api("job_caadac8e.json")
        assert caad["id"] == "caadac8e-381f-42a2-9801-202b351fff28"


class TestLeverUrlParsingAndNormalisation:
    @pytest.mark.parametrize(
        ("url", "expected_slug", "expected_id", "expected_canonical"),
        [
            (
                "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9",
                "palantir",
                "4775e970-ade8-4a0d-8145-9255dc4cbac9",
                "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9",
            ),
            (
                "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9/",
                "palantir",
                "4775e970-ade8-4a0d-8145-9255dc4cbac9",
                "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9",
            ),
            (
                "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066/apply",
                "Fliff",
                "b874a4eb-3fd2-48e9-a467-7dc24f586066",
                "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066",
            ),
            (
                "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066/apply/",
                "Fliff",
                "b874a4eb-3fd2-48e9-a467-7dc24f586066",
                "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066",
            ),
            (
                "https://jobs.lever.co/zoox/7206fd97-14e4-43a0-b903-ba65dfeee53e/apply?utm_source=greatrobots.ai&lever-source=greatrobots",
                "zoox",
                "7206fd97-14e4-43a0-b903-ba65dfeee53e",
                "https://jobs.lever.co/zoox/7206fd97-14e4-43a0-b903-ba65dfeee53e",
            ),
            (
                "https://jobs.lever.co/The-Battery-Network/aeced5e0-55e2-4b1f-86af-61cf04f9ff75/apply/?lever-origin=applied#apply",
                "The-Battery-Network",
                "aeced5e0-55e2-4b1f-86af-61cf04f9ff75",
                "https://jobs.lever.co/The-Battery-Network/aeced5e0-55e2-4b1f-86af-61cf04f9ff75",
            ),
        ],
    )
    def test_parses_and_canonicalises_valid_lever_and_apply_urls(
        self, url: str, expected_slug: str, expected_id: str, expected_canonical: str
    ):
        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == "lever"
        assert parsed.company_slug == expected_slug
        assert parsed.job_id == expected_id
        assert normalize_job_url(url, "lever") == expected_canonical
        assert url_carries_job_identifier(url, "lever") is True
        assert build_url_match_key(url, "lever") == expected_canonical

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://jobs.lever.co/palantir",
            "https://jobs.lever.co/palantir/",
            "https://jobs.lever.co/palantir?lever-via=59yrytAgmX&location=North%20America",
            "https://jobs.lever.co/palantir/?workplacetype=onsite&location=Oslo%2C%20Norway",
            "https://jobs.lever.co/palantir/apply",
            "https://jobs.lever.co/palantir/software-engineer",
            "https://jobs.lever.co/palantir/not-a-valid-uuid/apply",
            "https://jobs.lever.co/company0/2000",
            "https://jobs.lever.co/company0/2000/apply",
        ],
    )
    def test_rejects_board_roots_and_non_uuid_apply_urls_as_job_postings(self, invalid_url: str):
        assert parse_ats_url(invalid_url) is None
        assert url_carries_job_identifier(invalid_url, "lever") is False

    def test_serper_104_urls_regression_classification(self):
        from src.project_files.ats_url_parser import parse_lever_board_root_url

        urls = _load_api("serper_urls_104.json")
        assert len(urls) == 104

        parsed_jobs = [u for u in urls if parse_ats_url(u) is not None]
        apply_jobs = [u for u in parsed_jobs if "/apply" in u]
        board_roots = [u for u in urls if parse_ats_url(u) is None and parse_lever_board_root_url(u) is not None]
        other_invalid = [
            u for u in urls if parse_ats_url(u) is None and parse_lever_board_root_url(u) is None
        ]

        assert len(parsed_jobs) == 92  # 79 direct + 13 /apply
        assert len(apply_jobs) == 13
        assert len(board_roots) == 2
        assert len(other_invalid) == 10  # company0/2000..company9/2009 test/non-UUID URLs

    def test_posting_and_apply_variants_deduplicate_to_one_canonical_job(self):
        base_url = "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066"
        apply_url = "https://jobs.lever.co/Fliff/b874a4eb-3fd2-48e9-a467-7dc24f586066/apply/?utm_source=linkedin"
        assert build_url_match_key(base_url, "lever") == build_url_match_key(apply_url, "lever")

        from src.project_files.models import JobListing

        j1 = JobListing(
            id="lever:Fliff:b874a4eb-3fd2-48e9-a467-7dc24f586066",
            title="Senior Backend Engineer",
            company="Fliff",
            company_slug="Fliff",
            source_url=normalize_job_url(base_url, "lever"),
            apply_url=apply_url,
            provider="lever",
            ats_source="lever",
            provider_job_id="b874a4eb-3fd2-48e9-a467-7dc24f586066",
            data_source="api",
            scraped_at=datetime.now(timezone.utc),
            query_used="engineer",
        )
        j2 = j1.model_copy(deep=True, update={"source_url": apply_url})
        dedup = GlobalDeduplicator()
        unique = dedup.deduplicate([j1, j2])
        assert len(unique) == 1
        assert unique[0].source_url == base_url
        assert unique[0].apply_url == apply_url

    @pytest.mark.anyio
    async def test_search_orchestrator_discovers_board_roots_and_enriches_apply_urls(
        self, tmp_path, monkeypatch
    ):
        db_file = str(tmp_path / "orch_test.sqlite")
        reg = CompanyBoardRegistry(db_path=db_file)
        cache = CacheStore(db_path=db_file)
        monkeypatch.setattr("src.project_files.search_pipeline.company_board_registry", reg)
        monkeypatch.setattr("src.project_files.search_pipeline.cache_store", cache)

        data_4775 = _load_api("api_4775e970.json")
        # Return 404/empty on board HTML so test remains offline
        def handler(request: httpx.Request) -> httpx.Response:
            req = str(request.url)
            if "api.lever.co/v0/postings/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9" in req:
                return httpx.Response(200, json=data_4775)
            return httpx.Response(404, text="Not found")

        orch = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board_res = await orch._enrich_ats_item(
                platform="lever",
                item={
                    "link": "https://jobs.lever.co/palantir?lever-via=59yrytAgmX&location=North%20America",
                    "title": "Palantir Jobs",
                    "snippet": "",
                },
                query_str="software engineer",
                client=client,
            )
            assert board_res is None
            cand = reg.get_board("lever", "palantir")
            assert cand is not None
            assert cand.board_url == "https://jobs.lever.co/palantir"

            apply_link = "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9/apply/"
            job_res = await orch._enrich_ats_item(
                platform="lever",
                item={"link": apply_link, "title": "Deployment Strategist", "snippet": ""},
                query_str="software engineer",
                client=client,
            )
            assert job_res is not None
            assert job_res.title == "Deployment Strategist - US Government"
            assert job_res.source_url == "https://jobs.lever.co/palantir/4775e970-ade8-4a0d-8145-9255dc4cbac9"
            assert job_res.apply_url == data_4775["applyUrl"]


class TestLeverUnifiedExtractionAndCompleteness:
    def test_palantir_no_opening_duplication_and_clean_markdown_lists(self):
        _, _, listing = _extract_via_client_payload("api_4775e970.json")
        assert listing.description is not None
        assert listing.description.count("World-Changing Company") == 1
        assert "Deployment Strategist role centers around leveraging data" in listing.description
        assert "The estimated salary range for this position is estimated to be $110,000 - $170,000/year" in listing.description
        # Consecutive bullet items must not inject blank lines between bullets
        import re as _re

        assert _re.search(r"(?m)^(?:- |\d+\. )[^\n]+\n\n(?:- |\d+\. )", listing.description) is None

    def test_spotify_lists_only_builds_authentic_description(self):
        raw, _, listing = _extract_via_client_payload("api_785989a6.json")
        assert raw.description_is_authentic is True
        assert listing.description is not None
        assert "What You’ll Do" in listing.description or "What You'll Do" in listing.description
        assert "Who You Are" in listing.description
        assert "Where You'll Be" in listing.description
        assert "equal opportunity employer" in listing.description.lower()

    def test_battery_network_html_only_description_and_lists_preserved(self):
        _, _, listing = _extract_via_client_payload("api_aeced5e0.json")
        assert listing.description is not None
        assert "Full Stack Microsoft Developer" in listing.description
        assert "CORE QUALIFICATIONS" in listing.description
        assert "WORKING CONDITIONS" in listing.description
        assert len(listing.description) > 4000

    def test_extreme_networks_preserves_additional_section_without_opening_duplication(self):
        _, _, listing = _extract_via_client_payload("api_c977b005.json")
        assert listing.description is not None
        assert listing.description.count("Over 50,000 customers globally") <= 2
        assert listing.description.count("They rely on our top-rated") == 1
        assert listing.description.count("Senior Software Engineer (GenAI, ML)") == 1
        assert "up to USD 170000 plus benefits" in listing.description
        assert "barrier" in listing.description.lower()

    @pytest.mark.anyio
    async def test_client_board_adapter_and_direct_probe_are_consistent(self):
        data = _load_api("api_4775e970.json")
        board = CompanyBoard(
            id=1,
            company_name="Palantir",
            company_slug="palantir",
            ats_provider="lever",
            board_token="palantir",
            board_url="https://jobs.lever.co/palantir",
            discovery_source="test",
            source_posting_url=None,
            first_discovered_at=1000.0,
            last_discovered_at=1000.0,
            verification_status="candidate",
            monitoring_capability="supported",
        )

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "mode=json" in u or u.endswith("/postings/palantir"):
                return httpx.Response(200, json=[data])
            if f"/postings/palantir/{data['id']}" in u:
                return httpx.Response(200, json=data)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            client_res = await LeverClient().fetch_raw_result(
                ParsedATSUrl(ats="lever", company_slug="palantir", job_id=data["id"], raw_url=data["hostedUrl"]),
                client,
            )
            client_listing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(client_res.raw))
            board_res = await LeverBoardAdapter().check_board(board, client)
            probed_listings = await probe_lever_board("palantir", client)

        assert board_res.success and len(board_res.listings) == 1
        assert len(probed_listings) == 1
        adapter_listing = board_res.listings[0]
        probe_listing = probed_listings[0]

        for candidate in (adapter_listing, probe_listing):
            assert candidate.description == client_listing.description
            assert candidate.requirements == client_listing.requirements
            assert candidate.salary == client_listing.salary
            assert candidate.eligibility is not None
            assert candidate.eligibility.physical_location_country == client_listing.eligibility.physical_location_country

    @pytest.mark.anyio
    async def test_board_monitor_never_overwrites_richer_cache_fields(self, tmp_path):
        db_file = str(tmp_path / "monitor_preserve.sqlite")
        reg = CompanyBoardRegistry(db_path=db_file)
        cache = CacheStore(db_path=db_file)
        monitor = BoardMonitor(registry=reg)
        reg.register_candidate(
            company_name="Turning Point Global Solutions",
            ats_provider="lever",
            board_token="tpgsi",
            board_url="https://jobs.lever.co/tpgsi",
            company_logo_url="https://lever-client-logos.s3.us-west-2.amazonaws.com/5bb51c4c-37a1-40b2-814c-07e7c36f3d3e-1726437189818.png",
            company_logo_source="lever_main_header_logo",
            company_logo_verified=True,
        )

        # Pre-seed rich cached listing with verified logo and salary
        tpgsi_data = _load_api("api_1cb2b7f2.json")
        rich_raw_payload = dict(tpgsi_data)
        rich_raw_payload["salaryRange"] = {
            "min": 130000,
            "max": 160000,
            "currency": "USD",
            "interval": "per-year-salary",
        }
        from src.project_files.ats_api_client import lever_payload_to_raw

        rich_job = CanonicalJobAdapter.to_listing(
            JobExtractionService.extract(
                lever_payload_to_raw(rich_raw_payload, company_slug="tpgsi", default_company_name="Turning Point Global Solutions")
            )
        )
        rich_job.company_logo_url = "https://lever-client-logos.s3.us-west-2.amazonaws.com/5bb51c4c-37a1-40b2-814c-07e7c36f3d3e-1726437189818.png"
        rich_job.company_logo_source = "lever_main_header_logo"
        rich_job.company_logo_verified = True
        cache.set_url_cache(tpgsi_data["hostedUrl"], rich_job)

        # Now monitor fetches an unverified partial copy (no salary in feed)
        partial_item = dict(tpgsi_data)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[partial_item]) if "api.lever.co" in str(req.url) else httpx.Response(404))) as client:
            monitored = await monitor.poll_due_boards(max_boards=5, client=client, cache_store=cache)

        assert len(monitored) == 1
        after = cache.get_url_cache(tpgsi_data["hostedUrl"])
        assert after is not None
        assert after.company_logo_url == rich_job.company_logo_url
        assert after.company_logo_verified is True
        assert after.salary is not None and after.salary.minimum == 130000


class TestLeverRequirementsExtraction:
    def test_battery_network_separates_qualifications_from_duties_and_working_conditions(self):
        _, _, listing = _extract_via_client_payload("api_aeced5e0.json")
        req = listing.requirements
        assert req is not None
        assert "CORE QUALIFICATIONS" in req
        assert "PREFERRED QUALIFICATIONS" in req
        assert "SKILLS, KNOWLEDGE, & EXPERIENCE" in req
        assert "MAJOR DUTIES AND RESPONSIBILITIES" not in req
        assert "WORKING CONDITIONS" not in req
        assert "ABOUT THE BATTERY NETWORK" not in req

    def test_tpgsi_and_allata_extract_structured_lists_only_for_qualifications(self):
        _, _, tpgsi = _extract_via_client_payload("api_1cb2b7f2.json")
        assert tpgsi.requirements is not None
        assert "What We’re Looking For" in tpgsi.requirements or "What We're Looking For" in tpgsi.requirements
        assert "What You’ll Do" not in tpgsi.requirements
        assert "What’s in It For You" not in tpgsi.requirements

        _, _, allata = _extract_via_client_payload("api_b5b03a21.json")
        assert allata.requirements is not None
        assert "Hard Skills - Must have" in allata.requirements
        assert "Hard Skills - Nice to have" in allata.requirements
        assert "Soft Skills" in allata.requirements
        assert "Role & Responsibilities" not in allata.requirements

    def test_muttdata_separates_required_skills_from_perks_and_responsibilities(self):
        _, _, mutt = _extract_via_client_payload("api_624ad7e8.json")
        assert mutt.requirements is not None
        assert "Required Skills" in mutt.requirements
        assert "Responsibilities" not in mutt.requirements
        assert "Perks" not in mutt.requirements
        assert "work from anywhere" not in mutt.requirements.lower()

    def test_extreme_networks_no_lists_falls_back_to_prose_requirements(self):
        _, _, extreme = _extract_via_client_payload("api_c977b005.json")
        assert extreme.requirements is not None
        assert "python" in extreme.requirements.lower() or "experience" in extreme.requirements.lower()


class TestLeverEligibilityAndGeography:
    def test_country_code_flows_from_lever_api_into_eligibility(self):
        _, _, loft = _extract_via_client_payload("api_78ddafc0.json")
        assert loft.eligibility is not None
        assert loft.eligibility.physical_location_country == "United States"
        assert loft.eligibility.nigeria_eligible is False

        _, _, spotify_multi = _extract_via_client_payload("api_9f66e598.json")
        assert spotify_multi.eligibility is not None
        assert spotify_multi.eligibility.physical_location_country == "United Kingdom"
        assert spotify_multi.eligibility.nigeria_eligible is not True

    @pytest.mark.parametrize(
        ("location_text", "expected_country"),
        [
            ("Alameda, CA", "United States"),
            ("Foster City, CA", "United States"),
            ("San Francisco, CA", "United States"),
            ("Toronto, ON, Canada", "Canada"),
            ("Canada", "Canada"),
        ],
    )
    def test_ca_us_state_disambiguation_vs_canada(self, location_text: str, expected_country: str):
        elig = extract_eligibility(
            provider="lever",
            work_model="in_person",
            location=location_text,
            raw_location=location_text,
            description="Standard engineering role in our office.",
            raw_fields={},
        )
        assert elig is not None
        assert elig.physical_location_country == expected_country

    def test_muttdata_perks_work_from_anywhere_does_not_trigger_global_remote_or_nigeria_eligible(self):
        _, _, mutt = _extract_via_client_payload("api_624ad7e8.json")
        assert mutt.eligibility is not None
        assert mutt.eligibility.physical_location_country == "Argentina"
        assert mutt.eligibility.global_remote_explicit is not True
        assert mutt.eligibility.nigeria_eligible is False


class TestLeverSalaryExtraction:
    def test_structured_salary_range_preferred_and_cfs_tier_prose_not_collapsed(self):
        _, _, loft = _extract_via_client_payload("api_78ddafc0.json")
        assert loft.salary is not None
        assert (loft.salary.minimum, loft.salary.maximum, loft.salary.currency, loft.salary.period) == (
            150000,
            195000,
            "USD",
            "year",
        )

        _, _, cfs = _extract_via_client_payload("api_faa295da.json")
        assert cfs.salary is not None
        assert (cfs.salary.minimum, cfs.salary.maximum, cfs.salary.currency, cfs.salary.period) == (
            25,
            38,
            "USD",
            "hour",
        )
        assert (
            parse_text_salary(
                "For BS interns, the hourly rate is $25–$32\nFor MS/PhD interns, the hourly rate is $30–$38"
            )
            is None
        )

    def test_extreme_networks_up_to_upper_bound_only(self):
        _, _, extreme = _extract_via_client_payload("api_c977b005.json")
        assert extreme.salary is not None
        assert extreme.salary.minimum is None
        assert extreme.salary.maximum == 170000
        assert extreme.salary.currency == "USD"
        assert extreme.salary.period is None

    def test_jobgether_bold_cad_annual_range_and_mendix_period_none(self):
        _, _, jg = _extract_via_client_payload("api_8ae01813.json")
        assert jg.salary is not None
        assert (jg.salary.minimum, jg.salary.maximum, jg.salary.currency, jg.salary.period) == (
            160000,
            185000,
            "CAD",
            "year",
        )

        _, _, mendix = _extract_via_client_payload("api_925a47b7.json")
        assert mendix.salary is not None
        assert (mendix.salary.minimum, mendix.salary.maximum, mendix.salary.currency, mendix.salary.period) == (
            125300,
            250600,
            "USD",
            None,
        )

    @pytest.mark.anyio
    async def test_penumbra_bold_salary_and_alameda_ca_from_html_fixture(self, monkeypatch):
        monkeypatch.setattr("src.project_files.ats_page_enricher.cache_store.get_url_cache", lambda *_: None)
        monkeypatch.setattr("src.project_files.ats_page_enricher.cache_store.set_url_cache", lambda *_: None)
        pen_url = "https://jobs.lever.co/penumbrainc/42be630d-d9d1-41fd-b9f7-ffae5a08844c"
        html_text = _load_html("html_42be630d.html")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=html_text, request=req))
        ) as client:
            job, res = await enrich_ats_page_result(pen_url, "lever", "", "", "full stack", client)

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert job is not None
        assert job.salary is not None
        assert (job.salary.minimum, job.salary.maximum, job.salary.currency) == (95000, 145000, "USD")
        assert job.salary.raw_text is not None and not job.salary.raw_text.endswith("**")
        assert job.eligibility is not None
        assert job.eligibility.physical_location_country == "United States"

    def test_strada_pay_label_and_rejection_of_per_diem_meal_allowance_and_zeros(self):
        _, _, strada = _extract_via_client_payload("api_7e9da32d.json")
        assert strada.salary is not None
        assert strada.salary.currency == "USD"
        assert strada.salary.period == "hour"
        assert strada.salary.minimum == 23
        assert strada.salary.maximum == 25

        # Per-diem meal & home office allowance in Jobgether Brazil must NOT parse as salary
        _, _, brazil = _extract_via_client_payload("api_fad6ad02.json")
        assert brazil.salary is None

        # Structured zero/zero range rejected
        zero_payload = {"salaryRange": {"min": 0, "max": 0, "currency": "USD", "interval": "per-year-salary"}}
        assert extract_salary("lever", zero_payload, description="Benefits apply.") is None


class TestLeverLogoAndAuthoritativeCompanyName:
    def test_logo_extractor_accepts_tpgsi_and_penumbra_and_rejects_zoox_generic_refresh(self):
        tpgsi_soup = BeautifulSoup(_load_html("html_1cb2b7f2.html"), "lxml")
        res_tpgsi = extract_company_logo_for_provider(
            "lever",
            soup=tpgsi_soup,
            page_url="https://jobs.lever.co/tpgsi/1cb2b7f2-506b-4cb2-8d59-bc6e4771363f",
            company_name="Turning Point Global Solutions",
        )
        assert res_tpgsi.verified is True
        assert res_tpgsi.url == "https://lever-client-logos.s3.us-west-2.amazonaws.com/5bb51c4c-37a1-40b2-814c-07e7c36f3d3e-1726437189818.png"

        zoox_job_soup = BeautifulSoup(_load_html("html_9176aa65.html"), "lxml")
        res_zoox_job = extract_company_logo_for_provider(
            "lever",
            soup=zoox_job_soup,
            page_url="https://jobs.lever.co/zoox/9176aa65-14e3-4f9d-98f9-e755e9777d67",
            company_name="Zoox",
        )
        assert res_zoox_job.url is None
        assert res_zoox_job.verified is False

        zoox_board_soup = BeautifulSoup(_load_html("board_zoox.html"), "lxml")
        res_zoox_board = extract_company_logo_for_provider(
            "lever",
            soup=zoox_board_soup,
            page_url="https://jobs.lever.co/zoox",
            company_name="Zoox",
        )
        assert res_zoox_board.url is None
        assert res_zoox_board.verified is False

    @pytest.mark.anyio
    async def test_bounded_board_identity_enrichment_uses_authoritative_name_and_logo_with_cache(
        self, tmp_path
    ):
        from src.project_files.ats_api_client import enrich_lever_board_identity

        db_file = str(tmp_path / "board_logo.sqlite")
        reg = CompanyBoardRegistry(db_path=db_file)
        board_tpgsi_html = _load_html("board_tpgsi.html")
        board_zoox_html = _load_html("board_zoox.html")
        fetches: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            fetches.append(u)
            if u.rstrip("/") == "https://jobs.lever.co/tpgsi":
                return httpx.Response(200, text=board_tpgsi_html)
            if u.rstrip("/") == "https://jobs.lever.co/zoox":
                return httpx.Response(200, text=board_zoox_html)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            name1, logo1 = await enrich_lever_board_identity("tpgsi", client, registry=reg)
            # Second call for same board must hit cached registry state without another HTTP fetch
            name2, logo2 = await enrich_lever_board_identity("tpgsi", client, registry=reg)
            # Zoox board has no logo -> negative-cached without fabricating a logo
            z_name, z_logo = await enrich_lever_board_identity("zoox", client, registry=reg)
            z_name2, z_logo2 = await enrich_lever_board_identity("zoox", client, registry=reg)

        assert fetches.count("https://jobs.lever.co/tpgsi") == 1
        assert fetches.count("https://jobs.lever.co/zoox") == 1
        assert name1 == "Turning Point Global Solutions"
        assert name2 == "Turning Point Global Solutions"
        assert logo1.verified is True and logo1.url == logo2.url
        assert z_name == "Zoox"
        assert z_logo.url is None and z_logo.verified is False
        assert z_logo2.url is None

        # Dedup protection: unverified/null donor never clears verified logo
        from src.project_files.models import JobListing

        with_logo = JobListing(
            id="lever:tpgsi:1",
            provider="lever",
            data_source="api",
            ats_source="lever",
            title="Engineer",
            company="Turning Point Global Solutions",
            apply_url="https://jobs.lever.co/tpgsi/1/apply",
            source_url="https://jobs.lever.co/tpgsi/1",
            company_logo_url=logo1.url,
            company_logo_source=logo1.source,
            company_logo_verified=True,
            scraped_at=datetime.now(timezone.utc),
            query_used="engineer",
        )
        no_logo = with_logo.model_copy(
            deep=True,
            update={"company_logo_url": None, "company_logo_source": None, "company_logo_verified": False},
        )
        assert merge_listings(with_logo, no_logo).company_logo_url == logo1.url

    @pytest.mark.anyio
    async def test_html_fallback_extracts_penumbra_logo_salary_and_leaves_zoox_logo_null(self):
        from src.project_files.ats_page_enricher import enrich_ats_page_result

        pen_html = _load_html("html_42be630d.html")
        zoox_html = _load_html("html_9176aa65.html")

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            if "42be630d" in u:
                return httpx.Response(200, text=pen_html)
            if "9176aa65" in u:
                return httpx.Response(200, text=zoox_html)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            pen_job, _ = await enrich_ats_page_result(
                url="https://jobs.lever.co/penumbra/42be630d-d9d1-41fd-b9f7-ffae5a08844c",
                provider="lever",
                search_title="IT Full Stack Developer",
                snippet="",
                query_used="developer",
                client=client,
            )
            zoox_job, _ = await enrich_ats_page_result(
                url="https://jobs.lever.co/zoox/9176aa65-14e3-4f9d-98f9-e755e9777d67",
                provider="lever",
                search_title="Engineer",
                snippet="",
                query_used="engineer",
                client=client,
            )

        assert pen_job is not None
        assert pen_job.company == "Penumbra"
        assert pen_job.company_logo_verified is True
        assert pen_job.company_logo_url is not None and "lever-client-logos" in pen_job.company_logo_url
        assert pen_job.salary is not None
        assert (pen_job.salary.minimum, pen_job.salary.maximum, pen_job.salary.currency) == (95000, 145000, "USD")

        assert zoox_job is not None
        assert zoox_job.company_logo_url is None
        assert zoox_job.company_logo_verified is False


class TestLeverMultiLocationSupport:
    def test_spotify_all_locations_preserved(self):
        _, _, spotify = _extract_via_client_payload("api_9f66e598.json")
        assert spotify.location is not None
        assert "London" in spotify.location
        assert "Stockholm" in spotify.location

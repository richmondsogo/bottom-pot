"""
Step 37 Greenhouse Quality Pipeline tests (Milestones 1-11).
Grounded strictly in genuine captured fixtures under tests/fixtures/real/greenhouse/.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from src.project_files.ats_api_client import GreenhouseClient
from src.project_files.ats_page_enricher import enrich_ats_page_result
from src.project_files.ats_url_parser import parse_ats_url
from src.project_files.company_board_registry import CompanyBoardRegistry
from src.project_files.deduplicator import extract_id_match_key, listings_match
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.models import JobListing, SearchParams
from src.project_files.search_pipeline import SearchOrchestrator

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "real" / "greenhouse"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _load_html(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestMilestone2DiscoveryAndCanonicalisation:
    @pytest.mark.anyio
    async def test_corasps_hyphenated_id_api_lookup_canonical_identity_and_dedup(self):
        payload = _load_json("api_corasps_5131342007_8.json")
        serper_url = "https://job-boards.greenhouse.io/corasps/jobs/5131342007-8"
        parsed = parse_ats_url(serper_url)
        assert parsed is not None
        assert parsed.job_id == "5131342007-8"

        requested_urls: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requested_urls.append(str(req.url))
            return httpx.Response(200, json=payload)

        client_obj = GreenhouseClient()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            listing, res = await client_obj.fetch_result(parsed, http)

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        # API lookup preserves the full hyphenated ID as found on the public endpoint
        assert requested_urls == [
            "https://boards-api.greenhouse.io/v1/boards/corasps/jobs/5131342007-8?pay_transparency=true"
        ]
        # Real API response establishes canonical ID 5131342007 & absolute_url
        assert listing.source_record_id == "greenhouse:corasps:5131342007"
        assert listing.id == "greenhouse:corasps:5131342007"
        assert listing.apply_url == "https://job-boards.greenhouse.io/corasps/jobs/5131342007"

        # Deduplicates identically with a board-monitor listing whose item.id is 5131342007
        monitor_listing = JobListing(
            id="greenhouse:corasps:5131342007",
            source_record_id="greenhouse:corasps:5131342007",
            provider="greenhouse",
            company_slug="corasps",
            title="Full Stack Developer",
            company="Coras, An AtkinsRéalis Company",
            apply_url="https://job-boards.greenhouse.io/corasps/jobs/5131342007",
            source_url="https://job-boards.greenhouse.io/corasps/jobs/5131342007",
            data_source="api",
            ats_source="greenhouse",
            query_used="",
            scraped_at=datetime.now(timezone.utc),
        )
        assert extract_id_match_key(listing) == extract_id_match_key(monitor_listing)
        assert listings_match(listing, monitor_listing) is True

    @pytest.mark.anyio
    async def test_search_pipeline_canonicalizes_http_greenhouse_registers_board_root_and_rejects_arbitrary_custom_domain(
        self, tmp_path, monkeypatch
    ):
        from src.project_files import search_pipeline as sp_mod

        registry = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        monkeypatch.setattr(sp_mod, "company_board_registry", registry)
        monkeypatch.setattr(sp_mod.cache_store, "get_url_cache", lambda _u: None)
        monkeypatch.setattr(sp_mod.cache_store, "set_url_cache", lambda _u, _l, **kw: None)

        eu_payload = _load_json("api_cognite_5016416101.json")
        requested_urls: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            requested_urls.append(str(req.url))
            return httpx.Response(200, json=eu_payload)

        pipeline = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            # 1) Recognized http:// EU Greenhouse URL -> upgraded to HTTPS, NEVER fetched over http://
            listing = await pipeline._enrich_ats_item(
                platform="greenhouse",
                item={
                    "link": "http://job-boards.eu.greenhouse.io/cognite/jobs/5016416101",
                    "title": "Machine Learning Engineer at Cognite",
                    "snippet": "Apply now",
                },
                query_str="machine learning",
                client=http,
            )
            assert listing is not None
            assert listing.source_url.startswith("https://")
            assert all(u.startswith("https://") for u in requested_urls)

            # 2) Valid Greenhouse board root -> registers candidate board, returns None (no fabricated job)
            root_listing = await pipeline._enrich_ats_item(
                platform="greenhouse",
                item={
                    "link": "http://job-boards.greenhouse.io/discord",
                    "title": "Jobs at Discord",
                    "snippet": "Explore careers",
                },
                query_str="machine learning",
                client=http,
            )
            assert root_listing is None
            discord_board = registry.get_board("greenhouse", "discord")
            assert discord_board is not None
            assert discord_board.board_url == "https://boards.greenhouse.io/discord"

            # 3) Unverified arbitrary custom domain with ?gh_jid= -> dropped cleanly without network call
            count_before = len(requested_urls)
            custom_listing = await pipeline._enrich_ats_item(
                platform="greenhouse",
                item={
                    "link": "https://unverified-custom.example.com/careers?gh_jid=8140140",
                    "title": "Software Engineer",
                    "snippet": "Careers",
                },
                query_str="software engineer",
                client=http,
            )
            assert custom_listing is None
            assert len(requested_urls) == count_before

            # 4) Arbitrary non-Greenhouse http:// URL still dropped cleanly
            other_http = await pipeline._enrich_ats_item(
                platform="greenhouse",
                item={
                    "link": "http://other-site.example.com/jobs/123",
                    "title": "Engineer",
                    "snippet": "...",
                },
                query_str="engineer",
                client=http,
            )
            assert other_http is None


class TestMilestone3ExpiredRedirectHandling:
    @pytest.mark.anyio
    async def test_gitlab_expired_redirect_returns_not_found_and_closes_monitored_job(self, tmp_path, monkeypatch):
        from src.project_files import cache_store as cs_mod

        monkeypatch.setattr(cs_mod.cache_store, "get_url_cache", lambda _u: None)
        expired_html = _load_html("html_gitlab_expired_8860302002.html")
        expired_job_url = "https://job-boards.greenhouse.io/gitlab/jobs/8860302002"

        registry = CompanyBoardRegistry(db_path=str(tmp_path / "boards.sqlite"))
        board = registry.register_candidate(
            ats_provider="greenhouse",
            board_token="gitlab",
            company_name="GitLab",
            source_url=expired_job_url,
        )
        assert board is not None
        active_job = JobListing(
            id="greenhouse:gitlab:8860302002",
            source_record_id="greenhouse:gitlab:8860302002",
            provider="greenhouse",
            company_slug="gitlab",
            title="Senior Backend Engineer",
            company="GitLab",
            source_url=expired_job_url,
            apply_url=expired_job_url,
            data_source="api",
            ats_source="greenhouse",
            query_used="backend",
            scraped_at=datetime.now(timezone.utc),
        )
        assert registry.upsert_monitored_job(active_job, board_id=board.id) is True

        def handler(req: httpx.Request) -> httpx.Response:
            if str(req.url) == expired_job_url:
                return httpx.Response(
                    302,
                    headers={"Location": "https://job-boards.greenhouse.io/gitlab?error=true"},
                )
            return httpx.Response(200, text=expired_html, headers={"content-type": "text/html; charset=utf-8"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            listing, res = await enrich_ats_page_result(
                url=expired_job_url,
                provider="greenhouse",
                search_title="GitLab job",
                snippet="",
                query_used="backend",
                client=http,
                board_registry=registry,
            )

        assert listing is None
        assert res.outcome == ExtractionOutcome.NOT_FOUND

        with registry._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM monitored_jobs WHERE job_id = ?",
                ("greenhouse:gitlab:8860302002",),
            ).fetchone()
        assert row is not None and row[0] == "closed"


class TestMilestone4UnifiedExtraction:
    @pytest.mark.anyio
    async def test_greenhouse_payload_to_raw_unifies_client_adapter_and_direct_board_router(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.board_adapters import GreenhouseBoardAdapter
        from src.project_files.company_board_registry import CompanyBoard
        from src.project_files.direct_board_router import probe_greenhouse_board

        discord_item = _load_json("api_discord_8910013002.json")
        schonfeld_item = _load_json("api_schonfeld_8311595.json")
        # Ensure live captured Schonfeld sample retains trailing whitespace in raw company_name
        assert schonfeld_item["company_name"] == "Schonfeld "

        raw_discord = greenhouse_payload_to_raw(discord_item, company_slug="discord")
        assert raw_discord is not None
        assert raw_discord.raw_company == "Discord"

        requested_urls: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            u = str(req.url)
            requested_urls.append(u)
            if "/boards/discord/jobs?" in u:
                return httpx.Response(200, json={"jobs": [discord_item]})
            if "/boards/discord/jobs/8910013002" in u:
                return httpx.Response(200, json=discord_item)
            if "/boards/schonfeld/jobs?" in u:
                return httpx.Response(200, json={"jobs": [schonfeld_item]})
            return httpx.Response(404)

        client_obj = GreenhouseClient()
        adapter = GreenhouseBoardAdapter()
        discord_board = CompanyBoard(
            id=1,
            company_name="discord",  # lower/raw slug-like name should yield to item.company_name "Discord"
            company_slug="discord",
            ats_provider="greenhouse",
            board_token="discord",
            board_url="https://boards.greenhouse.io/discord",
            discovery_source="test",
            source_posting_url=None,
            first_discovered_at=1000.0,
            last_discovered_at=1000.0,
            verification_status="candidate",
            monitoring_capability="supported",
        )
        parsed_discord = parse_ats_url("https://job-boards.greenhouse.io/discord/jobs/8910013002")
        assert parsed_discord is not None

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client_listing, client_res = await client_obj.fetch_result(parsed_discord, http)
            board_res = await adapter.check_board(discord_board, http)
            probe_listings = await probe_greenhouse_board("discord", http)
            schonfeld_probe = await probe_greenhouse_board("schonfeld", http)

        assert client_res.outcome == ExtractionOutcome.SUCCESS and client_listing is not None
        assert board_res.success and len(board_res.listings) == 1
        assert len(probe_listings) == 1
        assert len(schonfeld_probe) == 1

        board_listing = board_res.listings[0]
        probe_listing = probe_listings[0]

        # Adapter and router both request content=true and pay_transparency=true
        adapter_urls = [u for u in requested_urls if "/boards/discord/jobs?" in u]
        assert len(adapter_urls) == 2
        assert all("content=true" in u and "pay_transparency=true" in u for u in adapter_urls)

        # Core canonical fields match across Client, BoardAdapter, and DirectBoardRouter
        for candidate in (client_listing, board_listing, probe_listing):
            assert candidate.id == "greenhouse:discord:8910013002"
            assert candidate.company == "Discord"
            assert candidate.title == discord_item["title"].strip()
            assert candidate.description_ok is True
            assert candidate.description == client_listing.description
            assert candidate.posted_at == client_listing.posted_at
            assert candidate.work_model == client_listing.work_model
            assert candidate.salary == client_listing.salary

        # Schonfeld trailing whitespace normalized away
        assert schonfeld_probe[0].company == "Schonfeld"

    @pytest.mark.anyio
    async def test_greenhouse_board_adapter_fingerprint_includes_version_and_pay_ranges(self):
        from src.project_files.board_adapters import GreenhouseBoardAdapter
        from src.project_files.company_board_registry import CompanyBoard

        adapter = GreenhouseBoardAdapter()
        base_item = _load_json("api_discord_8910013002.json")
        item_no_pay = dict(base_item)
        item_no_pay["pay_input_ranges"] = []

        board = CompanyBoard(
            id=1,
            company_name="Discord",
            company_slug="discord",
            ats_provider="greenhouse",
            board_token="discord",
            board_url="https://boards.greenhouse.io/discord",
            discovery_source="test",
            source_posting_url=None,
            first_discovered_at=1000.0,
            last_discovered_at=1000.0,
            verification_status="candidate",
            monitoring_capability="supported",
        )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"jobs": [item_no_pay]}))
        ) as http:
            res1 = await adapter.check_board(board, http)

        assert res1.success and res1.content_fingerprint is not None
        assert res1.content_fingerprint.startswith("v37:")

        # Adding pay_input_ranges MUST change fingerprint & return updated listings (not 304/not_modified)
        board.content_fingerprint = res1.content_fingerprint
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"jobs": [base_item]}))
        ) as http:
            res2 = await adapter.check_board(board, http)

        assert res2.success and res2.not_modified is False
        assert res2.content_fingerprint != res1.content_fingerprint
        assert len(res2.listings) == 1

    @pytest.mark.anyio
    async def test_probe_greenhouse_board_does_not_fabricate_posted_at_from_updated_at(self):
        from src.project_files.direct_board_router import probe_greenhouse_board

        item = {
            "id": 999,
            "title": "Backend Engineer",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/999",
            "location": {"name": "Remote, US"},
            "updated_at": "2026-10-15T12:00:00Z",
            "content": (
                "<p>Build distributed systems for our core platform team in production, design fault-tolerant "
                "APIs, collaborate across product engineering groups, and scale low-latency data pipelines "
                "serving millions of global requests every day with strong observability, automated testing, "
                "clear incident runbooks, and thoughtful architectural documentation across services.</p>"
            ),
        }
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"jobs": [item]}))
        ) as http:
            jobs = await probe_greenhouse_board("acme", http)

        assert len(jobs) == 1
        assert jobs[0].posted_at is None
        assert jobs[0].description_ok is True


class TestMilestone5Requirements:
    """Milestone 5: Greenhouse requirements extraction and stop headings."""

    def test_gitlab_what_youll_bring_extraction(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_gitlab_8771512002.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="gitlab", query_used="gitlab")
        canonical = JobExtractionService.extract(raw)

        assert canonical.requirements is not None
        reqs = canonical.requirements
        assert "professional experience" in reqs.lower()
        # Ensure stop headings pruned non-requirement sections
        assert "How GitLab Supports Full-Time Employees" not in reqs
        assert "Country Hiring Guidelines" not in reqs
        assert "Privacy Policy" not in reqs

    def test_databricks_what_we_look_for_extraction(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_databricks_8923831002.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="databricks", query_used="databricks")
        canonical = JobExtractionService.extract(raw)

        assert canonical.requirements is not None
        reqs = canonical.requirements
        assert "What we look for" in reqs or "experience" in reqs.lower()
        assert "Pay Range Transparency" not in reqs
        assert "About Databricks" not in reqs

    def test_figma_we_would_love_to_hear_extraction(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_figma_6238015004.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="figma", query_used="figma")
        canonical = JobExtractionService.extract(raw)

        assert canonical.requirements is not None
        reqs = canonical.requirements
        assert "Pay Transparency Disclosure" not in reqs
        assert "Application limits" not in reqs

    def test_spacex_basic_qualifications_extraction(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_spacex_8769729002.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="spacex", query_used="spacex")
        canonical = JobExtractionService.extract(raw)

        assert canonical.requirements is not None
        reqs = canonical.requirements
        assert "COMPENSATION AND BENEFITS" not in reqs
        assert "ITAR REQUIREMENTS" not in reqs

    def test_corasps_ideal_candidate_extraction(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_corasps_5131342007_8.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="corasps", query_used="corasps")
        canonical = JobExtractionService.extract(raw)

        assert canonical.requirements is not None
        reqs = canonical.requirements
        assert "Why join Coras" not in reqs


class TestMilestone6WorkModel:
    """Milestone 6: Greenhouse work model precision."""

    def test_spacex_negated_remote_hybrid_resolves_to_in_person(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.canonical_job_adapter import CanonicalJobAdapter
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_spacex_8769729002.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="spacex", query_used="spacex")
        canonical = JobExtractionService.extract(raw)
        listing = CanonicalJobAdapter.to_listing(canonical)

        assert canonical.work_model == "in_person"
        assert listing.is_remote is False

    def test_okta_li_hybrid_with_spaces_and_hyphen(self):
        from src.project_files.work_model import resolve_work_model, strip_li_tags

        desc = "<p>Join our team. #LI - Hybrid</p><p>We build great products.</p>"
        res = resolve_work_model(trusted_description=desc)
        assert res.value == "hybrid"
        assert res.source == "li_tag"

        stripped = strip_li_tags(desc)
        assert "#LI - Hybrid" not in stripped

    def test_checkr_3_plus_days_a_week_in_office(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_checkr_8369164.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="checkr", query_used="checkr")
        canonical = JobExtractionService.extract(raw)

        assert canonical.work_model == "hybrid"

    def test_excel_sports_management_3_days_a_week(self):
        from src.project_files.field_normalizer import to_markdown
        from src.project_files.work_model import resolve_work_model

        fixture_path = FIXTURES_DIR / "cached_excelsportsmanagement_4747594005.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        desc = to_markdown(data.get("description", ""))
        res = resolve_work_model(description=desc, trusted_description=desc)
        assert res.value == "hybrid"


class TestMilestone7Eligibility:
    """Milestone 7: Greenhouse geographic and employment eligibility precision."""

    def test_figma_product_copy_not_flagged_as_global_remote(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_figma_6238015004.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="figma", query_used="figma")
        canonical = JobExtractionService.extract(raw)

        assert canonical.eligibility is not None
        assert canonical.eligibility.global_remote_explicit is not True
        assert canonical.eligibility.nigeria_eligible is not True

    def test_reddit_ccpa_disclaimer_not_flagged_as_contractor(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_reddit_8304463.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="reddit", query_used="reddit")
        canonical = JobExtractionService.extract(raw)

        assert canonical.eligibility is not None
        assert canonical.eligibility.employment_arrangement != "contractor"

    def test_walkersands_b2b_marketing_not_flagged_as_contractor(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_walkersands_8331140.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="walkersands", query_used="walkersands")
        canonical = JobExtractionService.extract(raw)

        assert canonical.eligibility is not None
        assert canonical.eligibility.employment_arrangement != "contractor"

    def test_nortal_latam_restricted_location(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_nortal_5286444007.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="nortal", query_used="nortal")
        canonical = JobExtractionService.extract(raw)

        assert canonical.eligibility is not None
        assert canonical.eligibility.global_remote_explicit is not True
        assert canonical.eligibility.nigeria_eligible is not True


class TestMilestone8Salary:
    """Milestone 8: Greenhouse salary fidelity and guardrails."""

    def test_greenhouse_pay_input_ranges_clean_raw_text(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_gitlab_8771512002.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="gitlab", query_used="gitlab")
        canonical = JobExtractionService.extract(raw)

        assert canonical.salary is not None
        assert canonical.salary.minimum == 115200
        assert canonical.salary.maximum == 162000
        assert canonical.salary.currency == "USD"
        assert canonical.salary.period is None
        assert "<a class=" not in (canonical.salary.raw_text or "")

    def test_excel_sports_management_hourly_description_salary(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "cached_excelsportsmanagement_4747594005.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="excelsportsmanagement", query_used="excelsportsmanagement")
        canonical = JobExtractionService.extract(raw)

        assert canonical.salary is not None
        assert canonical.salary.minimum == 17
        assert canonical.salary.maximum == 17
        assert canonical.salary.currency == "USD"
        assert canonical.salary.period == "hour"

    def test_schonfeld_between_range_salary(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "cached_schonfeld_8171694.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="schonfeld", query_used="schonfeld")
        canonical = JobExtractionService.extract(raw)

        assert canonical.salary is not None
        assert canonical.salary.minimum == 100000
        assert canonical.salary.maximum == 110000
        assert canonical.salary.currency == "USD"
        assert canonical.salary.period == "year"

    def test_spacex_multi_level_preserves_none_salary(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_spacex_8643277002_levels.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="spacex", query_used="spacex")
        canonical = JobExtractionService.extract(raw)

        # Multi-level salary without single tier must resolve to None
        assert canonical.salary is None

    def test_twilio_canada_bare_dollar_is_unresolved_currency(self):
        from src.project_files.ats_api_client import greenhouse_payload_to_raw
        from src.project_files.job_extraction_service import JobExtractionService

        fixture_path = FIXTURES_DIR / "api_twilio_8258581.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw = greenhouse_payload_to_raw(data, company_slug="twilio", query_used="twilio")
        canonical = JobExtractionService.extract(raw)

        assert canonical.salary is not None
        assert canonical.salary.minimum == 160320
        assert canonical.salary.maximum == 200400
        assert canonical.salary.currency is None


class TestMilestone9LogosAndBoardIdentity:
    """Milestone 9: Greenhouse CDN employer logo extraction and authoritative board identity."""

    def test_discord_logo_extraction(self):
        from bs4 import BeautifulSoup
        from src.project_files.logo_extractor import extract_company_logo_for_provider

        fixture_path = FIXTURES_DIR / "html_discord_8910013002.html"
        html_content = fixture_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        res = extract_company_logo_for_provider(
            "greenhouse",
            soup=soup,
            page_url="https://job-boards.greenhouse.io/discord/jobs/8910013002",
            company_name="Discord",
        )
        assert res.url is not None
        assert "external_greenhouse_job_boards/logos" in res.url
        assert res.verified is True
        assert res.source == "greenhouse_cdn_logo"

    def test_cognite_logo_extraction(self):
        from bs4 import BeautifulSoup
        from src.project_files.logo_extractor import extract_company_logo_for_provider

        fixture_path = FIXTURES_DIR / "html_cognite_5016416101.html"
        html_content = fixture_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        res = extract_company_logo_for_provider(
            "greenhouse",
            soup=soup,
            page_url="https://job-boards.greenhouse.io/cognite/jobs/5016416101",
            company_name="Cognite",
        )
        assert res.url is not None
        assert "external_greenhouse_job_boards/logos" in res.url
        assert res.verified is True
        assert res.source == "greenhouse_cdn_logo"

    def test_canonical_unbranded_board_has_no_logo(self):
        from bs4 import BeautifulSoup
        from src.project_files.logo_extractor import extract_company_logo_for_provider

        fixture_path = FIXTURES_DIR / "board_canonical.html"
        html_content = fixture_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        res = extract_company_logo_for_provider(
            "greenhouse",
            soup=soup,
            page_url="https://job-boards.greenhouse.io/canonical_managed_posts",
            company_name="Canonical",
        )
        assert res.url is None
        assert res.verified is False

    @pytest.mark.anyio
    async def test_enrich_greenhouse_board_identity_normalizes_canonical(self):
        from src.project_files.ats_api_client import enrich_greenhouse_board_identity

        fixture_path = FIXTURES_DIR / "board_canonical.html"
        html_content = fixture_path.read_text(encoding="utf-8")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=html_content))
        ) as http:
            name, logo = await enrich_greenhouse_board_identity("canonical_managed_posts", http)

        # "Canonical_managed_posts" normalized to authoritative "Canonical"
        assert name == "Canonical"
        assert logo.url is None
        assert logo.verified is False

    @pytest.mark.anyio
    async def test_enrich_greenhouse_board_identity_discord(self):
        from src.project_files.ats_api_client import enrich_greenhouse_board_identity

        fixture_path = FIXTURES_DIR / "board_discord.html"
        html_content = fixture_path.read_text(encoding="utf-8")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=html_content))
        ) as http:
            name, logo = await enrich_greenhouse_board_identity("discord", http)

        assert name == "Discord"
        assert logo.url is not None
        assert "external_greenhouse_job_boards/logos" in logo.url
        assert logo.verified is True


class TestMilestone10CacheRepair:
    """Milestone 10: Bounded, zero-Serper Greenhouse cache repair."""

    @pytest.mark.anyio
    async def test_repair_greenhouse_cache_with_mocked_http(self, tmp_path):
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.greenhouse_cache_repair import repair_greenhouse_cache
        from src.project_files.models import JobListing

        db_path = str(tmp_path / "test_cache.sqlite")
        cache = CacheStore(db_path=db_path)
        registry = CompanyBoardRegistry(db_path=db_path)

        url1 = "https://job-boards.greenhouse.io/acme/jobs/101"
        url2 = "https://job-boards.greenhouse.io/acme/jobs/404"

        # Pre-populate degraded listings in url_cache
        degraded1 = JobListing(
            id="greenhouse:acme:101",
            provider="greenhouse",
            ats_source="greenhouse",
            data_source="scrape",
            title="Old Backend Title",
            company="acme",
            apply_url=url1,
            source_url=url1,
            query_used="acme",
            scraped_at=datetime.now(timezone.utc),
            description="<p>Old short body</p>",
            salary=None,
            requirements=None,
            work_model=None,
        )
        degraded2 = JobListing(
            id="greenhouse:acme:404",
            provider="greenhouse",
            ats_source="greenhouse",
            data_source="scrape",
            title="Expired Role",
            company="acme",
            apply_url=url2,
            source_url=url2,
            query_used="acme",
            scraped_at=datetime.now(timezone.utc),
            description="<p>Expired role body</p>",
        )
        cache.set_url_cache(url1, degraded1)
        cache.set_url_cache(url2, degraded2)

        board_html = (
            "<html><head><title>Jobs at Acme Corporation</title>"
            '<meta property="og:image" content="https://s1.cdn.greenhouse.io/external_greenhouse_job_boards/logos/1/original/logo.png" />'
            "</head><body><h1>Current openings at Acme Corporation</h1></body></html>"
        )
        board_api_json = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Senior Distributed Systems Engineer",
                    "absolute_url": url1,
                    "location": {"name": "Remote, United States"},
                    "content": (
                        "<p>Build distributed event streaming pipelines in production. "
                        "#LI-Remote</p>"
                        "<h3>What you bring</h3>"
                        "<ul><li>5+ years backend systems experience with Kafka and Go</li></ul>"
                    ),
                    "pay_input_ranges": [
                        {
                            "min_cents": 15000000,
                            "max_cents": 18000000,
                            "currency_type": "USD",
                            "title": "Base Salary",
                            "blurb": "<p>Annual base compensation rate</p>",
                        }
                    ],
                }
            ]
        }

        def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "job-boards.greenhouse.io/acme" in url_str:
                return httpx.Response(200, text=board_html)
            if "boards-api.greenhouse.io/v1/boards/acme/jobs/404" in url_str:
                return httpx.Response(404, json={"error": "Not Found"})
            if "boards-api.greenhouse.io/v1/boards/acme/jobs" in url_str:
                return httpx.Response(200, json=board_api_json)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as http:
            report1 = await repair_greenhouse_cache(
                cache=cache,
                registry=registry,
                client=http,
                concurrency=1,
            )

        assert report1.total_urls == 2
        assert report1.unique_slugs == 1
        assert report1.repaired_from_board_api == 1
        assert report1.expired_or_unavailable == 1
        assert report1.serper_calls_made == 0

        # Check repaired listing
        repaired1 = cache.get_url_cache(url1)
        assert repaired1 is not None
        assert repaired1.title == "Senior Distributed Systems Engineer"
        assert repaired1.work_model == "remote"
        assert repaired1.salary is not None
        assert repaired1.salary.minimum == 150000
        assert repaired1.salary.maximum == 180000
        assert repaired1.requirements is not None
        assert "Kafka and Go" in repaired1.requirements
        assert repaired1.company == "Acme Corporation"

        # Check 404 listing was preserved without crashing or dropping
        preserved2 = cache.get_url_cache(url2)
        assert preserved2 is not None
        assert preserved2.title == "Expired Role"

        # Check restartability / idempotency
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as http:
            report2 = await repair_greenhouse_cache(
                cache=cache,
                registry=registry,
                client=http,
                concurrency=1,
                force=False,
            )
        assert report2.skipped_already_repaired == 2
        assert report2.repaired_from_board_api == 0

    @pytest.mark.anyio
    async def test_synthetic_records_skipped_by_repair_and_rejected_by_registry(self, tmp_path):
        from src.project_files.ats_api_client import enrich_greenhouse_board_identity
        from src.project_files.ats_url_parser import is_valid_board_slug
        from src.project_files.cache_store import CacheStore
        from src.project_files.company_board_registry import CompanyBoardRegistry
        from src.project_files.greenhouse_cache_repair import repair_greenhouse_cache
        from src.project_files.models import JobListing

        db_path = str(tmp_path / "synthetic_guard.sqlite")
        cache = CacheStore(db_path=db_path)
        registry = CompanyBoardRegistry(db_path=db_path)

        synthetic_slugs = ["company0", "company9", "testcompany", "placeholder"]
        for idx, slug in enumerate(synthetic_slugs):
            assert is_valid_board_slug("greenhouse", slug) is False
            assert registry.register_candidate(ats_provider="greenhouse", board_token=slug, company_name=slug) is None
            assert (
                registry.set_board_identity(
                    ats_provider="greenhouse",
                    board_token=slug,
                    company_name=slug,
                )
                is None
            )

            synth_url = f"https://boards.greenhouse.io/{slug}/jobs/{1000 + idx}"
            cache.set_url_cache(
                synth_url,
                JobListing(
                    id=f"greenhouse:{slug}:{1000 + idx}",
                    provider="greenhouse",
                    ats_source="greenhouse",
                    data_source="api",
                    title="Software Engineer",
                    company=slug,
                    company_slug=slug,
                    apply_url=synth_url,
                    source_url=synth_url,
                    query_used='site:greenhouse.io "Software Engineer"',
                    scraped_at=datetime.now(timezone.utc),
                    description="Description",
                ),
            )

        http_calls: list[str] = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            http_calls.append(str(request.url))
            return httpx.Response(200, json={"jobs": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as http:
            # 1) Direct identity enrichment on synthetic slug must make 0 HTTP requests
            name, logo = await enrich_greenhouse_board_identity("company0", http, registry=registry)
            assert name is None
            assert logo.url is None

            # 2) Cache repair must skip synthetic records completely with 0 HTTP requests
            report = await repair_greenhouse_cache(
                cache=cache,
                registry=registry,
                client=http,
                concurrency=1,
            )

        assert http_calls == []
        assert report.skipped_synthetic == len(synthetic_slugs)
        assert report.total_urls == 0
        assert report.unique_slugs == 0
        assert report.expired_or_unavailable == 0
        assert report.repaired_from_board_api == 0
        assert registry.list_boards() == []

        with cache._get_connection() as conn:
            repair_rows = conn.execute("SELECT url FROM greenhouse_repair_state").fetchall()
        assert repair_rows == []






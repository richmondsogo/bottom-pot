"""Comprehensive tests for Step 43 Recruitee Quality Pipeline."""

from __future__ import annotations

import asyncio
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from src.project_files.ats_api_client import (
    ATS_CLIENTS,
    RecruiteeClient,
    enrich_recruitee_board_identity,
    recruitee_payload_to_raw,
)
from src.project_files.ats_url_parser import (
    parse_ats_url,
    parse_recruitee_board_root_url,
)
from src.project_files.board_adapters import (
    BOARD_ADAPTERS,
    RecruiteeBoardAdapter,
)
from src.project_files.board_monitor import BoardMonitor
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import (
    MONITORABLE_PROVIDERS,
    PROVISIONAL_PROVIDERS,
    CompanyBoardRegistry,
    build_canonical_board_url,
)
from src.project_files.deduplicator import GlobalDeduplicator
from src.project_files.direct_board_router import probe_direct_boards, probe_recruitee_board
from src.project_files.field_normalizer import parse_datetime
from src.project_files.http_resilience import (
    CircuitBreakerOpenError,
    HostRateLimitedError,
    ResilienceManager,
    ResponseTooLargeError,
    throttled_stream_bytes,
)
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.logo_extractor import extract_company_logo_for_provider
from src.project_files.url_normalizer import (
    build_id_match_key,
    build_url_match_key,
    canonicalize_recruitee_posting_url,
    normalize_job_url,
    url_carries_job_identifier,
)

RECRUITEE_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "recruitee"


def _load_tether_bytes() -> bytes:
    return gzip.decompress((RECRUITEE_FIXTURE_DIR / "tether_offers.json.gz").read_bytes())


def _load_tether_redirect_html() -> str:
    return gzip.decompress((RECRUITEE_FIXTURE_DIR / "tether_board_redirect.html.gz").read_bytes()).decode(
        "utf-8", errors="replace"
    )


def _fresh_registry(tmp_path: Path, name: str = "test_recruitee.sqlite") -> CompanyBoardRegistry:
    return CompanyBoardRegistry(db_path=str(tmp_path / name))


class TestRecruiteeUrlIngestionAndNormalization:
    def test_parses_real_slug_and_legacy_numeric_urls(self):
        cases = [
            ("https://miaplaza.recruitee.com/o/academic-dean", "miaplaza", "academic-dean"),
            (
                "https://tether.recruitee.com/o/fullstack-engineer-agenticops-100-remote-14",
                "tether",
                "fullstack-engineer-agenticops-100-remote-14",
            ),
            (
                "https://tether.recruitee.com/o/developer-productivity-engineer-100-remote-5/c/new",
                "tether",
                "developer-productivity-engineer-100-remote-5",
            ),
            (
                "https://tether.recruitee.com/o/developer-productivity-engineer-100-remote-5/c/new/?utm_source=serper",
                "tether",
                "developer-productivity-engineer-100-remote-5",
            ),
            ("https://Miaplaza.recruitee.com/o/2774909-academic-dean/", "miaplaza", "2774909"),
        ]
        for url, exp_slug, exp_token in cases:
            parsed = parse_ats_url(url)
            assert parsed is not None, f"Failed to parse {url}"
            assert parsed.ats == "recruitee"
            assert parsed.company_slug == exp_slug
            assert parsed.job_id == exp_token

    def test_rejects_reserved_subdomains_malformed_paths_and_custom_domains(self):
        for bad in [
            "https://www.recruitee.com/o/academic-dean",
            "https://api.recruitee.com/o/academic-dean",
            "https://app.recruitee.com/o/academic-dean",
            "https://careers.recruitee.com/o/academic-dean",
            "https://jobs.recruitee.com/o/academic-dean",
            "https://miaplaza.recruitee.com/",
            "https://miaplaza.recruitee.com/o/",
            "https://miaplaza.recruitee.com/o/academic-dean/extra",
            "https://miaplaza.recruitee.com/o/academic-dean/c/invalid",
        ]:
            assert parse_ats_url(bad) is None
            assert url_carries_job_identifier(bad, "recruitee") is False

        # Spoofed/custom domains must NOT be parsed as Recruitee slugs
        assert parse_ats_url("https://example.com/miaplaza.recruitee.com/o/academic-dean") is None
        assert parse_ats_url("https://careers.tether.io/o/fullstack-engineer") is None
        assert parse_recruitee_board_root_url("https://careers.tether.io/") is None

    def test_board_root_parser_and_canonical_board_url(self):
        assert parse_recruitee_board_root_url("https://miaplaza.recruitee.com/") == "miaplaza"
        assert parse_recruitee_board_root_url("https://Tether.recruitee.com?utm_medium=cpc") == "tether"
        assert parse_recruitee_board_root_url("https://miaplaza.recruitee.com/o/academic-dean") is None
        assert parse_recruitee_board_root_url("https://www.recruitee.com/") is None
        assert parse_recruitee_board_root_url("https://careers.tether.io/") is None
        assert build_canonical_board_url("recruitee", "miaplaza") == "https://miaplaza.recruitee.com"

    def test_normalization_preserves_apply_suffix_while_canonicalizing_match_keys(self):
        posting = "https://tether.recruitee.com/o/dev-eng?utm_source=google#apply"
        apply = "https://tether.recruitee.com/o/dev-eng/c/new/?utm_source=google"
        legacy = "http://Miaplaza.recruitee.com/o/2774909-academic-dean/?fbclid=123"

        assert normalize_job_url(posting, "recruitee") == "https://tether.recruitee.com/o/dev-eng"
        # Critical distinction: careers_apply_url keeps /c/new!
        assert normalize_job_url(apply, "recruitee") == "https://tether.recruitee.com/o/dev-eng/c/new"
        assert normalize_job_url(legacy, "recruitee") == "https://miaplaza.recruitee.com/o/2774909-academic-dean"

        assert canonicalize_recruitee_posting_url(apply) == "https://tether.recruitee.com/o/dev-eng"
        assert build_url_match_key(apply, "recruitee") == build_url_match_key(posting, "recruitee")
        assert url_carries_job_identifier(posting, "recruitee") is True
        assert url_carries_job_identifier(apply, "recruitee") is True
        assert url_carries_job_identifier("https://miaplaza.recruitee.com/", "recruitee") is False

    @pytest.mark.anyio
    async def test_search_pipeline_enriches_slug_urls_and_registers_board_roots(self, tmp_path):
        from src.project_files import company_board_registry as reg_mod
        from src.project_files import search_pipeline
        from src.project_files.search_pipeline import SearchOrchestrator

        reg = _fresh_registry(tmp_path, "search_reg.sqlite")
        tether_data = json.loads(_load_tether_bytes().decode("utf-8"))
        sample_offer = tether_data["offers"][0]
        slug_url = sample_offer["careers_url"]
        alias_apply_url = sample_offer["careers_apply_url"]
        board_root_url = "https://tether.recruitee.com/"

        async def handler(request: httpx.Request) -> httpx.Response:
            if "/api/offers/" in str(request.url):
                return httpx.Response(200, json={"offer": sample_offer})
            return httpx.Response(404)

        orch = SearchOrchestrator()
        orig_reg = search_pipeline.company_board_registry
        orig_mod_reg = reg_mod.company_board_registry
        search_pipeline.company_board_registry = reg
        reg_mod.company_board_registry = reg
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                # 1. Board root registers candidate without dropping into broken fallback
                root_res = await orch._enrich_ats_item(
                    "recruitee",
                    {"link": board_root_url, "title": "Tether Careers", "snippet": "..."},
                    "tether",
                    client,
                )
                assert root_res is None
                board = reg.get_board("recruitee", "tether")
                assert board is not None
                assert board.board_url == "https://tether.recruitee.com"

                # 2. Genuine slug-only offer URL reaches enrichment and preserves numeric ID
                job_res = await orch._enrich_ats_item(
                    "recruitee",
                    {"link": slug_url, "title": sample_offer["title"], "snippet": "snippet"},
                    "tether",
                    client,
                )
                assert job_res is not None
                assert job_res.id == f"recruitee:tether:{sample_offer['id']}"
                assert job_res.company == "Tether Operations Limited"

                # 3. Duplicate /c/new alias resolves to same canonical ID and keeps distinct apply_url
                alias_res = await orch._enrich_ats_item(
                    "recruitee",
                    {"link": alias_apply_url, "title": sample_offer["title"], "snippet": "snippet"},
                    "tether",
                    client,
                )
                assert alias_res is not None
                assert alias_res.id == job_res.id
                assert alias_res.apply_url == alias_apply_url
                assert alias_res.source_url == slug_url
        finally:
            search_pipeline.company_board_registry = orig_reg
            reg_mod.company_board_registry = orig_mod_reg


class TestRecruiteeSharedConverterAndFields:
    def test_utc_timestamp_parsing_and_no_created_at_fallback(self):
        dt = parse_datetime("2026-11-09 19:52:16 UTC")
        assert dt is not None
        assert dt == datetime(2026, 11, 9, 19, 52, 16, tzinfo=timezone.utc)

        # created_at must NOT substitute for missing published_at
        raw = recruitee_payload_to_raw(
            {
                "id": 999,
                "slug": "staff-eng",
                "title": "Staff Engineer",
                "company_name": "Acme Corp",
                "created_at": "2026-01-01 00:00:00 UTC",
                "published_at": None,
            },
            company_slug="acme",
        )
        assert raw is not None
        assert raw.raw_date is None
        canonical = JobExtractionService.extract(raw)
        assert canonical.posted_at is None
        assert raw.raw_fields["created_at"] == "2026-01-01 00:00:00 UTC"

    def test_custom_domain_preserved_and_no_fabricated_apply_suffix(self):
        raw = recruitee_payload_to_raw(
            {
                "id": 55501,
                "slug": "backend-engineer",
                "title": "Backend Engineer",
                "company_name": "High Roller",
                "careers_url": "https://highroller-careers.com/o/backend-engineer",
                "careers_apply_url": None,
                "description": "<p>Build distributed systems in Python.</p>",
                "published_at": "2026-11-10 10:00:00 UTC",
            },
            company_slug="highroller",
        )
        assert raw is not None
        listing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw))
        assert listing.source_url == "https://highroller-careers.com/o/backend-engineer"
        assert listing.apply_url == "https://highroller-careers.com/o/backend-engineer"
        assert listing.id == "recruitee:highroller:55501"
        assert listing.company == "High Roller"

    def test_workplace_boolean_truth_table_including_real_dransay_conflict(self):
        def _extract_wm(remote, hybrid, on_site, location=None, description="<p>Role details.</p>"):
            raw = recruitee_payload_to_raw(
                {
                    "id": 1001,
                    "slug": "test-role",
                    "title": "Engineer",
                    "company_name": "Test Co",
                    "remote": remote,
                    "hybrid": hybrid,
                    "on_site": on_site,
                    "location": location,
                    "description": description,
                },
                company_slug="testco",
            )
            assert raw is not None
            return CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw))

        # Single positive flag -> deterministic api_enum
        r_job = _extract_wm(True, False, False)
        assert r_job.work_model == "remote"
        assert r_job.work_model_source == "api_enum"
        assert r_job.work_model_evidence == "remote=true"

        h_job = _extract_wm(False, True, False)
        assert h_job.work_model == "hybrid"
        assert h_job.work_model_source == "api_enum"

        o_job = _extract_wm(False, False, True)
        assert o_job.work_model == "in_person"
        assert o_job.work_model_source == "api_enum"

        # Multiple conflicting True flags -> unknown (None), never guess even with "Homeoffice"
        c_job = _extract_wm(True, True, False, location="Homeoffice")
        assert c_job.work_model is None
        assert c_job.raw_workplace_type == "remote=true,hybrid=true"

        # All False -> unknown (None), never infer in_person from remote=False
        f_job = _extract_wm(False, False, False)
        assert f_job.work_model is None

        # Missing flags -> unknown (None)
        n_job = _extract_wm(None, None, None)
        assert n_job.work_model is None

        # Real dransay fixture offer 2650971 (remote=True, hybrid=True)
        dra_data = json.loads((RECRUITEE_FIXTURE_DIR / "dransay_offers.json").read_text(encoding="utf-8"))
        conflict_offer = next(o for o in dra_data["offers"] if o["id"] == 2650971)
        dra_raw = recruitee_payload_to_raw(conflict_offer, company_slug="dransay")
        assert dra_raw is not None
        dra_listing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(dra_raw))
        assert dra_listing.company == "Dr. Ansay Ltd."
        assert dra_listing.work_model is None

    def test_real_offer_salary_requirements_employment_type_and_eligibility(self):
        mia_data = json.loads((RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_text(encoding="utf-8"))
        eng_mgr = next(o for o in mia_data["offers"] if o["id"] == 2814479)
        raw = recruitee_payload_to_raw(eng_mgr, company_slug="miaplaza")
        assert raw is not None
        listing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(raw))
        assert listing.id == "recruitee:miaplaza:2814479"
        assert listing.company == "Miaplaza"
        assert listing.employment_type == "full_time"
        assert listing.work_model == "remote"
        assert listing.requirements is not None
        assert listing.posted_at is not None

        # Synthetic negative salary check -> None when absent
        no_sal_raw = recruitee_payload_to_raw(
            {"id": 7, "slug": "x", "title": "Role", "company_name": "Co", "salary": None},
            company_slug="co",
        )
        assert no_sal_raw is not None
        assert CanonicalJobAdapter.to_listing(JobExtractionService.extract(no_sal_raw)).salary is None

        # Explicit residency text inside requirements HTML is honored for eligibility
        elig_raw = recruitee_payload_to_raw(
            {
                "id": 8,
                "slug": "remote-ng",
                "title": "Python Engineer",
                "company_name": "RemoteCo",
                "remote": True,
                "hybrid": False,
                "on_site": False,
                "description": "<p>Join our distributed platform team.</p>",
                "requirements": "<ul><li>Must reside in Nigeria and be authorized to work locally.</li></ul>",
            },
            company_slug="remoteco",
        )
        assert elig_raw is not None
        elig_listing = CanonicalJobAdapter.to_listing(JobExtractionService.extract(elig_raw))
        assert elig_listing.eligibility is not None
        assert "Nigeria" in (elig_listing.eligibility.allowed_residence_countries or [])
        assert elig_listing.eligibility.nigeria_eligible is True

    @pytest.mark.anyio
    async def test_identity_and_deduplication_across_search_board_and_direct_probe(self):
        teth_data = json.loads(_load_tether_bytes().decode("utf-8"))
        offer = teth_data["offers"][0]
        slug_url = offer["careers_url"]
        parsed = parse_ats_url(slug_url)
        assert parsed is not None

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u.endswith(f"/api/offers/{parsed.job_id}"):
                return httpx.Response(200, json={"offer": offer})
            if u.endswith("/api/offers/"):
                return httpx.Response(200, json={"offers": [offer]})
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            search_listing, res = await RecruiteeClient().fetch_result(parsed, client)
            assert res.outcome.value == "success"
            assert search_listing is not None

            board_res = await RecruiteeBoardAdapter().check_board(_board("tether"), client)
            assert board_res.success is True
            assert len(board_res.listings) == 1
            board_listing = board_res.listings[0]

            probed = await probe_recruitee_board("tether", client)
            assert len(probed) == 1
            probe_listing = probed[0]

        for candidate in (board_listing, probe_listing):
            assert candidate.id == search_listing.id
            assert candidate.source_record_id == search_listing.source_record_id
            assert candidate.source_url == search_listing.source_url
            assert candidate.apply_url == search_listing.apply_url
            assert candidate.provider == search_listing.provider == "recruitee"
            assert candidate.ats_source == search_listing.ats_source == "recruitee"

        dedup = GlobalDeduplicator()
        merged = dedup.deduplicate([search_listing, board_listing, probe_listing])
        assert len(merged) == 1
        assert merged[0].id == search_listing.id


def _board(token: str, **kwargs):
    from src.project_files.company_board_registry import CompanyBoard

    defaults = {
        "id": 1,
        "company_name": token.capitalize(),
        "company_slug": token,
        "ats_provider": "recruitee",
        "board_token": token,
        "board_url": f"https://{token}.recruitee.com",
        "discovery_source": "test",
        "source_posting_url": None,
        "first_discovered_at": 1000.0,
        "last_discovered_at": 1000.0,
        "verification_status": "verified",
        "monitoring_capability": "supported",
    }
    defaults.update(kwargs)
    return CompanyBoard(**defaults)


class TestRecruiteeVerifiedLogoEnrichment:
    def test_extracts_nav_logo_from_real_miaplaza_html_and_rejects_hero_banner(self):
        mia_html = (RECRUITEE_FIXTURE_DIR / "miaplaza_board.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(mia_html, "html.parser")
        res = extract_company_logo_for_provider(
            "recruitee",
            soup=soup,
            page_url="https://miaplaza.recruitee.com/",
            company_name="Miaplaza",
        )
        assert res.verified is True
        assert res.source == "recruitee_nav_logo"
        assert res.url is not None
        assert "careers.recruiteecdn.com" in res.url
        assert "w_1920" not in res.url

        # Real JS redirect HTML from tether has og:image w_1920 banner and NO nav logo -> must reject!
        tether_soup = BeautifulSoup(_load_tether_redirect_html(), "html.parser")
        tether_res = extract_company_logo_for_provider(
            "recruitee",
            soup=tether_soup,
            page_url="https://tether.recruitee.com/",
            company_name="Tether Operations Limited",
        )
        assert tether_res.url is None
        assert tether_res.verified is False

        # Banner-only HTML (og:image w_1920, no nav logo) + generic platform asset must be rejected
        banner_only_html = """
        <html><head>
          <meta property="og:image" content="https://careers.recruiteecdn.com/image/upload/q_auto,w_1920,c_limit/production/images/CDJC/hero.jpeg">
        </head><body>
          <img class="custom-css-style-navigation-logo-image" src="https://recruitee.com/assets/recruitee-logo.png">
        </body></html>
        """
        rejected_res = extract_company_logo_for_provider(
            "recruitee",
            soup=BeautifulSoup(banner_only_html, "html.parser"),
            page_url="https://acme.recruitee.com/",
        )
        assert rejected_res.url is None
        assert rejected_res.verified is False

    @pytest.mark.anyio
    async def test_logo_enrichment_caches_coalesces_and_handles_js_redirect_fallback(self, tmp_path):
        reg = _fresh_registry(tmp_path, "logo_reg.sqlite")
        mia_html = (RECRUITEE_FIXTURE_DIR / "miaplaza_board.html").read_text(encoding="utf-8")
        calls = {"miaplaza": 0, "tether_root": 0, "tether_offer": 0}
        redirect_html = (
            '<html><head><title>Redirect to https://careers.tether.io/</title>'
            '<meta property="og:image" content="https://careers.recruiteecdn.com/image/upload/q_auto,w_1920,c_limit/production/images/CMvO/hero.png">'
            "</head><body>Redirecting...</body></html>"
        )
        offer_html = (
            '<html><body><img class="custom-css-style-navigation-logo-image" '
            'src="https://careers.recruiteecdn.com/image/upload/q_auto,w_400,c_limit/production/images/TETH/logo.png">'
            "</body></html>"
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u == "https://miaplaza.recruitee.com/":
                calls["miaplaza"] += 1
                await asyncio.sleep(0.01)
                return httpx.Response(200, text=mia_html)
            if u == "https://tether.recruitee.com/":
                calls["tether_root"] += 1
                return httpx.Response(200, text=redirect_html)
            if u == "https://tether.recruitee.com/o/role-1":
                calls["tether_offer"] += 1
                return httpx.Response(200, text=offer_html)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Single-flight coalescing on concurrent miaplaza lookups
            res1, res2 = await asyncio.gather(
                enrich_recruitee_board_identity("miaplaza", client, registry=reg),
                enrich_recruitee_board_identity("miaplaza", client, registry=reg),
            )
            assert calls["miaplaza"] == 1
            assert res1[1].verified is True
            assert res2[1].url == res1[1].url

            # Subsequent call hits 7-day SQLite cache without HTTP
            res3 = await enrich_recruitee_board_identity("miaplaza", client, registry=reg)
            assert calls["miaplaza"] == 1
            assert res3[1].url == res1[1].url

            # JS redirect root triggers at most 1 bounded fallback offer HTML fetch
            _, tether_logo = await enrich_recruitee_board_identity(
                "tether",
                client,
                registry=reg,
                fallback_offer_url="https://tether.recruitee.com/o/role-1",
            )
            assert calls["tether_root"] == 1
            assert calls["tether_offer"] == 1
            assert tether_logo.verified is True
            assert "TETH/logo.png" in (tether_logo.url or "")

            # Negative cache on board without logo anywhere
            _, neg_logo = await enrich_recruitee_board_identity("missingboard", client, registry=reg)
            assert neg_logo.url is None
            b_neg = reg.get_board("recruitee", "missingboard")
            assert b_neg is not None and b_neg.company_logo_checked_at is not None
            _, neg_logo2 = await enrich_recruitee_board_identity("missingboard", client, registry=reg)
            assert neg_logo2.url is None


class TestRecruiteeMonitoringLargePayloadAndResilience:
    def test_recruitee_is_monitorable_and_registered(self):
        assert "recruitee" in MONITORABLE_PROVIDERS
        assert "recruitee" not in PROVISIONAL_PROVIDERS
        assert "recruitee" in BOARD_ADAPTERS
        assert isinstance(BOARD_ADAPTERS["recruitee"], RecruiteeBoardAdapter)
        assert isinstance(ATS_CLIENTS["recruitee"], RecruiteeClient)

    @pytest.mark.anyio
    async def test_monitoring_real_large_tether_board_over_5mb_and_fingerprint_diffing(self, tmp_path):
        tether_bytes = _load_tether_bytes()
        assert len(tether_bytes) > 5 * 1024 * 1024
        tether_json = json.loads(tether_bytes.decode("utf-8"))
        mia_bytes = (RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_bytes()

        adapter = RecruiteeBoardAdapter()
        reg = _fresh_registry(tmp_path, "fp_reg.sqlite")

        # 1. Real 5.97 MB Tether board succeeds completely without truncation
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, content=tether_bytes)
                if "/api/offers/" in str(req.url)
                else httpx.Response(404)
            )
        ) as client:
            t_board = _board("tether", board_url="https://tether.recruitee.com")
            res = await adapter.check_board(t_board, client, registry=reg)
            assert res.success is True
            assert res.not_modified is False
            assert len(res.listings) == len(tether_json["offers"])
            assert res.content_fingerprint is not None

            # Same payload on subsequent poll -> not_modified=True
            t_board.content_fingerprint = res.content_fingerprint
            res_same = await adapter.check_board(t_board, client, registry=reg)
            assert res_same.success is True
            assert res_same.not_modified is True

        # 2. Mutating an offer field (salary/title) triggers fingerprint diff
        mutated = json.loads(mia_bytes.decode("utf-8"))
        mutated["offers"][0]["title"] = "Updated Academic Dean"
        m_board = _board("miaplaza", board_url="https://miaplaza.recruitee.com")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, content=mia_bytes)
                if "/api/offers/" in str(req.url)
                else httpx.Response(404)
            )
        ) as c1:
            res_orig = await adapter.check_board(m_board, c1, registry=reg)
            assert res_orig.success is True

        m_board.content_fingerprint = res_orig.content_fingerprint
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=mutated)
                if "/api/offers/" in str(req.url)
                else httpx.Response(404)
            )
        ) as c2:
            res_mut = await adapter.check_board(m_board, c2, registry=reg)
            assert res_mut.success is True
            assert res_mut.not_modified is False
            assert res_mut.content_fingerprint != res_orig.content_fingerprint

    @pytest.mark.anyio
    async def test_fingerprint_changes_on_fallback_offer_fields_and_uses_full_sha256(self, tmp_path):
        from src.project_files.board_adapters import _recruitee_job_content_hash

        base_offer = {
            "id": 99001,
            "slug": "senior-engineer",
            "title": "Senior Engineer",
            "company_name": "Acme Corp",
            "status": "published",
        }
        base_digest = _recruitee_job_content_hash(base_offer)
        assert len(base_digest) == 64
        assert all(c in "0123456789abcdef" for c in base_digest)

        adapter = RecruiteeBoardAdapter()
        reg = _fresh_registry(tmp_path, "fp_fallback_reg.sqlite")

        async def _check_payload(offer_obj: dict, prev_fp: str | None = None):
            board = _board("acme", board_url="https://acme.recruitee.com")
            if prev_fp is not None:
                board.content_fingerprint = prev_fp
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda req: httpx.Response(200, json={"offers": [offer_obj]})
                    if "/api/offers/" in str(req.url)
                    else httpx.Response(404)
                )
            ) as client:
                return await adapter.check_board(board, client, registry=reg)

        orig_res = await _check_payload(dict(base_offer))
        assert orig_res.success is True
        assert orig_res.content_fingerprint is not None

        fallback_mutations = (
            ("description_html", "<p>Updated HTML body</p>"),
            ("intro", "Updated role intro summary"),
            ("employment_type", "contract"),
            ("employmentType", "PART_TIME"),
            ("workplace_type", "hybrid"),
            ("workplaceType", "remote"),
            ("position", "Staff Engineer"),
            ("company", {"name": "Acme Holdings"}),
            ("companyName", "Acme Global"),
        )
        for field_name, field_value in fallback_mutations:
            mutated = dict(base_offer)
            mutated[field_name] = field_value
            assert _recruitee_job_content_hash(mutated) != base_digest
            mut_res = await _check_payload(mutated, prev_fp=orig_res.content_fingerprint)
            assert mut_res.success is True
            assert mut_res.not_modified is False, f"Fingerprint stayed same after mutating {field_name}"
            assert mut_res.content_fingerprint != orig_res.content_fingerprint

    @pytest.mark.anyio
    async def test_malformed_offer_records_fail_without_closing_monitored_jobs(self, tmp_path):
        reg = _fresh_registry(tmp_path, "malformed_reg.sqlite")
        reg.register_candidate(
            ats_provider="recruitee",
            board_token="miaplaza",
            company_name="Miaplaza",
            source_url="https://miaplaza.recruitee.com/",
            board_url="https://miaplaza.recruitee.com",
        )
        mia_data = json.loads((RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_text(encoding="utf-8"))
        two_offers = {"offers": mia_data["offers"][:2]}
        malformed_payloads: list[dict] = [
            {"offers": [{}]},
            {"offers": [{"id": 123, "status": "published"}]},
            {"offers": [mia_data["offers"][0], {"id": 123, "status": "published"}]},
            {"offers": ["not-an-object"]},
            {"offers": [{"id": 123, "title": "Eng", "status": "pending_review"}]},
            {"offers": [{"id": 123, "title": "Eng", "status": "paused"}]},
            {"offers": [mia_data["offers"][0], {"id": 123, "title": "Eng", "status": "unexpected_state"}]},
            {"offers": [{"id": 123, "title": "Eng", "status": ""}]},
            {"offers": [{"id": 123, "title": "Eng", "status": 123}]},
        ]
        state: dict[str, object] = {"payload": two_offers}

        async def handler(request: httpx.Request) -> httpx.Response:
            if "/api/offers/" not in str(request.url):
                return httpx.Response(404)
            return httpx.Response(200, json=state["payload"])

        adapter = RecruiteeBoardAdapter()
        monitor = BoardMonitor(registry=reg)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = reg.get_board("recruitee", "miaplaza")
            assert board is not None
            await monitor.check_single_board(board, client)
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 2

            for bad_payload in malformed_payloads:
                state["payload"] = bad_payload
                board = reg.get_board("recruitee", "miaplaza")
                assert board is not None

                direct_res = await adapter.check_board(board, client, registry=reg)
                assert direct_res.success is False, f"Expected failure for payload={bad_payload}"

                await monitor.check_single_board(board, client)
                assert len(reg.get_monitored_jobs_for_board(board.id)) == 2

            # Missing status retains active-offer handling (requires id/title)
            no_status_offer = dict(mia_data["offers"][0])
            no_status_offer.pop("status", None)
            state["payload"] = {"offers": [no_status_offer]}
            board = reg.get_board("recruitee", "miaplaza")
            assert board is not None
            no_status_res = await adapter.check_board(board, client, registry=reg)
            assert no_status_res.success is True
            assert len(no_status_res.listings) == 1

            # Explicitly recognized Recruitee inactive statuses are excluded cleanly without error
            for inactive_status in ("draft", "internal", "archived", "closed"):
                state["payload"] = {"offers": [{"id": 123, "title": "Old Role", "status": inactive_status}]}
                board = reg.get_board("recruitee", "miaplaza")
                assert board is not None
                inactive_res = await adapter.check_board(board, client, registry=reg)
                assert inactive_res.success is True
                assert inactive_res.listings == []

            await monitor.check_single_board(board, client)
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 0

    @pytest.mark.anyio
    async def test_board_monitor_reconciliation_and_non_closure_on_errors_or_oversize(self, tmp_path):
        reg = _fresh_registry(tmp_path, "monitor_reg.sqlite")
        reg.register_candidate(
            ats_provider="recruitee",
            board_token="miaplaza",
            company_name="Miaplaza",
            source_url="https://miaplaza.recruitee.com/",
            board_url="https://miaplaza.recruitee.com",
        )

        mia_data = json.loads((RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_text(encoding="utf-8"))
        two_offers = {"offers": mia_data["offers"][:2]}
        one_offer = {"offers": mia_data["offers"][:1]}
        empty_offers = {"offers": []}

        payload_state = {"mode": "two"}

        async def handler(request: httpx.Request) -> httpx.Response:
            if "/api/offers/" not in str(request.url):
                return httpx.Response(404)
            mode = payload_state["mode"]
            if mode == "two":
                return httpx.Response(200, json=two_offers)
            if mode == "one":
                return httpx.Response(200, json=one_offer)
            if mode == "empty":
                return httpx.Response(200, json=empty_offers)
            if mode == "404":
                return httpx.Response(404)
            if mode == "429":
                return httpx.Response(429, headers={"Retry-After": "1"})
            if mode == "500":
                return httpx.Response(500)
            if mode == "bad_json":
                return httpx.Response(200, text="{broken json")
            if mode == "bad_shape":
                return httpx.Response(200, json={"error": "not offers"})
            if mode == "timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            if mode == "network":
                raise httpx.ConnectError("connection reset", request=request)
            if mode == "oversized":
                # > 16 MiB default cap without Content-Length (tests streaming chunk cap)
                return httpx.Response(200, content=b"{" + b" " * (16 * 1024 * 1024 + 512) + b"}")
            raise AssertionError(f"Unknown mode {mode}")

        monitor = BoardMonitor(registry=reg)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = reg.get_board("recruitee", "miaplaza")
            assert board is not None

            # Initial poll populates 2 active monitored jobs
            await monitor.check_single_board(board, client)
            active = reg.get_monitored_jobs_for_board(board.id)
            assert len(active) == 2

            # Every error/malformed/oversized condition MUST preserve all 2 active jobs!
            for bad_mode in ("404", "429", "500", "bad_json", "bad_shape", "timeout", "network", "oversized"):
                payload_state["mode"] = bad_mode
                # Clear circuit breaker/backoff between error simulations
                from src.project_files.http_resilience import resilience_manager
                resilience_manager._host_tripped_until.clear()
                resilience_manager._host_failures.clear()
                resilience_manager._host_rate_limited_until.clear()

                board = reg.get_board("recruitee", "miaplaza")
                assert board is not None
                await monitor.check_single_board(board, client)
                still_active = reg.get_monitored_jobs_for_board(board.id)
                assert len(still_active) == 2, f"False closure on error mode={bad_mode}"

            # Removal from valid HTTP 200 list -> closes disappeared job only
            payload_state["mode"] = "one"
            board = reg.get_board("recruitee", "miaplaza")
            assert board is not None
            await monitor.check_single_board(board, client)
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 1

            # Explicit valid HTTP 200 {"offers": []} closes remaining active job
            payload_state["mode"] = "empty"
            board = reg.get_board("recruitee", "miaplaza")
            assert board is not None
            await monitor.check_single_board(board, client)
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 0

    @pytest.mark.anyio
    async def test_streaming_resilience_concurrency_429_circuit_breaker_and_no_semaphore_leak(self, monkeypatch):
        from src.config import settings
        from src.project_files import http_resilience

        custom_rm = ResilienceManager()
        orig_rm = http_resilience.resilience_manager
        http_resilience.resilience_manager = custom_rm
        try:
            url = "https://acme.recruitee.com/api/offers/"
            host = custom_rm.extract_host(url)

            # 1. Semaphore leak check across success, oversize, and network errors
            async def oversize_handler(req: httpx.Request) -> httpx.Response:
                return httpx.Response(200, headers={"Content-Length": "99999999"}, content=b"x")

            async with httpx.AsyncClient(transport=httpx.MockTransport(oversize_handler)) as client:
                with pytest.raises(ResponseTooLargeError):
                    await throttled_stream_bytes(client, url, max_bytes=100)

            sem = custom_rm._get_host_semaphore(host)
            assert sem._value == settings.per_host_concurrency_limit  # no leak!

            # 2. 429 Retry-After blocks immediately inside host backoff window
            async def rl_handler(req: httpx.Request) -> httpx.Response:
                return httpx.Response(429, headers={"Retry-After": "60"})

            async with httpx.AsyncClient(transport=httpx.MockTransport(rl_handler)) as client:
                status, _, _ = await throttled_stream_bytes(client, url, max_bytes=1024)
                assert status == 429
                with pytest.raises(HostRateLimitedError):
                    await throttled_stream_bytes(client, url, max_bytes=1024)

            assert custom_rm._get_host_semaphore(host)._value == settings.per_host_concurrency_limit

            # 3. Circuit breaker trips after threshold consecutive 5xx failures
            custom_rm._host_rate_limited_until.clear()
            monkeypatch.setattr(settings, "circuit_breaker_failure_threshold", 2)

            async def err_handler(req: httpx.Request) -> httpx.Response:
                return httpx.Response(503)

            async with httpx.AsyncClient(transport=httpx.MockTransport(err_handler)) as client:
                await throttled_stream_bytes(client, url, max_bytes=1024)
                await throttled_stream_bytes(client, url, max_bytes=1024)
                with pytest.raises(CircuitBreakerOpenError):
                    await throttled_stream_bytes(client, url, max_bytes=1024)

            assert custom_rm._get_host_semaphore(host)._value == settings.per_host_concurrency_limit
        finally:
            http_resilience.resilience_manager = orig_rm

    @pytest.mark.anyio
    async def test_interrupted_stream_records_failure_and_trips_circuit_breaker(self, monkeypatch):
        from src.config import settings
        from src.project_files import http_resilience

        class _InterruptedByteStream(httpx.AsyncByteStream):
            def __init__(self, req: httpx.Request):
                self._req = req

            async def __aiter__(self):
                yield b'{"offers": ['
                raise httpx.ReadError("connection reset mid-stream", request=self._req)

        custom_rm = ResilienceManager()
        orig_rm = http_resilience.resilience_manager
        http_resilience.resilience_manager = custom_rm
        try:
            url = "https://acme.recruitee.com/api/offers/"
            host = custom_rm.extract_host(url)
            monkeypatch.setattr(settings, "circuit_breaker_failure_threshold", 2)

            calls = {"count": 0}

            async def interrupted_handler(req: httpx.Request) -> httpx.Response:
                calls["count"] += 1
                return httpx.Response(200, stream=_InterruptedByteStream(req))

            async with httpx.AsyncClient(transport=httpx.MockTransport(interrupted_handler)) as client:
                # 1. Seed one prior failure; an interrupted stream must NOT reset failure count
                custom_rm.record_failure(host)
                assert custom_rm._host_failures[host] == 1

                with pytest.raises(httpx.ReadError):
                    await throttled_stream_bytes(client, url, max_bytes=4096)

                # Reaching threshold=2 must trip the breaker immediately
                with pytest.raises(CircuitBreakerOpenError):
                    await throttled_stream_bytes(client, url, max_bytes=4096)
                assert calls["count"] == 1

                # 2. Clean host: two interrupted streams reach threshold=2 and trip the breaker
                custom_rm._host_tripped_until.clear()
                custom_rm._host_failures.clear()
                calls["count"] = 0

                with pytest.raises(httpx.ReadError):
                    await throttled_stream_bytes(client, url, max_bytes=4096)
                assert custom_rm._host_failures[host] == 1

                with pytest.raises(httpx.ReadError):
                    await throttled_stream_bytes(client, url, max_bytes=4096)

                with pytest.raises(CircuitBreakerOpenError):
                    await throttled_stream_bytes(client, url, max_bytes=4096)
                assert calls["count"] == 2

            assert custom_rm._get_host_semaphore(host)._value == settings.per_host_concurrency_limit
        finally:
            http_resilience.resilience_manager = orig_rm


class TestRecruiteeDirectBoardRouter:
    @pytest.mark.anyio
    async def test_probe_recruitee_board_and_probe_direct_boards_integration(self, tmp_path, monkeypatch):
        from src.project_files import ats_api_client

        isolated_reg = _fresh_registry(tmp_path, "router_reg.sqlite")
        monkeypatch.setattr(ats_api_client, "company_board_registry", isolated_reg)

        mia_bytes = (RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_bytes()
        mia_html = (RECRUITEE_FIXTURE_DIR / "miaplaza_board.html").read_text(encoding="utf-8")

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u == "https://miaplaza.recruitee.com/api/offers/":
                return httpx.Response(200, content=mia_bytes)
            if u == "https://miaplaza.recruitee.com/":
                return httpx.Response(200, text=mia_html)
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            listings = await probe_direct_boards(["miaplaza"], client, platforms=["recruitee"])
            assert len(listings) == 7
            assert all(j.provider == "recruitee" for j in listings)
            assert all(j.company == "Miaplaza" for j in listings)
            assert all(j.company_logo_verified is True for j in listings)

            missing = await probe_recruitee_board("doesnotexist-xyz", client)
            assert missing == []

    @pytest.mark.anyio
    async def test_direct_discovery_snapshot_validation_rejects_partial_and_preserves_valid(
        self, tmp_path, monkeypatch
    ):
        from src.project_files import ats_api_client
        from src.project_files import search_pipeline
        from src.project_files.models import SearchParams
        from src.project_files.search_pipeline import SearchOrchestrator

        isolated_reg = _fresh_registry(tmp_path, "direct_val_reg.sqlite")
        monkeypatch.setattr(ats_api_client, "company_board_registry", isolated_reg)
        monkeypatch.setattr(search_pipeline, "company_board_registry", isolated_reg)

        mia_data = json.loads((RECRUITEE_FIXTURE_DIR / "miaplaza_offers.json").read_text(encoding="utf-8"))
        mia_html = (RECRUITEE_FIXTURE_DIR / "miaplaza_board.html").read_text(encoding="utf-8")
        valid_offer = mia_data["offers"][0]
        state: dict[str, object] = {"payload": {"offers": []}}

        async def handler(request: httpx.Request) -> httpx.Response:
            u = str(request.url)
            if u == "https://miaplaza.recruitee.com/api/offers/":
                return httpx.Response(200, json=state["payload"])
            if u == "https://miaplaza.recruitee.com/":
                return httpx.Response(200, text=mia_html)
            return httpx.Response(404)

        orchestrator = SearchOrchestrator()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # 1. Valid published offer mixed with unrecognized status -> no partial listings & no board registration
            state["payload"] = {
                "offers": [
                    valid_offer,
                    {"id": 999001, "title": "Unknown Status Role", "status": "unexpected_status"},
                ]
            }
            assert await probe_recruitee_board("miaplaza", client) == []
            _, orch_listings, _ = await orchestrator._search_direct_boards(
                slugs=["miaplaza"],
                params=SearchParams(job_title="miaplaza"),
                platforms=["recruitee"],
                client=client,
            )
            assert orch_listings == []
            assert isolated_reg.get_board("recruitee", "miaplaza") is None
            assert isolated_reg.list_boards() == []

            # 2. Valid published offer mixed with malformed offer -> no partial listings & no board registration
            state["payload"] = {
                "offers": [
                    valid_offer,
                    {"id": 999002, "status": "published"},  # missing title/position
                ]
            }
            assert await probe_recruitee_board("miaplaza", client) == []
            _, orch_listings, _ = await orchestrator._search_direct_boards(
                slugs=["miaplaza"],
                params=SearchParams(job_title="miaplaza"),
                platforms=["recruitee"],
                client=client,
            )
            assert orch_listings == []
            assert isolated_reg.get_board("recruitee", "miaplaza") is None
            assert isolated_reg.list_boards() == []

            # 3. Valid empty offers response -> returns [] cleanly and does not register board
            state["payload"] = {"offers": []}
            assert await probe_recruitee_board("miaplaza", client) == []
            _, orch_listings, _ = await orchestrator._search_direct_boards(
                slugs=["miaplaza"],
                params=SearchParams(job_title="miaplaza"),
                platforms=["recruitee"],
                client=client,
            )
            assert orch_listings == []
            assert isolated_reg.list_boards() == []

            # 4. Valid all-published response -> returns full listings and registers verified board
            state["payload"] = mia_data
            direct_listings = await probe_recruitee_board("miaplaza", client)
            assert len(direct_listings) == len(mia_data["offers"])
            _, orch_listings, _ = await orchestrator._search_direct_boards(
                slugs=["miaplaza"],
                params=SearchParams(job_title="miaplaza"),
                platforms=["recruitee"],
                client=client,
            )
            assert len(orch_listings) == len(mia_data["offers"])
            board = isolated_reg.get_board("recruitee", "miaplaza")
            assert board is not None
            assert board.verification_status == "verified"
            assert board.active_job_count == len(mia_data["offers"])

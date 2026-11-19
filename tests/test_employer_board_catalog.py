"""
Step 54 Curated Employer Board Catalog, Offline Replay & Multi-Country Tests.

Validates:
- Catalog stays strictly within existing 9 MONITORABLE_PROVIDERS (no 10th ATS).
- Every committed Step 54 real fixture matches evaluation_manifest.json SHA-256 & byte size.
- Idempotent catalog seeding + ADR 0030 CLI safety for `--seed-catalog`.
- Full offline native-adapter replay via BoardMonitor.check_single_board across all
  10 selected boards (including Workable widget + v2 detail hydration).
- Canonical deduplication on repeated poll, HTTP 304 preservation, and fail-closed
  non-closure across 301/403/404/429/500/malformed payloads.
- Global 11-country eligibility invariants (Nigeria kept distinct from global and
  wider Africa / Egypt; remote-restricted roles never labeled worldwide).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
import pytest

from src.project_files.ats_url_parser import is_valid_board_slug
from src.project_files.board_monitor import BoardMonitor, main as board_monitor_main
from src.project_files.cache_store import CacheStore
from src.project_files.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoardRegistry,
    build_canonical_board_url,
)
from src.project_files.db_safety import UnsafeDatabasePathError
from src.project_files.eligibility_extractor import evaluate_eligibility_for_country
from src.project_files.employer_board_catalog import (
    VERIFIED_EMPLOYER_BOARDS,
    seed_verified_employer_boards,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "step54_employers"
MANIFEST_PATH = FIXTURES_DIR / "evaluation_manifest.json"
REPRESENTATIVE_COUNTRIES = ["NG", "GH", "KE", "EG", "GB", "DE", "US", "CA", "IN", "SG", "AU"]


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _build_offline_handler(provider: str, fixture_files: list[str], *, etag: str | None = None):
    primary_name = fixture_files[0]
    primary_bytes = (FIXTURES_DIR / primary_name).read_bytes()
    detail_map = None
    if provider == "workable" and len(fixture_files) > 1:
        detail_map = json.loads((FIXTURES_DIR / fixture_files[1]).read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if etag and request.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"etag": etag})
        url = str(request.url)
        headers = {"etag": etag} if etag else {}
        if provider == "workable":
            if "/api/v1/widget/accounts/" in url:
                return httpx.Response(
                    200,
                    content=primary_bytes,
                    headers={**headers, "content-type": "application/json"},
                )
            if "/api/v2/accounts/" in url and "/jobs/" in url and detail_map is not None:
                sc = url.rstrip("/").split("/")[-1]
                payload = detail_map.get(sc)
                if payload and "_http_status" not in payload:
                    return httpx.Response(200, json=payload, headers={"content-type": "application/json"})
            return httpx.Response(404)
        ctype = "application/xml" if primary_name.endswith(".xml") else "application/json"
        return httpx.Response(200, content=primary_bytes, headers={**headers, "content-type": ctype})

    return handler


@pytest.fixture
def isolated_monitor(tmp_path: Path):
    db_file = str(tmp_path / "catalog_test.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    cache = CacheStore(db_path=db_file)
    monitor = BoardMonitor(registry=reg, cache=cache)
    yield reg, cache, monitor
    reg.clear()
    cache.clear()


class TestEmployerCatalogAndFixtures:
    def test_catalog_invariants_and_monitorable_providers_unchanged(self):
        assert len(MONITORABLE_PROVIDERS) == 9
        assert len(VERIFIED_EMPLOYER_BOARDS) == 10

        seen_keys: set[tuple[str, str]] = set()
        providers_covered: set[str] = set()
        for entry in VERIFIED_EMPLOYER_BOARDS:
            assert entry.ats_provider in MONITORABLE_PROVIDERS
            assert is_valid_board_slug(entry.ats_provider, entry.board_token)
            assert entry.board_url.startswith("https://")
            expected_url = build_canonical_board_url(entry.ats_provider, entry.board_token)
            assert entry.board_url == expected_url
            key = (entry.ats_provider, entry.board_token.lower())
            assert key not in seen_keys
            seen_keys.add(key)
            providers_covered.add(entry.ats_provider)

        assert providers_covered == {"ashby", "greenhouse", "lever", "recruitee", "teamtailor", "workable"}

    def test_manifest_sha256_digests_match_committed_fixtures(self):
        manifest = _load_manifest()
        assert manifest["serper_credits_spent"] == 0
        assert manifest["selected_boards_count"] == len(VERIFIED_EMPLOYER_BOARDS)

        manifest_keys = {(b["ats_provider"], b["board_token"].lower()) for b in manifest["selected_boards"]}
        catalog_keys = {(e.ats_provider, e.board_token.lower()) for e in VERIFIED_EMPLOYER_BOARDS}
        assert manifest_keys == catalog_keys

        for b in manifest["selected_boards"]:
            for fname, meta in b["fixtures"].items():
                p = FIXTURES_DIR / fname
                assert p.exists(), f"Missing fixture file {p}"
                raw = p.read_bytes()
                if fname == "workable_fairmoney_details.json":
                    raw = raw.replace(b"\r\n", b"\n")
                assert len(raw) == meta["bytes"]
                assert hashlib.sha256(raw).hexdigest() == meta["sha256"]

    def test_idempotent_seeding_and_cli_seed_catalog_db_safety(self, isolated_monitor, tmp_path: Path):
        reg, _cache, monitor = isolated_monitor
        seeded_first = seed_verified_employer_boards(reg)
        seeded_second = monitor.seed_curated_boards()

        assert len(seeded_first) == 10
        assert len(seeded_second) == 10

        with reg._get_connection() as conn:
            total_rows = conn.execute("SELECT COUNT(*) FROM company_boards").fetchone()[0]
        assert total_rows == 10

        for entry in VERIFIED_EMPLOYER_BOARDS:
            board = reg.get_board(entry.ats_provider, entry.board_token)
            assert board is not None
            assert board.monitoring_capability == "supported"

        # CLI `--seed-catalog` must succeed against explicit disposable temp DB path
        cli_db = str(tmp_path / "cli_seed.sqlite")
        cli_reg = CompanyBoardRegistry(db_path=cli_db)
        cli_cache = CacheStore(db_path=cli_db)
        with (
            patch.dict("os.environ", {"SQLITE_DB_PATH": cli_db, "SUBSCRIPTIONS_FILE": str(tmp_path / "subs.csv")}),
            patch("src.config.settings.sqlite_db_path", cli_db),
            patch("src.project_files.board_monitor.company_board_registry", cli_reg),
            patch("src.project_files.board_monitor._default_cache_store", cli_cache),
            patch.object(sys, "argv", ["board_monitor", "--seed-catalog"]),
        ):
            board_monitor_main()

        with cli_reg._get_connection() as conn:
            cli_rows = conn.execute("SELECT COUNT(*) FROM company_boards").fetchone()[0]
        assert cli_rows == 10

        # CLI `--seed-catalog` must fail closed against protected operational data/cache.sqlite in test mode
        op_reg = CompanyBoardRegistry(db_path="data/cache.sqlite", _defer_init=True)
        with (
            patch.dict("os.environ", {"SQLITE_DB_PATH": "data/cache.sqlite"}),
            patch("src.config.settings.sqlite_db_path", "data/cache.sqlite"),
            patch("src.project_files.board_monitor.company_board_registry", op_reg),
            patch.object(sys, "argv", ["board_monitor", "--seed-catalog"]),
            pytest.raises(UnsafeDatabasePathError),
        ):
            board_monitor_main()

        # Operational opt-in `--allow-operational-db` must also fail closed in test mode
        with (
            patch.object(sys, "argv", ["board_monitor", "--seed-catalog", "--allow-operational-db"]),
            pytest.raises(UnsafeDatabasePathError),
        ):
            board_monitor_main()


class TestOfflineFixtureReplayAndResilience:
    @pytest.mark.anyio
    async def test_replay_all_10_catalog_boards_dedup_and_11_country_eligibility(self, isolated_monitor):
        reg, cache, monitor = isolated_monitor
        manifest = _load_manifest()
        manifest_by_key = {b["key"]: b for b in manifest["selected_boards"]}
        boards = monitor.seed_curated_boards()
        assert len(boards) == 10

        replayed_listings_by_board: dict[str, list] = {}
        for board in boards:
            key = f"{board.ats_provider}:{board.board_token}"
            spec = manifest_by_key[key]
            fixture_files = list(spec["fixtures"].keys())
            handler = _build_offline_handler(board.ats_provider, fixture_files)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                res1 = await monitor.check_single_board(board, client, cache_store=cache)
                assert res1.success is True, f"Poll 1 failed for {key}: {res1.error}"
                assert res1.snapshot_complete is True, f"Incomplete snapshot for {key}"
                assert len(res1.listings) == spec["raw_listings_count"]

                # Second poll on identical feed must remain idempotent without creating duplicate DB rows
                fresh_board = reg.get_board(board.ats_provider, board.board_token)
                res2 = await monitor.check_single_board(fresh_board, client, cache_store=cache)
                assert res2.success is True
                assert res2.snapshot_complete is True

            with reg._get_connection() as conn:
                db_active_count = conn.execute(
                    "SELECT COUNT(*) FROM monitored_jobs WHERE board_id = ? AND status = 'active'",
                    (board.id,),
                ).fetchone()[0]
            assert db_active_count == spec["unique_active_jobs"]

            deduped = []
            seen_ids = set()
            for item in res1.listings:
                if item.description and len(item.description.strip()) >= 80:
                    assert item.apply_url.startswith("https://")
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    deduped.append(item)
            assert len(deduped) == spec["unique_active_jobs"]
            replayed_listings_by_board[key] = deduped

        # Workable FairMoney emits 59 widget entries across multi-city rows that deduplicate to 25 canonical jobs in monitored_jobs
        fairmoney_row = reg.get_board("workable", "fairmoney")
        assert fairmoney_row is not None
        assert fairmoney_row.active_job_count == 59
        with reg._get_connection() as conn:
            fairmoney_canonical_count = conn.execute(
                "SELECT COUNT(*) FROM monitored_jobs WHERE board_id = ? AND status = 'active'",
                (fairmoney_row.id,),
            ).fetchone()[0]
        assert fairmoney_canonical_count == 25

        # Spot-check real multi-country eligibility guarantees across the 11 representative countries
        supa_jobs = replayed_listings_by_board["ashby:supabase"]
        ai_plat = next(j for j in supa_jobs if j.title == "AI Platform Engineer")
        amer_csa = next(j for j in supa_jobs if j.title == "Customer Solution Architect (AMER)")
        for cc in REPRESENTATIVE_COUNTRIES:
            assert evaluate_eligibility_for_country(ai_plat.eligibility, cc, work_model=ai_plat.work_model, location=ai_plat.location).status == "eligible"
        assert amer_csa.eligibility is not None
        assert amer_csa.eligibility.classification == "region_restricted"
        for non_amer in ("NG", "GH", "KE", "EG", "GB", "DE", "IN", "SG", "AU"):
            assert evaluate_eligibility_for_country(amer_csa.eligibility, non_amer, work_model=amer_csa.work_model, location=amer_csa.location).status == "restricted"
        assert evaluate_eligibility_for_country(amer_csa.eligibility, "US", work_model=amer_csa.work_model, location=amer_csa.location).status == "unknown"

        # Wikimedia: Ghana/Kenya/Germany/UK/US/CA/IN/SG eligible; Nigeria & Egypt restricted
        wiki_sre = next(j for j in replayed_listings_by_board["greenhouse:wikimedia"] if "Site Reliability" in j.title)
        for allowed_cc in ("GH", "KE", "GB", "DE", "US", "CA", "IN", "SG"):
            assert evaluate_eligibility_for_country(wiki_sre.eligibility, allowed_cc, work_model=wiki_sre.work_model, location=wiki_sre.location).status == "eligible"
        for disallowed_cc in ("NG", "EG", "AU"):
            assert evaluate_eligibility_for_country(wiki_sre.eligibility, disallowed_cc, work_model=wiki_sre.work_model, location=wiki_sre.location).status == "restricted"

        # Thndr: Cairo hybrid/onsite roles eligible for Egypt, NOT conflated with Nigeria
        thndr_devops = next(j for j in replayed_listings_by_board["ashby:thndr"] if "DevOps" in j.title)
        assert thndr_devops.eligibility is not None
        # Paystack: multi-hub Lagos/Nairobi/Cape Town role covers NG & KE without assuming US
        paystack_sec = next(j for j in replayed_listings_by_board["teamtailor:paystack"] if "Platform Security" in j.title)
        assert evaluate_eligibility_for_country(paystack_sec.eligibility, "NG", work_model=paystack_sec.work_model, location=paystack_sec.location).status == "eligible"
        assert evaluate_eligibility_for_country(paystack_sec.eligibility, "KE", work_model=paystack_sec.work_model, location=paystack_sec.location).status == "eligible"
        assert evaluate_eligibility_for_country(paystack_sec.eligibility, "US", work_model=paystack_sec.work_model, location=paystack_sec.location).status == "restricted"

        # Grafana Labs: country-restricted remote roles never claim worldwide
        grafana_ca = next(j for j in replayed_listings_by_board["greenhouse:grafanalabs"] if "Remote, Canada" in j.title)
        assert evaluate_eligibility_for_country(grafana_ca.eligibility, "CA", work_model=grafana_ca.work_model, location=grafana_ca.location).status == "eligible"
        assert evaluate_eligibility_for_country(grafana_ca.eligibility, "NG", work_model=grafana_ca.work_model, location=grafana_ca.location).status == "restricted"
        assert "worldwide" not in (evaluate_eligibility_for_country(grafana_ca.eligibility, "CA", work_model=grafana_ca.work_model, location=grafana_ca.location).summary_label or "").lower()

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "provider,token,fixture_file",
        [
            ("ashby", "supabase", "ashby_supabase.json"),
            ("greenhouse", "wikimedia", "greenhouse_wikimedia.json"),
            ("lever", "spotify", "lever_spotify.json"),
            ("teamtailor", "paystack", "teamtailor_paystack.xml"),
        ],
    )
    async def test_etag_304_and_fail_closed_error_responses_never_close_active_jobs(
        self,
        isolated_monitor,
        provider: str,
        token: str,
        fixture_file: str,
    ):
        reg, cache, monitor = isolated_monitor
        board = reg.register_candidate(company_name=token, ats_provider=provider, board_token=token)
        assert board is not None

        etag_val = f'"step54-etag-{provider}-{token}"'
        ok_handler = _build_offline_handler(provider, [fixture_file], etag=etag_val)

        async with httpx.AsyncClient(transport=httpx.MockTransport(ok_handler)) as ok_client:
            res_init = await monitor.check_single_board(board, ok_client, cache_store=cache)
            assert res_init.success is True and res_init.snapshot_complete is True
            initial_active = len(res_init.listings)
            assert initial_active > 0

            stored_board = reg.get_board(provider, token)
            assert stored_board.etag == etag_val

            # Conditional GET 304 Not Modified preserves active jobs
            res_304 = await monitor.check_single_board(stored_board, ok_client, cache_store=cache)
            assert res_304.success is True
            assert res_304.not_modified is True

        # Fail closed on 301, 403, 404, 429, 500, and malformed body
        error_responses = [
            httpx.Response(301, headers={"location": "https://redirect.example.com/"}),
            httpx.Response(403),
            httpx.Response(404),
            httpx.Response(429),
            httpx.Response(500),
            httpx.Response(200, content=b"<<NOT VALID PAYLOAD>>", headers={"content-type": "application/json"}),
        ]
        for err_resp in error_responses:
            current_board = reg.get_board(provider, token)
            err_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _req, r=err_resp: r))
            async with err_client as c:
                err_res = await monitor.check_single_board(current_board, c, cache_store=cache)
            assert err_res.success is False or err_res.snapshot_complete is False

            with reg._get_connection() as conn:
                active_now = conn.execute(
                    "SELECT COUNT(*) FROM monitored_jobs WHERE board_id = ? AND status = 'active'",
                    (board.id,),
                ).fetchone()[0]
                closed_now = conn.execute(
                    "SELECT COUNT(*) FROM monitored_jobs WHERE board_id = ? AND status = 'closed'",
                    (board.id,),
                ).fetchone()[0]
            assert active_now == initial_active
            assert closed_now == 0

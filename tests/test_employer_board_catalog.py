"""
Steps 54–55 Curated Employer Board Catalog, Offline Replay & Multi-Country Tests.

Validates:
- Catalog stays strictly within existing 9 MONITORABLE_PROVIDERS (no 10th ATS).
- Every committed Step 54 & Step 55 real fixture matches its evaluation_manifest.json SHA-256 & byte size.
- Idempotent catalog seeding + ADR 0030 CLI safety for `--seed-catalog`.
- Full offline native-adapter replay via BoardMonitor.check_single_board across all
  20 verified boards (including Workable widget + v2 detail hydration).
- Canonical deduplication on repeated poll, HTTP 304 preservation, and fail-closed
  non-closure across 301/403/404/429/500/malformed payloads.
- Global 12-country eligibility invariants (Nigeria kept distinct from global and
  wider Africa / Egypt / South Africa; remote-restricted roles never labeled worldwide)
  plus worldwide diversification and early-career coverage (intern, graduate, junior).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
import pytest

from src.ats.ats_url_parser import is_valid_board_slug
from src.monitoring.board_monitor import BoardMonitor, main as board_monitor_main
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoardRegistry,
    build_canonical_board_url,
)
from src.safety.db_safety import UnsafeDatabasePathError
from src.extraction.eligibility_extractor import evaluate_eligibility_for_country
from src.monitoring.employer_board_catalog import (
    CATALOG_ACTIVATION_COMMAND,
    VERIFIED_EMPLOYER_BOARDS,
    preview_catalog_activation,
    seed_verified_employer_boards,
)
from src.safety.url_safety import StaticDnsResolver, use_dns_resolver

FIXTURES_54_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "step54_employers"
FIXTURES_55_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "step55_employers"
FIXTURES_56_DIR = Path(__file__).resolve().parent / "fixtures" / "real" / "step56_employers"
MANIFEST_54_PATH = FIXTURES_54_DIR / "evaluation_manifest.json"
MANIFEST_55_PATH = FIXTURES_55_DIR / "evaluation_manifest.json"
MANIFEST_56_PATH = FIXTURES_56_DIR / "evaluation_manifest.json"
REPRESENTATIVE_COUNTRIES = ["NG", "GH", "KE", "ZA", "EG", "GB", "DE", "US", "CA", "IN", "SG", "AU"]


def _load_manifest(path: Path = MANIFEST_54_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_offline_handler(
    provider: str,
    fixture_files: list[str],
    *,
    fixtures_dir: Path = FIXTURES_54_DIR,
    etag: str | None = None,
):
    primary_name = fixture_files[0]
    primary_bytes = (fixtures_dir / primary_name).read_bytes()
    detail_map = None
    if provider == "workable" and len(fixture_files) > 1:
        detail_map = json.loads((fixtures_dir / fixture_files[1]).read_text(encoding="utf-8"))

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
        assert len(VERIFIED_EMPLOYER_BOARDS) == 28

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
        m54 = _load_manifest(MANIFEST_54_PATH)
        m55 = _load_manifest(MANIFEST_55_PATH)
        m56 = _load_manifest(MANIFEST_56_PATH)
        assert m54["serper_credits_spent"] == 0
        assert m55["serper_credits_spent"] == 0
        assert m54["selected_boards_count"] == 10
        assert m55["new_boards_count"] == 10
        assert m56["new_boards_count"] == 8
        assert m56["total_catalog_boards_count"] == len(VERIFIED_EMPLOYER_BOARDS)
        assert m56["serper_credits_spent"] == 0
        assert m56["monitorable_providers_count"] == 9

        manifest_keys = {
            (b["ats_provider"], b["board_token"].lower())
            for b in [*m54["selected_boards"], *m55["selected_boards"], *m56["selected_boards"]]
        }
        catalog_keys = {(e.ats_provider, e.board_token.lower()) for e in VERIFIED_EMPLOYER_BOARDS}
        assert manifest_keys == catalog_keys

        for base_dir, manifest in ((FIXTURES_54_DIR, m54), (FIXTURES_55_DIR, m55), (FIXTURES_56_DIR, m56)):
            for b in manifest["selected_boards"]:
                for fname, meta in b["fixtures"].items():
                    p = base_dir / fname
                    assert p.exists(), f"Missing fixture file {p}"
                    raw = p.read_bytes().replace(b"\r\n", b"\n")
                    assert len(raw) == meta["bytes"]
                    assert hashlib.sha256(raw).hexdigest() == meta["sha256"]

    def test_idempotent_seeding_and_cli_seed_catalog_db_safety(self, isolated_monitor, tmp_path: Path):
        reg, _cache, monitor = isolated_monitor
        seeded_first = seed_verified_employer_boards(reg)
        seeded_second = monitor.seed_curated_boards()

        assert len(seeded_first) == 28
        assert len(seeded_second) == 28

        with reg._get_connection() as conn:
            total_rows = conn.execute("SELECT COUNT(*) FROM company_boards").fetchone()[0]
        assert total_rows == 28

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
            patch("src.core.settings.settings.sqlite_db_path", cli_db),
            patch("src.monitoring.board_monitor.company_board_registry", cli_reg),
            patch("src.monitoring.board_monitor._default_cache_store", cli_cache),
            patch.object(sys, "argv", ["board_monitor", "--seed-catalog"]),
        ):
            board_monitor_main()

        with cli_reg._get_connection() as conn:
            cli_rows = conn.execute("SELECT COUNT(*) FROM company_boards").fetchone()[0]
        assert cli_rows == 28

        # CLI `--preview-catalog` returns catalog activation status without opening operational DB
        preview = preview_catalog_activation()
        assert len(preview) == 28
        assert all(item["catalogued"] and not item["operationally_registered"] for item in preview)

        # CLI `--seed-catalog` must fail closed against protected operational data/cache.sqlite in test mode
        op_reg = CompanyBoardRegistry(db_path="data/cache.sqlite", _defer_init=True)
        with (
            patch.dict("os.environ", {"SQLITE_DB_PATH": "data/cache.sqlite"}),
            patch("src.core.settings.settings.sqlite_db_path", "data/cache.sqlite"),
            patch("src.monitoring.board_monitor.company_board_registry", op_reg),
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

    def test_cli_preview_catalog_never_opens_operational_db(self, capsys):
        with (
            patch("src.monitoring.board_monitor.cli_operational_runtime") as mock_runtime,
            patch.object(sys, "argv", ["board_monitor", "--preview-catalog"]),
        ):
            board_monitor_main()
        mock_runtime.assert_not_called()
        payload = json.loads(capsys.readouterr().out)
        assert payload["catalogued_boards"] == 28
        assert payload["operational_db_opened"] is False
        assert payload["operationally_registered"] is False
        assert payload["activation_command"] == CATALOG_ACTIVATION_COMMAND
        assert len(payload["boards"]) == 28


class TestOfflineFixtureReplayAndResilience:
    @pytest.fixture(autouse=True)
    def _offline_fixture_dns(self):
        resolver = StaticDnsResolver({
            "careers.paystack.com": "93.184.216.34",
            "propertyfinder.teamtailor.com": "93.184.216.34",
        })
        with use_dns_resolver(resolver):
            yield

    @pytest.mark.anyio
    async def test_replay_all_28_catalog_boards_dedup_and_12_country_eligibility(self, isolated_monitor):
        reg, cache, monitor = isolated_monitor
        m54 = _load_manifest(MANIFEST_54_PATH)
        m55 = _load_manifest(MANIFEST_55_PATH)
        m56 = _load_manifest(MANIFEST_56_PATH)
        spec_and_dir_by_key: dict[str, tuple[dict, Path]] = {
            **{b["key"]: (b, FIXTURES_54_DIR) for b in m54["selected_boards"]},
            **{b["key"]: (b, FIXTURES_55_DIR) for b in m55["selected_boards"]},
            **{b["key"]: (b, FIXTURES_56_DIR) for b in m56["selected_boards"]},
        }

        boards = monitor.seed_curated_boards()
        assert len(boards) == 28

        replayed_listings_by_board: dict[str, list] = {}
        for board in boards:
            key = f"{board.ats_provider}:{board.board_token}"
            spec, fdir = spec_and_dir_by_key[key]
            fixture_files = list(spec["fixtures"].keys())
            handler = _build_offline_handler(board.ats_provider, fixture_files, fixtures_dir=fdir)

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

        # Workable multi-city deduplication verified across FairMoney (59->25) and Kuda (7->5)
        fairmoney_row = reg.get_board("workable", "fairmoney")
        assert fairmoney_row is not None and fairmoney_row.active_job_count == 59
        kuda_row = reg.get_board("workable", "kuda")
        assert kuda_row is not None and kuda_row.active_job_count == 7

        # Step 54 Supabase checks + SF non-tech guard
        supa_jobs = replayed_listings_by_board["ashby:supabase"]
        ai_plat = next(j for j in supa_jobs if j.title == "AI Platform Engineer")
        amer_csa = next(j for j in supa_jobs if j.title == "Customer Solution Architect (AMER)")
        sf_comm = next(j for j in supa_jobs if "Community Lead (SF)" in (j.title or ""))
        for cc in REPRESENTATIVE_COUNTRIES:
            assert evaluate_eligibility_for_country(ai_plat.eligibility, cc, work_model=ai_plat.work_model, location=ai_plat.location).status == "eligible"
        assert amer_csa.eligibility is not None and amer_csa.eligibility.classification == "region_restricted"
        assert sf_comm.eligibility is not None and sf_comm.eligibility.classification != "worldwide"

        # Step 55 fixes on Step 54 fixtures: FairMoney Lending SWE & Paystack DevOps/DBA now NG-eligible
        fm_lending = next(j for j in replayed_listings_by_board["workable:fairmoney"] if "Software Engineer-Lending" in j.title)
        assert evaluate_eligibility_for_country(fm_lending.eligibility, "NG", work_model=fm_lending.work_model, location=fm_lending.location).status == "eligible"
        paystack_devops = next(j for j in replayed_listings_by_board["teamtailor:paystack"] if j.title == "Senior DevOps Engineer")
        paystack_dba = next(j for j in replayed_listings_by_board["teamtailor:paystack"] if j.title == "Senior Database Administrator")
        for pj in (paystack_devops, paystack_dba):
            assert evaluate_eligibility_for_country(pj.eligibility, "NG", work_model=pj.work_model, location=pj.location).status == "eligible"
            assert evaluate_eligibility_for_country(pj.eligibility, "KE", work_model=pj.work_model, location=pj.location).status == "eligible"
            assert evaluate_eligibility_for_country(pj.eligibility, "US", work_model=pj.work_model, location=pj.location).status == "restricted"

        # Step 54 Wikimedia multi-country check across 12 countries
        wiki_sre = next(j for j in replayed_listings_by_board["greenhouse:wikimedia"] if "Site Reliability" in j.title)
        for allowed_cc in ("GH", "KE", "ZA", "GB", "DE", "US", "CA", "IN", "SG"):
            assert evaluate_eligibility_for_country(wiki_sre.eligibility, allowed_cc, work_model=wiki_sre.work_model, location=wiki_sre.location).status == "eligible"
        for disallowed_cc in ("NG", "EG", "AU"):
            assert evaluate_eligibility_for_country(wiki_sre.eligibility, disallowed_cc, work_model=wiki_sre.work_model, location=wiki_sre.location).status == "restricted"

        # Step 55 Worldwide diversification: Metabase & Railway genuinely eligible across all 12 countries
        metabase_sec = next(j for j in replayed_listings_by_board["lever:metabase"] if j.title == "Security Engineer")
        railway_infra = next(j for j in replayed_listings_by_board["ashby:railway"] if j.title == "Infrastructure Engineer")
        for ww_job in (metabase_sec, railway_infra):
            assert ww_job.eligibility is not None and ww_job.eligibility.classification == "worldwide"
            for cc in REPRESENTATIVE_COUNTRIES:
                assert evaluate_eligibility_for_country(ww_job.eligibility, cc, work_model=ww_job.work_model, location=ww_job.location).status == "eligible"

        # Step 55 Multi-country remote & Africa-non-NG separation: DuckDuckGo & Kraken
        ddg_priv = next(j for j in replayed_listings_by_board["ashby:duck-duck-go"] if j.title == "Senior Privacy Engineer")
        for ok_cc in ("ZA", "IN", "SG", "GB", "US", "CA"):
            assert evaluate_eligibility_for_country(ddg_priv.eligibility, ok_cc, work_model=ddg_priv.work_model, location=ddg_priv.location).status == "eligible"
        assert evaluate_eligibility_for_country(ddg_priv.eligibility, "NG", work_model=ddg_priv.work_model, location=ddg_priv.location).status == "restricted"

        kraken_za = next(
            j for j in replayed_listings_by_board["ashby:kraken.com"]
            if j.eligibility and "ZA" in (j.eligibility.allowed_country_codes or []) and "GB" in (j.eligibility.allowed_country_codes or [])
        )
        assert evaluate_eligibility_for_country(kraken_za.eligibility, "ZA", work_model=kraken_za.work_model, location=kraken_za.location).status == "eligible"
        assert evaluate_eligibility_for_country(kraken_za.eligibility, "GB", work_model=kraken_za.work_model, location=kraken_za.location).status == "eligible"
        assert evaluate_eligibility_for_country(kraken_za.eligibility, "NG", work_model=kraken_za.work_model, location=kraken_za.location).status == "restricted"

        # Step 55 Kuda (NG hybrid & Abuja onsite) & Early-Career Boards (Electrum ZA, Whippy IE, Affirm CA/US, Lyft CA/US, Almedia DE)
        kuda_da = next(j for j in replayed_listings_by_board["workable:kuda"] if j.title == "Senior Data Analyst")
        assert evaluate_eligibility_for_country(kuda_da.eligibility, "NG", work_model=kuda_da.work_model, location=kuda_da.location).status == "eligible"
        assert evaluate_eligibility_for_country(kuda_da.eligibility, "US", work_model=kuda_da.work_model, location=kuda_da.location).status == "unknown"
        kuda_abuja = next(j for j in replayed_listings_by_board["workable:kuda"] if "Abuja" in (j.title or ""))
        assert evaluate_eligibility_for_country(kuda_abuja.eligibility, "NG", work_model=kuda_abuja.work_model, location=kuda_abuja.location).status == "eligible"
        assert evaluate_eligibility_for_country(kuda_abuja.eligibility, "US", work_model=kuda_abuja.work_model, location=kuda_abuja.location).status == "restricted"
        assert evaluate_eligibility_for_country(kuda_abuja.eligibility, "ZA", work_model=kuda_abuja.work_model, location=kuda_abuja.location).status == "restricted"

        electrum_grad = next(j for j in replayed_listings_by_board["workable:electrum"] if "Graduate Programme" in j.title)
        electrum_intern = next(j for j in replayed_listings_by_board["workable:electrum"] if "Internship" in j.title)
        for ej in (electrum_grad, electrum_intern):
            assert evaluate_eligibility_for_country(ej.eligibility, "ZA", work_model=ej.work_model, location=ej.location).status == "eligible"
            assert evaluate_eligibility_for_country(ej.eligibility, "NG", work_model=ej.work_model, location=ej.location).status == "restricted"

        affirm_ca = next(j for j in replayed_listings_by_board["greenhouse:affirm"] if "Software Engineer I" in j.title and "Canada" in (j.location or ""))
        assert evaluate_eligibility_for_country(affirm_ca.eligibility, "CA", work_model=affirm_ca.work_model, location=affirm_ca.location).status == "eligible"
        assert evaluate_eligibility_for_country(affirm_ca.eligibility, "NG", work_model=affirm_ca.work_model, location=affirm_ca.location).status == "restricted"

        lyft_interns = [j for j in replayed_listings_by_board["greenhouse:lyft"] if "Intern" in (j.title or "")]
        assert len(lyft_interns) >= 10

        almedia_jr = next(j for j in replayed_listings_by_board["ashby:almedia"] if "Junior Software Engineer - Data" in j.title)
        assert evaluate_eligibility_for_country(almedia_jr.eligibility, "DE", work_model=almedia_jr.work_model, location=almedia_jr.location).status == "eligible"
        assert evaluate_eligibility_for_country(almedia_jr.eligibility, "NG", work_model=almedia_jr.work_model, location=almedia_jr.location).status == "restricted"

        whippy_intern = next(j for j in replayed_listings_by_board["ashby:whippy"] if "Intern" in j.title)
        assert evaluate_eligibility_for_country(whippy_intern.eligibility, "IE", work_model=whippy_intern.work_model, location=whippy_intern.location).status == "eligible"
        assert evaluate_eligibility_for_country(whippy_intern.eligibility, "NG", work_model=whippy_intern.work_model, location=whippy_intern.location).status == "restricted"

        # Step 56 board assertions & city-hub fixes across newly promoted boards
        affirm_london = next(j for j in replayed_listings_by_board["greenhouse:affirm"] if "London" in (j.title or ""))
        assert affirm_london.eligibility.physical_location_country_code == "GB"
        assert evaluate_eligibility_for_country(affirm_london.eligibility, "GB", work_model=affirm_london.work_model, location=affirm_london.location).status == "eligible"
        assert evaluate_eligibility_for_country(affirm_london.eligibility, "NG", work_model=affirm_london.work_model, location=affirm_london.location).status == "unknown"

        elevenlabs_ww = next(j for j in replayed_listings_by_board["ashby:elevenlabs"] if j.title == "Full-Stack Engineer (Backend Leaning)")
        assert elevenlabs_ww.eligibility.classification == "worldwide"
        assert evaluate_eligibility_for_country(elevenlabs_ww.eligibility, "NG", work_model=elevenlabs_ww.work_model, location=elevenlabs_ww.location).status == "eligible"
        assert evaluate_eligibility_for_country(elevenlabs_ww.eligibility, "DE", work_model=elevenlabs_ww.work_model, location=elevenlabs_ww.location).status == "eligible"

        elevenlabs_eu = next(j for j in replayed_listings_by_board["ashby:elevenlabs"] if j.title == "Applied AI Engineer")
        assert elevenlabs_eu.eligibility.classification == "region_restricted"
        assert evaluate_eligibility_for_country(elevenlabs_eu.eligibility, "DE", work_model=elevenlabs_eu.work_model, location=elevenlabs_eu.location).status == "unknown"
        assert evaluate_eligibility_for_country(elevenlabs_eu.eligibility, "NG", work_model=elevenlabs_eu.work_model, location=elevenlabs_eu.location).status == "restricted"

        circle_lead = next(j for j in replayed_listings_by_board["ashby:circle"] if "Lead Engineer, Member Growth" in j.title)
        assert circle_lead.eligibility.classification == "worldwide"
        assert evaluate_eligibility_for_country(circle_lead.eligibility, "NG", work_model=circle_lead.work_model, location=circle_lead.location).status == "eligible"

        cohere_intern = next(j for j in replayed_listings_by_board["ashby:cohere"] if "Machine Learning Intern" in j.title)
        assert cohere_intern.work_model == "remote"
        assert evaluate_eligibility_for_country(cohere_intern.eligibility, "CA", work_model=cohere_intern.work_model, location=cohere_intern.location).status == "eligible"
        assert evaluate_eligibility_for_country(cohere_intern.eligibility, "US", work_model=cohere_intern.work_model, location=cohere_intern.location).status == "eligible"
        assert evaluate_eligibility_for_country(cohere_intern.eligibility, "NG", work_model=cohere_intern.work_model, location=cohere_intern.location).status == "restricted"

        keyrock_london = next(
            j
            for j in replayed_listings_by_board["ashby:keyrock"]
            if "Innovation Quant Developer Intern" in j.title and "London" in j.title
        )
        assert keyrock_london.eligibility.physical_location_country_code == "GB"
        assert evaluate_eligibility_for_country(keyrock_london.eligibility, "GB", work_model=keyrock_london.work_model, location=keyrock_london.location).status == "eligible"

        coinbase_sg = next(j for j in replayed_listings_by_board["greenhouse:coinbase"] if "Software Engineer Intern" in j.title and "Singapore" in (j.location or ""))
        assert coinbase_sg.eligibility.physical_location_country_code == "SG"
        assert evaluate_eligibility_for_country(coinbase_sg.eligibility, "SG", work_model=coinbase_sg.work_model, location=coinbase_sg.location).status == "eligible"
        assert evaluate_eligibility_for_country(coinbase_sg.eligibility, "NG", work_model=coinbase_sg.work_model, location=coinbase_sg.location).status == "unknown"

        sentry_intern = next(j for j in replayed_listings_by_board["ashby:sentry"] if "Intern" in j.title)
        assert evaluate_eligibility_for_country(sentry_intern.eligibility, "AT", work_model=sentry_intern.work_model, location=sentry_intern.location).status == "eligible"
        assert evaluate_eligibility_for_country(sentry_intern.eligibility, "NG", work_model=sentry_intern.work_model, location=sentry_intern.location).status == "unknown"

        pf_grad = next(j for j in replayed_listings_by_board["teamtailor:propertyfinder"] if "Graduate" in j.title)
        assert pf_grad.eligibility.physical_location_country_code == "AE"

        foodics_jr = next(j for j in replayed_listings_by_board["workable:foodics"] if "Junior AI Forward Engineer" in j.title)
        assert foodics_jr.work_model == "remote"
        assert foodics_jr.eligibility.physical_location_country_code == "JO"
        assert evaluate_eligibility_for_country(foodics_jr.eligibility, "JO", work_model=foodics_jr.work_model, location=foodics_jr.location).status == "unknown"

        # Step 55 & Step 56 diversification guarantees documented in evaluation_manifest.json
        assert m55["comparison"]["step55_combined_20_boards"]["concentration_nigeria_tech"]["largest_employer_share_pct"] < 60.0
        assert m55["comparison"]["step55_combined_20_boards"]["concentration_worldwide_tech"]["largest_employer_share_pct"] < 75.0
        assert m55["comparison"]["step55_combined_20_boards"]["career_stages_tech"]["early_career_total"] >= 30
        assert (
            m56["comparison"]["step56_combined_28_boards"]["concentration_worldwide_fresh90_tech"]["largest_employer_share_pct"]
            < m56["comparison"]["step55_baseline_20_boards_recomputed"]["concentration_worldwide_fresh90_tech"]["largest_employer_share_pct"]
        )
        assert m56["comparison"]["step56_combined_28_boards"]["concentration_nigeria_tech"]["largest_employer_share_pct"] < 45.0
        assert m56["early_career_crosstab_after"]["total_early_career_tech"] > m56["early_career_crosstab_before"]["total_early_career_tech"]
        assert m56["serper_credits_spent"] == 0

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "provider,token,fixture_file,fixtures_dir",
        [
            ("ashby", "supabase", "ashby_supabase.json", FIXTURES_54_DIR),
            ("greenhouse", "wikimedia", "greenhouse_wikimedia.json", FIXTURES_54_DIR),
            ("lever", "spotify", "lever_spotify.json", FIXTURES_54_DIR),
            ("teamtailor", "paystack", "teamtailor_paystack.xml", FIXTURES_54_DIR),
            ("lever", "metabase", "lever_metabase.json", FIXTURES_55_DIR),
            ("greenhouse", "affirm", "greenhouse_affirm.json", FIXTURES_55_DIR),
        ],
    )
    async def test_etag_304_and_fail_closed_error_responses_never_close_active_jobs(
        self,
        isolated_monitor,
        provider: str,
        token: str,
        fixture_file: str,
        fixtures_dir: Path,
    ):
        reg, cache, monitor = isolated_monitor
        board = reg.register_candidate(company_name=token, ats_provider=provider, board_token=token)
        assert board is not None

        etag_val = f'"step55-etag-{provider}-{token}"'
        ok_handler = _build_offline_handler(provider, [fixture_file], fixtures_dir=fixtures_dir, etag=etag_val)

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

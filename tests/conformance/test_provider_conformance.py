"""
Executable Provider Contract Conformance Suite (Clauses C1-C12).

Parametrized over every monitored adapter in ``BOARD_ADAPTERS`` using offline
fixtures in ``tests/conformance/fixtures.py`` and disposable SQLite DBs in
``tmp_path``. No live network or real DNS calls are ever made.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
import importlib
from pathlib import Path
import re
from typing import Any

import httpx
import pytest

from src.core.http_resilience import resilience_manager
from src.monitoring.board_monitor import BoardMonitor
from src.providers.board_adapters import BOARD_ADAPTERS, GreenhouseBoardAdapter
from src.safety.url_safety import StaticDnsResolver, use_dns_resolver
from src.storage.company_board_registry import CompanyBoardRegistry
from tests.conformance.fixtures import ALL_PROVIDERS, PROVIDER_SPECS

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = REPO_ROOT / "src" / "providers"


def _load_contract_module() -> Any | None:
    try:
        return importlib.import_module("src.providers.contract")
    except ImportError:
        return None


@pytest.fixture(autouse=True)
def _reset_resilience_per_test() -> Any:
    resilience_manager.reset()
    yield
    resilience_manager.reset()


def _seed_board_and_initial_poll(
    tmp_path: Path,
    provider: str,
) -> tuple[CompanyBoardRegistry, BoardMonitor, Any]:
    spec = PROVIDER_SPECS[provider]
    reg = CompanyBoardRegistry(db_path=str(tmp_path / "conformance.sqlite"))
    monitor = BoardMonitor(registry=reg)
    board = reg.register_candidate(
        company_name=spec.company_name,
        ats_provider=spec.provider,
        board_token=spec.board_token,
        board_url=spec.board_url,
    )
    assert board is not None
    # Mark logo checked so offline fixtures do not attempt extra logo enrichment fetches
    with reg._get_connection() as conn:
        conn.execute(
            "UPDATE company_boards SET company_logo_checked_at = 1000.0 WHERE id = ?",
            (board.id,),
        )
        conn.commit()
    board = reg.get_board(spec.provider, spec.board_token)
    assert board is not None
    return reg, monitor, spec


def test_conformance_registry_covers_every_board_adapter() -> None:
    assert set(PROVIDER_SPECS.keys()) == set(BOARD_ADAPTERS.keys())


# ---------------------------------------------------------------------------
# C1: Incomplete snapshot never closes any job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
@pytest.mark.parametrize(
    "failure_mode",
    ["http_500", "malformed", "missing_root_shape", "truncated_snapshot", "oversized_stream"],
)
async def test_c1_incomplete_snapshot_never_closes_jobs(
    tmp_path: Path,
    provider: str,
    failure_mode: str,
) -> None:
    reg, monitor, spec = _seed_board_and_initial_poll(tmp_path, provider)
    try:
        with use_dns_resolver(spec.resolver()):
            board = reg.get_board(spec.provider, spec.board_token)
            assert board is not None
            async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
                initial = await monitor.check_single_board(board, client)
            assert initial.success is True
            initial_active = reg.get_monitored_jobs_for_board(board.id)
            assert len(initial_active) >= 2

            board_after = reg.get_board(spec.provider, spec.board_token)
            assert board_after is not None
            adapter = BOARD_ADAPTERS[provider]
            async with httpx.AsyncClient(transport=spec.build_transport(failure_mode, {})) as client:
                res = await adapter.check_board(
                    board_after,
                    client,
                    max_response_bytes=3 * 1024 * 1024,
                    resolver=spec.resolver(),
                )
            assert res.snapshot_complete is False
            if not (provider == "teamtailor" and failure_mode == "truncated_snapshot"):
                # Teamtailor partial RSS + HTML fallback failure preserves partial RSS with snapshot_complete=False
                assert res.success is False
            elif getattr(res, "incomplete_reason", None) is None and res.success:
                pytest.fail("Teamtailor partial snapshot missing incomplete_reason")

            # Run several times in BoardMonitor to ensure even multi-strike policies never close on failure
            for _ in range(3):
                resilience_manager.reset()
                cur_board = reg.get_board(spec.provider, spec.board_token)
                assert cur_board is not None
                async with httpx.AsyncClient(transport=spec.build_transport(failure_mode, {})) as client:
                    await monitor.check_single_board(cur_board, client)

            still_active = reg.get_monitored_jobs_for_board(board.id)
            assert set(still_active.keys()) == set(initial_active.keys())
    finally:
        reg.clear()


# ---------------------------------------------------------------------------
# C2: Genuinely empty board vs failed fetch distinguished
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c2_empty_board_vs_failed_fetch(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()

    with use_dns_resolver(spec.resolver()):
        async with httpx.AsyncClient(transport=spec.build_transport("empty", {})) as client:
            empty_res = await adapter.check_board(board, client, resolver=spec.resolver())
        assert empty_res.success is True
        assert empty_res.not_modified is False
        assert empty_res.snapshot_complete is True
        assert empty_res.listings == []
        assert getattr(empty_res, "failure_kind", None) is None

        for err_mode in ("http_500", "http_404", "malformed", "missing_root_shape"):
            resilience_manager.reset()
            async with httpx.AsyncClient(transport=spec.build_transport(err_mode, {})) as client:
                fail_res = await adapter.check_board(board, client, resolver=spec.resolver())
            assert fail_res.success is False
            assert fail_res.snapshot_complete is False
            assert getattr(fail_res, "failure_kind", None) is not None


# ---------------------------------------------------------------------------
# C3: Identity stability across polls & ID drift / duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c3_identity_stability_duplicate_rejection_and_id_drift(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    contract = _load_contract_module()

    with use_dns_resolver(spec.resolver()):
        board = spec.make_board()
        async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
            r1 = await adapter.check_board(board, client, resolver=spec.resolver())
        assert r1.success is True and len(r1.listings) >= 2

        async with httpx.AsyncClient(transport=spec.build_transport("edited_title", {})) as client:
            r2 = await adapter.check_board(board, client, resolver=spec.resolver())
        assert r2.success is True
        assert {j.id for j in r2.listings} == {j.id for j in r1.listings}

        # Duplicate IDs within one snapshot must fail closed
        async with httpx.AsyncClient(transport=spec.build_transport("duplicate_ids", {})) as client:
            dup_res = await adapter.check_board(board, client, resolver=spec.resolver())
        assert dup_res.success is False
        assert dup_res.snapshot_complete is False

    assert contract is not None and hasattr(contract, "detect_id_drift"), (
        "detect_id_drift primitive not extracted in src/providers/contract.py"
    )
    drifted = [
        r1.listings[0].model_copy(update={"id": f"{provider}:{spec.board_token}:drifted-id-999"}),
        *r1.listings[1:],
    ]
    events = contract.detect_id_drift(
        r1.listings,
        drifted,
        provider=provider,
        board_token=spec.board_token,
    )
    assert len(events) == 1
    assert events[0].previous_job_id == r1.listings[0].id
    assert events[0].current_job_id == f"{provider}:{spec.board_token}:drifted-id-999"


# ---------------------------------------------------------------------------
# C4: Canonical 64-hex SHA-256 fingerprint (noise invariant & edit sensitive)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c4_canonical_sha256_fingerprint_noise_invariance_and_edits(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]

    with use_dns_resolver(spec.resolver()):
        board = spec.make_board()
        async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
            r1 = await adapter.check_board(board, client, resolver=spec.resolver())
        assert r1.success is True and r1.content_fingerprint is not None
        assert re.fullmatch(r"[0-9a-f]{64}", r1.content_fingerprint), (
            f"{provider} fingerprint must be full canonical 64-hex SHA-256, got {r1.content_fingerprint!r}"
        )

        # Reordering + JSON key order + extra whitespace noise must keep fingerprint identical
        board_same = spec.make_board(content_fingerprint=r1.content_fingerprint)
        async with httpx.AsyncClient(
            transport=spec.build_transport("reordered_whitespace_noise", {})
        ) as client:
            r_noisy = await adapter.check_board(board_same, client, resolver=spec.resolver())
        assert r_noisy.success is True
        assert r_noisy.content_fingerprint == r1.content_fingerprint
        assert r_noisy.not_modified is True

        # Relevant edits (title + deep content past offset 250) must invalidate fingerprint
        async with httpx.AsyncClient(transport=spec.build_transport("edited_title", {})) as client:
            r_title = await adapter.check_board(board_same, client, resolver=spec.resolver())
        assert r_title.success is True
        assert r_title.not_modified is False
        assert r_title.content_fingerprint != r1.content_fingerprint

        async with httpx.AsyncClient(
            transport=spec.build_transport("edited_deep_description", {})
        ) as client:
            r_deep = await adapter.check_board(board_same, client, resolver=spec.resolver())
        assert r_deep.success is True
        assert r_deep.not_modified is False
        assert r_deep.content_fingerprint != r1.content_fingerprint


# ---------------------------------------------------------------------------
# C5: 304 / unchanged response mutates and closes nothing
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c5_not_modified_304_or_unchanged_mutates_and_closes_nothing(
    tmp_path: Path,
    provider: str,
) -> None:
    reg, monitor, spec = _seed_board_and_initial_poll(tmp_path, provider)
    try:
        with use_dns_resolver(spec.resolver()):
            board = reg.get_board(spec.provider, spec.board_token)
            assert board is not None
            async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
                r1 = await monitor.check_single_board(board, client)
            assert r1.success is True and not r1.not_modified
            initial_active = reg.get_monitored_jobs_for_board(board.id)
            assert len(initial_active) >= 2
            first_seen_ids = set(initial_active.keys())

            # Unchanged HTTP 200 payload matching content_fingerprint
            b2 = reg.get_board(spec.provider, spec.board_token)
            assert b2 is not None and b2.content_fingerprint
            async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
                r_fp = await monitor.check_single_board(b2, client)
            assert r_fp.success is True
            assert r_fp.not_modified is True
            assert r_fp.listings == []

            # Conditional 304 for providers supporting ETag / If-None-Match
            if spec.supports_http_304:
                b3 = reg.get_board(spec.provider, spec.board_token)
                assert b3 is not None
                if not b3.etag:
                    b3.etag = f'"{provider}-v1"'

                seen_inm: list[str | None] = []
                inner_transport = spec.build_transport("conditional_304", {})

                def _capture_304(req: httpx.Request) -> httpx.Response:
                    seen_inm.append(req.headers.get("If-None-Match"))
                    resp = inner_transport.handle_request(req)
                    if resp.status_code != 304:
                        return httpx.Response(412, text="Expected conditional 304", request=req)
                    return resp

                async with httpx.AsyncClient(transport=httpx.MockTransport(_capture_304)) as client:
                    r_304 = await monitor.check_single_board(b3, client)
                assert any(v is not None for v in seen_inm), f"{provider} did not send If-None-Match"
                assert r_304.success is True
                assert r_304.not_modified is True
                assert r_304.listings == []

            after_active = reg.get_monitored_jobs_for_board(board.id)
            assert set(after_active.keys()) == first_seen_ids
    finally:
        reg.clear()


# ---------------------------------------------------------------------------
# C6: 3 MiB response size cap enforced fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
@pytest.mark.parametrize("cap_mode", ["oversized_content_length", "oversized_stream"])
async def test_c6_response_cap_3mib_fail_closed(provider: str, cap_mode: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()
    contract = _load_contract_module()

    with use_dns_resolver(spec.resolver()):
        async with httpx.AsyncClient(transport=spec.build_transport(cap_mode, {})) as client:
            res = await adapter.check_board(
                board,
                client,
                max_response_bytes=3 * 1024 * 1024,
                resolver=spec.resolver(),
            )
    assert res.success is False
    assert res.snapshot_complete is False
    assert contract is not None, "FailureKind enum missing in src/providers/contract.py"
    assert res.failure_kind == contract.FailureKind.RESPONSE_TOO_LARGE


# ---------------------------------------------------------------------------
# C7: Shared host-resilience layer & SSRF validation; no adapter builds own client
# ---------------------------------------------------------------------------


def test_c7_ast_no_adapter_builds_own_client_or_bypasses_shared_http() -> None:
    assert (PROVIDERS_DIR / "http.py").is_file(), "Shared src/providers/http.py primitive missing"
    for py_file in sorted(PROVIDERS_DIR.glob("*.py")):
        if py_file.name in {"__init__.py", "http.py"}:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr in {"AsyncClient", "Client"}:
                    pytest.fail(f"{py_file.name}:{node.lineno} constructs its own httpx client")
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"client", "http_client", "http"}
                    and attr in {"get", "post", "put", "delete", "head", "patch", "request", "stream"}
                ):
                    pytest.fail(
                        f"{py_file.name}:{node.lineno} calls {node.func.value.id}.{attr}() directly instead of src/providers/http.py"
                    )


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c7_runtime_circuit_breaker_rate_limit_and_ssrf_block(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()
    contract = _load_contract_module()
    assert contract is not None, "FailureKind enum missing in src/providers/contract.py"

    # 1. Open circuit breaker -> short-circuits with ZERO HTTP requests
    state_cb: dict[str, Any] = {}
    for _ in range(10):
        resilience_manager.record_failure(spec.primary_host)
    async with httpx.AsyncClient(transport=spec.build_transport("normal", state_cb)) as client:
        cb_res = await adapter.check_board(board, client, resolver=spec.resolver())
    assert cb_res.success is False
    assert cb_res.snapshot_complete is False
    assert cb_res.failure_kind == contract.FailureKind.CIRCUIT_OPEN
    assert state_cb.get("calls", 0) == 0

    # 2. Host rate limit backoff -> short-circuits with ZERO HTTP requests
    resilience_manager.reset()
    state_rl: dict[str, Any] = {}
    resilience_manager.record_rate_limit(spec.primary_host, "30")
    async with httpx.AsyncClient(transport=spec.build_transport("normal", state_rl)) as client:
        rl_res = await adapter.check_board(board, client, resolver=spec.resolver())
    assert rl_res.success is False
    assert rl_res.snapshot_complete is False
    assert rl_res.failure_kind == contract.FailureKind.RATE_LIMITED
    assert state_rl.get("calls", 0) == 0

    # 3. Private DNS resolution via SSRF check -> blocked before ZERO HTTP requests
    resilience_manager.reset()
    state_ssrf: dict[str, Any] = {}
    unsafe_resolver = StaticDnsResolver({spec.primary_host: "127.0.0.1"})
    with use_dns_resolver(unsafe_resolver):
        async with httpx.AsyncClient(transport=spec.build_transport("normal", state_ssrf)) as client:
            ssrf_res = await adapter.check_board(board, client, resolver=unsafe_resolver)
    assert ssrf_res.success is False
    assert ssrf_res.snapshot_complete is False
    assert ssrf_res.failure_kind == contract.FailureKind.UNSAFE_URL
    assert state_ssrf.get("calls", 0) == 0


# ---------------------------------------------------------------------------
# C8: Missing-job confirmation configured through one policy object
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c8_reconciliation_policy_object(tmp_path: Path, provider: str) -> None:
    contract = _load_contract_module()
    assert contract is not None and hasattr(contract, "ReconciliationPolicy"), (
        "ReconciliationPolicy missing in src/providers/contract.py"
    )
    policy = contract.get_reconciliation_policy(provider)
    spec = PROVIDER_SPECS[provider]
    assert policy.missing_confirmation_threshold == spec.expected_missing_threshold

    reg, _, _ = _seed_board_and_initial_poll(tmp_path, provider)
    try:
        monitor = BoardMonitor(
            registry=reg,
            reconciliation_policy=contract.ReconciliationPolicy(missing_confirmation_threshold=2),
        )
        with use_dns_resolver(spec.resolver()):
            board = reg.get_board(spec.provider, spec.board_token)
            assert board is not None
            async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client:
                r1 = await monitor.check_single_board(board, client)
            assert r1.success is True
            assert len(reg.get_monitored_jobs_for_board(board.id)) >= 2

            # Poll 2: complete snapshot with only 1 job -> missing jobs remain active after 1st strike
            b2 = reg.get_board(spec.provider, spec.board_token)
            assert b2 is not None
            async with httpx.AsyncClient(transport=spec.build_transport("subset_one", {})) as client:
                r2 = await monitor.check_single_board(b2, client)
            assert r2.success is True
            assert len(reg.get_monitored_jobs_for_board(board.id)) >= 2

            # Poll 3: second consecutive complete missing observation -> closes missing jobs
            b3 = reg.get_board(spec.provider, spec.board_token)
            assert b3 is not None
            # Clear ETag/fingerprint to simulate fresh poll with same 1-job subset
            with reg._get_connection() as conn:
                conn.execute(
                    "UPDATE company_boards SET etag = NULL, content_fingerprint = NULL WHERE id = ?",
                    (b3.id,),
                )
                conn.commit()
            b3 = reg.get_board(spec.provider, spec.board_token)
            assert b3 is not None
            async with httpx.AsyncClient(transport=spec.build_transport("subset_one", {})) as client:
                r3 = await monitor.check_single_board(b3, client)
            assert r3.success is True
            assert len(reg.get_monitored_jobs_for_board(board.id)) == 1
    finally:
        reg.clear()


# ---------------------------------------------------------------------------
# C9: Unknown stays null (ADR 0001)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c9_unknown_stays_null_adr_0001(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()

    with use_dns_resolver(spec.resolver()):
        async with httpx.AsyncClient(transport=spec.build_transport("neutral_adr0001", {})) as client:
            res = await adapter.check_board(board, client, resolver=spec.resolver())
    assert res.success is True and len(res.listings) == 1
    job = res.listings[0]
    assert job.work_model is None
    assert job.is_remote is None
    assert job.salary is None
    assert job.employment_type is None
    if job.eligibility is not None:
        assert job.eligibility.nigeria_eligible is None
        assert job.eligibility.classification == "unknown"


# ---------------------------------------------------------------------------
# C10: Deterministic output for a given fixture with injected clock and no network
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c10_deterministic_output_with_injected_clock(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()
    fixed_clock = lambda: datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    with use_dns_resolver(spec.resolver()):
        async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client1:
            r1 = await adapter.check_board(
                board, client1, clock=fixed_clock, resolver=spec.resolver()
            )
        async with httpx.AsyncClient(transport=spec.build_transport("normal", {})) as client2:
            r2 = await adapter.check_board(
                board, client2, clock=fixed_clock, resolver=spec.resolver()
            )

    assert r1.success is True and r2.success is True
    assert r1.content_fingerprint == r2.content_fingerprint
    assert [j.model_dump() for j in r1.listings] == [j.model_dump() for j in r2.listings]
    assert r1.detail_states == r2.detail_states
    assert all(j.scraped_at == fixed_clock() for j in r1.listings)


# ---------------------------------------------------------------------------
# C11: Cancellation propagates (never swallowed)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c11_cancellation_propagates(provider: str) -> None:
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()

    with use_dns_resolver(spec.resolver()):
        async with httpx.AsyncClient(transport=spec.build_transport("cancelled", {})) as client:
            with pytest.raises(asyncio.CancelledError):
                await adapter.check_board(board, client, resolver=spec.resolver())


@pytest.mark.anyio
async def test_c11_greenhouse_detail_and_board_monitor_propagate_cancellation(tmp_path: Path) -> None:
    adapter = GreenhouseBoardAdapter()
    spec = PROVIDER_SPECS["greenhouse"]
    board = spec.make_board()

    def _gh_detail_cancel(req: httpx.Request) -> httpx.Response:
        if "/jobs/" in str(req.url):
            raise asyncio.CancelledError()
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 42,
                        "title": "Engineer",
                        "absolute_url": "https://boards.greenhouse.io/wikimedia/jobs/42",
                        "location": {"name": "Remote"},
                        "updated_at": "2026-10-01T10:00:00Z",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(_gh_detail_cancel)) as client:
        with pytest.raises(asyncio.CancelledError):
            await adapter.check_board(
                board, client, fetch_publication_dates=True, resolver=spec.resolver()
            )

    reg, monitor, _ = _seed_board_and_initial_poll(tmp_path, "greenhouse")
    try:
        async with httpx.AsyncClient(transport=spec.build_transport("cancelled", {})) as client:
            with pytest.raises(asyncio.CancelledError):
                await monitor.poll_due_boards(max_boards=5, client=client)
    finally:
        reg.clear()


# ---------------------------------------------------------------------------
# C12: Failures classified with closed enum FailureKind, never free text
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ALL_PROVIDERS)
async def test_c12_closed_failure_kind_enum(provider: str) -> None:
    contract = _load_contract_module()
    assert contract is not None and hasattr(contract, "FailureKind"), (
        "FailureKind enum missing in src/providers/contract.py"
    )
    FailureKind = contract.FailureKind
    spec = PROVIDER_SPECS[provider]
    adapter = BOARD_ADAPTERS[provider]
    board = spec.make_board()

    expected_map = {
        "http_404": FailureKind.NOT_FOUND,
        "http_429": FailureKind.RATE_LIMITED,
        "http_500": FailureKind.HTTP_ERROR,
        "timeout": FailureKind.TIMEOUT,
        "network": FailureKind.NETWORK_ERROR,
        "malformed": FailureKind.PARSE_ERROR,
        "missing_root_shape": FailureKind.PARSE_ERROR,
        "oversized_stream": FailureKind.RESPONSE_TOO_LARGE,
    }
    with use_dns_resolver(spec.resolver()):
        for mode, expected_kind in expected_map.items():
            resilience_manager.reset()
            async with httpx.AsyncClient(transport=spec.build_transport(mode, {})) as client:
                res = await adapter.check_board(
                    board,
                    client,
                    max_response_bytes=3 * 1024 * 1024,
                    resolver=spec.resolver(),
                )
            assert res.success is False
            assert isinstance(res.failure_kind, FailureKind), (
                f"{provider} ({mode}) returned non-enum failure_kind={res.failure_kind!r}"
            )
            assert res.failure_kind == expected_kind, (
                f"{provider} ({mode}) expected {expected_kind}, got {res.failure_kind}"
            )

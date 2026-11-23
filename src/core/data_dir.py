"""Configurable data directory and backward-compatible storage path resolution.

Provides `BOTTOM_POT_DATA_DIR` support so fresh production installs store state
outside the repository tree by default while keeping legacy `data/cache.sqlite`
and `subscriptions.csv` installs working unchanged until migrated.

Automated test/E2E/CI contexts always isolate onto a disposable directory and
fail closed if resolved paths overlap any protected operational location.
"""

from __future__ import annotations

import atexit
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.safety.db_safety import (
    REPO_ROOT,
    OwnedDisposableWorkspace,
    assert_safe_sqlite_db_path,
    assert_safe_subscriptions_path,
    default_production_data_dir,
    is_test_or_disposable_context,
    resolve_canonical_path_following_links,
)

DataDirMode = Literal[
    "test",
    "configured_data_dir",
    "legacy_repo_install",
    "default_production_dir",
]

_DEFAULT_TEST_WS_LOCK = threading.Lock()
_DEFAULT_TEST_WORKSPACE: OwnedDisposableWorkspace | None = None


def _get_or_create_default_test_workspace() -> OwnedDisposableWorkspace:
    global _DEFAULT_TEST_WORKSPACE
    with _DEFAULT_TEST_WS_LOCK:
        if _DEFAULT_TEST_WORKSPACE is None:
            ws = OwnedDisposableWorkspace.create(prefix="bottom-pot-test-default-")
            atexit.register(ws.cleanup)
            _DEFAULT_TEST_WORKSPACE = ws
        return _DEFAULT_TEST_WORKSPACE


def legacy_repo_data_dir(repo_root: Path = REPO_ROOT) -> Path:
    """Return the legacy in-repository data directory path (`<repo>/data`)."""
    return repo_root / "data"


@dataclass(frozen=True)
class ResolvedDataPaths:
    data_dir: Path
    sqlite_db_path: Path
    subscriptions_file: Path
    mode: DataDirMode
    legacy_db_present: bool


def _clean_opt_path(raw: str | os.PathLike[str] | None) -> str | None:
    if raw is None:
        return None
    text = os.fspath(raw).strip()
    return text or None


def resolve_data_paths(
    *,
    configured_data_dir: str | os.PathLike[str] | None = None,
    configured_db_path: str | os.PathLike[str] | None = None,
    configured_subscriptions_file: str | os.PathLike[str] | None = None,
    repo_root: Path = REPO_ROOT,
    is_test: bool | None = None,
) -> ResolvedDataPaths:
    """
    Resolve effective SQLite DB, subscriptions CSV, and parent data directory.

    Precedence (production / non-test):
    1. Explicit `BOTTOM_POT_DATA_DIR` (`configured_data_dir`): places state under that dir
       unless `SQLITE_DB_PATH` / `SUBSCRIPTIONS_FILE` explicitly overrides individual files.
    2. Legacy install compatibility: if `SQLITE_DB_PATH` is explicitly set OR legacy
       `<repo_root>/data/cache.sqlite` already exists on disk, keep existing repo paths.
    3. Fresh production install: default outside the repository tree via
       `default_production_data_dir()`.

    Test / E2E / CI contexts always isolate to disposable storage and fail closed if an
    explicit test target or `BOTTOM_POT_DATA_DIR` resolves to a protected path.
    """
    data_dir_str = _clean_opt_path(configured_data_dir)
    db_path_str = _clean_opt_path(configured_db_path)
    subs_str = _clean_opt_path(configured_subscriptions_file)

    legacy_dir = legacy_repo_data_dir(repo_root)
    legacy_db = legacy_dir / "cache.sqlite"
    legacy_present = legacy_db.exists()
    effective_test = is_test_or_disposable_context() if is_test is None else bool(is_test)

    if effective_test:
        if db_path_str is not None:
            resolved_db = Path(db_path_str).expanduser()
            resolved_dir = (
                Path(data_dir_str).expanduser()
                if data_dir_str is not None
                else resolved_db.parent
            )
            resolved_subs = (
                Path(subs_str).expanduser()
                if subs_str is not None
                else (resolved_dir / "subscriptions.csv")
            )
            return ResolvedDataPaths(
                data_dir=resolved_dir,
                sqlite_db_path=resolved_db,
                subscriptions_file=resolved_subs,
                mode="test",
                legacy_db_present=legacy_present,
            )

        if data_dir_str is not None:
            resolved_dir = resolve_canonical_path_following_links(
                Path(data_dir_str).expanduser(),
                base_dir=repo_root,
            )
            resolved_db = Path(
                assert_safe_sqlite_db_path(
                    resolved_dir / "cache.sqlite",
                    context="test",
                    repo_root=repo_root,
                )
            )
            candidate_subs = (
                Path(subs_str).expanduser()
                if subs_str is not None
                else (resolved_dir / "subscriptions.csv")
            )
            resolved_subs = Path(
                assert_safe_subscriptions_path(
                    candidate_subs,
                    context="test",
                    repo_root=repo_root,
                )
            )
            return ResolvedDataPaths(
                data_dir=resolved_dir,
                sqlite_db_path=resolved_db,
                subscriptions_file=resolved_subs,
                mode="test",
                legacy_db_present=legacy_present,
            )

        ws = _get_or_create_default_test_workspace()
        return ResolvedDataPaths(
            data_dir=ws.root,
            sqlite_db_path=ws.db_path,
            subscriptions_file=Path(subs_str).expanduser() if subs_str is not None else ws.subscriptions_file,
            mode="test",
            legacy_db_present=legacy_present,
        )

    if data_dir_str is not None:
        resolved_dir = resolve_canonical_path_following_links(
            Path(data_dir_str).expanduser(),
            base_dir=repo_root,
        )
        resolved_db = Path(db_path_str).expanduser() if db_path_str is not None else (resolved_dir / "cache.sqlite")
        resolved_subs = (
            Path(subs_str).expanduser()
            if subs_str is not None
            else (resolved_dir / "subscriptions.csv")
        )
        return ResolvedDataPaths(
            data_dir=resolved_dir,
            sqlite_db_path=resolved_db,
            subscriptions_file=resolved_subs,
            mode="configured_data_dir",
            legacy_db_present=legacy_present,
        )

    if db_path_str is not None or legacy_present:
        resolved_db = Path(db_path_str).expanduser() if db_path_str is not None else legacy_db
        resolved_subs = (
            Path(subs_str).expanduser()
            if subs_str is not None
            else (repo_root / "subscriptions.csv")
        )
        return ResolvedDataPaths(
            data_dir=resolved_db.parent,
            sqlite_db_path=resolved_db,
            subscriptions_file=resolved_subs,
            mode="legacy_repo_install",
            legacy_db_present=legacy_present,
        )

    resolved_dir = default_production_data_dir()
    resolved_subs = (
        Path(subs_str).expanduser()
        if subs_str is not None
        else (resolved_dir / "subscriptions.csv")
    )
    return ResolvedDataPaths(
        data_dir=resolved_dir,
        sqlite_db_path=resolved_dir / "cache.sqlite",
        subscriptions_file=resolved_subs,
        mode="default_production_dir",
        legacy_db_present=legacy_present,
    )


def describe_data_paths(
    *,
    configured_data_dir: str | None = None,
    configured_db_path: str | None = None,
    configured_subscriptions_file: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return a read-only JSON-serializable summary of configured and default data directories."""
    env_data_dir = os.environ.get("BOTTOM_POT_DATA_DIR", "").strip()
    env_db_path = os.environ.get("SQLITE_DB_PATH", "").strip()
    env_subs = os.environ.get("SUBSCRIPTIONS_FILE", "").strip()

    eff_data_dir = configured_data_dir if configured_data_dir is not None else (env_data_dir or None)
    eff_db_path = configured_db_path if configured_db_path is not None else (env_db_path or None)
    eff_subs = configured_subscriptions_file if configured_subscriptions_file is not None else (env_subs or None)

    resolved = resolve_data_paths(
        configured_data_dir=eff_data_dir,
        configured_db_path=eff_db_path,
        configured_subscriptions_file=eff_subs,
        repo_root=repo_root,
    )
    return {
        "mode": resolved.mode,
        "is_test_context": is_test_or_disposable_context(),
        "active_data_dir": str(resolved.data_dir),
        "active_sqlite_db_path": str(resolved.sqlite_db_path),
        "active_subscriptions_file": str(resolved.subscriptions_file),
        "default_production_data_dir": str(default_production_data_dir()),
        "legacy_repo_data_dir": str(legacy_repo_data_dir(repo_root)),
        "legacy_db_present": resolved.legacy_db_present,
        "env": {
            "BOTTOM_POT_DATA_DIR": env_data_dir or None,
            "SQLITE_DB_PATH": env_db_path or None,
            "SUBSCRIPTIONS_FILE": env_subs or None,
        },
    }

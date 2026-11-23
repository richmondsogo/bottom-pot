"""WAL/SHM-safe SQLite backup, integrity check, and disposable restore rehearsal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any

from src.core.exceptions import SafetyError
from src.safety.db_safety import (
    OwnedDisposableWorkspace,
    REPO_ROOT,
    UnsafeDatabasePathError,
    _comparable,
    _is_within_or_equal,
    _is_within_or_equal_ci,
    assert_safe_sqlite_db_path,
    cli_operational_runtime,
    get_protected_data_directories,
    resolve_canonical_path_following_links,
)

KNOWN_TABLES: tuple[str, ...] = (
    "company_boards",
    "monitored_jobs",
    "serper_cache",
    "serper_daily_budget",
    "url_cache",
    "monitor_leases",
)
_LABEL_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class IntegrityResult:
    db_path: str
    check_mode: str
    ok: bool
    messages: list[str]
    file_size_bytes: int
    sidecar_sizes: dict[str, int]
    journal_mode: str | None
    page_count: int | None
    page_size: int | None
    user_version: int | None
    table_counts: dict[str, int]


@dataclass(frozen=True)
class BackupResult:
    created_at_utc: str
    source_db: str
    backup_path: str
    manifest_path: str
    sha256: str
    byte_size: int
    source_journal_mode: str | None
    integrity_ok: bool
    table_counts: dict[str, int]


@dataclass(frozen=True)
class RestoreRehearsalResult:
    backup_path: str
    rehearsal_db: str
    workspace_kept: bool
    sha256_match: bool
    backup_sha256: str
    restored_sha256: str
    ok: bool
    messages: list[str]
    journal_mode: str | None
    table_counts: dict[str, int]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_sidecar_sizes(db_path: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists() and sidecar.is_file():
            sizes[suffix] = sidecar.stat().st_size
    return sizes


def _collect_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    counts: dict[str, int] = {}
    for (name,) in rows:
        if not isinstance(name, str) or not _SAFE_IDENT_RE.fullmatch(name):
            continue
        # Only inspect known app tables or ordinary top-level tables cleanly (skip FTS shadow internals).
        if "_" in name and name.startswith("monitored_jobs_fts_"):
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        counts[name] = int(count)
    return counts


def _is_inside_any_protected_dir(candidate_dir: Path) -> Path | None:
    for protected_dir in get_protected_data_directories():
        if _is_within_or_equal(candidate_dir, protected_dir) or _is_within_or_equal_ci(
            candidate_dir, protected_dir
        ):
            return protected_dir
    return None


def _sanitize_label(label: str | None) -> str | None:
    if label is None:
        return None
    cleaned = label.strip()
    if not cleaned:
        return None
    if not _LABEL_RE.fullmatch(cleaned):
        raise ValueError(
            f"Invalid backup label {label!r}: use 1-40 ASCII letters, digits, '-' or '_'."
        )
    return cleaned


def _inspect_sqlite_connection(
    db_path: Path,
    *,
    quick: bool = False,
) -> tuple[bool, list[str], str | None, int | None, int | None, int | None, dict[str, int]]:
    check_sql = "PRAGMA quick_check;" if quick else "PRAGMA integrity_check;"
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        conn.execute("PRAGMA query_only = ON;")
        rows = conn.execute(check_sql).fetchall()
        messages = [str(row[0]) for row in rows if row]
        ok = len(messages) == 1 and messages[0].strip().lower() == "ok"
        jm_row = conn.execute("PRAGMA journal_mode;").fetchone()
        pc_row = conn.execute("PRAGMA page_count;").fetchone()
        ps_row = conn.execute("PRAGMA page_size;").fetchone()
        uv_row = conn.execute("PRAGMA user_version;").fetchone()
        counts = _collect_table_counts(conn)
        return (
            ok,
            messages,
            str(jm_row[0]) if jm_row and jm_row[0] is not None else None,
            int(pc_row[0]) if pc_row and pc_row[0] is not None else None,
            int(ps_row[0]) if ps_row and ps_row[0] is not None else None,
            int(uv_row[0]) if uv_row and uv_row[0] is not None else None,
            counts,
        )
    except SafetyError:
        raise
    except sqlite3.DatabaseError as exc:
        return (False, [str(exc)], None, None, None, None, {})
    finally:
        conn.close()


def verify_database_integrity(
    db_path: str | Path,
    *,
    allow_operational_db: bool = False,
    quick: bool = False,
) -> IntegrityResult:
    """Run read-only SQLite integrity_check/quick_check plus page and table diagnostics."""
    check_mode = "quick_check" if quick else "integrity_check"
    with cli_operational_runtime(
        "scripts.db_backup:main",
        allow_operational_db=allow_operational_db,
    ):
        safe_str = assert_safe_sqlite_db_path(db_path, operation="connect")
        if safe_str == ":memory:":
            raise UnsafeDatabasePathError("Cannot run file integrity check on ':memory:' database.")
        safe_path = Path(safe_str)
        if not safe_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {safe_path}")
        if not safe_path.is_file():
            raise UnsafeDatabasePathError(f"Target '{safe_path}' is not a regular SQLite file.")

        file_size = safe_path.stat().st_size
        sidecars = _collect_sidecar_sizes(safe_path)
        (
            ok,
            messages,
            journal_mode,
            page_count,
            page_size,
            user_version,
            table_counts,
        ) = _inspect_sqlite_connection(safe_path, quick=quick)

    return IntegrityResult(
        db_path=str(safe_path),
        check_mode=check_mode,
        ok=ok,
        messages=messages,
        file_size_bytes=file_size,
        sidecar_sizes=sidecars,
        journal_mode=journal_mode,
        page_count=page_count,
        page_size=page_size,
        user_version=user_version,
        table_counts=table_counts,
    )


def backup_database(
    source_db: str | Path,
    *,
    output_dir: str | Path,
    label: str | None = None,
    allow_operational_db: bool = False,
) -> BackupResult:
    """
    Create a self-contained WAL/SHM-consistent SQLite backup using sqlite3 online backup API.

    Refuses writing inside any protected operational data directory or the repository root,
    reads the source with `PRAGMA query_only = ON`, verifies integrity of the written snapshot
    before finalizing atomically, and emits a `.meta.json` SHA-256 manifest alongside it.
    """
    clean_label = _sanitize_label(label)
    out_dir = resolve_canonical_path_following_links(output_dir, base_dir=Path.cwd())
    protected_overlap = _is_inside_any_protected_dir(out_dir)
    if protected_overlap is not None:
        raise UnsafeDatabasePathError(
            f"Refusing backup output inside protected operational directory '{protected_overlap}' (got '{out_dir}')."
        )
    resolved_repo = resolve_canonical_path_following_links(REPO_ROOT, base_dir=REPO_ROOT)
    if _comparable(out_dir) == _comparable(resolved_repo):
        raise UnsafeDatabasePathError(
            f"Refusing backup output directly in repository root '{resolved_repo}'; pick a dedicated backup directory."
        )

    with cli_operational_runtime(
        "scripts.db_backup:main",
        allow_operational_db=allow_operational_db,
    ):
        safe_src_str = assert_safe_sqlite_db_path(source_db, operation="connect")
        if safe_src_str == ":memory:":
            raise UnsafeDatabasePathError("Cannot back up an ':memory:' SQLite database.")
        safe_src = Path(safe_src_str)
        if not safe_src.exists():
            raise FileNotFoundError(f"Source SQLite database not found: {safe_src}")
        if not safe_src.is_file():
            raise UnsafeDatabasePathError(f"Source '{safe_src}' is not a regular file.")

        now_utc = datetime.now(timezone.utc)
        stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")
        stem = f"bottom-pot-backup-{stamp}" + (f"-{clean_label}" if clean_label else "")
        final_path = out_dir / f"{stem}.sqlite"
        if final_path.exists():
            for idx in range(2, 100):
                candidate = out_dir / f"{stem}-{idx:02d}.sqlite"
                if not candidate.exists():
                    final_path = candidate
                    break
            else:
                raise FileExistsError(f"Too many backup files exist for timestamp prefix '{stem}'.")

        safe_dst = Path(assert_safe_sqlite_db_path(final_path, operation="connect"))
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = out_dir / f".{safe_dst.name}.{os.getpid()}.tmp"
        if tmp_path.exists():
            tmp_path.unlink()

        src_conn: sqlite3.Connection | None = None
        dst_conn: sqlite3.Connection | None = None
        source_journal_mode: str | None = None
        table_counts: dict[str, int] = {}
        try:
            src_conn = sqlite3.connect(str(safe_src), timeout=30.0)
            src_conn.execute("PRAGMA query_only = ON;")
            jm_row = src_conn.execute("PRAGMA journal_mode;").fetchone()
            source_journal_mode = str(jm_row[0]) if jm_row and jm_row[0] is not None else None

            dst_conn = sqlite3.connect(str(tmp_path), timeout=30.0)
            src_conn.backup(dst_conn, pages=250, sleep=0.05)

            check_rows = dst_conn.execute("PRAGMA integrity_check;").fetchall()
            messages = [str(row[0]) for row in check_rows if row]
            if not (len(messages) == 1 and messages[0].strip().lower() == "ok"):
                raise RuntimeError(f"Backup snapshot failed PRAGMA integrity_check: {messages}")

            table_counts = _collect_table_counts(dst_conn)
            dst_conn.commit()
        except SafetyError:
            raise
        except (sqlite3.Error, OSError, RuntimeError, ValueError):
            if dst_conn is not None:
                dst_conn.close()
                dst_conn = None
            if src_conn is not None:
                src_conn.close()
                src_conn = None
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        finally:
            if dst_conn is not None:
                dst_conn.close()
            if src_conn is not None:
                src_conn.close()

        sha256 = _sha256_file(tmp_path)
        byte_size = tmp_path.stat().st_size
        os.replace(tmp_path, safe_dst)

        manifest_path = Path(f"{safe_dst}.meta.json")
        result = BackupResult(
            created_at_utc=now_utc.isoformat(),
            source_db=str(safe_src),
            backup_path=str(safe_dst),
            manifest_path=str(manifest_path),
            sha256=sha256,
            byte_size=byte_size,
            source_journal_mode=source_journal_mode,
            integrity_ok=True,
            table_counts=table_counts,
        )
        manifest_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
        return result


def rehearse_restore(
    backup_path: str | Path,
    *,
    keep_temp: bool = False,
) -> RestoreRehearsalResult:
    """
    Copy a standalone backup file into a fresh OwnedDisposableWorkspace and verify SHA-256
    plus full PRAGMA integrity_check and table row counts without touching operational storage.
    """
    raw = Path(os.fspath(backup_path)).expanduser()
    resolved_backup = resolve_canonical_path_following_links(raw, base_dir=Path.cwd())
    if not resolved_backup.exists():
        raise FileNotFoundError(f"Backup file not found: {resolved_backup}")
    if not resolved_backup.is_file():
        raise UnsafeDatabasePathError(f"Backup path '{resolved_backup}' is not a regular file.")

    protected_overlap = _is_inside_any_protected_dir(resolved_backup.parent)
    if protected_overlap is not None:
        raise UnsafeDatabasePathError(
            f"Refusing restore rehearsal directly from live operational directory '{protected_overlap}'; "
            "copy or create backups in a separate backup directory."
        )

    backup_sha256 = _sha256_file(resolved_backup)
    ws = OwnedDisposableWorkspace.create(prefix="bottom-pot-restore-rehearsal-")
    rehearsal_db = Path(assert_safe_sqlite_db_path(ws.root / "rehearsal.sqlite"))
    try:
        shutil.copyfile(resolved_backup, rehearsal_db)
        restored_sha256 = _sha256_file(rehearsal_db)
        ok, messages, journal_mode, _, _, _, table_counts = _inspect_sqlite_connection(
            rehearsal_db,
            quick=False,
        )
        sha_match = backup_sha256 == restored_sha256
        if not sha_match:
            ok = False
            messages = [*messages, "SHA-256 mismatch between backup source and rehearsal copy."]
        return RestoreRehearsalResult(
            backup_path=str(resolved_backup),
            rehearsal_db=str(rehearsal_db),
            workspace_kept=keep_temp,
            sha256_match=sha_match,
            backup_sha256=backup_sha256,
            restored_sha256=restored_sha256,
            ok=ok,
            messages=messages,
            journal_mode=journal_mode,
            table_counts=table_counts,
        )
    finally:
        if not keep_temp:
            ws.cleanup()

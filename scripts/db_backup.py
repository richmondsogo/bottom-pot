"""CLI for SQLite path inspection, WAL/SHM-safe backup, integrity check, and restore rehearsal.

Usage:
    python scripts/db_backup.py paths [--json]
    python scripts/db_backup.py check [--db PATH] [--quick] [--allow-operational-db] [--json]
    python scripts/db_backup.py backup --output-dir DIR [--db PATH] [--label NAME] [--allow-operational-db] [--json]
    python scripts/db_backup.py rehearse --backup PATH [--keep-temp] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.data_dir import describe_data_paths  # noqa: E402
from src.core.settings import settings  # noqa: E402
from src.storage.db_backup import (  # noqa: E402
    BackupResult,
    IntegrityResult,
    RestoreRehearsalResult,
    backup_database,
    rehearse_restore,
    verify_database_integrity,
)


def _format_table_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "(none)"
    return ", ".join(f"{name}={val}" for name, val in sorted(counts.items()))


def _print_paths_text(info: dict[str, Any]) -> None:
    print("Bottom Pot Data Storage Paths")
    print("-----------------------------")
    print(f"Resolution mode            : {info['mode']}")
    print(f"Test/disposable context    : {info['is_test_context']}")
    print(f"Active data directory      : {info['active_data_dir']}")
    print(f"Active SQLite database     : {info['active_sqlite_db_path']}")
    print(f"Active subscriptions CSV   : {info['active_subscriptions_file']}")
    print(f"Default outside-repo dir   : {info['default_production_data_dir']}")
    print(f"Legacy repo data dir       : {info['legacy_repo_data_dir']}")
    print(f"Legacy data/cache.sqlite   : {'present' if info['legacy_db_present'] else 'absent'}")


def _print_check_text(res: IntegrityResult) -> None:
    print(f"SQLite Check ({res.check_mode}) : {'PASSED' if res.ok else 'FAILED'}")
    print(f"Database path   : {res.db_path}")
    print(f"Size (bytes)    : {res.file_size_bytes}")
    print(f"Journal mode    : {res.journal_mode or '-'}")
    print(f"Sidecars        : {res.sidecar_sizes or '{}'}")
    print(f"Tables          : {_format_table_counts(res.table_counts)}")
    print(f"Messages        : {', '.join(res.messages)}")


def _print_backup_text(res: BackupResult) -> None:
    print("SQLite Backup   : COMPLETED")
    print(f"Source DB       : {res.source_db}")
    print(f"Backup file     : {res.backup_path}")
    print(f"Manifest file   : {res.manifest_path}")
    print(f"SHA-256         : {res.sha256}")
    print(f"Size (bytes)    : {res.byte_size}")
    print(f"Source journal  : {res.source_journal_mode or '-'}")
    print(f"Tables          : {_format_table_counts(res.table_counts)}")


def _print_rehearse_text(res: RestoreRehearsalResult) -> None:
    print(f"Restore Rehearsal : {'PASSED' if res.ok else 'FAILED'}")
    print(f"Backup source     : {res.backup_path}")
    print(f"Temp rehearsal DB : {res.rehearsal_db} ({'kept' if res.workspace_kept else 'cleaned'})")
    print(f"SHA-256 match     : {res.sha256_match}")
    print(f"Tables            : {_format_table_counts(res.table_counts)}")
    print(f"Messages          : {', '.join(res.messages)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operational SQLite data-dir, backup, integrity check, and restore rehearsal utility."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_paths = sub.add_parser("paths", help="Inspect resolved data/DB/subscriptions paths without opening SQLite.")
    p_paths.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output.")

    p_check = sub.add_parser("check", help="Run read-only SQLite integrity_check/quick_check.")
    p_check.add_argument("--db", default=None, help="Target SQLite DB path (defaults to configured SQLITE_DB_PATH).")
    p_check.add_argument("--quick", action="store_true", help="Run PRAGMA quick_check instead of full integrity_check.")
    p_check.add_argument(
        "--allow-operational-db",
        action="store_true",
        help="Explicitly authorize opening the configured operational database outside test contexts.",
    )
    p_check.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output.")

    p_backup = sub.add_parser("backup", help="Create a WAL/SHM-consistent standalone SQLite backup.")
    p_backup.add_argument("--db", default=None, help="Source SQLite DB path (defaults to configured SQLITE_DB_PATH).")
    p_backup.add_argument("--output-dir", required=True, help="Destination backup directory (must sit outside operational data dir).")
    p_backup.add_argument("--label", default=None, help="Optional ASCII label appended to backup filename.")
    p_backup.add_argument(
        "--allow-operational-db",
        action="store_true",
        help="Explicitly authorize backing up the configured operational database outside test contexts.",
    )
    p_backup.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output.")

    p_rehearse = sub.add_parser("rehearse", help="Rehearse restoring a backup file into a disposable workspace.")
    p_rehearse.add_argument("--backup", required=True, help="Path to standalone backup .sqlite file.")
    p_rehearse.add_argument("--keep-temp", action="store_true", help="Retain temporary rehearsal workspace after completion.")
    p_rehearse.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "paths":
        info = describe_data_paths()
        if args.as_json:
            print(json.dumps(info, indent=2))
        else:
            _print_paths_text(info)
        return 0

    if args.command == "check":
        db_target = args.db or settings.sqlite_db_path
        res = verify_database_integrity(
            db_target,
            allow_operational_db=args.allow_operational_db,
            quick=args.quick,
        )
        if args.as_json:
            print(json.dumps(asdict(res), indent=2))
        else:
            _print_check_text(res)
        return 0 if res.ok else 1

    if args.command == "backup":
        db_target = args.db or settings.sqlite_db_path
        res = backup_database(
            db_target,
            output_dir=args.output_dir,
            label=args.label,
            allow_operational_db=args.allow_operational_db,
        )
        if args.as_json:
            print(json.dumps(asdict(res), indent=2))
        else:
            _print_backup_text(res)
        return 0

    if args.command == "rehearse":
        res = rehearse_restore(
            args.backup,
            keep_temp=args.keep_temp,
        )
        if args.as_json:
            print(json.dumps(asdict(res), indent=2))
        else:
            _print_rehearse_text(res)
        return 0 if res.ok else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

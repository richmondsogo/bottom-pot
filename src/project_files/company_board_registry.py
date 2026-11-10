"""
Persistent Company-Board Registry.

Automatically discovers, verifies, and indexes company ATS boards
(Greenhouse, Lever, Ashby, etc.) in SQLite (data/cache.sqlite).

Rules:
- Strictly adheres to ADR 0001 ("Unknown beats wrong").
- Never treats generic stopwords or placeholders ("personio", "icims", "apply", "careers") as valid boards.
- Deduplicates on (ats_provider, board_token) so a company's board is only registered once.
- Tracks verification status, monitoring capabilities, and scheduling timestamps.
- Survives application restarts with WAL mode and atomic transactions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from typing import Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict

from src.config import settings
from src.project_files.ats_url_parser import is_valid_board_slug
from src.project_files.field_normalizer import humanize_slug


@dataclass
class CompanyBoard:
    id: int
    company_name: str
    company_slug: str
    ats_provider: str
    board_token: str
    board_url: str
    discovery_source: str
    source_posting_url: str | None
    first_discovered_at: float
    last_discovered_at: float
    verification_status: str  # 'candidate' | 'verified' | 'rejected'
    monitoring_capability: str  # 'supported' | 'unsupported' | 'provisional'
    last_successful_check: float | None = None
    next_scheduled_check: float | None = None
    failure_count: int = 0
    polling_priority: int = 1
    etag: str | None = None
    last_modified: str | None = None
    content_fingerprint: str | None = None
    active_job_count: int = 0


# Providers with verified public listing endpoints eligible for independent monitoring
MONITORABLE_PROVIDERS: frozenset[str] = frozenset({
    "greenhouse",
    "lever",
    "ashby",
})

PROVISIONAL_PROVIDERS: frozenset[str] = frozenset({
    "smartrecruiters",
    "recruitee",
    "workable",
    "bamboohr",
})


def build_canonical_board_url(ats_provider: str, board_token: str) -> str:
    """Build canonical public board URL for a given ATS and token."""
    provider = ats_provider.lower().strip()
    token = board_token.strip()
    if provider == "greenhouse":
        return f"https://boards.greenhouse.io/{token}"
    elif provider == "lever":
        return f"https://jobs.lever.co/{token}"
    elif provider == "ashby":
        return f"https://jobs.ashbyhq.com/{token}"
    elif provider == "workable":
        return f"https://apply.workable.com/{token}"
    elif provider == "smartrecruiters":
        return f"https://jobs.smartrecruiters.com/{token}"
    elif provider == "bamboohr":
        return f"https://{token}.bamboohr.com/careers"
    elif provider == "recruitee":
        return f"https://{token}.recruitee.com"
    elif provider == "jobvite":
        return f"https://jobs.jobvite.com/{token}"
    elif provider == "teamtailor":
        return f"https://{token}.teamtailor.com"
    elif provider == "personio":
        return f"https://{token}.jobs.personio.de"
    elif provider == "breezy":
        return f"https://{token}.breezy.hr"
    elif provider == "jazzhr":
        return f"https://{token}.applytojob.com"
    elif provider == "avature":
        return f"https://{token}.avature.net/careers"
    elif provider == "workday":
        return f"https://{token}.myworkdayjobs.com"
    elif provider == "taleo":
        return f"https://{token}.taleo.net"
    return f"https://{token}.{provider}.com"


class CompanyBoardRegistry:
    """Persistent SQLite registry of employer boards across all ATS platforms."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.sqlite_db_path
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        parent = Path(self.db_path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS company_boards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_name TEXT NOT NULL,
                        company_slug TEXT NOT NULL,
                        ats_provider TEXT NOT NULL,
                        board_token TEXT NOT NULL,
                        board_url TEXT NOT NULL,
                        discovery_source TEXT NOT NULL,
                        source_posting_url TEXT,
                        first_discovered_at REAL NOT NULL,
                        last_discovered_at REAL NOT NULL,
                        verification_status TEXT NOT NULL DEFAULT 'candidate',
                        monitoring_capability TEXT NOT NULL DEFAULT 'unsupported',
                        last_successful_check REAL,
                        next_scheduled_check REAL,
                        failure_count INTEGER NOT NULL DEFAULT 0,
                        polling_priority INTEGER NOT NULL DEFAULT 1,
                        etag TEXT,
                        last_modified TEXT,
                        content_fingerprint TEXT,
                        active_job_count INTEGER DEFAULT 0,
                        UNIQUE(ats_provider, board_token)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_boards_provider_token ON company_boards(ats_provider, board_token)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_boards_monitor ON company_boards(verification_status, monitoring_capability, next_scheduled_check)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_boards_company_slug ON company_boards(company_slug)"
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to initialize SQLite company_boards table: {exc}")

    def register_candidate(
        self,
        *,
        company_name: str | None = None,
        ats_provider: str,
        board_token: str,
        source_url: str | None = None,
        discovery_source: str = "search",
    ) -> CompanyBoard | None:
        """
        Registers or updates a discovered company board candidate.
        Returns CompanyBoard instance, or None if the board_token is an invalid placeholder.
        """
        if not ats_provider or not board_token:
            return None

        clean_provider = ats_provider.strip().lower()
        clean_token = board_token.strip().lower()

        # Reject generic stopwords, ATS names, or non-viable board slugs
        if not is_valid_board_slug(clean_provider, clean_token):
            logger.debug(
                f"[registry] Rejected invalid/placeholder board token '{clean_token}' for ATS {clean_provider}"
            )
            return None

        clean_name = company_name.strip() if company_name and company_name.strip() else humanize_slug(clean_token)
        company_slug = clean_token
        board_url = build_canonical_board_url(clean_provider, clean_token)
        now = time.time()

        # Determine monitoring capability
        if clean_provider in MONITORABLE_PROVIDERS:
            monitoring_capability = "supported"
        elif clean_provider in PROVISIONAL_PROVIDERS:
            monitoring_capability = "provisional"
        else:
            monitoring_capability = "unsupported"

        try:
            with self._get_connection() as conn:
                # Check if exists
                cursor = conn.execute(
                    """
                    SELECT id, company_name, company_slug, ats_provider, board_token,
                           board_url, discovery_source, source_posting_url, first_discovered_at,
                           last_discovered_at, verification_status, monitoring_capability,
                           last_successful_check, next_scheduled_check, failure_count,
                           polling_priority, etag, last_modified, content_fingerprint, active_job_count
                    FROM company_boards
                    WHERE ats_provider = ? AND board_token = ?
                    """,
                    (clean_provider, clean_token),
                )
                row = cursor.fetchone()
                if row:
                    # Existing board: update last_discovered_at without modifying schedule/verification
                    conn.execute(
                        """
                        UPDATE company_boards
                        SET last_discovered_at = ?
                        WHERE id = ?
                        """,
                        (now, row[0]),
                    )
                    conn.commit()
                    return CompanyBoard(
                        id=row[0],
                        company_name=row[1],
                        company_slug=row[2],
                        ats_provider=row[3],
                        board_token=row[4],
                        board_url=row[5],
                        discovery_source=row[6],
                        source_posting_url=row[7],
                        first_discovered_at=row[8],
                        last_discovered_at=now,
                        verification_status=row[10],
                        monitoring_capability=row[11],
                        last_successful_check=row[12],
                        next_scheduled_check=row[13],
                        failure_count=row[14],
                        polling_priority=row[15],
                        etag=row[16],
                        last_modified=row[17],
                        content_fingerprint=row[18],
                        active_job_count=row[19],
                    )

                # New candidate: schedule initial verification check immediately
                cursor = conn.execute(
                    """
                    INSERT INTO company_boards (
                        company_name, company_slug, ats_provider, board_token,
                        board_url, discovery_source, source_posting_url,
                        first_discovered_at, last_discovered_at, verification_status,
                        monitoring_capability, next_scheduled_check, failure_count, polling_priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?, ?, 0, 1)
                    """,
                    (
                        clean_name,
                        company_slug,
                        clean_provider,
                        clean_token,
                        board_url,
                        discovery_source,
                        source_url,
                        now,
                        now,
                        monitoring_capability,
                        now,  # eligible for check immediately
                    ),
                )
                new_id = cursor.lastrowid
                conn.commit()
                return CompanyBoard(
                    id=new_id,
                    company_name=clean_name,
                    company_slug=company_slug,
                    ats_provider=clean_provider,
                    board_token=clean_token,
                    board_url=board_url,
                    discovery_source=discovery_source,
                    source_posting_url=source_url,
                    first_discovered_at=now,
                    last_discovered_at=now,
                    verification_status="candidate",
                    monitoring_capability=monitoring_capability,
                    next_scheduled_check=now,
                    failure_count=0,
                    polling_priority=1,
                )
        except Exception as exc:
            logger.error(f"[registry] Failed to register candidate ({clean_provider}:{clean_token}): {exc}")
            return None

    def get_board(self, ats_provider: str, board_token: str) -> CompanyBoard | None:
        """Fetch a board record by provider and token."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, company_name, company_slug, ats_provider, board_token,
                           board_url, discovery_source, source_posting_url, first_discovered_at,
                           last_discovered_at, verification_status, monitoring_capability,
                           last_successful_check, next_scheduled_check, failure_count,
                           polling_priority, etag, last_modified, content_fingerprint, active_job_count
                    FROM company_boards
                    WHERE ats_provider = ? AND board_token = ?
                    """,
                    (ats_provider.lower().strip(), board_token.lower().strip()),
                )
                row = cursor.fetchone()
                if row:
                    return CompanyBoard(*row)
        except Exception as exc:
            logger.debug(f"[registry] Lookup failed: {exc}")
        return None

    def list_boards(
        self,
        *,
        status: str | None = None,
        monitoring_capability: str | None = None,
        limit: int = 100,
    ) -> list[CompanyBoard]:
        """List registered boards with optional status filtering."""
        boards: list[CompanyBoard] = []
        try:
            with self._get_connection() as conn:
                query = "SELECT id, company_name, company_slug, ats_provider, board_token, board_url, discovery_source, source_posting_url, first_discovered_at, last_discovered_at, verification_status, monitoring_capability, last_successful_check, next_scheduled_check, failure_count, polling_priority, etag, last_modified, content_fingerprint, active_job_count FROM company_boards"
                params: list = []
                clauses = []
                if status:
                    clauses.append("verification_status = ?")
                    params.append(status)
                if monitoring_capability:
                    clauses.append("monitoring_capability = ?")
                    params.append(monitoring_capability)
                if clauses:
                    query += " WHERE " + " AND ".join(clauses)
                query += " ORDER BY last_discovered_at DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, tuple(params))
                for row in cursor.fetchall():
                    boards.append(CompanyBoard(*row))
        except Exception as exc:
            logger.debug(f"[registry] list_boards failed: {exc}")
        return boards

    def get_due_monitoring_boards(self, limit: int = 20) -> list[CompanyBoard]:
        """
        Fetch boards due for monitoring checks:
        - Must be 'supported'
        - Must not be 'rejected'
        - next_scheduled_check is NULL or <= now
        - failure_count < 5
        Ordered by priority DESC, next_scheduled_check ASC.
        """
        now = time.time()
        boards: list[CompanyBoard] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, company_name, company_slug, ats_provider, board_token,
                           board_url, discovery_source, source_posting_url, first_discovered_at,
                           last_discovered_at, verification_status, monitoring_capability,
                           last_successful_check, next_scheduled_check, failure_count,
                           polling_priority, etag, last_modified, content_fingerprint, active_job_count
                    FROM company_boards
                    WHERE monitoring_capability = 'supported'
                      AND verification_status IN ('candidate', 'verified')
                      AND (next_scheduled_check IS NULL OR next_scheduled_check <= ?)
                      AND failure_count < 5
                      AND polling_priority > 0
                    ORDER BY polling_priority DESC, next_scheduled_check ASC
                    LIMIT ?
                    """,
                    (now, limit),
                )
                for row in cursor.fetchall():
                    boards.append(CompanyBoard(*row))
        except Exception as exc:
            logger.debug(f"[registry] get_due_monitoring_boards failed: {exc}")
        return boards

    def record_check_success(
        self,
        board_id: int,
        *,
        active_job_count: int,
        content_fingerprint: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        interval_seconds: int = 1800,  # 30 min default
    ) -> None:
        """Records a successful board check, marks board verified, resets failures, and schedules next check."""
        now = time.time()
        next_check = now + interval_seconds
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE company_boards
                    SET verification_status = 'verified',
                        monitoring_capability = 'supported',
                        last_successful_check = ?,
                        next_scheduled_check = ?,
                        failure_count = 0,
                        active_job_count = ?,
                        content_fingerprint = COALESCE(?, content_fingerprint),
                        etag = COALESCE(?, etag),
                        last_modified = COALESCE(?, last_modified)
                    WHERE id = ?
                    """,
                    (now, next_check, active_job_count, content_fingerprint, etag, last_modified, board_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"[registry] Failed to record check success for board {board_id}: {exc}")

    def record_check_failure(
        self,
        board_id: int,
        *,
        error: str,
        base_backoff_seconds: int = 900,  # 15 mins base
    ) -> None:
        """Records a failed check, applies exponential backoff, and marks rejected after 5 consecutive failures."""
        now = time.time()
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT failure_count FROM company_boards WHERE id = ?", (board_id,))
                row = cursor.fetchone()
                current_failures = row[0] if row else 0
                new_failures = current_failures + 1

                # Backoff: 15m * (2 ^ failures), capped at 24 hours (86400s)
                backoff = min(86400, base_backoff_seconds * (2 ** min(new_failures, 6)))
                next_check = now + backoff
                new_status = "rejected" if new_failures >= 5 else "candidate"

                conn.execute(
                    """
                    UPDATE company_boards
                    SET failure_count = ?,
                        verification_status = CASE WHEN ? = 'rejected' THEN 'rejected' ELSE verification_status END,
                        next_scheduled_check = ?
                    WHERE id = ?
                    """,
                    (new_failures, new_status, next_check, board_id),
                )
                conn.commit()
                logger.debug(
                    f"[registry] Board {board_id} failed check ({error}). Failures={new_failures}, backoff={backoff}s"
                )
        except Exception as exc:
            logger.warning(f"[registry] Failed to record check failure for board {board_id}: {exc}")

    def clear(self) -> None:
        """Clear registry table (used in tests)."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM company_boards")
                conn.commit()
        except Exception as exc:
            logger.debug(f"[registry] Clear failed: {exc}")


company_board_registry = CompanyBoardRegistry()

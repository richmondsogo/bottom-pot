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
import json
from pathlib import Path
import random
import re
import sqlite3
import time
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict

from src.config import settings
from src.project_files.ats_url_parser import is_valid_board_slug
from src.project_files.field_normalizer import humanize_slug
from src.project_files.models import JobListing


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


def build_canonical_board_url(ats_provider: str, board_token: str) -> str | None:
    """Build canonical public board URL for a given ATS and token. Returns None if provider lacks public board route."""
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
    # Unverified / non-standardized ATS formats without authentic public board routes:
    # (workday, taleo, sap, avature, jobadder, icims) - do NOT fabricate guessed URLs
    return None


class CompanyBoardRegistry:
    """Persistent SQLite registry of employer boards across all ATS platforms."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.sqlite_db_path
        self._monitored_store_version: int = 1
        self._ensure_db()

    def get_monitored_store_version(self) -> int:
        """Return the durable cross-process revision counter stored in SQLite."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT value FROM registry_meta WHERE key = 'store_version'"
                ).fetchone()
                if row:
                    return int(row[0])
        except Exception as exc:
            logger.debug(f"[registry] Error reading store_version from DB: {exc}")
        return 1

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if getattr(self, "_mem_conn", None) is None:
                self._mem_conn = sqlite3.connect(":memory:", timeout=10.0)
            return self._mem_conn
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
                # 1. Company boards registry table
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

                # 2. Durable searchable monitored jobs store
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS monitored_jobs (
                        job_id TEXT PRIMARY KEY,
                        board_id INTEGER REFERENCES company_boards(id),
                        ats_provider TEXT NOT NULL,
                        company_slug TEXT NOT NULL,
                        company_name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        location TEXT,
                        work_model TEXT,
                        employment_type TEXT,
                        salary TEXT,
                        description TEXT,
                        requirements TEXT,
                        posted_at TEXT,
                        first_discovered_at REAL NOT NULL,
                        last_checked_at REAL NOT NULL,
                        source_url TEXT NOT NULL,
                        apply_url TEXT,
                        confidence_score REAL,
                        source_evidence TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        content_fingerprint TEXT,
                        canonical_json TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_board ON monitored_jobs(board_id, status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_provider ON monitored_jobs(ats_provider, status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_status ON monitored_jobs(status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_dates ON monitored_jobs(status, first_discovered_at DESC)"
                )

                # 3. FTS5 full-text keyword search index with synchronisation triggers
                try:
                    conn.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS monitored_jobs_fts USING fts5(
                            job_id UNINDEXED,
                            title,
                            company_name,
                            location,
                            description,
                            requirements,
                            tokenize='unicode61 remove_diacritics 2'
                        )
                        """
                    )
                    conn.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_monitored_jobs_ai AFTER INSERT ON monitored_jobs BEGIN
                            INSERT INTO monitored_jobs_fts(job_id, title, company_name, location, description, requirements)
                            VALUES (new.job_id, new.title, new.company_name, new.location, new.description, new.requirements);
                        END;
                        """
                    )
                    conn.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_monitored_jobs_ad AFTER DELETE ON monitored_jobs BEGIN
                            DELETE FROM monitored_jobs_fts WHERE job_id = old.job_id;
                        END;
                        """
                    )
                    conn.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_monitored_jobs_au AFTER UPDATE ON monitored_jobs BEGIN
                            DELETE FROM monitored_jobs_fts WHERE job_id = old.job_id;
                            INSERT INTO monitored_jobs_fts(job_id, title, company_name, location, description, requirements)
                            VALUES (new.job_id, new.title, new.company_name, new.location, new.description, new.requirements);
                        END;
                        """
                    )
                except Exception as fts_exc:
                    logger.warning(f"Failed to create FTS5 index for monitored_jobs: {fts_exc}")

                # 4. Cross-process atomic leases for scheduler locking across Windows & Linux
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS monitor_leases (
                        lease_name TEXT PRIMARY KEY,
                        holder_id TEXT NOT NULL,
                        acquired_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )

                # 5. Cross-process durable revision metadata for whole-search cache invalidation
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS registry_meta (
                        key TEXT PRIMARY KEY,
                        value INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    "INSERT OR IGNORE INTO registry_meta (key, value) VALUES ('store_version', 1)"
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
        if not board_url:
            return None
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
                    ORDER BY CASE WHEN next_scheduled_check IS NULL THEN 0 ELSE 1 END,
                             next_scheduled_check ASC,
                             polling_priority DESC
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
        """Records a successful board check, marks board verified, resets failures, and schedules next check with jitter."""
        now = time.time()
        # Apply +/- 10% jitter (min 30s) to avoid thundering herd polling spikes
        jitter_range = max(30, interval_seconds // 10)
        jitter = random.randint(-jitter_range, jitter_range)
        next_check = now + max(300, interval_seconds + jitter)
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

    def upsert_monitored_job(
        self,
        job: JobListing,
        board_id: int | None = None,
        content_fingerprint: str | None = None,
    ) -> bool:
        """
        Inserts or updates a discovered canonical job listing in the persistent monitored store.
        Survives application restarts and tracks full provenance and lifecycle status.
        """
        if not job or not job.id:
            return False

        now = time.time()
        job_id = job.id.strip()
        provider = (job.ats_source or job.provider or "unknown").strip().lower()
        company_slug = job.company_slug or (job.id.split(":")[1] if ":" in job.id else "")
        company_name = job.company or humanize_slug(company_slug)
        title = job.title.strip()
        location = job.location.strip() if job.location else None
        work_model = job.work_model
        emp_type = job.employment_type

        salary_str: str | None = None
        if job.salary:
            if hasattr(job.salary, "model_dump_json"):
                salary_str = job.salary.model_dump_json()
            else:
                salary_str = str(job.salary)

        desc = job.description
        reqs_str: str | None = None
        if job.requirements:
            reqs_str = json.dumps(job.requirements) if isinstance(job.requirements, list) else str(job.requirements)

        posted_at_iso = job.posted_at.isoformat() if job.posted_at else None
        source_url = job.source_url or job.apply_url or ""
        apply_url = job.apply_url or job.source_url or ""
        confidence = float(job.extraction_confidence) if job.extraction_confidence is not None else None
        evidence_str: str | None = None
        if job.field_evidence:
            if isinstance(job.field_evidence, list):
                evidence_list = [
                    (v.model_dump() if hasattr(v, "model_dump") else v)
                    for v in job.field_evidence
                ]
                evidence_str = json.dumps(evidence_list)
            elif isinstance(job.field_evidence, dict):
                evidence_dict = {
                    k: (v.model_dump() if hasattr(v, "model_dump") else v)
                    for k, v in job.field_evidence.items()
                }
                evidence_str = json.dumps(evidence_dict)
            else:
                evidence_str = str(job.field_evidence)
        canonical_json = job.model_dump_json()

        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT first_discovered_at FROM monitored_jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE monitored_jobs
                        SET board_id = COALESCE(?, board_id),
                            ats_provider = ?,
                            company_slug = ?,
                            company_name = ?,
                            title = ?,
                            location = ?,
                            work_model = ?,
                            employment_type = ?,
                            salary = ?,
                            description = ?,
                            requirements = ?,
                            posted_at = COALESCE(?, posted_at),
                            last_checked_at = ?,
                            source_url = ?,
                            apply_url = ?,
                            confidence_score = ?,
                            source_evidence = ?,
                            status = 'active',
                            content_fingerprint = COALESCE(?, content_fingerprint),
                            canonical_json = ?
                        WHERE job_id = ?
                        """,
                        (
                            board_id,
                            provider,
                            company_slug,
                            company_name,
                            title,
                            location,
                            work_model,
                            emp_type,
                            salary_str,
                            desc,
                            reqs_str,
                            posted_at_iso,
                            now,
                            source_url,
                            apply_url,
                            confidence,
                            evidence_str,
                            content_fingerprint,
                            canonical_json,
                            job_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO monitored_jobs (
                            job_id, board_id, ats_provider, company_slug, company_name,
                            title, location, work_model, employment_type, salary,
                            description, requirements, posted_at, first_discovered_at,
                            last_checked_at, source_url, apply_url, confidence_score,
                            source_evidence, status, content_fingerprint, canonical_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                        """,
                        (
                            job_id,
                            board_id,
                            provider,
                            company_slug,
                            company_name,
                            title,
                            location,
                            work_model,
                            emp_type,
                            salary_str,
                            desc,
                            reqs_str,
                            posted_at_iso,
                            now,
                            now,
                            source_url,
                            apply_url,
                            confidence,
                            evidence_str,
                            content_fingerprint,
                            canonical_json,
                        ),
                    )
                conn.execute(
                    "UPDATE registry_meta SET value = value + 1 WHERE key = 'store_version'"
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"[registry] Failed to upsert monitored job {job_id}: {exc}")
            return False

    def get_monitored_job(self, job_id: str) -> JobListing | None:
        """Fetch a single monitored job listing from the durable store by canonical ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT canonical_json FROM monitored_jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    return JobListing.model_validate_json(row[0])
        except Exception as exc:
            logger.debug(f"[registry] Failed to get monitored job {job_id}: {exc}")
        return None

    def get_known_publication_dates(self, board_id: int) -> dict[str, str]:
        """Returns mapping of provider_job_id (and full job_id) to ISO posted_at string

        for monitored jobs on this board that have an authoritative publication date.
        """
        dates: dict[str, str] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT job_id, posted_at FROM monitored_jobs WHERE board_id = ? AND posted_at IS NOT NULL",
                    (board_id,),
                )
                for job_id, posted_at in cursor.fetchall():
                    if posted_at:
                        dates[job_id] = str(posted_at)
                        parts = job_id.split(":")
                        if len(parts) >= 3:
                            dates[parts[-1]] = str(posted_at)
        except Exception as exc:
            logger.debug(f"[registry] get_known_publication_dates failed: {exc}")
        return dates

    def search_monitored_jobs(
        self,
        query: str,
        location: str | None = None,
        is_remote: bool | None = None,
        platforms: list[str] | None = None,
        posted_within_days: int | None = None,
        exclude_keywords: list[str] | None = None,
        limit: int = 50,
    ) -> list[JobListing]:
        """
        Queries persistent monitored jobs matching keyword, location, remote, platform,
        and date filters. Uses SQLite FTS5 index where possible, with fallback to structured SQL.
        """
        results: list[JobListing] = []
        clean_words = [
            w for w in re.sub(r"[^\w\s-]", " ", query).split()
            if len(w) > 1 and not w.isdigit()
        ]

        where_clauses = ["m.status = 'active'"]
        params: list[Any] = []

        if location and location.strip():
            where_clauses.append("(m.location LIKE ? OR m.description LIKE ?)")
            loc_param = f"%{location.strip()}%"
            params.extend([loc_param, loc_param])

        if is_remote is True:
            # Explicit work_model takes precedence:
            # - 'remote': match
            # - 'hybrid', 'onsite': never match remote-only
            # - Unknown work_model: fallback to location text heuristics
            where_clauses.append(
                "("
                "m.work_model = 'remote' OR ("
                "(m.work_model IS NULL OR m.work_model NOT IN ('remote', 'hybrid', 'onsite')) "
                "AND m.location LIKE '%remote%' "
                "AND m.location NOT LIKE '%not remote%' "
                "AND m.location NOT LIKE '%hybrid%'"
                ")"
                ")"
            )
        elif is_remote is False:
            # Exclude verified remote jobs while retaining hybrid, onsite, and unknown non-remote
            where_clauses.append(
                "("
                "m.work_model IN ('hybrid', 'onsite') OR ("
                "(m.work_model IS NULL OR m.work_model NOT IN ('remote', 'hybrid', 'onsite')) "
                "AND (m.location IS NULL OR (m.location NOT LIKE '%remote%' OR m.location LIKE '%not remote%' OR m.location LIKE '%hybrid%'))"
                ")"
                ")"
            )

        if platforms is not None:
            clean_plats = [p.strip().lower() for p in platforms if p and p.strip()]
            if not clean_plats:
                return []
            placeholders = ",".join("?" for _ in clean_plats)
            where_clauses.append(f"m.ats_provider IN ({placeholders})")
            params.extend(clean_plats)

        if posted_within_days and posted_within_days > 0:
            cutoff = time.time() - (posted_within_days * 86400)
            cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
            where_clauses.append("m.posted_at IS NOT NULL AND m.posted_at >= ?")
            params.append(cutoff_iso)

        fts_success = False
        if clean_words:
            fts_query_str = " AND ".join(f'"{re.sub(r"[\"*]", "", w)}"*' for w in clean_words)
            try:
                with self._get_connection() as conn:
                    sql = (
                        f"SELECT m.canonical_json FROM monitored_jobs m "
                        f"JOIN monitored_jobs_fts f ON m.job_id = f.job_id "
                        f"WHERE monitored_jobs_fts MATCH ? AND " + " AND ".join(where_clauses) + " "
                        f"ORDER BY m.first_discovered_at DESC LIMIT ?"
                    )
                    full_params = [fts_query_str] + params + [limit * 2]
                    cursor = conn.execute(sql, tuple(full_params))
                    for (json_data,) in cursor.fetchall():
                        try:
                            job = JobListing.model_validate_json(json_data)
                            results.append(job)
                        except Exception:
                            continue
                fts_success = True
            except Exception as fts_err:
                logger.debug(f"[registry] FTS5 search failed, falling back to LIKE: {fts_err}")
                fts_success = False

        if not fts_success:
            like_clauses = list(where_clauses)
            like_params = list(params)
            for w in clean_words:
                like_clauses.append("(m.title LIKE ? OR m.company_name LIKE ? OR m.description LIKE ?)")
                w_param = f"%{w}%"
                like_params.extend([w_param, w_param, w_param])

            try:
                with self._get_connection() as conn:
                    sql = (
                        f"SELECT m.canonical_json FROM monitored_jobs m WHERE "
                        + " AND ".join(like_clauses)
                        + f" ORDER BY m.first_discovered_at DESC LIMIT ?"
                    )
                    full_params = like_params + [limit * 2]
                    cursor = conn.execute(sql, tuple(full_params))
                    for (json_data,) in cursor.fetchall():
                        try:
                            job = JobListing.model_validate_json(json_data)
                            results.append(job)
                        except Exception:
                            continue
            except Exception as sql_err:
                logger.warning(f"[registry] Monitored jobs search failed: {sql_err}")

        if exclude_keywords:
            ex_low = [ek.strip().lower() for ek in exclude_keywords if ek and ek.strip()]
            filtered: list[JobListing] = []
            for j in results:
                t_low = (j.title or "").lower()
                d_low = (j.description or "").lower()
                if any(ek in t_low or ek in d_low for ek in ex_low):
                    continue
                filtered.append(j)
            results = filtered

        return results[:limit]

    def mark_missing_jobs_closed(self, board_id: int, active_job_ids: set[str]) -> int:
        """
        Marks active jobs belonging to a board that are missing from the latest check as 'closed'.
        Preserves complete history without deleting rows (ADR 0001).
        """
        now = time.time()
        try:
            with self._get_connection() as conn:
                if not active_job_ids:
                    cursor = conn.execute(
                        "UPDATE monitored_jobs SET status = 'closed', last_checked_at = ? WHERE board_id = ? AND status = 'active'",
                        (now, board_id),
                    )
                else:
                    placeholders = ",".join("?" for _ in active_job_ids)
                    cursor = conn.execute(
                        f"UPDATE monitored_jobs SET status = 'closed', last_checked_at = ? WHERE board_id = ? AND status = 'active' AND job_id NOT IN ({placeholders})",
                        (now, board_id, *active_job_ids),
                    )
                closed_count = cursor.rowcount
                if closed_count > 0:
                    conn.execute(
                        "UPDATE registry_meta SET value = value + 1 WHERE key = 'store_version'"
                    )
                conn.commit()
            if closed_count > 0:
                logger.info(f"[registry] Marked {closed_count} jobs closed for board {board_id}")
            return closed_count
        except Exception as exc:
            logger.warning(f"[registry] Failed to mark missing jobs closed for board {board_id}: {exc}")
            return 0

    def acquire_lease(self, lease_name: str, holder_id: str, ttl_seconds: float = 60.0) -> bool:
        """
        Cross-process atomic lease acquisition in SQLite.
        Works across Windows, Linux, FastAPI workers, and CLI daemons without PID signals.
        """
        now = time.time()
        expires_at = now + ttl_seconds
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM monitor_leases WHERE expires_at < ?", (now,))
                conn.execute(
                    "INSERT OR IGNORE INTO monitor_leases (lease_name, holder_id, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
                    (lease_name, holder_id, now, expires_at),
                )
                conn.execute(
                    "UPDATE monitor_leases SET expires_at = ? WHERE lease_name = ? AND holder_id = ?",
                    (expires_at, lease_name, holder_id),
                )
                conn.commit()

                cursor = conn.execute("SELECT holder_id FROM monitor_leases WHERE lease_name = ?", (lease_name,))
                row = cursor.fetchone()
                return bool(row and row[0] == holder_id)
        except Exception as exc:
            logger.warning(f"[registry] Error acquiring lease '{lease_name}' for '{holder_id}': {exc}")
            return False

    def renew_lease(self, lease_name: str, holder_id: str, ttl_seconds: float = 60.0) -> bool:
        """Heartbeat renewal for an active lease."""
        now = time.time()
        expires_at = now + ttl_seconds
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE monitor_leases SET expires_at = ? WHERE lease_name = ? AND holder_id = ?",
                    (expires_at, lease_name, holder_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as exc:
            logger.warning(f"[registry] Error renewing lease '{lease_name}' for '{holder_id}': {exc}")
            return False

    def release_lease(self, lease_name: str, holder_id: str) -> None:
        """Explicit graceful release of a lease."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM monitor_leases WHERE lease_name = ? AND holder_id = ?",
                    (lease_name, holder_id),
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"[registry] Error releasing lease '{lease_name}': {exc}")

    def get_monitoring_status(self) -> dict[str, Any]:
        """Provides status metrics on registered boards, scheduling latency, throughput limits, and monitored jobs."""
        now = time.time()
        hourly_capacity = int((3600 / max(1, settings.monitoring_interval_seconds)) * settings.monitoring_batch_size)
        checks_per_board_hour = 3600.0 / max(1, settings.monitoring_board_interval_seconds)
        sustainable_boards = int(hourly_capacity / max(0.01, checks_per_board_hour))

        stats = {
            "total_boards": 0,
            "verified_boards": 0,
            "candidate_boards": 0,
            "due_boards": 0,
            "overdue_boards": 0,
            "oldest_overdue_seconds": 0.0,
            "batch_size": settings.monitoring_batch_size,
            "poll_interval_seconds": settings.monitoring_interval_seconds,
            "board_interval_seconds": settings.monitoring_board_interval_seconds,
            "concurrency_limit": settings.monitoring_concurrency_limit,
            "hourly_check_capacity": hourly_capacity,
            "sustainable_board_count": sustainable_boards,
            "active_monitored_jobs": 0,
            "closed_monitored_jobs": 0,
            "store_version": self.get_monitored_store_version(),
        }
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*),
                        SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN verification_status = 'candidate' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN monitoring_capability = 'supported' AND verification_status IN ('candidate', 'verified') AND (next_scheduled_check IS NULL OR next_scheduled_check <= ?) AND failure_count < 5 AND polling_priority > 0 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN monitoring_capability = 'supported' AND verification_status IN ('candidate', 'verified') AND next_scheduled_check IS NOT NULL AND next_scheduled_check < ? AND failure_count < 5 AND polling_priority > 0 THEN 1 ELSE 0 END)
                    FROM company_boards
                    """,
                    (now, now),
                ).fetchone()
                if row:
                    stats["total_boards"] = row[0] or 0
                    stats["verified_boards"] = row[1] or 0
                    stats["candidate_boards"] = row[2] or 0
                    stats["due_boards"] = row[3] or 0
                    stats["overdue_boards"] = row[4] or 0

                min_row = conn.execute(
                    """
                    SELECT MIN(next_scheduled_check)
                    FROM company_boards
                    WHERE monitoring_capability = 'supported'
                      AND verification_status IN ('candidate', 'verified')
                      AND next_scheduled_check IS NOT NULL
                      AND next_scheduled_check <= ?
                      AND failure_count < 5
                      AND polling_priority > 0
                    """,
                    (now,),
                ).fetchone()
                if min_row and min_row[0] is not None:
                    stats["oldest_overdue_seconds"] = round(max(0.0, now - float(min_row[0])), 1)

                j_row = conn.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END)
                    FROM monitored_jobs
                    """
                ).fetchone()
                if j_row:
                    stats["active_monitored_jobs"] = j_row[0] or 0
                    stats["closed_monitored_jobs"] = j_row[1] or 0
        except Exception as exc:
            logger.debug(f"[registry] Error getting monitoring status: {exc}")
        return stats

    def clear(self) -> None:
        """Clear registry table (used in tests)."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM company_boards")
                conn.execute("DELETE FROM monitored_jobs")
                try:
                    conn.execute("DELETE FROM monitored_jobs_fts")
                except Exception:
                    pass
                conn.execute("DELETE FROM monitor_leases")
                conn.execute(
                    "UPDATE registry_meta SET value = value + 1 WHERE key = 'store_version'"
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"[registry] Clear failed: {exc}")


company_board_registry = CompanyBoardRegistry()

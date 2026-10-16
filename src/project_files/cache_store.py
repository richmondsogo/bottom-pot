"""
Persistent SQLite cache and budget store for Serper calls and enriched job URLs.
Database lives in data/cache.sqlite (gitignored).
Survives worker restarts and --reload.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Optional

from loguru import logger

from src.config import settings
from src.project_files.models import JobListing


class CacheStore:
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
                    CREATE TABLE IF NOT EXISTS serper_cache (
                        key TEXT PRIMARY KEY,
                        response_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS serper_daily_budget (
                        day_utc TEXT PRIMARY KEY,
                        call_count INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS url_cache (
                        url TEXT PRIMARY KEY,
                        listing_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to initialize SQLite cache tables: {exc}")

    # ── Serper Cache ────────────────────────────────────────────────────────

    def get_serper_cache(self, key: str) -> dict | None:
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT response_json FROM serper_cache WHERE key = ? AND expires_at > ?",
                    (key, now),
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as exc:
            logger.debug(f"Serper cache lookup failed for {key}: {exc}")
        return None

    def set_serper_cache(
        self,
        key: str,
        data: dict,
        ttl_hours: float | None = None,
    ) -> None:
        try:
            ttl = ttl_hours if ttl_hours is not None else settings.serper_cache_ttl_hours
            now = time.time()
            expires_at = now + (ttl * 3600)
            payload = json.dumps(data)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO serper_cache (key, response_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        response_json=excluded.response_json,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """,
                    (key, payload, now, expires_at),
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"Serper cache set failed for {key}: {exc}")

    # ── Daily Budget ────────────────────────────────────────────────────────

    def get_daily_budget_count(self, day_utc: str | None = None) -> int:
        day = day_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT call_count FROM serper_daily_budget WHERE day_utc = ?",
                    (day,),
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except Exception as exc:
            logger.debug(f"Failed to get daily budget count: {exc}")
            return 0

    def check_and_increment_daily_budget(
        self,
        budget_limit: int | None = None,
        day_utc: str | None = None,
    ) -> tuple[bool, int]:
        """
        Atomically check and increment the daily Serper call count for today (UTC).
        Returns (allowed, current_count).
        If allowed is False, current_count has reached or exceeded budget_limit.
        """
        limit = budget_limit if budget_limit is not None else settings.serper_daily_budget
        day = day_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT call_count FROM serper_daily_budget WHERE day_utc = ?",
                    (day,),
                )
                row = cursor.fetchone()
                current = int(row[0]) if row else 0

                if current >= limit:
                    return (False, current)

                new_count = current + 1
                conn.execute(
                    """
                    INSERT INTO serper_daily_budget (day_utc, call_count)
                    VALUES (?, ?)
                    ON CONFLICT(day_utc) DO UPDATE SET call_count = excluded.call_count
                    """,
                    (day, new_count),
                )
                conn.commit()
                return (True, new_count)
        except Exception as exc:
            logger.warning(f"Failed to check/increment daily budget: {exc}")
            return (True, 0)

    # ── Per-URL Cache ───────────────────────────────────────────────────────

    def get_url_cache(self, url: str) -> JobListing | None:
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT listing_json FROM url_cache WHERE url = ? AND expires_at > ?",
                    (url, now),
                )
                row = cursor.fetchone()
                if row:
                    return JobListing.model_validate_json(row[0])
        except Exception as exc:
            logger.debug(f"URL cache lookup failed for {url}: {exc}")
        return None

    def set_url_cache(
        self,
        url: str,
        listing: JobListing,
        ttl_hours: float | None = None,
    ) -> None:
        try:
            ttl = ttl_hours if ttl_hours is not None else settings.url_cache_ttl_hours
            now = time.time()
            expires_at = now + (ttl * 3600)
            payload = listing.model_dump_json()
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO url_cache (url, listing_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        listing_json=excluded.listing_json,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """,
                    (url, payload, now, expires_at),
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"URL cache set failed for {url}: {exc}")

    # ── Maintenance / Testing ───────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all tables (used in testing)."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM serper_cache")
                conn.execute("DELETE FROM serper_daily_budget")
                conn.execute("DELETE FROM url_cache")
                conn.commit()
        except Exception as exc:
            logger.debug(f"Failed to clear cache: {exc}")


cache_store = CacheStore()

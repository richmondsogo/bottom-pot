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

    @staticmethod
    def _is_plain_subset_of_richer_description(incoming_desc: str, existing_desc: str) -> bool:
        """
        Return True when incoming looks like an incomplete plain-only opening truncation
        (e.g. descriptionPlain without lists[]/additional) of a richer existing description.
        """
        import re as _re

        norm_in = _re.sub(r"\s+", " ", incoming_desc.strip()).lower()
        norm_ex = _re.sub(r"\s+", " ", existing_desc.strip()).lower()
        if not norm_in or len(norm_in) >= len(norm_ex):
            return False
        has_richer_structure = ("\n- " in existing_desc or "\n### " in existing_desc or "\n**" in existing_desc) and (
            len(existing_desc) - len(incoming_desc) >= 120
        )
        if not has_richer_structure:
            return False
        prefix_probe = norm_in[: min(len(norm_in), 160)]
        return len(prefix_probe) >= 60 and norm_ex.startswith(prefix_probe) and (
            norm_in in norm_ex or norm_ex[: len(norm_in)] == norm_in
        )

    @staticmethod
    def _merge_preserving_completeness(
        incoming: JobListing,
        existing: JobListing,
        *,
        preserve_omitted_optional_fields: bool = False,
    ) -> JobListing:
        """
        Update a cached/monitored listing from a newer incoming observation while
        protecting against incomplete or degraded payloads and preserving verified logos.

        - Incomplete/degraded incoming payloads (snippet fallbacks, error outcomes, empty
          or non-quality descriptions, or plain-only truncations of richer descriptions)
          keep existing richer content via progressive merge.
        - Partial monitor feeds (`preserve_omitted_optional_fields=True`) preserve existing
          optional salary/requirements/eligibility when omitted by the feed, while still
          applying legitimate edits (including shorter descriptions, corrected salaries,
          and updated locations/work models).
        - Authoritative full updates (`preserve_omitted_optional_fields=False`, non-degraded)
          replace fields cleanly, allowing genuine deletion of salary/requirements and
          shorter rewritten descriptions, while never downgrading a verified company logo.
        """
        from src.project_files.deduplicator import merge_listings
        from src.project_files.field_normalizer import humanize_slug

        inc_desc = (incoming.description or "").strip()
        ex_desc = (existing.description or "").strip()
        is_degraded = bool(
            (incoming.data_source == "snippet" and existing.data_source in ("api", "scrape"))
            or getattr(incoming, "extraction_outcome", None)
            or (not inc_desc and bool(ex_desc))
            or (not incoming.description_ok and existing.description_ok)
            or (
                inc_desc
                and ex_desc
                and CacheStore._is_plain_subset_of_richer_description(inc_desc, ex_desc)
            )
        )

        if is_degraded:
            merged = merge_listings(incoming, existing)
            # If existing had richer description and incoming was plain-only subset, keep existing description/ok
            if ex_desc and (not inc_desc or (not incoming.description_ok and existing.description_ok) or CacheStore._is_plain_subset_of_richer_description(inc_desc, ex_desc)):
                merged.description = existing.description
                merged.description_ok = existing.description_ok
        else:
            merged = incoming.model_copy(deep=True)
            # Preserve existing aliases + merge provenance
            combined_aliases = set(merged.aliases) | set(existing.aliases)
            if existing.id and existing.id != merged.id:
                combined_aliases.add(existing.id)
            combined_aliases.discard(merged.id)
            merged.aliases = sorted(combined_aliases)

            # Avoid downgrading an authoritative company name to a generic slug guess
            slug_guess = humanize_slug(incoming.company_slug) if incoming.company_slug else None
            if (
                existing.company
                and existing.company != "Unknown"
                and (not merged.company or merged.company == "Unknown" or (slug_guess and merged.company == slug_guess and existing.company != slug_guess))
            ):
                merged.company = existing.company

            if preserve_omitted_optional_fields:
                if merged.salary is None and existing.salary is not None:
                    merged.salary = existing.salary
                if not merged.requirements and existing.requirements:
                    merged.requirements = existing.requirements
                if merged.eligibility is None and existing.eligibility is not None:
                    merged.eligibility = existing.eligibility

        # Always preserve verified company logo against unverified/empty incoming candidates
        if existing.company_logo_verified and existing.company_logo_url:
            if not merged.company_logo_verified or not merged.company_logo_url:
                merged.company_logo_url = existing.company_logo_url
                merged.company_logo_source = existing.company_logo_source
                merged.company_logo_verified = True
        return merged

    def get_url_cache(self, url: str) -> JobListing | None:
        from src.project_files.url_normalizer import normalize_job_url

        norm_url = normalize_job_url(url) or url
        try:
            now = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT listing_json FROM url_cache WHERE (url = ? OR url = ?) AND expires_at > ?",
                    (norm_url, url, now),
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
        from src.project_files.url_normalizer import normalize_job_url

        norm_url = normalize_job_url(url, getattr(listing, "provider", None)) or url
        try:
            ttl = ttl_hours if ttl_hours is not None else settings.url_cache_ttl_hours
            now = time.time()
            expires_at = now + (ttl * 3600)
            with self._get_connection() as conn:
                existing_row = conn.execute(
                    "SELECT listing_json FROM url_cache WHERE (url = ? OR url = ?) AND expires_at > ?",
                    (norm_url, url, now),
                ).fetchone()
                final_listing = listing
                if existing_row:
                    try:
                        existing = JobListing.model_validate_json(existing_row[0])
                        final_listing = self._merge_preserving_completeness(listing, existing)
                    except Exception:
                        final_listing = listing

                payload = final_listing.model_dump_json()
                conn.execute(
                    """
                    INSERT INTO url_cache (url, listing_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        listing_json=excluded.listing_json,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """,
                    (norm_url, payload, now, expires_at),
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

"""
Ashby Zero-Serper Operational Cache & Monitored Jobs Repair (Step 39).

Refreshes degraded Ashby rows in `url_cache`, reconciles Ashby rows in
`company_boards`, and syncs active `monitored_jobs` using public unauthenticated
Ashby endpoints:
1. GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
2. Bounded board HTML identity enrichment (organization.name + verified square logo)
3. Single-posting AshbyClient fallback when an item is absent from the board feed.

Guarantees:
- 0 Serper credits consumed (`serper_calls_used == 0`).
- Restartable progress checkpointing via `ashby_repair_state` keyed by version `v39`.
- Idempotent re-runs skipping already repaired/terminal URLs unless `force=True`.
- Strict synthetic exclusion (`company0..company9`, `example.com`, test/dummy slugs).
- Conservative URL alias canonicalization (re-keys normalized URL & removes superseded
  tracking/application alias rows only after durable write).
- 404 / transient preservation (never deletes valid historical cached entries).
- Completeness-aware merging preserving verified company logos and existing descriptions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
import httpx
from loguru import logger

from src.config import settings
from src.project_files.ats_api_client import (
    AshbyClient,
    ashby_payload_to_raw,
    enrich_ashby_board_identity,
)
from src.project_files.ats_url_parser import ParsedATSUrl, parse_ats_url
from src.project_files.cache_store import CacheStore, cache_store as _default_cache_store
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    company_board_registry as _default_registry,
)
from src.project_files.field_normalizer import humanize_slug
from src.project_files.http_headers import browser_headers
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.logo_extractor import (
    LogoResult,
    extract_ashby_app_data_from_soup,
    extract_company_logo_for_provider,
)
from src.project_files.models import JobListing
from src.project_files.url_normalizer import normalize_job_url

REPAIR_VERSION = "v39"
_SYNTHETIC_DOMAINS = {"example.com", "example.org", "example.net", "localhost", "test.local"}
_SYNTHETIC_SLUGS = {
    "testslug",
    "testcompany",
    "samplecompany",
    "dummy",
    "fake",
}
_SYNTHETIC_SLUG_RE = re.compile(r"^(company\d+|testslug\d*|testcompany\d*|samplecompany\d*)$")


@dataclass
class AshbyRepairReport:
    dry_run: bool = False
    total_urls: int = 0
    unique_slugs: int = 0
    repaired_from_board_api: int = 0
    repaired_from_posting_api: int = 0
    canonicalized_urls: int = 0
    boards_reconciled: int = 0
    boards_identity_enriched: int = 0
    monitored_jobs_updated: int = 0
    monitored_jobs_closed: int = 0
    expired_or_unavailable: int = 0
    skipped_already_repaired: int = 0
    skipped_synthetic: int = 0
    unparsed_urls: int = 0
    transient_errors: int = 0
    serper_calls_used: int = 0


def _ensure_repair_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ashby_repair_state (
            url TEXT PRIMARY KEY,
            repair_version TEXT NOT NULL,
            status TEXT NOT NULL,
            repaired_at REAL NOT NULL,
            detail TEXT
        )
        """
    )


def _record_repair_state(
    cache: CacheStore,
    url: str,
    status: str,
    detail: str | None = None,
) -> None:
    with cache._get_connection() as conn:
        _ensure_repair_table(conn)
        conn.execute(
            """
            INSERT INTO ashby_repair_state (url, repair_version, status, repaired_at, detail)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                repair_version=excluded.repair_version,
                status=excluded.status,
                repaired_at=excluded.repaired_at,
                detail=excluded.detail
            """,
            (url, REPAIR_VERSION, status, time.time(), detail),
        )
        conn.commit()


def _load_completed_urls(cache: CacheStore) -> set[str]:
    with cache._get_connection() as conn:
        _ensure_repair_table(conn)
        rows = conn.execute(
            """
            SELECT url FROM ashby_repair_state
            WHERE repair_version = ? AND status IN ('repaired', 'unavailable_404', 'unparsed')
            """,
            (REPAIR_VERSION,),
        ).fetchall()
    return {str(row[0]) for row in rows if row and row[0]}


def _is_synthetic_slug(slug: str | None) -> bool:
    s = (slug or "").strip().lower()
    if not s:
        return False
    if s in _SYNTHETIC_SLUGS or _SYNTHETIC_SLUG_RE.fullmatch(s):
        return True
    return s.startswith(("test-", "dummy-", "fake-", "synthetic-"))


def _is_synthetic_ashby_record(
    url: str,
    slug: str | None,
    existing: JobListing | None = None,
) -> bool:
    parsed_netloc = urlparse(url).netloc.lower()
    if parsed_netloc in _SYNTHETIC_DOMAINS or parsed_netloc.endswith(".example.com"):
        return True
    if _is_synthetic_slug(slug):
        return True
    if existing is not None:
        if _is_synthetic_slug(existing.company_slug):
            return True
        if existing.source_url:
            src_netloc = urlparse(existing.source_url).netloc.lower()
            if src_netloc in _SYNTHETIC_DOMAINS or src_netloc.endswith(".example.com"):
                return True
    return False


async def _fetch_board_identity_readonly(
    company_slug: str,
    client: httpx.AsyncClient,
) -> tuple[str | None, LogoResult]:
    """Read-only Ashby board page identity probe for --dry-run (never writes SQLite)."""
    slug = (company_slug or "").strip()
    if not slug:
        return None, LogoResult()
    encoded_slug = quote(slug, safe="-_.~")
    board_url = f"https://jobs.ashbyhq.com/{encoded_slug}"
    headers = {
        **browser_headers(board_url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"),
        "Accept-Encoding": "gzip, deflate",
    }
    try:
        resp = await client.get(
            board_url,
            headers=headers,
            timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
        )
    except Exception:
        return None, LogoResult()
    if resp.status_code != 200:
        return None, LogoResult()
    content_type = (resp.headers.get("content-type") or "").lower()
    body_text = resp.text or ""
    if "json" in content_type or not body_text.lstrip().startswith("<"):
        return None, LogoResult()

    soup = BeautifulSoup(body_text, "html.parser")
    app_data = extract_ashby_app_data_from_soup(soup)
    org_name: str | None = None
    if isinstance(app_data, dict):
        org = app_data.get("organization")
        if isinstance(org, dict):
            raw_name = org.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                org_name = raw_name.strip()
    logo = extract_company_logo_for_provider(
        "ashby",
        soup=soup,
        page_url=board_url,
        company_name=org_name,
    )
    return org_name, logo


def _listing_from_ashby_item(
    item: dict,
    *,
    company_slug: str,
    source_url: str | None,
    board_name: str | None,
    logo: LogoResult,
) -> JobListing | None:
    raw = ashby_payload_to_raw(
        item,
        company_slug=company_slug,
        source_url=source_url,
        query_used=company_slug,
        default_company_name=board_name or humanize_slug(company_slug),
        is_board_monitor=False,
        company_logo_url=logo.url if logo.verified else None,
        company_logo_source=logo.source if logo.verified else None,
        company_logo_verified=bool(logo.verified and logo.url),
    )
    if raw is None or not raw.raw_title or not raw.source_url:
        return None
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "ashby"
    listing.ats_source = "ashby"
    listing.data_source = "api"
    if logo.verified and logo.url and not listing.company_logo_url:
        listing.company_logo_url = logo.url
        listing.company_logo_source = logo.source
        listing.company_logo_verified = True
    return listing


def _mark_monitored_job_closed_if_present(
    registry: CompanyBoardRegistry,
    *,
    job_id: str | None,
    url: str,
) -> int:
    now = time.time()
    closed = 0
    with registry._get_connection() as conn:
        if job_id:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE job_id = ? AND ats_provider = 'ashby' AND status = 'active'
                """,
                (now, job_id),
            )
            closed += max(0, cur.rowcount or 0)
        if closed == 0 and url:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE (source_url = ? OR apply_url = ?) AND ats_provider = 'ashby' AND status = 'active'
                """,
                (now, url, url),
            )
            closed += max(0, cur.rowcount or 0)
        if closed > 0:
            conn.commit()
    return closed


def _sync_monitored_job_if_present(
    registry: CompanyBoardRegistry,
    listing: JobListing,
) -> int:
    """Update an already-tracked monitored_jobs row with repaired listing data."""
    with registry._get_connection() as conn:
        row = conn.execute(
            "SELECT board_id, content_fingerprint FROM monitored_jobs WHERE job_id = ?",
            (listing.id,),
        ).fetchone()
    if row is None:
        return 0
    ok = registry.upsert_monitored_job(
        listing,
        board_id=row[0],
        content_fingerprint=row[1],
    )
    return 1 if ok else 0


def _write_canonical_url_cache(
    cache: CacheStore,
    *,
    original_url: str,
    canonical_url: str,
    listing: JobListing,
    ttl_hours: float | None,
) -> bool:
    """
    Persist `listing` at `canonical_url` with completeness preservation.
    When `canonical_url != original_url`, safely merge with any existing row at
    `canonical_url` first and delete the superseded unnormalized alias row afterwards.
    Returns True if alias re-keying occurred.
    """
    existing_canonical: JobListing | None = None
    if canonical_url != original_url:
        with cache._get_connection() as conn:
            row = conn.execute(
                "SELECT listing_json FROM url_cache WHERE url = ?",
                (canonical_url,),
            ).fetchone()
        if row and row[0]:
            try:
                existing_canonical = JobListing.model_validate_json(row[0])
            except Exception:
                existing_canonical = None

    final_listing = listing
    if existing_canonical is not None:
        final_listing = CacheStore._merge_preserving_completeness(
            final_listing,
            existing_canonical,
            preserve_omitted_optional_fields=False,
        )

    cache.set_url_cache(canonical_url, final_listing, ttl_hours=ttl_hours)

    if canonical_url != original_url:
        with cache._get_connection() as conn:
            conn.execute("DELETE FROM url_cache WHERE url = ?", (original_url,))
            conn.commit()
        return True
    return False


async def _fetch_board_jobs_map(
    slug: str,
    client: httpx.AsyncClient,
) -> tuple[int | None, dict[str, dict]]:
    encoded_slug = quote(slug, safe="-_.~")
    board_api_url = f"https://api.ashbyhq.com/posting-api/job-board/{encoded_slug}?includeCompensation=true"
    headers = browser_headers(board_api_url, "application/json")
    headers["Accept-Encoding"] = "gzip, deflate"
    try:
        resp = await client.get(
            board_api_url,
            headers=headers,
            timeout=12.0,
        )
    except Exception as exc:
        logger.debug(f"[ashby-repair] Board list fetch failed for {slug}: {exc}")
        return None, {}

    if resp.status_code != 200:
        return resp.status_code, {}

    try:
        payload = resp.json()
    except Exception:
        return 200, {}
    if not isinstance(payload, dict):
        return 200, {}

    jobs_list = payload.get("jobs")
    if not isinstance(jobs_list, list):
        return 200, {}

    items_by_id: dict[str, dict] = {}
    for item in jobs_list:
        if isinstance(item, dict) and item.get("id"):
            items_by_id[str(item["id"]).strip().lower()] = item
    return 200, items_by_id


async def repair_ashby_cache(
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    force: bool = False,
    dry_run: bool = False,
) -> AshbyRepairReport:
    """
    Re-extract degraded Ashby rows in `url_cache`, reconcile `company_boards`
    identities, and sync active Ashby `monitored_jobs`.

    Guarantees 0 Serper credits used, restartability via `ashby_repair_state`,
    preservation of valid historical cache entries on 404/transient errors,
    synthetic record skipping, conservative alias re-keying, and non-mutating
    simulation when `dry_run=True`.
    """
    target_cache = cache or _default_cache_store
    target_registry = registry or _default_registry
    report = AshbyRepairReport(dry_run=dry_run)

    if dry_run:
        with target_cache._get_connection() as conn:
            has_state_table = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ashby_repair_state'"
                ).fetchone()
            )
            if has_state_table and not force:
                rows_state = conn.execute(
                    """
                    SELECT url FROM ashby_repair_state
                    WHERE repair_version = ? AND status IN ('repaired', 'unavailable_404', 'unparsed')
                    """,
                    (REPAIR_VERSION,),
                ).fetchall()
                completed_urls = {str(r[0]) for r in rows_state if r and r[0]}
            else:
                completed_urls = set()
            cache_rows = conn.execute(
                "SELECT url, listing_json FROM url_cache WHERE LOWER(url) LIKE '%ashby%' ORDER BY created_at ASC"
            ).fetchall()
    else:
        completed_urls = set() if force else _load_completed_urls(target_cache)
        with target_cache._get_connection() as conn:
            _ensure_repair_table(conn)
            cache_rows = conn.execute(
                "SELECT url, listing_json FROM url_cache WHERE LOWER(url) LIKE '%ashby%' ORDER BY created_at ASC"
            ).fetchall()

    grouped_rows: dict[str, list[tuple[str, str, ParsedATSUrl, JobListing | None]]] = {}
    raw_slug_by_lower: dict[str, str] = {}
    genuine_total_urls = 0

    for url, raw_json in cache_rows:
        existing_listing: JobListing | None = None
        if raw_json:
            try:
                existing_listing = JobListing.model_validate_json(raw_json)
            except Exception:
                existing_listing = None

        parsed = parse_ats_url(url)
        candidate_slug = parsed.company_slug if parsed else (existing_listing.company_slug if existing_listing else None)
        if _is_synthetic_ashby_record(url, candidate_slug, existing_listing):
            report.skipped_synthetic += 1
            continue

        if parsed is None or parsed.ats != "ashby" or not parsed.company_slug or not parsed.job_id:
            if (
                existing_listing
                and existing_listing.company_slug
                and existing_listing.provider_job_id
                and parsed is None
            ):
                clean_jid = existing_listing.provider_job_id
                if ":" in clean_jid:
                    clean_jid = clean_jid.split(":")[-1]
                parsed = ParsedATSUrl(
                    ats="ashby",
                    company_slug=existing_listing.company_slug,
                    job_id=clean_jid.lower(),
                    raw_url=url,
                )
            else:
                genuine_total_urls += 1
                if not force and url in completed_urls:
                    report.skipped_already_repaired += 1
                    continue
                report.unparsed_urls += 1
                if not dry_run:
                    _record_repair_state(target_cache, url, "unparsed", "Not a single Ashby job posting URL")
                continue

        norm_url = normalize_job_url(url, "ashby") or url
        genuine_total_urls += 1
        if not force and (url in completed_urls or norm_url in completed_urls):
            report.skipped_already_repaired += 1
            continue

        slug_key = parsed.company_slug.lower()
        raw_slug_by_lower.setdefault(slug_key, parsed.company_slug)
        grouped_rows.setdefault(slug_key, []).append((url, norm_url, parsed, existing_listing))

    report.total_urls = genuine_total_urls

    # Collect active monitored_jobs slugs
    with target_registry._get_connection() as conn:
        monitored_rows = conn.execute(
            """
            SELECT job_id, company_slug, source_url, canonical_json
            FROM monitored_jobs
            WHERE ats_provider = 'ashby' AND status = 'active'
            """
        ).fetchall()
        board_rows = conn.execute(
            """
            SELECT board_token, company_name, company_logo_url, company_logo_verified, company_logo_checked_at
            FROM company_boards
            WHERE ats_provider = 'ashby'
            """
        ).fetchall()

    monitored_by_slug: dict[str, list[tuple[str, str, str | None, JobListing | None]]] = {}
    for canonical_id, slug, source_url, canonical_json in monitored_rows:
        slug_norm = (slug or "").strip().lower()
        existing_mon: JobListing | None = None
        if canonical_json:
            try:
                existing_mon = JobListing.model_validate_json(canonical_json)
            except Exception:
                existing_mon = None
        if _is_synthetic_ashby_record(source_url or "", slug_norm, existing_mon):
            report.skipped_synthetic += 1
            continue
        if not force and f"monitored:{canonical_id}" in completed_urls:
            continue
        raw_slug_by_lower.setdefault(slug_norm, (slug or "").strip() or slug_norm)
        monitored_by_slug.setdefault(slug_norm, []).append(
            (str(canonical_id), slug_norm, source_url, existing_mon)
        )

    board_slugs_to_reconcile: set[str] = set()
    for board_token, _b_name, b_logo_url, b_logo_verified, b_checked_at in board_rows:
        slug_norm = (board_token or "").strip().lower()
        if not slug_norm or _is_synthetic_slug(slug_norm):
            continue
        raw_slug_by_lower.setdefault(slug_norm, slug_norm)
        if slug_norm in grouped_rows or slug_norm in monitored_by_slug or force or (b_checked_at is None):
            board_slugs_to_reconcile.add(slug_norm)

    all_slugs = sorted(set(grouped_rows.keys()) | set(monitored_by_slug.keys()) | board_slugs_to_reconcile)
    report.unique_slugs = len(grouped_rows)

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15.0)
    sem = asyncio.Semaphore(max(1, concurrency))
    ashby_client = AshbyClient()

    async def _process_slug(slug_key: str) -> None:
        async with sem:
            fetch_slug = raw_slug_by_lower.get(slug_key, slug_key)
            board_name: str | None = None
            board_logo = LogoResult()
            try:
                if dry_run:
                    board_name, board_logo = await _fetch_board_identity_readonly(fetch_slug, http_client)
                else:
                    board_name, board_logo = await enrich_ashby_board_identity(
                        fetch_slug,
                        http_client,
                        registry=target_registry,
                    )
                if board_logo.verified and board_logo.url:
                    report.boards_identity_enriched += 1
            except Exception as exc:
                logger.debug(f"[ashby-repair] Identity enrich skipped for {slug_key}: {exc}")

            if slug_key in board_slugs_to_reconcile:
                report.boards_reconciled += 1

            slug_url_rows = grouped_rows.get(slug_key, [])
            slug_mon_rows = monitored_by_slug.get(slug_key, [])
            if not slug_url_rows and not slug_mon_rows:
                return

            status_code, items_by_id = await _fetch_board_jobs_map(fetch_slug, http_client)
            synced_job_ids: set[str] = set()

            # 1) Repair url_cache rows for this slug
            for url, norm_url, parsed, existing_listing in slug_url_rows:
                matched_item = items_by_id.get((parsed.job_id or "").lower())
                if matched_item is not None:
                    repaired = _listing_from_ashby_item(
                        matched_item,
                        company_slug=parsed.company_slug,
                        source_url=norm_url,
                        board_name=board_name,
                        logo=board_logo,
                    )
                    if repaired is not None:
                        if dry_run:
                            report.repaired_from_board_api += 1
                            if norm_url != url:
                                report.canonicalized_urls += 1
                            continue
                        if existing_listing is not None:
                            repaired = CacheStore._merge_preserving_completeness(
                                repaired,
                                existing_listing,
                                preserve_omitted_optional_fields=False,
                            )
                        canonicalized = _write_canonical_url_cache(
                            target_cache,
                            original_url=url,
                            canonical_url=norm_url,
                            listing=repaired,
                            ttl_hours=ttl_hours,
                        )
                        if canonicalized:
                            report.canonicalized_urls += 1
                        synced_count = _sync_monitored_job_if_present(target_registry, repaired)
                        report.monitored_jobs_updated += synced_count
                        if synced_count:
                            _record_repair_state(target_cache, f"monitored:{repaired.id}", "repaired", "monitored_job")
                        synced_job_ids.add(repaired.id)
                        report.repaired_from_board_api += 1
                        detail = "board_api_canonicalized" if canonicalized else "board_api"
                        _record_repair_state(target_cache, url, "repaired", detail)
                        if canonicalized:
                            _record_repair_state(target_cache, norm_url, "repaired", "board_api")
                        continue

                # Fall back to single-posting Ashby API for unlisted or unavailable/404 postings
                res = await ashby_client.fetch_raw_result(parsed, http_client)
                if res.outcome == ExtractionOutcome.SUCCESS and res.raw is not None:
                    if not res.raw.raw_fields.get("company_logo_url") and board_logo.verified and board_logo.url:
                        res.raw.raw_fields["company_logo_url"] = board_logo.url
                        res.raw.raw_fields["company_logo_source"] = board_logo.source
                        res.raw.raw_fields["company_logo_verified"] = True
                    if board_name and (
                        not res.raw.raw_company
                        or res.raw.raw_company == "Unknown"
                        or res.raw.raw_company == humanize_slug(parsed.company_slug)
                    ):
                        res.raw.raw_company = board_name

                    canonical = JobExtractionService.extract(res.raw)
                    repaired = CanonicalJobAdapter.to_listing(canonical)
                    repaired.provider = "ashby"
                    repaired.ats_source = "ashby"
                    repaired.data_source = "api"
                    if board_logo.verified and board_logo.url and not repaired.company_logo_url:
                        repaired.company_logo_url = board_logo.url
                        repaired.company_logo_source = board_logo.source
                        repaired.company_logo_verified = True

                    if dry_run:
                        report.repaired_from_posting_api += 1
                        if norm_url != url:
                            report.canonicalized_urls += 1
                        continue

                    if existing_listing is not None:
                        repaired = CacheStore._merge_preserving_completeness(
                            repaired,
                            existing_listing,
                            preserve_omitted_optional_fields=False,
                        )
                    canonicalized = _write_canonical_url_cache(
                        target_cache,
                        original_url=url,
                        canonical_url=norm_url,
                        listing=repaired,
                        ttl_hours=ttl_hours,
                    )
                    if canonicalized:
                        report.canonicalized_urls += 1
                    synced_count = _sync_monitored_job_if_present(target_registry, repaired)
                    report.monitored_jobs_updated += synced_count
                    if synced_count:
                        _record_repair_state(target_cache, f"monitored:{repaired.id}", "repaired", "monitored_job")
                    synced_job_ids.add(repaired.id)
                    report.repaired_from_posting_api += 1
                    detail = "posting_api_canonicalized" if canonicalized else "posting_api"
                    _record_repair_state(target_cache, url, "repaired", detail)
                    if canonicalized:
                        _record_repair_state(target_cache, norm_url, "repaired", "posting_api")
                elif res.outcome == ExtractionOutcome.NOT_FOUND:
                    report.expired_or_unavailable += 1
                    if dry_run:
                        continue
                    canonical_id = existing_listing.id if existing_listing else f"ashby:{parsed.company_slug.lower()}:{parsed.job_id}"
                    closed = _mark_monitored_job_closed_if_present(
                        target_registry,
                        job_id=canonical_id,
                        url=norm_url,
                    )
                    report.monitored_jobs_closed += closed
                    _record_repair_state(
                        target_cache,
                        url,
                        "unavailable_404",
                        f"HTTP {res.status_code or 404}",
                    )
                else:
                    report.transient_errors += 1

            # 2) Sync active monitored_jobs for this slug if not already refreshed via url_cache
            if not dry_run and status_code == 200 and items_by_id:
                for canonical_id, m_slug, m_source_url, existing_mon in slug_mon_rows:
                    if canonical_id in synced_job_ids:
                        continue
                    provider_job_id = canonical_id.split(":")[-1].lower() if ":" in canonical_id else ""
                    item = items_by_id.get(provider_job_id)
                    if item is not None:
                        repaired = _listing_from_ashby_item(
                            item,
                            company_slug=m_slug,
                            source_url=m_source_url,
                            board_name=board_name,
                            logo=board_logo,
                        )
                        if repaired is not None:
                            if existing_mon is not None:
                                repaired = CacheStore._merge_preserving_completeness(
                                    repaired,
                                    existing_mon,
                                    preserve_omitted_optional_fields=False,
                                )
                            synced_count = _sync_monitored_job_if_present(target_registry, repaired)
                            report.monitored_jobs_updated += synced_count
                            _record_repair_state(target_cache, f"monitored:{canonical_id}", "repaired", "board_api_monitored")

    try:
        tasks = [_process_slug(s) for s in all_slugs]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        if own_client:
            await http_client.aclose()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair degraded Ashby cache rows without Serper spend.")
    parser.add_argument("--force", action="store_true", help="Re-process URLs even if marked completed in state table.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate repair without writing to SQLite.")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent company slugs.")
    args = parser.parse_args()

    logger.info(f"[ashby-repair] Starting Ashby cache repair (dry_run={args.dry_run}, force={args.force})...")
    rep = asyncio.run(repair_ashby_cache(force=args.force, dry_run=args.dry_run, concurrency=args.concurrency))
    logger.info(f"[ashby-repair] Completed: {json.dumps(asdict(rep), indent=2)}")


if __name__ == "__main__":
    main()

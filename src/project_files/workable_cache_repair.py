"""
Workable Zero-Serper Operational Cache & Monitored Jobs Repair (Step 41).

Refreshes degraded Workable rows in `url_cache`, promotes and reconciles Workable
rows in `company_boards`, and syncs active `monitored_jobs` using public
unauthenticated Workable GET endpoints:
1. GET https://apply.workable.com/api/v1/accounts/{slug} (board identity + logo)
2. GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}
   (via WorkableClient, with clean Markdown fallback only if `.md` is served).

Guarantees:
- 0 Serper credits consumed (`serper_calls_used == 0`).
- Restartable progress checkpointing via `workable_repair_state` keyed by version `v41`.
- Idempotent re-runs skipping already repaired/terminal URLs unless `force=True`.
- Strict synthetic exclusion (`company0..company9`, `example.com`, test/dummy slugs).
- Conservative URL alias canonicalization (re-keys normalized URL & removes superseded
  `/apply`, `?utm_*`, trailing-slash, or subdomain alias rows only after durable write).
- 404 / transient preservation (never deletes valid historical cached entries).
- Completeness-aware merging preserving verified company logos, posted_at, and descriptions.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
import re
import sqlite3
import time
from urllib.parse import quote, urlparse

import httpx
from loguru import logger

from src.config import settings
from src.project_files.ats_api_client import (
    WorkableClient,
    enrich_workable_board_identity,
)
from src.project_files.ats_url_parser import ParsedATSUrl, parse_ats_url
from src.project_files.cache_store import CacheStore, cache_store as _default_cache_store
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    build_canonical_board_url,
    company_board_registry as _default_registry,
)
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.field_normalizer import humanize_slug
from src.project_files.http_headers import browser_headers
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.logo_extractor import LogoResult, extract_company_logo_for_provider
from src.project_files.models import JobListing
from src.project_files.url_normalizer import normalize_job_url

REPAIR_VERSION = "v41"
_SYNTHETIC_DOMAINS = {"example.com", "example.org", "example.net", "localhost", "test.local"}
_SYNTHETIC_SLUGS = {
    "testslug",
    "testcompany",
    "samplecompany",
    "examplecompany",
    "dummy",
    "fake",
}
_SYNTHETIC_SLUG_RE = re.compile(r"^(company\d+|testslug\d*|testcompany\d*|samplecompany\d*)$")


@dataclass
class WorkableRepairReport:
    dry_run: bool = False
    total_urls: int = 0
    unique_slugs: int = 0
    repaired_from_v2_api: int = 0
    canonicalized_urls: int = 0
    boards_reconciled: int = 0
    boards_promoted: int = 0
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
        CREATE TABLE IF NOT EXISTS workable_repair_state (
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
            INSERT INTO workable_repair_state (url, repair_version, status, repaired_at, detail)
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
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workable_repair_state'"
        ).fetchone()
        if not table_exists:
            return set()
        rows = conn.execute(
            """
            SELECT url FROM workable_repair_state
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


def _is_synthetic_workable_record(
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
    """Read-only Workable account API probe for --dry-run (never writes SQLite)."""
    slug = (company_slug or "").strip()
    if not slug:
        return None, LogoResult()
    encoded_slug = quote(slug, safe="-_.~")
    account_url = f"https://apply.workable.com/api/v1/accounts/{encoded_slug}"
    headers = browser_headers(account_url, "application/json")
    try:
        resp = await client.get(
            account_url,
            headers=headers,
            timeout=min(float(settings.ats_request_timeout_seconds), 8.0),
        )
    except Exception:
        return None, LogoResult()
    if resp.status_code != 200:
        return None, LogoResult()
    try:
        payload = resp.json()
    except Exception:
        return None, LogoResult()
    if not isinstance(payload, dict):
        return None, LogoResult()

    raw_name = payload.get("name")
    org_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    raw_logo = payload.get("logo")
    logo = extract_company_logo_for_provider(
        "workable",
        workable_account_logo=(str(raw_logo).strip() if isinstance(raw_logo, str) and raw_logo.strip() else None),
        page_url=f"https://apply.workable.com/{encoded_slug}",
        company_name=org_name,
    )
    return org_name, logo


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
                WHERE job_id = ? AND ats_provider = 'workable' AND status = 'active'
                """,
                (now, job_id),
            )
            closed += max(0, cur.rowcount or 0)
        if closed == 0 and url:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE (source_url = ? OR apply_url = ?) AND ats_provider = 'workable' AND status = 'active'
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


def _promote_workable_board_if_needed(
    registry: CompanyBoardRegistry,
    slug: str,
) -> int:
    """Ensure existing Workable board row uses supported capability and canonical board URL."""
    canonical_board_url = build_canonical_board_url("workable", slug)
    with registry._get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE company_boards
            SET monitoring_capability = 'supported',
                board_url = COALESCE(NULLIF(board_url, ''), ?)
            WHERE ats_provider = 'workable'
              AND LOWER(board_token) = ?
              AND monitoring_capability != 'supported'
            """,
            (canonical_board_url, slug.lower()),
        )
        promoted = max(0, cur.rowcount or 0)
        if promoted > 0:
            conn.commit()
    return promoted


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


async def repair_workable_cache(
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    force: bool = False,
    dry_run: bool = False,
) -> WorkableRepairReport:
    """
    Re-extract degraded Workable rows in `url_cache`, promote/reconcile `company_boards`
    identities, and sync active Workable `monitored_jobs`.

    Guarantees 0 Serper credits used, restartability via `workable_repair_state`,
    preservation of valid historical cache entries on 404/transient errors,
    synthetic record skipping, conservative alias re-keying, and non-mutating
    simulation when `dry_run=True`.
    """
    target_cache = cache or _default_cache_store
    target_registry = registry or _default_registry
    report = WorkableRepairReport(dry_run=dry_run)

    completed_urls = set() if force else _load_completed_urls(target_cache)

    with target_cache._get_connection() as conn:
        url_rows = conn.execute(
            """
            SELECT url, listing_json FROM url_cache
            WHERE LOWER(url) LIKE '%workable.com%'
               OR LOWER(listing_json) LIKE '%"workable"%'
            ORDER BY created_at ASC
            """
        ).fetchall()

    grouped_rows: dict[str, list[tuple[str, str, ParsedATSUrl, JobListing | None]]] = {}
    raw_slug_by_lower: dict[str, str] = {}
    genuine_total_urls = 0

    for url, listing_json in url_rows:
        existing_listing: JobListing | None = None
        if listing_json:
            try:
                existing_listing = JobListing.model_validate_json(listing_json)
            except Exception:
                existing_listing = None

        parsed = parse_ats_url(url)
        is_workable_row = (
            (parsed is not None and parsed.ats == "workable")
            or "workable.com" in url.lower()
            or (
                existing_listing is not None
                and (existing_listing.provider == "workable" or existing_listing.ats_source == "workable")
            )
        )
        if not is_workable_row:
            continue

        if _is_synthetic_workable_record(
            url,
            parsed.company_slug if parsed else (existing_listing.company_slug if existing_listing else None),
            existing_listing,
        ):
            report.skipped_synthetic += 1
            continue

        if parsed is None or parsed.ats != "workable" or not parsed.company_slug or not parsed.job_id:
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
                    ats="workable",
                    company_slug=existing_listing.company_slug,
                    job_id=clean_jid,
                    raw_url=url,
                )
            else:
                genuine_total_urls += 1
                if not force and url in completed_urls:
                    report.skipped_already_repaired += 1
                    continue
                report.unparsed_urls += 1
                if not dry_run:
                    _record_repair_state(target_cache, url, "unparsed", "Not a single Workable job posting URL")
                continue

        norm_url = normalize_job_url(url, "workable") or url
        genuine_total_urls += 1
        if not force and (url in completed_urls or (norm_url == url and norm_url in completed_urls)):
            report.skipped_already_repaired += 1
            continue

        slug_key = parsed.company_slug.lower()
        raw_slug_by_lower.setdefault(slug_key, parsed.company_slug)
        grouped_rows.setdefault(slug_key, []).append((url, norm_url, parsed, existing_listing))

    report.total_urls = genuine_total_urls

    # Collect active monitored_jobs & Workable board rows
    with target_registry._get_connection() as conn:
        monitored_rows = conn.execute(
            """
            SELECT job_id, company_slug, source_url, canonical_json
            FROM monitored_jobs
            WHERE ats_provider = 'workable' AND status = 'active'
            """
        ).fetchall()
        board_rows = conn.execute(
            """
            SELECT board_token, company_name, company_logo_url, company_logo_verified,
                   company_logo_checked_at, monitoring_capability
            FROM company_boards
            WHERE ats_provider = 'workable'
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
        if _is_synthetic_workable_record(source_url or "", slug_norm, existing_mon):
            report.skipped_synthetic += 1
            continue
        if not force and f"monitored:{canonical_id}" in completed_urls:
            continue
        raw_slug_by_lower.setdefault(slug_norm, (slug or "").strip() or slug_norm)
        monitored_by_slug.setdefault(slug_norm, []).append(
            (str(canonical_id), slug_norm, source_url, existing_mon)
        )

    board_slugs_to_reconcile: set[str] = set()
    for board_token, _b_name, _b_logo_url, _b_logo_verified, b_checked_at, b_cap in board_rows:
        slug_norm = (board_token or "").strip().lower()
        if not slug_norm or _is_synthetic_slug(slug_norm):
            continue
        raw_slug_by_lower.setdefault(slug_norm, slug_norm)
        if (
            slug_norm in grouped_rows
            or slug_norm in monitored_by_slug
            or force
            or (b_checked_at is None)
            or (b_cap != "supported")
        ):
            board_slugs_to_reconcile.add(slug_norm)

    all_slugs = sorted(set(grouped_rows.keys()) | set(monitored_by_slug.keys()) | board_slugs_to_reconcile)
    report.unique_slugs = len(grouped_rows)

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15.0)
    sem = asyncio.Semaphore(max(1, concurrency))
    workable_client = WorkableClient()

    async def _process_slug(slug_key: str) -> None:
        async with sem:
            fetch_slug = raw_slug_by_lower.get(slug_key, slug_key)
            board_name: str | None = None
            board_logo = LogoResult()

            if not dry_run and slug_key in board_slugs_to_reconcile:
                report.boards_promoted += _promote_workable_board_if_needed(target_registry, fetch_slug)

            try:
                if dry_run:
                    board_name, board_logo = await _fetch_board_identity_readonly(fetch_slug, http_client)
                else:
                    board_name, board_logo = await enrich_workable_board_identity(
                        fetch_slug,
                        http_client,
                        registry=target_registry,
                    )
                if board_logo.verified and board_logo.url:
                    report.boards_identity_enriched += 1
            except Exception as exc:
                logger.debug(f"[workable-repair] Identity enrich skipped for {slug_key}: {exc}")

            if slug_key in board_slugs_to_reconcile:
                report.boards_reconciled += 1

            slug_url_rows = grouped_rows.get(slug_key, [])
            if not slug_url_rows:
                return

            # Sort canonical rows before unnormalized aliases so canonical rows coalesce cleanly
            ordered_rows = sorted(slug_url_rows, key=lambda row: (0 if row[0] == row[1] else 1, row[0]))
            processed_norms: dict[str, JobListing] = {}

            for url, norm_url, parsed, existing_listing in ordered_rows:
                if norm_url in processed_norms:
                    already_repaired = processed_norms[norm_url]
                    if dry_run:
                        if norm_url != url:
                            report.canonicalized_urls += 1
                        continue
                    merged = (
                        CacheStore._merge_preserving_completeness(
                            already_repaired,
                            existing_listing,
                            preserve_omitted_optional_fields=False,
                        )
                        if existing_listing is not None
                        else already_repaired
                    )
                    canonicalized = _write_canonical_url_cache(
                        target_cache,
                        original_url=url,
                        canonical_url=norm_url,
                        listing=merged,
                        ttl_hours=ttl_hours,
                    )
                    if canonicalized:
                        report.canonicalized_urls += 1
                        _record_repair_state(target_cache, url, "repaired", "v2_api_canonicalized_alias")
                    _record_repair_state(target_cache, norm_url, "repaired", "v2_api")
                    processed_norms[norm_url] = merged
                    continue

                res = await workable_client.fetch_raw_result(parsed, http_client)
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
                    repaired.provider = "workable"
                    repaired.ats_source = "workable"
                    repaired.data_source = "api"
                    if board_logo.verified and board_logo.url and not repaired.company_logo_url:
                        repaired.company_logo_url = board_logo.url
                        repaired.company_logo_source = board_logo.source
                        repaired.company_logo_verified = True

                    if dry_run:
                        report.repaired_from_v2_api += 1
                        if norm_url != url:
                            report.canonicalized_urls += 1
                        processed_norms[norm_url] = repaired
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
                    report.repaired_from_v2_api += 1
                    detail = "v2_api_canonicalized" if canonicalized else "v2_api"
                    _record_repair_state(target_cache, url, "repaired", detail)
                    if canonicalized:
                        _record_repair_state(target_cache, norm_url, "repaired", "v2_api")
                    processed_norms[norm_url] = repaired
                elif res.outcome == ExtractionOutcome.NOT_FOUND:
                    report.expired_or_unavailable += 1
                    if dry_run:
                        continue
                    canonical_id = (
                        existing_listing.id
                        if existing_listing
                        else f"workable:{parsed.company_slug.lower()}:{parsed.job_id}"
                    )
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

    try:
        tasks = [_process_slug(s) for s in all_slugs]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        if own_client:
            await http_client.aclose()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair degraded Workable cache rows without Serper spend.")
    parser.add_argument("--force", action="store_true", help="Re-process URLs even if marked completed in state table.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate repair without writing to SQLite.")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent company slugs.")
    args = parser.parse_args()

    logger.info(f"[workable-repair] Starting Workable cache repair (dry_run={args.dry_run}, force={args.force})...")
    rep = asyncio.run(repair_workable_cache(force=args.force, dry_run=args.dry_run, concurrency=args.concurrency))
    logger.info(f"[workable-repair] Completed: {json.dumps(asdict(rep), indent=2)}")


if __name__ == "__main__":
    main()

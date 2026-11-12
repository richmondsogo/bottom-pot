"""
Bounded, zero-Serper-credit, restartable Greenhouse cache & monitored_jobs repair utility.

Re-extracts degraded pre-Step-37 Greenhouse records in `url_cache` and `monitored_jobs`
using existing Greenhouse JSON/board APIs while:
- Spending 0 Serper credits.
- Batching active postings per company slug (`GET /v1/boards/{slug}/jobs?content=true&pay_transparency=true`).
- Respecting active vs 404/410 expired vs transient error outcomes.
- Preserving richer existing data via completeness-aware merging.
- Tracking per-URL progress in SQLite (`greenhouse_repair_state`) so interrupted runs
  safely resume without duplicating work.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json
import sqlite3
import time

import httpx
from loguru import logger

from src.project_files.ats_api_client import (
    GreenhouseClient,
    enrich_greenhouse_board_identity,
    greenhouse_payload_to_raw,
)
from src.project_files.ats_url_parser import ParsedATSUrl, parse_ats_url
from src.project_files.cache_store import CacheStore, cache_store as _default_cache_store
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    company_board_registry as _default_registry,
)
from src.project_files.extraction_outcome import ExtractionOutcome
from src.project_files.field_normalizer import humanize_slug
from src.project_files.http_headers import browser_headers
from src.project_files.job_extraction_service import JobExtractionService
from src.project_files.logo_extractor import LogoResult
from src.project_files.models import JobListing
from src.project_files.url_normalizer import normalize_job_url

REPAIR_VERSION = "v37"


@dataclass
class GreenhouseRepairReport:
    total_urls: int = 0
    unique_slugs: int = 0
    skipped_already_repaired: int = 0
    repaired_from_board_api: int = 0
    repaired_from_posting_api: int = 0
    expired_or_unavailable: int = 0
    transient_errors: int = 0
    unparsed_urls: int = 0
    boards_identity_enriched: int = 0
    monitored_jobs_updated: int = 0
    monitored_jobs_closed: int = 0
    serper_calls_made: int = 0


def _ensure_repair_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS greenhouse_repair_state (
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
            INSERT INTO greenhouse_repair_state (url, repair_version, status, repaired_at, detail)
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
            SELECT url FROM greenhouse_repair_state
            WHERE repair_version = ? AND status IN ('repaired', 'unavailable_404')
            """,
            (REPAIR_VERSION,),
        ).fetchall()
    return {str(row[0]) for row in rows if row and row[0]}


def _listing_from_greenhouse_item(
    item: dict,
    *,
    company_slug: str,
    source_url: str | None,
    board_name: str | None,
    logo: LogoResult,
) -> JobListing | None:
    raw = greenhouse_payload_to_raw(
        item,
        company_slug=company_slug,
        source_url=source_url,
        query_used=company_slug,
        default_company_name=board_name or humanize_slug(company_slug),
        is_board_monitor=False,
    )
    if raw is None or not raw.raw_title or not raw.source_url:
        return None
    if logo.url and logo.verified and not raw.raw_fields.get("company_logo_url"):
        raw.raw_fields["company_logo_url"] = logo.url
        raw.raw_fields["company_logo_source"] = logo.source
        raw.raw_fields["company_logo_verified"] = True
    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = "greenhouse"
    listing.ats_source = "greenhouse"
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
                WHERE job_id = ? AND ats_provider = 'greenhouse' AND status = 'active'
                """,
                (now, job_id),
            )
            closed += max(0, cur.rowcount or 0)
        if closed == 0 and url:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE (source_url = ? OR apply_url = ?) AND ats_provider = 'greenhouse' AND status = 'active'
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


async def _fetch_board_jobs_map(
    slug: str,
    client: httpx.AsyncClient,
) -> tuple[int | None, dict[str, dict]]:
    board_api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true"
    try:
        resp = await client.get(
            board_api_url,
            headers=browser_headers(board_api_url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            timeout=12.0,
        )
    except Exception as exc:
        logger.debug(f"[greenhouse-repair] Board list fetch failed for {slug}: {exc}")
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
            items_by_id[str(item["id"]).strip()] = item
    return 200, items_by_id


async def repair_greenhouse_cache(
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    force: bool = False,
) -> GreenhouseRepairReport:
    """
    Re-extract degraded Greenhouse rows in `url_cache` and active Greenhouse `monitored_jobs`.

    Guarantees 0 Serper credits used, restartability via `greenhouse_repair_state`,
    preservation of valid historical cache entries on 404/transient errors, and
    completeness-aware merging.
    """
    target_cache = cache or _default_cache_store
    target_registry = registry or _default_registry
    report = GreenhouseRepairReport()

    completed_urls = set() if force else _load_completed_urls(target_cache)

    with target_cache._get_connection() as conn:
        _ensure_repair_table(conn)
        cache_rows = conn.execute(
            "SELECT url, listing_json FROM url_cache WHERE url LIKE '%greenhouse.io/%' ORDER BY created_at ASC"
        ).fetchall()

    report.total_urls = len(cache_rows)
    grouped_rows: dict[str, list[tuple[str, ParsedATSUrl, JobListing | None]]] = {}

    for url, raw_json in cache_rows:
        if not force and url in completed_urls:
            report.skipped_already_repaired += 1
            continue

        existing_listing: JobListing | None = None
        if raw_json:
            try:
                existing_listing = JobListing.model_validate_json(raw_json)
            except Exception:
                existing_listing = None

        parsed = parse_ats_url(url)
        if parsed is None or parsed.ats != "greenhouse" or not parsed.company_slug or not parsed.job_id:
            if existing_listing and existing_listing.company_slug and existing_listing.provider_job_id:
                clean_jid = existing_listing.provider_job_id
                if ":" in clean_jid:
                    clean_jid = clean_jid.split(":")[-1]
                parsed = ParsedATSUrl(
                    ats="greenhouse",
                    company_slug=existing_listing.company_slug,
                    job_id=clean_jid,
                    raw_url=url,
                )
            else:
                report.unparsed_urls += 1
                _record_repair_state(target_cache, url, "unparsed", "Not a single Greenhouse job posting URL")
                continue

        grouped_rows.setdefault(parsed.company_slug.lower(), []).append((url, parsed, existing_listing))

    # Also collect active monitored_jobs slugs so monitored rows without url_cache stay updated
    with target_registry._get_connection() as conn:
        monitored_rows = conn.execute(
            """
            SELECT job_id, company_slug, source_url, canonical_json
            FROM monitored_jobs
            WHERE ats_provider = 'greenhouse' AND status = 'active'
            """
        ).fetchall()

    monitored_by_slug: dict[str, list[tuple[str, str, str | None, JobListing | None]]] = {}
    for canonical_id, slug, source_url, canonical_json in monitored_rows:
        if not force and f"monitored:{canonical_id}" in completed_urls:
            continue
        slug_norm = (slug or "").strip().lower()
        if not slug_norm:
            continue
        existing_mon: JobListing | None = None
        if canonical_json:
            try:
                existing_mon = JobListing.model_validate_json(canonical_json)
            except Exception:
                existing_mon = None
        monitored_by_slug.setdefault(slug_norm, []).append(
            (str(canonical_id), slug_norm, source_url, existing_mon)
        )

    all_slugs = sorted(set(grouped_rows.keys()) | set(monitored_by_slug.keys()))
    report.unique_slugs = len(grouped_rows)

    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15.0)
    sem = asyncio.Semaphore(max(1, concurrency))
    greenhouse_client = GreenhouseClient()

    async def _process_slug(slug: str) -> None:
        async with sem:
            board_name: str | None = None
            board_logo = LogoResult()
            try:
                board_name, board_logo = await enrich_greenhouse_board_identity(
                    slug,
                    http_client,
                    registry=target_registry,
                )
                if board_logo.verified and board_logo.url:
                    report.boards_identity_enriched += 1
            except Exception as exc:
                logger.debug(f"[greenhouse-repair] Identity enrich skipped for {slug}: {exc}")

            status_code, items_by_id = await _fetch_board_jobs_map(slug, http_client)
            synced_job_ids: set[str] = set()

            # 1) Repair url_cache rows for this slug
            for url, parsed, existing_listing in grouped_rows.get(slug, []):
                matched_item = items_by_id.get(parsed.job_id)
                if matched_item is not None:
                    repaired = _listing_from_greenhouse_item(
                        matched_item,
                        company_slug=parsed.company_slug,
                        source_url=url,
                        board_name=board_name,
                        logo=board_logo,
                    )
                    if repaired is not None:
                        if existing_listing is not None:
                            repaired = CacheStore._merge_preserving_completeness(
                                repaired,
                                existing_listing,
                                preserve_omitted_optional_fields=False,
                            )
                        target_cache.set_url_cache(url, repaired, ttl_hours=ttl_hours)
                        synced_count = _sync_monitored_job_if_present(target_registry, repaired)
                        report.monitored_jobs_updated += synced_count
                        if synced_count:
                            _record_repair_state(target_cache, f"monitored:{repaired.id}", "repaired", "monitored_job")
                        synced_job_ids.add(repaired.id)
                        report.repaired_from_board_api += 1
                        _record_repair_state(target_cache, url, "repaired", "board_api")
                        norm_written = normalize_job_url(url, "greenhouse")
                        if norm_written and norm_written != url:
                            _record_repair_state(target_cache, norm_written, "repaired", "board_api_normalized")
                        continue

                # Fall back to single-posting Greenhouse API for unlisted or unavailable/404 postings
                res = await greenhouse_client.fetch_raw_result(parsed, http_client)
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
                    repaired.provider = "greenhouse"
                    repaired.ats_source = "greenhouse"
                    repaired.data_source = "api"
                    if board_logo.verified and board_logo.url and not repaired.company_logo_url:
                        repaired.company_logo_url = board_logo.url
                        repaired.company_logo_source = board_logo.source
                        repaired.company_logo_verified = True

                    if existing_listing is not None:
                        repaired = CacheStore._merge_preserving_completeness(
                            repaired,
                            existing_listing,
                            preserve_omitted_optional_fields=False,
                        )
                    target_cache.set_url_cache(url, repaired, ttl_hours=ttl_hours)
                    synced_count = _sync_monitored_job_if_present(target_registry, repaired)
                    report.monitored_jobs_updated += synced_count
                    if synced_count:
                        _record_repair_state(target_cache, f"monitored:{repaired.id}", "repaired", "monitored_job")
                    synced_job_ids.add(repaired.id)
                    report.repaired_from_posting_api += 1
                    _record_repair_state(target_cache, url, "repaired", "posting_api")
                    norm_written = normalize_job_url(url, "greenhouse")
                    if norm_written and norm_written != url:
                        _record_repair_state(target_cache, norm_written, "repaired", "posting_api_normalized")
                elif res.outcome == ExtractionOutcome.NOT_FOUND:
                    canonical_id = existing_listing.id if existing_listing else f"greenhouse:{parsed.company_slug.lower()}:{parsed.job_id}"
                    closed = _mark_monitored_job_closed_if_present(
                        target_registry,
                        job_id=canonical_id,
                        url=url,
                    )
                    report.monitored_jobs_closed += closed
                    report.expired_or_unavailable += 1
                    _record_repair_state(
                        target_cache,
                        url,
                        "unavailable_404",
                        f"HTTP {res.status_code or 404}",
                    )
                else:
                    report.transient_errors += 1

            # 2) Sync active monitored_jobs for this slug if not already refreshed via url_cache
            if status_code == 200 and items_by_id:
                for canonical_id, m_slug, m_source_url, existing_mon in monitored_by_slug.get(slug, []):
                    if canonical_id in synced_job_ids:
                        continue
                    provider_job_id = canonical_id.split(":")[-1] if ":" in canonical_id else ""
                    item = items_by_id.get(provider_job_id)
                    if item is not None:
                        repaired = _listing_from_greenhouse_item(
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
    parser = argparse.ArgumentParser(description="Repair degraded Greenhouse cache rows without Serper spend.")
    parser.add_argument("--force", action="store_true", help="Re-process URLs even if marked completed in state table.")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent company slugs.")
    args = parser.parse_args()

    logger.info("[greenhouse-repair] Starting Greenhouse cache repair...")
    rep = asyncio.run(repair_greenhouse_cache(force=args.force, concurrency=args.concurrency))
    logger.info(f"[greenhouse-repair] Completed: {json.dumps(asdict(rep), indent=2)}")


if __name__ == "__main__":
    main()

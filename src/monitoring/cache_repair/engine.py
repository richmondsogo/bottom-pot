"""
Generic bounded, idempotent, dry-run-by-default ATS cache & monitored-job repair engine.

Unifies SQLite checkpointing, SSRF-safe HTTP client creation, synthetic record
exclusion, completeness-preserving URL cache canonicalization, monitored-job sync,
bounded URL/slug budgets, and CLI execution across provider repair strategies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable, Sequence
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.ats.ats_url_parser import ParsedATSUrl, parse_ats_url
from src.core.clock import epoch_now
from src.core.exceptions import SafetyError
from src.core.models import JobListing
from src.extraction.canonical_job_adapter import CanonicalJobAdapter
from src.extraction.extraction_outcome import ExtractionOutcome
from src.extraction.field_normalizer import humanize_slug
from src.extraction.job_extraction_service import JobExtractionService, RawJobPosting
from src.extraction.logo_extractor import LogoResult
from src.extraction.url_normalizer import normalize_job_url
from src.safety.db_safety import cli_operational_runtime
from src.safety.url_safety import create_ssrf_safe_async_client
from src.storage.cache_store import CacheStore
from src.storage.cache_store import cache_store as _default_cache_store
from src.storage.company_board_registry import (
    CompanyBoardRegistry,
)
from src.storage.company_board_registry import (
    company_board_registry as _default_registry,
)

ALLOWED_REPAIR_STATE_TABLES: frozenset[str] = frozenset({
    "lever_repair_state",
    "greenhouse_repair_state",
    "ashby_repair_state",
    "workable_repair_state",
})
SYNTHETIC_DOMAINS: frozenset[str] = frozenset({
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "test.local",
})
SYNTHETIC_SLUGS: frozenset[str] = frozenset({
    "testslug",
    "testcompany",
    "samplecompany",
    "examplecompany",
    "dummy",
    "fake",
})
SYNTHETIC_SLUG_RE = re.compile(
    r"^(company\d+|testslug\d*|testcompany\d*|samplecompany\d*)$",
    re.IGNORECASE,
)


@dataclass
class CacheRepairReport:
    """Unified execution summary produced by ``run_cache_repair``."""

    dry_run: bool = True
    total_urls: int = 0
    unique_slugs: int = 0
    skipped_synthetic: int = 0
    skipped_already_repaired: int = 0
    repaired_from_board_api: int = 0
    repaired_from_posting_api: int = 0
    canonicalized_urls: int = 0
    boards_reconciled: int = 0
    boards_promoted: int = 0
    boards_identity_enriched: int = 0
    monitored_jobs_updated: int = 0
    monitored_jobs_closed: int = 0
    expired_or_unavailable: int = 0
    transient_errors: int = 0
    unparsed_urls: int = 0
    serper_calls_used: int = 0


@dataclass(frozen=True)
class SinglePostingResult:
    """Normalized outcome from a single-posting ATS fallback API lookup."""

    outcome: ExtractionOutcome
    raw: RawJobPosting | None = None
    status_code: int | None = None


@dataclass(frozen=True)
class CacheRepairStrategy:
    """Declarative provider strategy consumed by ``run_cache_repair``."""

    provider: str
    state_table: str
    repair_version: str
    url_cache_query: str
    unparsed_detail: str
    terminal_statuses: tuple[str, ...] = ("repaired", "unavailable_404")
    total_urls_mode: str = "genuine"
    check_completed_at_top: bool = False
    check_norm_url_completed: bool = False
    require_parsed_none_for_fallback: bool = True
    strip_colon_from_fallback_id: bool = True
    lowercase_fallback_id: bool = False
    canonicalize_aliases: bool = False
    coalesce_aliases_within_slug: bool = False
    record_normalized_alias_state: bool = False
    supports_board_feed: bool = True
    board_item_id_lowercase: bool = False
    sync_monitored_from_board_feed: bool = True
    reconcile_company_boards: bool = False
    check_capability_supported: bool = False
    monitored_board_state_detail: str = "monitored_job"
    state_detail_prefix_board: str = "board_api"
    state_detail_prefix_posting: str = "posting_api"
    is_matching_row: Callable[[str, ParsedATSUrl | None, JobListing | None], bool] | None = None
    is_synthetic: Callable[[str, str | None, JobListing | None], bool] | None = None
    is_synthetic_slug: Callable[[str | None], bool] | None = None
    enrich_identity: Callable[
        [str, httpx.AsyncClient, CompanyBoardRegistry, bool],
        Awaitable[tuple[str | None, LogoResult]],
    ] | None = None
    promote_board: Callable[[CompanyBoardRegistry, str], int] | None = None
    fetch_board_items_map: Callable[
        [str, httpx.AsyncClient],
        Awaitable[tuple[int | None, dict[str, dict]]],
    ] | None = None
    listing_from_board_item: Callable[
        [dict, str, str | None, str | None, LogoResult],
        JobListing | None,
    ] | None = None
    fetch_single_posting: Callable[
        [ParsedATSUrl, httpx.AsyncClient],
        Awaitable[SinglePostingResult],
    ] | None = None


def parse_cached_listing(raw_json: str | None) -> JobListing | None:
    """Parse a serialized cached ``JobListing`` row, returning None on corrupt JSON."""
    if not raw_json:
        return None
    try:
        return JobListing.model_validate_json(raw_json)
    except (ValueError, TypeError):
        return None


def is_synthetic_slug(slug: str | None) -> bool:
    """Return True if *slug* matches known synthetic or test placeholder tokens."""
    s = (slug or "").strip().lower()
    if not s:
        return False
    if s in SYNTHETIC_SLUGS or SYNTHETIC_SLUG_RE.fullmatch(s):
        return True
    return s.startswith(("test-", "dummy-", "fake-", "synthetic-"))


def is_synthetic_record(
    url: str,
    slug: str | None,
    existing: JobListing | None = None,
) -> bool:
    """Return True when a URL, slug, or cached listing belongs to synthetic test fixtures."""
    parsed_netloc = urlparse(url).netloc.lower()
    if parsed_netloc in SYNTHETIC_DOMAINS or parsed_netloc.endswith(".example.com"):
        return True
    if is_synthetic_slug(slug):
        return True
    if existing is not None:
        if is_synthetic_slug(existing.company_slug):
            return True
        if existing.source_url:
            src_netloc = urlparse(existing.source_url).netloc.lower()
            if src_netloc in SYNTHETIC_DOMAINS or src_netloc.endswith(".example.com"):
                return True
    return False


def build_listing_from_raw(
    provider: str,
    raw: RawJobPosting | None,
    *,
    board_name: str | None,
    company_slug: str,
    logo: LogoResult,
) -> JobListing | None:
    """Normalize a ``RawJobPosting`` into a canonical ``JobListing`` preserving verified logo/company."""
    if raw is None or not raw.raw_title or not raw.source_url:
        return None
    if logo.url and logo.verified and not raw.raw_fields.get("company_logo_url"):
        raw.raw_fields["company_logo_url"] = logo.url
        raw.raw_fields["company_logo_source"] = logo.source
        raw.raw_fields["company_logo_verified"] = True
    if board_name and (
        not raw.raw_company
        or raw.raw_company == "Unknown"
        or raw.raw_company == humanize_slug(company_slug)
    ):
        raw.raw_company = board_name

    canonical = JobExtractionService.extract(raw)
    listing = CanonicalJobAdapter.to_listing(canonical)
    listing.provider = provider
    listing.ats_source = provider
    listing.data_source = "api"
    if logo.verified and logo.url and not listing.company_logo_url:
        listing.company_logo_url = logo.url
        listing.company_logo_source = logo.source
        listing.company_logo_verified = True
    return listing


def _validated_state_table(table_name: str) -> str:
    if table_name not in ALLOWED_REPAIR_STATE_TABLES:
        raise ValueError(f"Unsupported repair state table: {table_name!r}")
    return table_name


def ensure_repair_table(conn: sqlite3.Connection, state_table: str) -> None:
    tbl = _validated_state_table(state_table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            url TEXT PRIMARY KEY,
            repair_version TEXT NOT NULL,
            status TEXT NOT NULL,
            repaired_at REAL NOT NULL,
            detail TEXT
        )
        """
    )


def record_repair_state(
    cache: CacheStore,
    state_table: str,
    repair_version: str,
    url: str,
    status: str,
    detail: str | None = None,
) -> None:
    tbl = _validated_state_table(state_table)
    with cache._get_connection() as conn:
        ensure_repair_table(conn, tbl)
        conn.execute(
            f"""
            INSERT INTO {tbl} (url, repair_version, status, repaired_at, detail)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                repair_version=excluded.repair_version,
                status=excluded.status,
                repaired_at=excluded.repaired_at,
                detail=excluded.detail
            """,
            (url, repair_version, status, epoch_now(), detail),
        )
        conn.commit()


def load_completed_urls(
    cache: CacheStore,
    state_table: str,
    repair_version: str,
    terminal_statuses: Sequence[str],
    *,
    dry_run: bool,
) -> set[str]:
    tbl = _validated_state_table(state_table)
    placeholders = ",".join("?" for _ in terminal_statuses)
    with cache._get_connection() as conn:
        has_table = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (tbl,),
            ).fetchone()
        )
        if not has_table:
            if not dry_run:
                ensure_repair_table(conn, tbl)
            return set()
        rows = conn.execute(
            f"""
            SELECT url FROM {tbl}
            WHERE repair_version = ? AND status IN ({placeholders})
            """,
            (repair_version, *terminal_statuses),
        ).fetchall()
    return {str(row[0]) for row in rows if row and row[0]}


def mark_monitored_job_closed_if_present(
    registry: CompanyBoardRegistry,
    *,
    provider: str,
    job_id: str | None,
    url: str,
) -> int:
    now = epoch_now()
    closed = 0
    with registry._get_connection() as conn:
        if job_id:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE job_id = ? AND ats_provider = ? AND status = 'active'
                """,
                (now, job_id, provider),
            )
            closed += max(0, cur.rowcount or 0)
        if closed == 0 and url:
            cur = conn.execute(
                """
                UPDATE monitored_jobs
                SET status = 'closed', last_checked_at = ?
                WHERE (source_url = ? OR apply_url = ?) AND ats_provider = ? AND status = 'active'
                """,
                (now, url, url, provider),
            )
            closed += max(0, cur.rowcount or 0)
        if closed > 0:
            conn.commit()
    return closed


def sync_monitored_job_if_present(
    registry: CompanyBoardRegistry,
    listing: JobListing,
) -> int:
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


def write_canonical_url_cache(
    cache: CacheStore,
    *,
    original_url: str,
    canonical_url: str,
    listing: JobListing,
    ttl_hours: float | None,
) -> bool:
    """Persist *listing* at *canonical_url* and remove any superseded unnormalized alias row."""
    existing_canonical: JobListing | None = None
    if canonical_url != original_url:
        with cache._get_connection() as conn:
            row = conn.execute(
                "SELECT listing_json FROM url_cache WHERE url = ?",
                (canonical_url,),
            ).fetchone()
        if row and row[0]:
            existing_canonical = parse_cached_listing(row[0])

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


def _persist_repaired_url(
    strategy: CacheRepairStrategy,
    cache: CacheStore,
    registry: CompanyBoardRegistry,
    report: CacheRepairReport,
    *,
    url: str,
    norm_url: str,
    repaired: JobListing,
    existing_listing: JobListing | None,
    ttl_hours: float | None,
    detail_prefix: str,
    synced_job_ids: set[str],
) -> JobListing:
    if existing_listing is not None:
        repaired = CacheStore._merge_preserving_completeness(
            repaired,
            existing_listing,
            preserve_omitted_optional_fields=False,
        )

    if strategy.canonicalize_aliases:
        canonicalized = write_canonical_url_cache(
            cache,
            original_url=url,
            canonical_url=norm_url,
            listing=repaired,
            ttl_hours=ttl_hours,
        )
        if canonicalized:
            report.canonicalized_urls += 1
    else:
        canonicalized = False
        cache.set_url_cache(url, repaired, ttl_hours=ttl_hours)

    synced_count = sync_monitored_job_if_present(registry, repaired)
    report.monitored_jobs_updated += synced_count
    if synced_count:
        record_repair_state(
            cache,
            strategy.state_table,
            strategy.repair_version,
            f"monitored:{repaired.id}",
            "repaired",
            "monitored_job",
        )
    synced_job_ids.add(repaired.id)

    if strategy.canonicalize_aliases:
        detail = f"{detail_prefix}_canonicalized" if canonicalized else detail_prefix
        record_repair_state(
            cache, strategy.state_table, strategy.repair_version, url, "repaired", detail
        )
        if canonicalized:
            record_repair_state(
                cache, strategy.state_table, strategy.repair_version, norm_url, "repaired", detail_prefix
            )
    else:
        record_repair_state(
            cache, strategy.state_table, strategy.repair_version, url, "repaired", detail_prefix
        )
        if strategy.record_normalized_alias_state:
            norm_written = normalize_job_url(url, strategy.provider)
            if norm_written and norm_written != url:
                record_repair_state(
                    cache,
                    strategy.state_table,
                    strategy.repair_version,
                    norm_written,
                    "repaired",
                    f"{detail_prefix}_normalized",
                )
    return repaired


async def run_cache_repair(
    strategy: CacheRepairStrategy,
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    max_urls: int | None = None,
    max_slugs: int | None = None,
    force: bool = False,
    dry_run: bool = True,
) -> CacheRepairReport:
    """
    Execute bounded, idempotent, zero-Serper cache & monitored-job repair for *strategy*.

    Defaults to ``dry_run=True`` so callers must explicitly pass ``dry_run=False`` to
    persist mutations to SQLite.
    """
    target_cache = cache or _default_cache_store
    target_registry = registry or _default_registry
    report = CacheRepairReport(dry_run=dry_run)

    completed_urls = (
        set()
        if force
        else load_completed_urls(
            target_cache,
            strategy.state_table,
            strategy.repair_version,
            strategy.terminal_statuses,
            dry_run=dry_run,
        )
    )

    with target_cache._get_connection() as conn:
        if not dry_run:
            ensure_repair_table(conn, strategy.state_table)
        cache_rows = conn.execute(strategy.url_cache_query).fetchall()

    grouped_rows: dict[str, list[tuple[str, str, ParsedATSUrl, JobListing | None]]] = {}
    raw_slug_by_lower: dict[str, str] = {}
    genuine_total_urls = 0
    queued_urls = 0

    for url, raw_json in cache_rows:
        if strategy.check_completed_at_top and not force and url in completed_urls:
            report.skipped_already_repaired += 1
            continue

        parsed = parse_ats_url(url)
        existing_listing = parse_cached_listing(raw_json)
        if strategy.is_matching_row is not None and not strategy.is_matching_row(url, parsed, existing_listing):
            continue

        candidate_slug = (
            parsed.company_slug
            if parsed is not None
            else (existing_listing.company_slug if existing_listing else None)
        )
        if strategy.is_synthetic is not None and strategy.is_synthetic(url, candidate_slug, existing_listing):
            report.skipped_synthetic += 1
            continue

        if (
            parsed is None
            or parsed.ats != strategy.provider
            or not parsed.company_slug
            or not parsed.job_id
        ):
            can_fallback = (
                existing_listing is not None
                and bool(existing_listing.company_slug)
                and bool(existing_listing.provider_job_id)
                and (not strategy.require_parsed_none_for_fallback or parsed is None)
            )
            if can_fallback and existing_listing is not None:
                clean_jid = existing_listing.provider_job_id or ""
                if strategy.strip_colon_from_fallback_id and ":" in clean_jid:
                    clean_jid = clean_jid.split(":")[-1]
                if strategy.lowercase_fallback_id:
                    clean_jid = clean_jid.lower()
                parsed = ParsedATSUrl(
                    ats=strategy.provider,
                    company_slug=existing_listing.company_slug or "",
                    job_id=clean_jid,
                    raw_url=url,
                )
            else:
                genuine_total_urls += 1
                if not strategy.check_completed_at_top and not force and url in completed_urls:
                    report.skipped_already_repaired += 1
                    continue
                report.unparsed_urls += 1
                if not dry_run:
                    record_repair_state(
                        target_cache,
                        strategy.state_table,
                        strategy.repair_version,
                        url,
                        "unparsed",
                        strategy.unparsed_detail,
                    )
                continue

        if strategy.is_synthetic is not None and strategy.is_synthetic(
            url, parsed.company_slug, existing_listing
        ):
            report.skipped_synthetic += 1
            continue

        norm_url = normalize_job_url(url, strategy.provider) or url
        genuine_total_urls += 1
        already_done = url in completed_urls or (
            strategy.check_norm_url_completed and norm_url in completed_urls
        )
        if not strategy.check_completed_at_top and not force and already_done:
            report.skipped_already_repaired += 1
            continue

        if max_urls is not None and queued_urls >= max(0, int(max_urls)):
            continue
        queued_urls += 1

        slug_key = parsed.company_slug.lower()
        raw_slug_by_lower.setdefault(slug_key, parsed.company_slug)
        grouped_rows.setdefault(slug_key, []).append((url, norm_url, parsed, existing_listing))

    report.total_urls = (
        len(cache_rows) if strategy.total_urls_mode == "raw_rows" else genuine_total_urls
    )

    with target_registry._get_connection() as conn:
        monitored_rows = conn.execute(
            """
            SELECT job_id, company_slug, source_url, canonical_json
            FROM monitored_jobs
            WHERE ats_provider = ? AND status = 'active'
            """,
            (strategy.provider,),
        ).fetchall()
        board_rows = (
            conn.execute(
                """
                SELECT board_token, company_logo_checked_at, monitoring_capability
                FROM company_boards
                WHERE ats_provider = ?
                """,
                (strategy.provider,),
            ).fetchall()
            if strategy.reconcile_company_boards
            else []
        )

    monitored_by_slug: dict[str, list[tuple[str, str, str | None, JobListing | None]]] = {}
    for canonical_id, slug, source_url, canonical_json in monitored_rows:
        slug_norm = (slug or "").strip().lower()
        existing_mon = parse_cached_listing(canonical_json)
        if strategy.is_synthetic is not None and strategy.is_synthetic(
            source_url or "", slug_norm, existing_mon
        ):
            report.skipped_synthetic += 1
            continue
        if not slug_norm and strategy.provider == "lever":
            continue
        if not force and f"monitored:{canonical_id}" in completed_urls:
            continue
        raw_slug_by_lower.setdefault(slug_norm, (slug or "").strip() or slug_norm)
        monitored_by_slug.setdefault(slug_norm, []).append(
            (str(canonical_id), slug_norm, source_url, existing_mon)
        )

    board_slugs_to_reconcile: set[str] = set()
    for board_token, b_checked_at, b_cap in board_rows:
        slug_norm = (board_token or "").strip().lower()
        if not slug_norm:
            continue
        if strategy.is_synthetic_slug is not None and strategy.is_synthetic_slug(slug_norm):
            continue
        raw_slug_by_lower.setdefault(slug_norm, slug_norm)
        if (
            slug_norm in grouped_rows
            or slug_norm in monitored_by_slug
            or force
            or b_checked_at is None
            or (strategy.check_capability_supported and b_cap != "supported")
        ):
            board_slugs_to_reconcile.add(slug_norm)

    all_slugs = sorted(
        set(grouped_rows.keys()) | set(monitored_by_slug.keys()) | board_slugs_to_reconcile
    )
    if max_slugs is not None:
        all_slugs = all_slugs[: max(0, int(max_slugs))]
    report.unique_slugs = len(grouped_rows)

    own_client = client is None
    http_client = client or create_ssrf_safe_async_client(timeout=15.0)
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def _process_slug(slug_key: str) -> None:
        async with sem:
            fetch_slug = raw_slug_by_lower.get(slug_key, slug_key)
            if not dry_run and strategy.promote_board is not None and slug_key in board_slugs_to_reconcile:
                report.boards_promoted += strategy.promote_board(target_registry, fetch_slug)

            board_name: str | None = None
            board_logo = LogoResult()
            if strategy.enrich_identity is not None:
                try:
                    board_name, board_logo = await strategy.enrich_identity(
                        fetch_slug, http_client, target_registry, dry_run
                    )
                    if board_logo.verified and board_logo.url:
                        report.boards_identity_enriched += 1
                except (asyncio.CancelledError, SafetyError):
                    raise
                except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
                    logger.debug(f"[{strategy.provider}-repair] Identity enrich skipped for {slug_key}: {exc}")

            if slug_key in board_slugs_to_reconcile:
                report.boards_reconciled += 1

            slug_url_rows = grouped_rows.get(slug_key, [])
            slug_mon_rows = monitored_by_slug.get(slug_key, [])
            if not slug_url_rows and (not strategy.sync_monitored_from_board_feed or not slug_mon_rows):
                return

            status_code: int | None = None
            items_by_id: dict[str, dict] = {}
            if strategy.supports_board_feed and strategy.fetch_board_items_map is not None:
                status_code, items_by_id = await strategy.fetch_board_items_map(
                    fetch_slug, http_client
                )

            synced_job_ids: set[str] = set()
            ordered_rows = (
                sorted(slug_url_rows, key=lambda r: (0 if r[0] == r[1] else 1, r[0]))
                if strategy.coalesce_aliases_within_slug
                else slug_url_rows
            )
            processed_norms: dict[str, JobListing] = {}

            for url, norm_url, parsed, existing_listing in ordered_rows:
                if strategy.coalesce_aliases_within_slug and norm_url in processed_norms:
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
                    canon = write_canonical_url_cache(
                        target_cache,
                        original_url=url,
                        canonical_url=norm_url,
                        listing=merged,
                        ttl_hours=ttl_hours,
                    )
                    if canon:
                        report.canonicalized_urls += 1
                        record_repair_state(
                            target_cache,
                            strategy.state_table,
                            strategy.repair_version,
                            url,
                            "repaired",
                            f"{strategy.state_detail_prefix_posting}_canonicalized_alias",
                        )
                    record_repair_state(
                        target_cache,
                        strategy.state_table,
                        strategy.repair_version,
                        norm_url,
                        "repaired",
                        strategy.state_detail_prefix_posting,
                    )
                    processed_norms[norm_url] = merged
                    continue

                if (
                    strategy.supports_board_feed
                    and strategy.listing_from_board_item is not None
                    and items_by_id
                ):
                    lookup_id = (parsed.job_id or "").lower() if strategy.board_item_id_lowercase else (parsed.job_id or "")
                    matched_item = items_by_id.get(lookup_id)
                    if matched_item is not None:
                        target_src = norm_url if strategy.canonicalize_aliases else url
                        repaired = strategy.listing_from_board_item(
                            matched_item,
                            parsed.company_slug,
                            target_src,
                            board_name,
                            board_logo,
                        )
                        if repaired is not None:
                            if dry_run:
                                report.repaired_from_board_api += 1
                                if strategy.canonicalize_aliases and norm_url != url:
                                    report.canonicalized_urls += 1
                                continue
                            _persist_repaired_url(
                                strategy,
                                target_cache,
                                target_registry,
                                report,
                                url=url,
                                norm_url=norm_url,
                                repaired=repaired,
                                existing_listing=existing_listing,
                                ttl_hours=ttl_hours,
                                detail_prefix=strategy.state_detail_prefix_board,
                                synced_job_ids=synced_job_ids,
                            )
                            report.repaired_from_board_api += 1
                            continue

                if strategy.fetch_single_posting is None:
                    continue
                single_res = await strategy.fetch_single_posting(parsed, http_client)
                if single_res.outcome == ExtractionOutcome.SUCCESS and single_res.raw is not None:
                    repaired = build_listing_from_raw(
                        strategy.provider,
                        single_res.raw,
                        board_name=board_name,
                        company_slug=parsed.company_slug,
                        logo=board_logo,
                    )
                    if repaired is not None:
                        if dry_run:
                            report.repaired_from_posting_api += 1
                            if strategy.canonicalize_aliases and norm_url != url:
                                report.canonicalized_urls += 1
                            if strategy.coalesce_aliases_within_slug:
                                processed_norms[norm_url] = repaired
                            continue
                        repaired = _persist_repaired_url(
                            strategy,
                            target_cache,
                            target_registry,
                            report,
                            url=url,
                            norm_url=norm_url,
                            repaired=repaired,
                            existing_listing=existing_listing,
                            ttl_hours=ttl_hours,
                            detail_prefix=strategy.state_detail_prefix_posting,
                            synced_job_ids=synced_job_ids,
                        )
                        report.repaired_from_posting_api += 1
                        if strategy.coalesce_aliases_within_slug:
                            processed_norms[norm_url] = repaired
                        continue

                if single_res.outcome == ExtractionOutcome.NOT_FOUND:
                    report.expired_or_unavailable += 1
                    if dry_run:
                        continue
                    canonical_id = (
                        existing_listing.id
                        if existing_listing
                        else f"{strategy.provider}:{parsed.company_slug.lower()}:{parsed.job_id}"
                    )
                    closed = mark_monitored_job_closed_if_present(
                        target_registry,
                        provider=strategy.provider,
                        job_id=canonical_id,
                        url=norm_url if strategy.canonicalize_aliases else url,
                    )
                    report.monitored_jobs_closed += closed
                    record_repair_state(
                        target_cache,
                        strategy.state_table,
                        strategy.repair_version,
                        url,
                        "unavailable_404",
                        f"HTTP {single_res.status_code or 404}",
                    )
                else:
                    report.transient_errors += 1

            if (
                not dry_run
                and strategy.sync_monitored_from_board_feed
                and strategy.listing_from_board_item is not None
                and status_code == 200
                and items_by_id
            ):
                for canonical_id, m_slug, m_source_url, existing_mon in slug_mon_rows:
                    if canonical_id in synced_job_ids:
                        continue
                    raw_jid = canonical_id.split(":")[-1] if ":" in canonical_id else ""
                    lookup_jid = raw_jid.lower() if strategy.board_item_id_lowercase else raw_jid
                    item = items_by_id.get(lookup_jid)
                    if item is None:
                        continue
                    repaired = strategy.listing_from_board_item(
                        item, m_slug, m_source_url, board_name, board_logo
                    )
                    if repaired is None:
                        continue
                    if existing_mon is not None:
                        repaired = CacheStore._merge_preserving_completeness(
                            repaired,
                            existing_mon,
                            preserve_omitted_optional_fields=False,
                        )
                    synced_count = sync_monitored_job_if_present(target_registry, repaired)
                    report.monitored_jobs_updated += synced_count
                    if synced_count or strategy.monitored_board_state_detail != "monitored_job":
                        record_repair_state(
                            target_cache,
                            strategy.state_table,
                            strategy.repair_version,
                            f"monitored:{canonical_id}",
                            "repaired",
                            strategy.monitored_board_state_detail,
                        )

    try:
        tasks = [_process_slug(slug_key) for slug_key in all_slugs]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        if own_client:
            await http_client.aclose()

    return report


def run_repair_cli(
    entrypoint: str,
    description: str,
    run_coro: Callable[..., Awaitable[object]],
    argv: Sequence[str] | None = None,
    *,
    supports_ttl_hours: bool = False,
) -> int:
    """Standard dry-run-by-default CLI runner shared by all cache repair modules."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist repaired records to SQLite (default is read-only --dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate repair without writing to SQLite (default unless --apply is set).",
    )
    parser.add_argument("--force", action="store_true", help="Re-process URLs even if marked repaired.")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent company slugs.")
    parser.add_argument("--max-urls", type=int, default=None, help="Maximum URLs to process in this run.")
    if supports_ttl_hours:
        parser.add_argument("--ttl-hours", type=float, default=None, help="Override url_cache TTL in hours.")
    parser.add_argument(
        "--allow-operational-db",
        action="store_true",
        help="Explicitly authorize opening operational data/cache.sqlite outside test contexts.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    effective_dry_run = bool(args.dry_run or not args.apply)

    kwargs: dict[str, object] = {
        "concurrency": args.concurrency,
        "force": args.force,
        "dry_run": effective_dry_run,
        "max_urls": args.max_urls,
    }
    if supports_ttl_hours:
        kwargs["ttl_hours"] = args.ttl_hours

    with cli_operational_runtime(
        entrypoint,
        allow_operational_db=args.allow_operational_db,
    ):
        report = asyncio.run(run_coro(**kwargs))
    print(json.dumps(asdict(report), indent=2))
    return 0

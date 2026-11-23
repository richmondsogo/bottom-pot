"""
Greenhouse zero-Serper cache & monitored_jobs repair strategy.

Delegates orchestration, SQLite checkpointing, SSRF-safe HTTP lifecycle, and
dry-run-by-default CLI execution to ``src.monitoring.cache_repair.engine``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

import httpx
from loguru import logger

from src.ats.ats_api_client import (
    GreenhouseClient,
    enrich_greenhouse_board_identity,
    greenhouse_payload_to_raw,
)
from src.ats.ats_url_parser import ParsedATSUrl, is_valid_board_slug
from src.core.http_headers import browser_headers
from src.core.models import JobListing
from src.extraction.field_normalizer import humanize_slug
from src.extraction.logo_extractor import LogoResult
from src.monitoring.cache_repair.engine import (
    CacheRepairReport,
    CacheRepairStrategy,
    SinglePostingResult,
    build_listing_from_raw,
    run_cache_repair,
    run_repair_cli,
)
from src.storage.cache_store import CacheStore
from src.storage.company_board_registry import CompanyBoardRegistry

REPAIR_VERSION = "v37"

_SYNTHETIC_SLUG_RE = re.compile(
    r"^(?:company\d+|test[-_]?company\d*|fake[-_]?(?:company)?\d*|dummy[-_]?(?:company)?\d*|placeholder[-_]?\d*)$",
    re.IGNORECASE,
)


def _is_synthetic_greenhouse_record(
    company_slug: str | None,
    existing: JobListing | None = None,
) -> bool:
    """Return True for known synthetic/test/placeholder Greenhouse records."""
    slug_norm = (company_slug or "").strip().lower()
    if not slug_norm or not is_valid_board_slug("greenhouse", slug_norm):
        return True
    if existing is not None:
        if existing.company_slug and _SYNTHETIC_SLUG_RE.match(existing.company_slug.strip()):
            return True
        if existing.company and _SYNTHETIC_SLUG_RE.match(existing.company.strip()):
            return True
    return False


def _is_synthetic_row(_url: str, slug: str | None, existing: JobListing | None) -> bool:
    return _is_synthetic_greenhouse_record(slug, existing)


@dataclass
class GreenhouseRepairReport:
    total_urls: int = 0
    unique_slugs: int = 0
    skipped_synthetic: int = 0
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
    except (httpx.HTTPError, OSError) as exc:
        logger.debug(f"[greenhouse-repair] Board list fetch failed for {slug}: {exc}")
        return None, {}

    if resp.status_code != 200:
        return resp.status_code, {}

    try:
        payload = resp.json()
    except (ValueError, TypeError):
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


async def _enrich_identity(
    slug: str,
    client: httpx.AsyncClient,
    registry: CompanyBoardRegistry,
    _dry_run: bool,
) -> tuple[str | None, LogoResult]:
    return await enrich_greenhouse_board_identity(slug, client, registry=registry)


def _listing_from_greenhouse_item(
    item: dict,
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
    return build_listing_from_raw(
        "greenhouse",
        raw,
        board_name=board_name,
        company_slug=company_slug,
        logo=logo,
    )


async def _fetch_single_posting(
    parsed: ParsedATSUrl,
    client: httpx.AsyncClient,
) -> SinglePostingResult:
    res = await GreenhouseClient().fetch_raw_result(parsed, client)
    return SinglePostingResult(outcome=res.outcome, raw=res.raw, status_code=res.status_code)


GREENHOUSE_REPAIR_STRATEGY = CacheRepairStrategy(
    provider="greenhouse",
    state_table="greenhouse_repair_state",
    repair_version=REPAIR_VERSION,
    url_cache_query="SELECT url, listing_json FROM url_cache WHERE url LIKE '%greenhouse.io/%' ORDER BY created_at ASC",
    unparsed_detail="Not a single Greenhouse job posting URL",
    terminal_statuses=("repaired", "unavailable_404"),
    require_parsed_none_for_fallback=False,
    record_normalized_alias_state=True,
    monitored_board_state_detail="board_api_monitored",
    is_synthetic=_is_synthetic_row,
    enrich_identity=_enrich_identity,
    fetch_board_items_map=_fetch_board_jobs_map,
    listing_from_board_item=_listing_from_greenhouse_item,
    fetch_single_posting=_fetch_single_posting,
)


def _to_greenhouse_report(base: CacheRepairReport) -> GreenhouseRepairReport:
    return GreenhouseRepairReport(
        total_urls=base.total_urls,
        unique_slugs=base.unique_slugs,
        skipped_synthetic=base.skipped_synthetic,
        skipped_already_repaired=base.skipped_already_repaired,
        repaired_from_board_api=base.repaired_from_board_api,
        repaired_from_posting_api=base.repaired_from_posting_api,
        expired_or_unavailable=base.expired_or_unavailable,
        transient_errors=base.transient_errors,
        unparsed_urls=base.unparsed_urls,
        boards_identity_enriched=base.boards_identity_enriched,
        monitored_jobs_updated=base.monitored_jobs_updated,
        monitored_jobs_closed=base.monitored_jobs_closed,
        serper_calls_made=base.serper_calls_used,
    )


async def repair_greenhouse_cache(
    *,
    cache: CacheStore | None = None,
    registry: CompanyBoardRegistry | None = None,
    client: httpx.AsyncClient | None = None,
    ttl_hours: float | None = None,
    concurrency: int = 4,
    max_urls: int | None = None,
    max_slugs: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> GreenhouseRepairReport:
    """Re-extract degraded Greenhouse rows in ``url_cache`` and active Greenhouse ``monitored_jobs``."""
    base = await run_cache_repair(
        GREENHOUSE_REPAIR_STRATEGY,
        cache=cache,
        registry=registry,
        client=client,
        ttl_hours=ttl_hours,
        concurrency=concurrency,
        max_urls=max_urls,
        max_slugs=max_slugs,
        force=force,
        dry_run=dry_run,
    )
    return _to_greenhouse_report(base)


def main(argv: Sequence[str] | None = None) -> None:
    run_repair_cli(
        "src.monitoring.cache_repair.greenhouse:main",
        "Repair degraded Greenhouse cache rows without Serper spend (--apply to write).",
        repair_greenhouse_cache,
        argv=argv,
    )


if __name__ == "__main__":
    main()

"""
Lever zero-Serper cache & monitored_jobs repair strategy.

Delegates orchestration, SQLite checkpointing, SSRF-safe HTTP lifecycle, and
dry-run-by-default CLI execution to ``src.monitoring.cache_repair.engine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import httpx
from loguru import logger

from src.ats.ats_api_client import (
    LeverClient,
    enrich_lever_board_identity,
    lever_payload_to_raw,
)
from src.ats.ats_url_parser import ParsedATSUrl
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

REPAIR_VERSION = "v36"


@dataclass
class LeverRepairReport:
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


async def _fetch_board_postings_map(
    slug: str,
    client: httpx.AsyncClient,
) -> tuple[int | None, dict[str, dict]]:
    board_api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = await client.get(
            board_api_url,
            headers=browser_headers(board_api_url, "application/json,text/plain;q=0.9,*/*;q=0.8"),
            timeout=12.0,
        )
    except (httpx.HTTPError, OSError) as exc:
        logger.debug(f"[lever-repair] Board list fetch failed for {slug}: {exc}")
        return None, {}

    if resp.status_code != 200:
        return resp.status_code, {}

    try:
        payload = resp.json()
    except (ValueError, TypeError):
        return 200, {}
    if not isinstance(payload, list):
        return 200, {}

    items_by_id: dict[str, dict] = {}
    for item in payload:
        if isinstance(item, dict) and item.get("id"):
            items_by_id[str(item["id"]).strip()] = item
    return 200, items_by_id


async def _enrich_identity(
    slug: str,
    client: httpx.AsyncClient,
    registry: CompanyBoardRegistry,
    _dry_run: bool,
) -> tuple[str | None, LogoResult]:
    return await enrich_lever_board_identity(slug, client, registry=registry)


def _listing_from_lever_item(
    item: dict,
    company_slug: str,
    source_url: str | None,
    board_name: str | None,
    logo: LogoResult,
) -> JobListing | None:
    raw = lever_payload_to_raw(
        item,
        company_slug=company_slug,
        source_url=source_url,
        query_used=company_slug,
        default_company_name=board_name or humanize_slug(company_slug),
        is_board_monitor=False,
    )
    return build_listing_from_raw(
        "lever",
        raw,
        board_name=board_name,
        company_slug=company_slug,
        logo=logo,
    )


async def _fetch_single_posting(
    parsed: ParsedATSUrl,
    client: httpx.AsyncClient,
) -> SinglePostingResult:
    res = await LeverClient().fetch_raw_result(parsed, client)
    return SinglePostingResult(outcome=res.outcome, raw=res.raw, status_code=res.status_code)


LEVER_REPAIR_STRATEGY = CacheRepairStrategy(
    provider="lever",
    state_table="lever_repair_state",
    repair_version=REPAIR_VERSION,
    url_cache_query="SELECT url, listing_json FROM url_cache WHERE url LIKE '%lever.co/%' ORDER BY created_at ASC",
    unparsed_detail="Not a single Lever job posting URL",
    terminal_statuses=("repaired", "unavailable_404"),
    total_urls_mode="raw_rows",
    check_completed_at_top=True,
    require_parsed_none_for_fallback=False,
    strip_colon_from_fallback_id=False,
    record_normalized_alias_state=True,
    enrich_identity=_enrich_identity,
    fetch_board_items_map=_fetch_board_postings_map,
    listing_from_board_item=_listing_from_lever_item,
    fetch_single_posting=_fetch_single_posting,
)


def _to_lever_report(base: CacheRepairReport) -> LeverRepairReport:
    return LeverRepairReport(
        total_urls=base.total_urls,
        unique_slugs=base.unique_slugs,
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


async def repair_lever_cache(
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
) -> LeverRepairReport:
    """Re-extract degraded Lever rows in ``url_cache`` and active Lever ``monitored_jobs``."""
    base = await run_cache_repair(
        LEVER_REPAIR_STRATEGY,
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
    return _to_lever_report(base)


def main(argv: Sequence[str] | None = None) -> int:
    return run_repair_cli(
        "src.monitoring.cache_repair.lever:main",
        "Bounded Lever cache repair (0 Serper credits; --apply to write).",
        repair_lever_cache,
        argv=argv,
        supports_ttl_hours=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

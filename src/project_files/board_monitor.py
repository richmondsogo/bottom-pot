"""
Independent ATS Company-Board Monitor & Scheduler.

Regularly monitors registered employer boards without repeated user searches:
- Queries company boards due for polling.
- Calls provider-specific adapters (Greenhouse, Lever, Ashby) with bounded concurrency.
- Detects new and modified jobs using ETags, Last-Modified, and SHA256 content fingerprints.
- Pipes newly discovered jobs into the canonical cache store.
- Supports both background daemon execution and CLI one-shot execution.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Optional

import httpx
from loguru import logger

from src.config import settings
from src.project_files.board_adapters import BOARD_ADAPTERS, BoardCheckResult
from src.project_files.cache_store import CacheStore, cache_store as _default_cache_store
from src.project_files.company_board_registry import (
    CompanyBoard,
    CompanyBoardRegistry,
    company_board_registry,
)
from src.project_files.models import JobListing


class BoardMonitor:
    """Orchestrates independent checking of registered company ATS boards."""

    def __init__(self, registry: CompanyBoardRegistry | None = None, cache: CacheStore | None = None):
        self.registry = registry or company_board_registry
        self._cache_store = cache or _default_cache_store

    async def check_single_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
        cache_store: CacheStore | None = None,
    ) -> BoardCheckResult:
        """Execute a check against one registered board and record the outcome."""
        adapter = BOARD_ADAPTERS.get(board.ats_provider)
        if not adapter:
            return BoardCheckResult(
                success=False,
                error=f"No monitor adapter for ATS provider '{board.ats_provider}'",
            )

        try:
            known_dates = self.registry.get_known_publication_dates(board.id)
            known_monitored_jobs = self.registry.get_monitored_jobs_for_board(board.id)
            result = await adapter.check_board(
                board,
                client,
                fetch_publication_dates=True,
                known_publication_dates=known_dates,
                known_monitored_jobs=known_monitored_jobs,
                registry=self.registry,
            )
            if result.not_modified:
                # Board has not changed: update check timestamp and schedule next without reparsing
                self.registry.record_check_success(
                    board.id,
                    active_job_count=board.active_job_count,
                    content_fingerprint=result.content_fingerprint or board.content_fingerprint,
                    etag=result.etag,
                    last_modified=result.last_modified,
                )
                logger.debug(f"[monitor] Board {board.ats_provider}:{board.board_token} unchanged (304/fingerprint)")
                return result

            target_cache = cache_store or self._cache_store
            if result.success:
                # Board updated with jobs: persist into durable searchable store and fast URL cache
                persisted_listings: list[JobListing] = []
                for job in result.listings:
                    # Completeness-aware merge with any richer cached listing before updating stores
                    existing_cached = target_cache.get_url_cache(job.source_url)
                    if existing_cached is not None:
                        job = CacheStore._merge_preserving_completeness(
                            job,
                            existing_cached,
                            preserve_omitted_optional_fields=True,
                        )
                    self.registry.upsert_monitored_job(
                        job,
                        board_id=board.id,
                        content_fingerprint=result.content_fingerprint,
                        preserve_last_checked_at=(
                            result.refreshed_job_ids is not None
                            and job.id not in result.refreshed_job_ids
                        ),
                    )
                    target_cache.set_url_cache(job.source_url, job)
                    persisted_listings.append(job)
                result.listings = persisted_listings

                # Lifecycle policy: any previously active jobs from this board not returned in latest poll are marked closed
                active_job_ids = {j.id for j in result.listings}
                self.registry.mark_missing_jobs_closed(board.id, active_job_ids)

                self.registry.record_check_success(
                    board.id,
                    active_job_count=len(result.listings),
                    content_fingerprint=result.content_fingerprint,
                    etag=result.etag,
                    last_modified=result.last_modified,
                    interval_seconds=settings.monitoring_board_interval_seconds,
                )
                logger.info(
                    f"[monitor] Board {board.ats_provider}:{board.board_token} checked: {len(result.listings)} active jobs"
                )
                return result

            # Check failed (e.g. 404, 500, network error)
            self.registry.record_check_failure(board.id, error=result.error or "Unknown failure")
            return result
        except Exception as exc:
            err_msg = str(exc)
            self.registry.record_check_failure(board.id, error=err_msg)
            return BoardCheckResult(success=False, error=err_msg)

    async def poll_due_boards(
        self,
        max_boards: int | None = None,
        client: httpx.AsyncClient | None = None,
        cache_store: CacheStore | None = None,
    ) -> list[JobListing]:
        """Fetch and check due boards concurrently with bounded semaphore limits."""
        effective_limit = max_boards if max_boards is not None else settings.monitoring_batch_size
        due_boards = self.registry.get_due_monitoring_boards(limit=effective_limit)
        if not due_boards:
            return []

        logger.debug(f"[monitor] Found {len(due_boards)} boards due for check")
        http_client = client if client is not None else httpx.AsyncClient(timeout=15.0)
        should_close = client is None

        sem = asyncio.Semaphore(settings.monitoring_concurrency_limit)
        collected_jobs: list[JobListing] = []

        async def _bounded_check(board: CompanyBoard):
            async with sem:
                res = await self.check_single_board(board, http_client, cache_store=cache_store)
                if res.success and not res.not_modified:
                    collected_jobs.extend(res.listings)

        try:
            await asyncio.gather(*(_bounded_check(board) for board in due_boards), return_exceptions=True)
            return collected_jobs
        finally:
            if should_close:
                await http_client.aclose()

    async def run_loop(
        self,
        interval_seconds: int | None = None,
        interval: int | None = None,
        stop_event: asyncio.Event | None = None,
        holder_id: str | None = None,
    ) -> None:
        """Continuous polling daemon with graceful shutdown and SQLite lease heartbeats."""
        poll_interval = interval_seconds or interval or settings.monitoring_interval_seconds
        actual_holder_id = holder_id or f"proc-{os.getpid()}-{int(time.time())}"
        logger.info(f"[monitor] Starting continuous monitoring loop (interval={poll_interval}s, holder={actual_holder_id})")

        # Try to acquire lease if not already acquired
        has_lease = self.registry.acquire_lease("board_monitor", actual_holder_id, ttl_seconds=max(60.0, poll_interval * 1.5))
        if not has_lease:
            logger.warning("[monitor] Could not acquire board_monitor lease. Another instance is active.")
            return

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                while True:
                    if stop_event and stop_event.is_set():
                        logger.info("[monitor] Stop event set. Exiting monitoring loop.")
                        break

                    # Renew lease heartbeat
                    self.registry.renew_lease("board_monitor", actual_holder_id, ttl_seconds=max(60.0, poll_interval * 1.5))

                    try:
                        jobs = await self.poll_due_boards(max_boards=settings.monitoring_batch_size, client=client)
                        if jobs:
                            logger.info(f"[monitor] Polling round completed with {len(jobs)} total jobs updated.")
                    except Exception as exc:
                        logger.error(f"[monitor] Error during polling round: {exc}")

                    # Sleep until next round with stop_event responsiveness and heartbeat
                    for sec in range(max(1, poll_interval)):
                        if stop_event and stop_event.is_set():
                            break
                        if sec > 0 and sec % 20 == 0:
                            self.registry.renew_lease("board_monitor", actual_holder_id, ttl_seconds=max(60.0, poll_interval * 1.5))
                        await asyncio.sleep(1.0)
            finally:
                self.registry.release_lease("board_monitor", actual_holder_id)
                logger.info(f"[monitor] Released board_monitor lease for {actual_holder_id}")


# ---------------------------------------------------------------------------
# CLI Command Runner
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Bottom Pot Independent ATS Board Monitor")
    parser.add_argument("--run-once", action="store_true", help="Run a single polling round and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in the background")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds between polling rounds")
    parser.add_argument("--limit", type=int, default=25, help="Maximum boards to check per round")
    args = parser.parse_args()

    monitor = BoardMonitor()
    holder_id = f"cli-{os.getpid()}-{int(time.time())}"

    # Use cross-process SQLite lease (fully Windows and Linux compatible)
    if not monitor.registry.acquire_lease("board_monitor", holder_id, ttl_seconds=max(60.0, args.interval * 1.5)):
        logger.error("Another monitor instance is currently running with active lease. Exiting.")
        sys.exit(0)

    try:
        if args.run_once:
            logger.info("Executing single monitoring check round...")
            jobs = asyncio.run(monitor.poll_due_boards(max_boards=args.limit))
            logger.info(f"Single check complete. Discovered/updated {len(jobs)} listings.")
        else:
            logger.info(f"Starting monitoring daemon (holder={holder_id})...")
            asyncio.run(monitor.run_loop(interval_seconds=args.interval, holder_id=holder_id))
    finally:
        monitor.registry.release_lease("board_monitor", holder_id)


if __name__ == "__main__":
    main()

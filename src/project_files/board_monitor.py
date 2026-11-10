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
from src.project_files.cache_store import cache_store
from src.project_files.company_board_registry import (
    CompanyBoard,
    CompanyBoardRegistry,
    company_board_registry,
)
from src.project_files.models import JobListing


class BoardMonitor:
    """Orchestrates independent checking of registered company ATS boards."""

    def __init__(self, registry: CompanyBoardRegistry | None = None):
        self.registry = registry or company_board_registry

    async def check_single_board(
        self,
        board: CompanyBoard,
        client: httpx.AsyncClient,
    ) -> BoardCheckResult:
        """Execute a check against one registered board and record the outcome."""
        adapter = BOARD_ADAPTERS.get(board.ats_provider)
        if not adapter:
            return BoardCheckResult(
                success=False,
                error=f"No monitor adapter for ATS provider '{board.ats_provider}'",
            )

        try:
            result = await adapter.check_board(board, client)
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

            if result.success:
                # Board updated with jobs: cache newly extracted jobs
                for job in result.listings:
                    cache_store.set_url_cache(job.source_url, job)

                self.registry.record_check_success(
                    board.id,
                    active_job_count=len(result.listings),
                    content_fingerprint=result.content_fingerprint,
                    etag=result.etag,
                    last_modified=result.last_modified,
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
        max_boards: int = 20,
        client: httpx.AsyncClient | None = None,
    ) -> list[JobListing]:
        """Fetch and check due boards concurrently with bounded semaphore limits."""
        due_boards = self.registry.get_due_monitoring_boards(limit=max_boards)
        if not due_boards:
            return []

        logger.debug(f"[monitor] Found {len(due_boards)} boards due for check")
        http_client = client if client is not None else httpx.AsyncClient(timeout=15.0)
        should_close = client is None

        sem = asyncio.Semaphore(settings.monitoring_concurrency_limit)
        collected_jobs: list[JobListing] = []

        async def _bounded_check(board: CompanyBoard):
            async with sem:
                res = await self.check_single_board(board, http_client)
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
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Continuous polling daemon with graceful shutdown support."""
        interval = interval_seconds or settings.monitoring_interval_seconds
        logger.info(f"[monitor] Starting continuous monitoring loop (interval={interval}s)")

        async with httpx.AsyncClient(timeout=20.0) as client:
            while True:
                if stop_event and stop_event.is_set():
                    logger.info("[monitor] Stop event set. Exiting monitoring loop.")
                    break

                try:
                    jobs = await self.poll_due_boards(max_boards=25, client=client)
                    if jobs:
                        logger.info(f"[monitor] Polling round completed with {len(jobs)} total jobs updated.")
                except Exception as exc:
                    logger.error(f"[monitor] Error during polling round: {exc}")

                # Sleep until next round with stop_event responsiveness
                for _ in range(max(1, interval)):
                    if stop_event and stop_event.is_set():
                        break
                    await asyncio.sleep(1.0)


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

    # Lock file to prevent duplicate scheduler processes
    lock_file = Path("data/monitor.lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        if lock_file.exists():
            try:
                pid = int(lock_file.read_text(encoding="utf-8").strip())
                # Check if process with PID is still running
                if os.name != "nt":
                    os.kill(pid, 0)
                    logger.error(f"Monitor already running (PID {pid}). Exiting.")
                    sys.exit(1)
            except (ValueError, OSError):
                # Stale lockfile
                pass

        lock_file.write_text(str(os.getpid()), encoding="utf-8")
        monitor = BoardMonitor()

        if args.run_once:
            logger.info("Executing single monitoring check round...")
            jobs = asyncio.run(monitor.poll_due_boards(max_boards=args.limit))
            logger.info(f"Single check complete. Discovered/updated {len(jobs)} listings.")
        else:
            logger.info("Starting monitoring daemon...")
            asyncio.run(monitor.run_loop(interval_seconds=args.interval))
    finally:
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()

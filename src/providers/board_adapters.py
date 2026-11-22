"""
ATS Company-Board Adapter Registry & Compatibility Facade.

Per-provider monitoring implementations live in dedicated modules under
``src/providers/<provider>.py`` backed by shared primitives in
``src/providers/{contract,fingerprint,http,pagination,detail_hydration}.py``.

This module preserves the historic ``src.providers.board_adapters`` import
surface (``BOARD_ADAPTERS``, adapter classes, and shared helpers) for
downstream callers and regression tests.
"""

from __future__ import annotations

from src.providers.ashby import AshbyBoardAdapter, _ashby_job_content_hash
from src.providers.contract import (
    BoardCheckResult,
    FailureKind,
    ReconciliationPolicy,
    SnapshotResult,
    get_reconciliation_policy,
)
from src.providers.fingerprint import canonical_content_hash, compute_board_fingerprint
from src.providers.greenhouse import GreenhouseBoardAdapter
from src.providers.lever import LeverBoardAdapter
from src.providers.personio import (
    PersonioBoardAdapter,
    _get_personio_xml,
    _merge_personio_feeds,
    _personio_position_to_listing,
    parse_personio_xml_feed,
)
from src.providers.pinpoint import (
    PinpointBoardAdapter,
    _pinpoint_item_to_listing,
    parse_pinpoint_postings_json,
    resolve_pinpoint_board_timeout,
)
from src.providers.recruitee import (
    RecruiteeBoardAdapter,
    _recruitee_job_content_hash,
    hydrate_recruitee_offers,
    validate_recruitee_offers_snapshot,
)
from src.providers.smartrecruiters import (
    SmartRecruitersBoardAdapter,
    fetch_smartrecruiters_postings_snapshot,
    hydrate_smartrecruiters_board_jobs,
    validate_smartrecruiters_page,
)
from src.providers.teamtailor import (
    TeamtailorBoardAdapter,
    _parse_teamtailor_html_jobs_page,
    _teamtailor_rss_item_to_listing,
    parse_teamtailor_rss_feed,
)
from src.providers.workable import (
    WorkableBoardAdapter,
    _workable_widget_differs_from_listing,
    hydrate_workable_board_jobs,
)

BOARD_ADAPTERS: dict[str, object] = {
    "greenhouse": GreenhouseBoardAdapter(),
    "lever": LeverBoardAdapter(),
    "ashby": AshbyBoardAdapter(),
    "workable": WorkableBoardAdapter(),
    "recruitee": RecruiteeBoardAdapter(),
    "smartrecruiters": SmartRecruitersBoardAdapter(),
    "teamtailor": TeamtailorBoardAdapter(),
    "personio": PersonioBoardAdapter(),
    "pinpointhq": PinpointBoardAdapter(),
}

__all__ = [
    "AshbyBoardAdapter",
    "BOARD_ADAPTERS",
    "BoardCheckResult",
    "FailureKind",
    "GreenhouseBoardAdapter",
    "LeverBoardAdapter",
    "PersonioBoardAdapter",
    "PinpointBoardAdapter",
    "ReconciliationPolicy",
    "RecruiteeBoardAdapter",
    "SmartRecruitersBoardAdapter",
    "SnapshotResult",
    "TeamtailorBoardAdapter",
    "WorkableBoardAdapter",
    "_ashby_job_content_hash",
    "_get_personio_xml",
    "_merge_personio_feeds",
    "_parse_teamtailor_html_jobs_page",
    "_personio_position_to_listing",
    "_pinpoint_item_to_listing",
    "_recruitee_job_content_hash",
    "_teamtailor_rss_item_to_listing",
    "_workable_widget_differs_from_listing",
    "canonical_content_hash",
    "compute_board_fingerprint",
    "fetch_smartrecruiters_postings_snapshot",
    "get_reconciliation_policy",
    "hydrate_recruitee_offers",
    "hydrate_smartrecruiters_board_jobs",
    "hydrate_workable_board_jobs",
    "parse_personio_xml_feed",
    "parse_pinpoint_postings_json",
    "parse_teamtailor_rss_feed",
    "resolve_pinpoint_board_timeout",
    "validate_recruitee_offers_snapshot",
    "validate_smartrecruiters_page",
]

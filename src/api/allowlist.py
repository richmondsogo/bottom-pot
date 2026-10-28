"""
Allowlist configuration and serialization utilities for public SSE search stream redaction.

Anonymous callers receive only explicitly allowlisted fields.
All operational metadata, telemetry, and scraping provenance remain admin-only.
"""

from __future__ import annotations

import json
from typing import Optional, Set
from pydantic import BaseModel

# ── Field Classifications ──────────────────────────────────────────────────────

USER_JOB_FIELDS: Set[str] = {
    "id",
    "provider",
    "title",
    "company",
    "company_slug",
    "location",
    "is_remote",
    "employment_type",
    "work_model",
    "department",
    "salary",
    "description",
    "requirements",
    "posted_at",
    "apply_url",
    "ats_source",
}

ADMIN_JOB_FIELDS: Set[str] = {
    "data_source",
    "work_model_source",
    "work_model_evidence",
    "raw_workplace_type",
    "description_ok",
    "extraction_confidence",
    "scraped_at",
    "source_url",
    "query_used",
}

USER_RESULTS_BATCH_FIELDS: Set[str] = {
    "batch",
    "total_so_far",
}

ADMIN_RESULTS_BATCH_FIELDS: Set[str] = set()

USER_DONE_FIELDS: Set[str] = {
    "total",
}

ADMIN_DONE_FIELDS: Set[str] = {
    "search_time_ms",
    "serper_queries_used",
    "providers_searched",
    "providers_skipped",
    "cached",
    "dropped_count",
    "serper_calls",
    "serper_cache_hits",
    "pages_fetched",
    "budget_exhausted",
    "message",
}

USER_ALLOWED_EVENTS: Set[str] = {
    "results",
    "done",
    "error",
}

RESULTS_BATCH_INCLUDE = {
    "total_so_far": True,
    "batch": {"__all__": USER_JOB_FIELDS},
}


def sanitize_error_message(code: str) -> str:
    """Returns fixed user-safe message chosen by code for anonymous callers."""
    code_upper = (code or "").upper()
    if "TIMEOUT" in code_upper:
        return "The search took too long. Please try again."
    if code_upper == "PROVIDER_ERROR":
        return "Something went wrong while searching. Please try again."
    return "Something went wrong while searching. Please try again."


def serialize_event_for_user(event_name: str, event_data: BaseModel) -> Optional[str]:
    """
    Serializes SSE event payload for anonymous users using explicit allowlists.
    Returns None if the event type should be omitted for anonymous users.
    """
    if event_name not in USER_ALLOWED_EVENTS:
        return None

    if event_name == "results":
        return event_data.model_dump_json(include=RESULTS_BATCH_INCLUDE)

    if event_name == "done":
        total = getattr(event_data, "total", 0)
        budget_exhausted = bool(getattr(event_data, "budget_exhausted", False))
        return json.dumps(
            {
                "total": total,
                "incomplete": budget_exhausted,
            },
            separators=(",", ":"),
        )

    if event_name == "error":
        code = getattr(event_data, "code", "UNKNOWN_ERROR")
        safe_message = sanitize_error_message(code)
        return json.dumps(
            {
                "message": safe_message,
                "code": code,
            },
            separators=(",", ":"),
        )

    return None

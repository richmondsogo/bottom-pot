"""Unit and integration tests for canonical job freshness and read-only reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.report_freshness import report_from_fixtures, report_from_sqlite
from src.api.allowlist import ADMIN_JOB_FIELDS, USER_JOB_FIELDS, serialize_event_for_user
from src.core.models import JobListing, ResultsBatch
from src.extraction.freshness import (
    FRESH_MAX_DAYS,
    RECENT_MAX_DAYS,
    FreshnessTier,
    compute_age_days,
    compute_freshness,
    detect_evergreen_signal,
    sort_jobs_by_freshness,
)
from src.safety.db_safety import UnsafeDatabasePathError
from src.storage.company_board_registry import CompanyBoardRegistry

REF_NOW = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)


def _days_ago(days: int) -> datetime:
    return REF_NOW - timedelta(days=days)


def _make_job(job_id: str, **overrides) -> JobListing:
    payload = {
        "id": job_id,
        "provider": "greenhouse",
        "data_source": "api",
        "title": f"Engineer {job_id}",
        "company": f"Company {job_id}",
        "location": "Remote",
        "work_model": "remote",
        "scraped_at": REF_NOW,
        "apply_url": f"https://boards.greenhouse.io/acme/jobs/{job_id}",
        "source_url": f"https://boards.greenhouse.io/acme/jobs/{job_id}",
        "query_used": "engineer",
        "ats_source": "greenhouse",
    }
    payload.update(overrides)
    return JobListing(**payload)


def test_freshness_tier_boundaries_and_unlisted_handling():
    assert FRESH_MAX_DAYS == 30
    assert RECENT_MAX_DAYS == 90

    assert compute_freshness(posted_at=_days_ago(0), now=REF_NOW) == FreshnessTier.FRESH
    assert compute_freshness(posted_at=_days_ago(30), now=REF_NOW) == FreshnessTier.FRESH
    assert compute_freshness(posted_at=_days_ago(31), now=REF_NOW) == FreshnessTier.RECENT
    assert compute_freshness(posted_at=_days_ago(90), now=REF_NOW) == FreshnessTier.RECENT
    assert compute_freshness(posted_at=_days_ago(91), now=REF_NOW) == FreshnessTier.STALE
    assert compute_freshness(posted_at=REF_NOW + timedelta(days=2), now=REF_NOW) == FreshnessTier.FRESH

    # Missing posted_at remains None while recently seen, and becomes stale after 90 days observed
    assert compute_freshness(posted_at=None, first_seen_at=_days_ago(5), now=REF_NOW) is None
    assert compute_freshness(posted_at=None, first_seen_at=_days_ago(90), now=REF_NOW) is None
    assert compute_freshness(posted_at=None, first_seen_at=_days_ago(91), now=REF_NOW) == FreshnessTier.STALE

    # Age days clamping & first_seen_at fallback
    assert compute_age_days(_days_ago(14), now=REF_NOW) == 14
    assert compute_age_days(None, first_seen_at=_days_ago(9), now=REF_NOW) == 9
    assert compute_age_days(REF_NOW + timedelta(days=3), now=REF_NOW) == 0
    assert compute_age_days(None, first_seen_at=None, now=REF_NOW) is None


def test_evergreen_detection_is_strictly_explicit_only():
    # Old or undated postings NEVER become evergreen without explicit ATS flag or statement
    assert detect_evergreen_signal(title="Senior Backend Engineer", description="Build reliable APIs.") is None
    assert compute_freshness(posted_at=_days_ago(400), now=REF_NOW) == FreshnessTier.STALE
    assert compute_freshness(posted_at=None, first_seen_at=_days_ago(200), now=REF_NOW) == FreshnessTier.STALE

    # Explicit ATS boolean / type / metadata flags
    assert detect_evergreen_signal(raw_fields={"isEvergreen": True}) == "ats_flag:isEvergreen"
    assert detect_evergreen_signal(raw_fields={"requisitionType": "evergreen"}) == "ats_flag:requisitionType"
    assert (
        detect_evergreen_signal(
            raw_fields={"metadata": [{"name": "Evergreen Requisition", "value": "true"}]}
        )
        == "ats_flag:metadata"
    )

    # Explicit ongoing pipeline / multi-hire statement
    sig = detect_evergreen_signal(
        description="We maintain rolling applications for this engineering pipeline across regions."
    )
    assert sig is not None and sig.startswith("statement:")
    assert compute_freshness(posted_at=_days_ago(200), evergreen_signal=sig, now=REF_NOW) == FreshnessTier.EVERGREEN


def test_sort_jobs_by_freshness_tier_order_and_stability():
    stale_1 = _make_job("stale-1", posted_at=_days_ago(120))
    stale_2 = _make_job("stale-2", posted_at=_days_ago(200))
    unlisted = _make_job("unlisted-1", posted_at=None)
    evergreen = _make_job(
        "evergreen-1",
        posted_at=_days_ago(200),
        evergreen_signal="statement:rolling applications",
    )
    recent = _make_job("recent-1", posted_at=_days_ago(45))
    fresh_1 = _make_job("fresh-1", posted_at=_days_ago(2))
    fresh_2 = _make_job("fresh-2", posted_at=_days_ago(10))

    assert stale_1.freshness == FreshnessTier.STALE
    assert unlisted.freshness is None
    assert evergreen.freshness == FreshnessTier.EVERGREEN
    assert recent.freshness == FreshnessTier.RECENT
    assert fresh_1.freshness == FreshnessTier.FRESH

    ordered = sort_jobs_by_freshness([stale_1, unlisted, stale_2, evergreen, recent, fresh_1, fresh_2])
    assert [j.id for j in ordered] == [
        "fresh-1",
        "fresh-2",
        "recent-1",
        "evergreen-1",
        "unlisted-1",
        "stale-1",
        "stale-2",
    ]


def test_allowlist_and_model_exposure_for_freshness_fields():
    assert {"first_seen_at", "last_verified_at", "freshness"} <= USER_JOB_FIELDS
    assert "evergreen_signal" in ADMIN_JOB_FIELDS
    assert (USER_JOB_FIELDS & ADMIN_JOB_FIELDS) == set()
    assert (USER_JOB_FIELDS | ADMIN_JOB_FIELDS) == set(JobListing.model_fields.keys())

    job = _make_job(
        "greenhouse:acme:fresh-exposure",
        posted_at=_days_ago(3),
        first_seen_at=_days_ago(2),
        last_verified_at=REF_NOW,
        evergreen_signal="statement:rolling applications",
        freshness=FreshnessTier.EVERGREEN,
    )
    payload_str = serialize_event_for_user("results", ResultsBatch(batch=[job], total_so_far=1))
    assert payload_str is not None
    user_payload = json.loads(payload_str)["batch"][0]
    assert user_payload["freshness"] == "evergreen"
    assert user_payload["first_seen_at"] is not None
    assert user_payload["last_verified_at"] is not None
    assert "evergreen_signal" not in user_payload


def test_registry_hydrates_freshness_timestamps_and_orders_results(tmp_path: Path):
    db_path = tmp_path / "registry_freshness.sqlite"
    registry = CompanyBoardRegistry(db_path=str(db_path))

    stale_job = _make_job(
        "greenhouse:acme:stale-role",
        title="Backend Systems Engineer (Legacy)",
        posted_at=datetime.now(timezone.utc) - timedelta(days=180),
        freshness=FreshnessTier.STALE,
    )
    fresh_job = _make_job(
        "greenhouse:acme:fresh-role",
        title="Backend Systems Engineer (Current)",
        posted_at=datetime.now(timezone.utc) - timedelta(days=2),
        freshness=FreshnessTier.FRESH,
    )
    evergreen_job = _make_job(
        "greenhouse:acme:evergreen-role",
        title="Backend Systems Engineer (General Application)",
        posted_at=datetime.now(timezone.utc) - timedelta(days=220),
        evergreen_signal="statement:general application",
        freshness=FreshnessTier.EVERGREEN,
    )

    assert registry.upsert_monitored_job(stale_job) is True
    assert registry.upsert_monitored_job(evergreen_job) is True
    assert registry.upsert_monitored_job(fresh_job) is True

    found = registry.search_monitored_jobs("Backend Systems", limit=10)
    assert [j.id for j in found] == [
        "greenhouse:acme:fresh-role",
        "greenhouse:acme:evergreen-role",
        "greenhouse:acme:stale-role",
    ]
    for item in found:
        assert item.first_seen_at is not None
        assert item.last_verified_at is not None

    # Read-only freshness report CLI logic does not alter the SQLite file bytes and counts tiers accurately
    before_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
    summary = report_from_sqlite(db_path, now=datetime.now(timezone.utc))
    after_sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert before_sha == after_sha
    assert summary["total_postings"] == 3
    assert summary["providers"]["greenhouse"]["fresh"] == 1
    assert summary["providers"]["greenhouse"]["evergreen"] == 1
    assert summary["providers"]["greenhouse"]["stale"] == 1


def test_report_freshness_rejects_operational_db_and_scans_fixtures(tmp_path: Path):
    with pytest.raises(UnsafeDatabasePathError):
        report_from_sqlite(Path("data/cache.sqlite"))

    sample_dir = tmp_path / "fixtures" / "ashby"
    sample_dir.mkdir(parents=True)
    (sample_dir / "board.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {"id": "1", "title": "Fresh Eng", "publishedAt": _days_ago(5).isoformat()},
                    {"id": "2", "title": "Stale Eng", "publishedAt": _days_ago(180).isoformat()},
                    {"id": "3", "title": "Ongoing", "publishedAt": _days_ago(180).isoformat(), "isEvergreen": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    summary = report_from_fixtures(tmp_path / "fixtures", now=REF_NOW)
    assert summary["total_postings"] == 3
    assert summary["providers"]["ashby"]["fresh"] == 1
    assert summary["providers"]["ashby"]["stale"] == 1
    assert summary["providers"]["ashby"]["evergreen"] == 1

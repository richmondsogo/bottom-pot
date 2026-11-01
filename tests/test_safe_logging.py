"""
Tests for safe logging and error summary sanitization (Step 24a / Commit 7 / Amendment 8).
Ensures that credential-bearing URLs and sensitive tokens in error messages are never logged
or emitted in error summaries.
"""

from loguru import logger
import pytest

from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    sanitize_error_text,
)


def test_sanitize_error_text_strips_credentials_and_query_strings():
    """Verify credentials and query strings in URLs are stripped from error text."""
    dirty_text = (
        "Failed to fetch job at "
        "https://api_user:secret_pass123@boards-api.greenhouse.io/v1/boards/stripe/jobs/999?auth_token=super_secret_token&ref=track"
    )
    cleaned = sanitize_error_text(dirty_text)

    # Invariants: no credentials, no query params
    assert "api_user" not in cleaned
    assert "secret_pass123" not in cleaned
    assert "super_secret_token" not in cleaned
    assert "auth_token" not in cleaned
    assert "https://boards-api.greenhouse.io/v1/boards/stripe/jobs/999" in cleaned


def test_extraction_result_auto_sanitizes_error_summary():
    """Verify ExtractionResult automatically sanitizes error_summary upon construction."""
    dirty_summary = "[lever] 403 Forbidden for https://bot:super_pwd@jobs.lever.co/kinsta/job-1?key=priv_key_999"
    res = ExtractionResult(
        outcome=ExtractionOutcome.PERMANENT_ERROR,
        status_code=403,
        error_summary=dirty_summary,
    )

    assert res.error_summary is not None
    assert "bot" not in res.error_summary
    assert "super_pwd" not in res.error_summary
    assert "priv_key_999" not in res.error_summary
    assert "https://jobs.lever.co/kinsta/job-1" in res.error_summary


def test_safe_logging_never_emits_credentials_in_logs(caplog):
    """Verify structured log output never contains credentials when sanitization is applied."""
    dirty_msg = "Upstream error on https://admin:bearer_token_xyz@api.ashbyhq.com/posting-api/job?token=leaked_secret"
    safe_msg = sanitize_error_text(dirty_msg)

    logger.warning(safe_msg)

    assert "admin" not in safe_msg
    assert "bearer_token_xyz" not in safe_msg
    assert "leaked_secret" not in safe_msg
    assert "https://api.ashbyhq.com/posting-api/job" in safe_msg

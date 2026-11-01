"""
Unit tests for ExtractionOutcome taxonomy, ADR 0029 mapping table, and error sanitization.
"""

import httpx
import pytest

from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    map_status_or_exception_to_outcome,
    sanitize_error_text,
)
from src.project_files.http_resilience import CircuitBreakerOpenError


class TestExtractionOutcomeMapping:
    """Test mapping table defined in ADR 0029."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            (200, ExtractionOutcome.SUCCESS),
            (201, ExtractionOutcome.SUCCESS),
            (404, ExtractionOutcome.NOT_FOUND),
            (410, ExtractionOutcome.NOT_FOUND),
            (429, ExtractionOutcome.RATE_LIMITED),
            (408, ExtractionOutcome.RETRYABLE_ERROR),
            (500, ExtractionOutcome.RETRYABLE_ERROR),
            (502, ExtractionOutcome.RETRYABLE_ERROR),
            (503, ExtractionOutcome.RETRYABLE_ERROR),
            (504, ExtractionOutcome.RETRYABLE_ERROR),
            (401, ExtractionOutcome.PERMANENT_ERROR),
            (403, ExtractionOutcome.PERMANENT_ERROR),
            (400, ExtractionOutcome.PERMANENT_ERROR),
            (422, ExtractionOutcome.PERMANENT_ERROR),
        ],
    )
    def test_status_code_mapping(self, status: int, expected: ExtractionOutcome):
        outcome = map_status_or_exception_to_outcome(status_code=status)
        assert outcome == expected

    def test_timeout_exception_mapping(self):
        exc = httpx.ReadTimeout("Read timed out")
        outcome = map_status_or_exception_to_outcome(exception=exc)
        assert outcome == ExtractionOutcome.RETRYABLE_ERROR

    def test_connect_error_mapping(self):
        exc = httpx.ConnectError("Connection refused")
        outcome = map_status_or_exception_to_outcome(exception=exc)
        assert outcome == ExtractionOutcome.RETRYABLE_ERROR

    def test_circuit_breaker_open_mapping(self):
        exc = CircuitBreakerOpenError("boards.greenhouse.io")
        outcome = map_status_or_exception_to_outcome(exception=exc)
        assert outcome == ExtractionOutcome.RETRYABLE_ERROR

    def test_http_status_error_mapping(self):
        req = httpx.Request("GET", "https://api.lever.co/v0/postings/foo/bar")
        resp = httpx.Response(404, request=req)
        exc = httpx.HTTPStatusError("Not Found", request=req, response=resp)
        outcome = map_status_or_exception_to_outcome(exception=exc)
        assert outcome == ExtractionOutcome.NOT_FOUND

        resp_503 = httpx.Response(503, request=req)
        exc_503 = httpx.HTTPStatusError("Service Unavailable", request=req, response=resp_503)
        outcome_503 = map_status_or_exception_to_outcome(exception=exc_503)
        assert outcome_503 == ExtractionOutcome.RETRYABLE_ERROR


class TestSanitizeErrorText:
    """Test URL and credential sanitization in error messages."""

    def test_strips_token_and_query_parameters(self):
        raw = "Failed fetching https://api.example.com/jobs/123?token=secret123&user=admin"
        sanitized = sanitize_error_text(raw)
        assert "token=secret123" not in sanitized
        assert "user=admin" not in sanitized
        assert sanitized == "Failed fetching https://api.example.com/jobs/123"

    def test_strips_basic_auth_credentials(self):
        raw = "Failed connect to https://user:pass123@api.lever.co/v0/postings/job1"
        sanitized = sanitize_error_text(raw)
        assert "pass123" not in sanitized
        assert "user:" not in sanitized
        assert sanitized == "Failed connect to https://api.lever.co/v0/postings/job1"

    def test_preserves_trailing_punctuation(self):
        raw = "Error occurred at (https://boards.greenhouse.io/v1/jobs/999?api_key=xyz)."
        sanitized = sanitize_error_text(raw)
        assert "api_key=xyz" not in sanitized
        assert sanitized == "Error occurred at (https://boards.greenhouse.io/v1/jobs/999)."

    def test_extraction_result_sanitizes_automatically(self):
        result = ExtractionResult(
            outcome=ExtractionOutcome.RETRYABLE_ERROR,
            error_summary="Timeout on https://user:secret@ashbyhq.com/api/job?token=xyz123",
        )
        assert "secret" not in result.error_summary
        assert "token=xyz123" not in result.error_summary
        assert result.error_summary == "Timeout on https://ashbyhq.com/api/job"

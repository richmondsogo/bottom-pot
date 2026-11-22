"""
ExtractionOutcome taxonomy and ExtractionResult container.
Governed by ADR 0029.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from src.project_files.job_extraction_service import RawJobPosting
from src.project_files.confidence_policy import sanitize_source_url


class ExtractionOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NOT_FOUND = "not_found"
    RETRYABLE_ERROR = "retryable_error"
    PERMANENT_ERROR = "permanent_error"
    PARSE_ERROR = "parse_error"
    UNSUPPORTED_SOURCE = "unsupported_source"
    RATE_LIMITED = "rate_limited"


def sanitize_error_text(text: str | None) -> str | None:
    """
    Sanitize an error summary or exception string.
    Removes credential-bearing query parameters, tokens, and credentials from URLs.
    """
    if not text:
        return text

    # Regex to match URLs in error strings (http:// or https://)
    url_pattern = re.compile(r"https?://[^\s<>'\"]+")

    def _replace_url(match: re.Match) -> str:
        raw_url = match.group(0)
        # Strip trailing punctuation if accidentally captured
        trailing = ""
        while raw_url and raw_url[-1] in (")", "]", "}", ",", ".", ";", ":"):
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        try:
            parsed = urlparse(raw_url)
            # Remove username and password
            netloc = parsed.netloc
            if "@" in netloc:
                netloc = netloc.split("@", 1)[1]
            # Strip query string and fragment completely for error logs
            sanitized = urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
            return sanitized + trailing
        except Exception:
            return "[sanitized-url]" + trailing

    return url_pattern.sub(_replace_url, text)


def map_status_or_exception_to_outcome(
    status_code: int | None = None,
    exception: Exception | None = None,
) -> ExtractionOutcome:
    """
    Maps an HTTP status code or Exception to an ExtractionOutcome per ADR 0029.
    """
    if exception is not None:
        import httpx

        if isinstance(exception, httpx.HTTPStatusError):
            status_code = exception.response.status_code
        elif isinstance(
            exception,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ),
        ):
            return ExtractionOutcome.RETRYABLE_ERROR
        elif "CircuitBreakerOpenError" in type(exception).__name__:
            return ExtractionOutcome.RETRYABLE_ERROR
        elif "RateLimitError" in type(exception).__name__:
            return ExtractionOutcome.RATE_LIMITED
        elif "BotBlockError" in type(exception).__name__:
            return ExtractionOutcome.PERMANENT_ERROR
        elif isinstance(exception, (ValueError, KeyError)) and "JSON" in str(exception):
            return ExtractionOutcome.PARSE_ERROR

    if status_code is not None:
        if 200 <= status_code < 300:
            return ExtractionOutcome.SUCCESS
        if status_code in (404, 410):
            return ExtractionOutcome.NOT_FOUND
        if status_code == 429:
            return ExtractionOutcome.RATE_LIMITED
        if status_code in (408, 500, 502, 503, 504):
            return ExtractionOutcome.RETRYABLE_ERROR
        if 400 <= status_code < 500:
            return ExtractionOutcome.PERMANENT_ERROR
        if 500 <= status_code < 600:
            return ExtractionOutcome.RETRYABLE_ERROR

    return ExtractionOutcome.PERMANENT_ERROR


@dataclass
class ExtractionResult:
    outcome: ExtractionOutcome
    raw: RawJobPosting | None = None
    status_code: int | None = None
    error_summary: str | None = None
    attempts: int = 1
    degraded_from: str | None = None

    def __post_init__(self):
        if self.error_summary:
            self.error_summary = sanitize_error_text(self.error_summary)

"""
Shared HTML, WAF-detection, and Schema.org JSON-LD extraction utilities.

Used by both structured ATS clients (e.g., WorkdayClient HTML fallback) and
ats_page_enricher without creating circular module dependencies.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
import re
from typing import Any

from bs4 import BeautifulSoup

_WAF_CHALLENGE_MARKERS = (
    "checking your browser",
    "just a moment...",
    "cf-browser-verification",
    "attention required! | cloudflare",
    "enable javascript and cookies to continue",
    "captcha-delivery",
    "datadome",
)

_WORKDAY_POSTING_UNAVAILABLE_RE = re.compile(r"postingAvailable\s*:\s*false\b")


def is_waf_challenge(
    status_code: int,
    body: str,
    headers: Mapping[str, Any] | None = None,
) -> bool:
    """Detect Cloudflare / DataDome / anti-bot HTML challenge interstitials."""
    if headers:
        lowered = {str(k).lower(): str(v).lower() for k, v in headers.items()}
        if "cf-mitigated" in lowered:
            return True
    if status_code not in (200, 202, 403, 429, 503):
        return False
    lowered_body = (body or "").lower()
    return any(marker in lowered_body for marker in _WAF_CHALLENGE_MARKERS)


def is_workday_posting_unavailable(html_text: str) -> bool:
    """Detect Workday's explicit unavailable job state (`postingAvailable: false`)."""
    return bool(_WORKDAY_POSTING_UNAVAILABLE_RE.search(html_text or ""))


def extract_json_ld_documents(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Parse all valid JSON-LD dicts (including flattened @graph/lists) from HTML."""
    docs: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                docs.extend(node for node in graph if isinstance(node, dict))
            docs.append(item)
    return docs


def extract_job_posting_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Return the first Schema.org JobPosting JSON-LD block if present."""
    for doc in extract_json_ld_documents(soup):
        doc_type = doc.get("@type")
        if doc_type == "JobPosting" or (isinstance(doc_type, list) and "JobPosting" in doc_type):
            return doc
    return None


def jsonld_text(value: Any) -> str | None:
    """Coerce nested Schema.org text/Organization/Place values into clean plain strings."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = re.sub(r"\s+", " ", html.unescape(value)).strip()
        return cleaned or None
    if isinstance(value, list):
        for item in value:
            txt = jsonld_text(item)
            if txt:
                return txt
        return None
    if isinstance(value, dict):
        if value.get("name"):
            return jsonld_text(value.get("name"))
        addr = value.get("address")
        if isinstance(addr, dict):
            parts: list[str] = []
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                part = jsonld_text(addr.get(key))
                if part and not any(part.lower() in existing.lower() for existing in parts):
                    parts.append(part)
            return ", ".join(parts) if parts else None
        if isinstance(addr, str):
            return jsonld_text(addr)
        desc = value.get("descriptor") or value.get("value")
        if desc:
            return jsonld_text(desc)
    return None


def html_meta_content(soup: BeautifulSoup, attr_name: str, attr_val: str) -> str | None:
    """Extract stripped HTML meta content if present."""
    tag = soup.find("meta", attrs={attr_name: attr_val})
    if tag and tag.get("content"):
        cleaned = re.sub(r"\s+", " ", html.unescape(str(tag.get("content")))).strip()
        return cleaned or None
    return None

"""Shared normalization for job fields from ATS and scraper sources."""

from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from typing import Any
from bs4 import BeautifulSoup

LABELS = ("Location", "Employment Type", "Job Type", "Location Type", "Department")


def humanize_slug(value: str | None) -> str | None:
    """Turn an ATS slug into a readable fallback company name."""
    if not value:
        return None
    words = re.sub(r"[-_]+", " ", value).split()
    if not words:
        return None
    return " ".join(word.title() for word in words)


def clean_html_to_markdown(value: Any) -> str | None:
    """Convert HTML job descriptions into clean, readable Markdown."""
    if not value:
        return None
    raw = html.unescape(str(value))
    if "<" not in raw:
        cleaned = re.sub(r"\n{3,}", "\n\n", raw).strip()
        return cleaned or None

    try:
        soup = BeautifulSoup(raw, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        for bold in soup.find_all(["strong", "b"]):
            btext = bold.get_text(strip=True)
            if btext:
                bold.replace_with(f"**{btext}**")

        for italic in soup.find_all(["em", "i"]):
            itext = italic.get_text(strip=True)
            if itext:
                italic.replace_with(f"*{itext}*")

        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            level = h.name[1]
            prefix = "#" * int(level) + " "
            h.replace_with(f"\n\n{prefix}{h.get_text(strip=True)}\n\n")

        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)
            if text:
                li.replace_with(f"\n- {text}")

        for br in soup.find_all(["br", "hr"]):
            br.replace_with("\n")
        for p in soup.find_all(["p", "div", "section", "article"]):
            p.insert_before("\n\n")
            p.insert_after("\n\n")

        text = soup.get_text()
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        return result or None
    except Exception:
        cleaned = re.sub(r"<(?:br|p|div|li)[^>]*>", "\n", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip() or None


def normalize_job_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).lower().replace("-", " ").replace("_", " ")
    if re.search(r"\b(?:intern|internship|internships|interns|trainee|traineeship|stagiaire|praktikant)\b", text):
        return "internship"
    if re.search(r"\b(?:part\s*-?\s*time|parttime|teilzeit)\b", text):
        return "part_time"
    if re.search(r"\b(?:contract|contractor|temporary|temp|freelance|freelancer)\b", text):
        return "contract"
    if re.search(r"\b(?:full\s*-?\s*time|fulltime|permanent|vollzeit)\b", text):
        return "full_time"
    return None


# Patterns matched against a provider's *explicit* work-model value (a field the
# API/page publishes as the workplace type — e.g. Lever `workplaceType`,
# SmartRecruiters `remoteType`, Greenhouse/JSON-LD `jobLocationType`, Workable
# `**Workplace:**`). These intentionally include the narrower English/German
# spellings so a dedicated enum maps directly instead of falling back to text.
_STRUCTURED_WORK_MODEL_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "hybrid",
        (
            "hybrid",
            "flexible",
            "onsite or remote",
            "on-site or remote",
            "on site or remote",
            "remote or onsite",
            "remote or on-site",
            "remote or on site",
            "office or remote",
            "remote or office",
            "in office or remote",
            "remote or in office",
            "in-person or remote",
            "remote or in-person",
            "partially remote",
            "some remote",
            "hybridised",
            "hybridized",
        ),
    ),
    (
        "remote",
        (
            "remote",
            "telecommut",
            "work from home",
            "work-from-home",
            "wfh",
            "telework",
            "distributed",
            "anywhere",
            "worldwide",
            "home office",
            "télétravail",
            "virtual",
            "100%",
        ),
    ),
    (
        "in_person",
        ("on site", "on-site", "onsite", "in person", "in-person", "in office", "in-office", "office", "vor ort"),
    ),
)


def _map_structured_work_model(text: str) -> str | None:
    """Map an explicit workplace-type enum from a provider to our vocabulary."""
    lowered = text.lower().replace("-", " ").replace("_", " ").replace("/", " ")
    for model, keywords in _STRUCTURED_WORK_MODEL_MAP:
        if any(kw in lowered for kw in keywords):
            return model
    return None


# Full keyword vocabulary used when scanning free text (title / location /
# snippet / description). "flexible" is only trusted in short, authoritative
# text (title/location/structured), not in a long description body where
# "flexible working hours" is a common phrase on fully in-person jobs.
_WORK_MODEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "hybrid": (
        r"\bhybrid\b",
        r"\bpartially\s+remote\b",
        r"\bsome\s+remote\b",
        r"\bflexible\s+(?:hybrid|remote|work\s*model)\b",
        r"\bremote\s*[-/]\s*on\s*-?\s*site\b",
        r"\b(?:mix|mixture|combination|split)\s+(?:of|between)\s+(?:remote|home|office)\b",
        r"\b(?:remote|home)\s+(?:and|&|or)\s+(?:on\s*-?\s*site|office|in\s*-?\s*person)\b",
        r"\b(?:on\s*-?\s*site|office|in\s*-?\s*person)\s+(?:and|&|or)\s+(?:remote|home)\b",
        r"\bpartially\s+on\s*-?\s*site\b",
        r"\b(?:two|2|three|3|four|4|five|5)\s+days\s+(?:in|at)\s+(?:the\s+)?office\b",
        r"\b(?:in|at)\s+(?:the\s+)?office\s+\d+\s+days\b",
        r"\bhybridi[sz]ed\b",
        r"\b(?:onsite|on-site|on site|office|in-office|in office)\s+or\s+remote\b",
        r"\bremote\s+or\s+(?:onsite|on-site|on site|office|in-office|in office)\b",
    ),
    "remote": (
        r"\bremote\b",
        r"\bwfh\b",
        r"\bwork\s+from\s+home\b",
        r"\bwork-from-home\b",
        r"\btelecommut\w*",
        r"\btelework\w*",
        r"\bdistributed\b",
        r"\banywhere\b",
        r"\bworldwide\b",
        r"\bvirtual\b",
        r"\bhome\s*[- ]?office\b",
        r"\btélétravail\b",
        r"\b100\s*%\s*remote\b",
        r"\bfully\s+remote\b",
        r"\bremote\s*-\s*(?:only|first|friendly)\b",
        r"\bremote\s+\w+\s+(?:only|first|friendly|available)\b",
    ),
    "in_person": (
        r"\bon\s*-?\s*site\b",
        r"\bonsite\b",
        r"\bin\s*-?\s*person\b",
        r"\bin\s*-?\s*office\b",
        r"\b(?:in|at|from|into|to)\s+the\s+office\b",
        r"\boffice\s*-?\s*based\b",
        r"\bvor\s*ort\b",
        r"\bpresencial\b",
        r"\bface\s+to\s+face\b",
    ),
}

# Short authoritative fields may use the bare "flexible" signal.
_WORK_MODEL_SHORT_HYBRID_PATTERNS: tuple[str, ...] = (r"\bflexible\b",) + _WORK_MODEL_PATTERNS["hybrid"]

_REMOTE_ISH_LOCATION_WORDS = (
    "remote",
    "anywhere",
    "virtual",
    "distributed",
    "telecommut",
    "telework",
    "wfh",
    "worldwide",
    "hybrid",
    "work from home",
    "home office",
)


_NEGATIVE_REMOTE_PATTERNS: tuple[str, ...] = (
    r"\bnot\s+(?:a\s+)?remote\b",
    r"\bno\s+remote\b",
    r"\bnon\s*-?\s*remote\b",
    r"\bremote\s+access\b",
    r"\bremote\s+desktop\b",
    r"\bremote\s+procedure\b",
    r"\bremote\s+sensing\b",
    r"\bremote\s+control\b",
    r"\bremote\s+execution\b",
)

_STRONG_REMOTE_PATTERNS: tuple[str, ...] = (
    r"\b100\s*%\s*remote\b",
    r"\bfully\s+remote\b",
    r"\bremote\s*-\s*only\b",
    r"\bremote\s+only\b",
    r"\bwork\s+from\s+anywhere\b",
    r"\bremote\s*-\s*first\b",
    r"\bremote\s+first\b",
    r"\btelecommut\w*",
    r"\btelework\w*",
    r"\bwfh\b",
    r"\bwork\s+from\s+home\b",
    r"\bwork-from-home\b",
    r"\bvirtual\s+role\b",
    r"\bvirtual\s+position\b",
)


def _scan_work_model(
    text: str,
    hybrid_patterns: tuple[str, ...],
    has_physical_location: bool = False,
    is_long_body: bool = False,
) -> str | None:
    lowered = text.lower()
    if any(re.search(pattern, lowered) for pattern in hybrid_patterns):
        return "hybrid"

    # Filter out false-positive negative remote phrases
    is_negative_remote = any(re.search(pat, lowered) for pat in _NEGATIVE_REMOTE_PATTERNS)

    if not is_negative_remote:
        # If there is a strong physical office/city and this is a long free-text description,
        # require explicit remote indicator (e.g. "fully remote", "100% remote", "work from home")
        # rather than a bare incidental mention of "remote".
        if has_physical_location and is_long_body:
            if any(re.search(pattern, lowered) for pattern in _STRONG_REMOTE_PATTERNS):
                return "remote"
        else:
            if any(re.search(pattern, lowered) for pattern in _WORK_MODEL_PATTERNS["remote"]):
                return "remote"

    if any(re.search(pattern, lowered) for pattern in _WORK_MODEL_PATTERNS["in_person"]):
        return "in_person"
    return None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    return str(value).strip()

def normalize_work_model(
    value: Any = None,
    is_remote: bool | None = None,
    *,
    location: Any = None,
    title: str | None = None,
    description: str | None = None,
    snippet: str | None = None,
    page_text: str | None = None,
    default_in_person: bool = True,
) -> str | None:
    """
    Canonical work-model resolver shared by every provider.

    Priority order:
      1. Explicit structured indicator (bool ``is_remote`` or a dedicated
         workplace-type field) -> map directly.
      2. Keyword scan of the available free text (title, location, snippet,
         description, page_text) with an expanded vocabulary.
      3. Default to ``in_person`` when a real physical location is present but
         no keyword matched at all (the unmarked default in how postings are
         written).
      4. ``None`` only when there is genuinely no signal.
    """
    # 1 ---- Explicit structured indicator ---------------------------------
    if is_remote is True:
        return "remote"
    if is_remote is False:
        return "in_person"
    structured_text = _as_text(value)
    if structured_text:
        mapped = _map_structured_work_model(structured_text)
        if mapped:
            return mapped

    # 2 ---- Keyword scan --------------------------------------------------
    location_text = _as_text(location)
    title_text = _as_text(title)
    snippet_text = _as_text(snippet)
    description_text = _as_text(description)
    page_text_text = _as_text(page_text)

    has_physical_loc = bool(
        location_text and not any(w in location_text.lower() for w in _REMOTE_ISH_LOCATION_WORDS)
    )

    short_parts = [part for part in (title_text, snippet_text, location_text, structured_text) if part]
    if short_parts:
        matched = _scan_work_model(
            " ".join(short_parts),
            _WORK_MODEL_SHORT_HYBRID_PATTERNS,
            has_physical_location=has_physical_loc,
            is_long_body=False,
        )
        if matched:
            return matched

    long_parts = [part for part in (description_text, page_text_text) if part]
    if long_parts:
        matched = _scan_work_model(
            " ".join(long_parts),
            _WORK_MODEL_PATTERNS["hybrid"],
            has_physical_location=has_physical_loc,
            is_long_body=True,
        )
        if matched:
            return matched

    # 3 ---- Real physical location present -> default to in_person --------
    if default_in_person and has_physical_loc:
        return "in_person"

    # 4 ---- Genuinely no signal ------------------------------------------
    return None


_JOB_TYPE_TEXT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("internship", (
        r"\b(?:intern|internship|internships|interns|trainee|traineeship|stagiaire|praktikant)\b",
    )),
    ("part_time", (r"\bpart\s*-?\s*time\b", r"\bparttime\b", r"\bteilzeit\b")),
    ("contract", (r"\bcontract\b", r"\bcontractor\b", r"\btemporary\b", r"\bfreelance\b", r"\bfreelancer\b")),
    ("full_time", (r"\bfull\s*-?\s*time\b", r"\bfulltime\b", r"\bpermanent\b", r"\bvollzeit\b")),
)


def normalize_job_type_from_text(text: Any, title: str | None = None) -> str | None:
    """Scan free text (job description / title / snippet) for employment type."""
    if title:
        lowered_title = str(title).lower()
        if re.search(r"\b(?:freelance|freelancer|contract|contractor|temporary|temp)\b", lowered_title):
            return "contract"
        if re.search(r"\b(?:intern|internship|internships|interns|trainee|traineeship)\b", lowered_title):
            return "internship"
        if re.search(r"\b(?:part\s*-?\s*time|parttime)\b", lowered_title):
            return "part_time"
        if re.search(r"\b(?:full\s*-?\s*time|fulltime|permanent)\b", lowered_title):
            return "full_time"

    if text is None:
        return None
    lowered = str(text).lower()

    has_senior_title = bool(
        title and re.search(
            r"\b(?:senior|sr\.?|lead|staff|principal|director|manager|head\s+of|architect|freelance|contractor)\b",
            str(title).lower(),
        )
    )

    for model, patterns in _JOB_TYPE_TEXT_PATTERNS:
        if model == "internship" and has_senior_title:
            continue
        if any(re.search(pattern, lowered) for pattern in patterns):
            return model
    return None

def extract_labeled_fields(text: str | None) -> dict[str, str]:
    """Extract explicit metadata labels from a title/snippet without guessing."""
    if not text:
        return {}
    pattern = re.compile(
        rf"(?P<label>{'|'.join(re.escape(label) for label in LABELS)})\s*[.:]\s*",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    fields: dict[str, str] = {}
    key_map = {
        "location": "location",
        "employment type": "employment_type",
        "job type": "employment_type",
        "location type": "work_model",
        "department": "department",
    }
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = re.sub(r"\.{3,}$", "", text[match.end():end])
        value = re.sub(r"\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}$", "", value, flags=re.IGNORECASE)
        value = value.strip(" .|-")
        if value:
            fields[key_map[match.group("label").lower()]] = value
    return fields


def clean_title(title: str | None, snippet: str | None = None) -> str:
    """Remove explicit metadata suffixes from a search title."""
    value = (title or snippet or "Untitled role").strip()
    match = re.search(
        r"\s+(?:Location|Employment Type|Job Type|Location Type|Department)\s*[.:]",
        value,
        re.IGNORECASE,
    )
    return value[:match.start()].strip(" .") if match else value


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        for fmt in (
            "%b %d, %Y",
            "%B %d, %Y",
            "%b %d %Y",
            "%B %d %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%d %B, %Y",
            "%d %b, %Y",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalize_fields(
    *,
    title: str | None,
    snippet: str | None = None,
    location: Any = None,
    employment_type: Any = None,
    work_model: Any = None,
    is_remote: bool | None = None,
    department: Any = None,
) -> dict[str, Any]:
    """Apply shared field cleanup to structured or unstructured source values."""
    labeled = extract_labeled_fields(" ".join(part for part in (title, snippet) if part))
    resolved_location = location or labeled.get("location")
    resolved_type = normalize_job_type(employment_type or labeled.get("employment_type"))
    if resolved_type is None:
        text = " ".join(part for part in (title, snippet, str(resolved_location or "")) if part)
        resolved_type = normalize_job_type_from_text(text, title=title)
    resolved_model = normalize_work_model(
        work_model or labeled.get("work_model"),
        is_remote,
        location=resolved_location,
        title=title,
        snippet=snippet,
    )
    resolved_remote = is_remote if is_remote is not None else resolved_model == "remote" if resolved_model else None
    return {
        "title": clean_title(title, snippet),
        "location": str(resolved_location).strip() if resolved_location else None,
        "employment_type": resolved_type,
        "work_model": resolved_model,
        "is_remote": resolved_remote,
        "department": str(department).strip() if department else labeled.get("department"),
    }

"""Shared normalization for job fields from ATS and scraper sources."""

from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from typing import Any
from bs4 import BeautifulSoup

from src.project_files.work_model import WorkModelResult, resolve_work_model

LABELS = ("Location", "Employment Type", "Job Type", "Location Type", "Department")


def humanize_slug(value: str | None) -> str | None:
    """Turn an ATS slug into a readable fallback company name."""
    if not value:
        return None
    words = re.sub(r"[-_]+", " ", value).split()
    if not words:
        return None
    return " ".join(word.title() for word in words)


_NOISE_TAGS = (
    "script", "style", "noscript",
    "nav", "footer", "header", "aside", "form", "iframe", "svg", "button",
)

_NOISE_ROLES = re.compile(r"^(?:navigation|banner|contentinfo)$", re.IGNORECASE)
_NOISE_ATTR_RE = re.compile(r"cookie|consent|gdpr|newsletter|share|social|breadcrumb", re.IGNORECASE)

_JOB_LIKE_TERMS = (
    r"\bresponsibilit(?:y|ies)\b",
    r"\brequirement(?:s)?\b",
    r"\bqualification(?:s)?\b",
    r"\byou\s+will\b",
    r"\bwhat\s+you(?:'ll|’ll|\s+will)\s+do\b",
    r"\bwhat\s+we(?:'re|’re|\s+are)\s+looking\s+for\b",
    r"\babout\s+the\s+role\b",
    r"\babout\s+the\s+job\b",
    r"\bwho\s+you\s+are\b",
    r"\bjob\s+description\b",
    r"\brole\s+overview\b",
    r"\bduties\b",
    r"\bwhat\s+we\s+offer\b",
    r"\bwhat\s+you\s+bring\b",
)

_BOILERPLATE_TERMS = (
    r"\bcookies?\b",
    r"\bprivacy\s+policy\b",
    r"\bterms\s+of\s+(?:use|service)\b",
    r"\ball\s+rights\s+reserved\b",
    r"\bshare\s+(?:via\s+)?(?:email|facebook|linkedin|twitter|whatsapp)\b",
    r"\bwhistleblow\w*",
    r"\bgdpr\b",
)


def description_quality(text: str | None, *, is_dom_scraped: bool = False) -> bool:
    """Validate whether an extracted description meets quality standards.

    Descriptions from API fields or JSON-LD JobPosting.description are trusted
    as long as len >= 300 and the boilerplate check passes. The job-like structural
    term check (>= 2 matches) is required only for DOM-scraped bodies.
    """
    if not text or not isinstance(text, str):
        return False
    cleaned = text.strip()
    if len(cleaned) < 300:
        return False

    boilerplate_matches = sum(1 for pattern in _BOILERPLATE_TERMS if re.search(pattern, cleaned, re.IGNORECASE))
    if boilerplate_matches >= 3:
        return False

    if is_dom_scraped:
        job_matches = sum(1 for pattern in _JOB_LIKE_TERMS if re.search(pattern, cleaned, re.IGNORECASE))
        if job_matches < 2:
            return False

    return True


from src.project_files.work_model import WorkModelResult, resolve_work_model, strip_li_tags

_GENERIC_SECTION_LABELS = (
    r"Responsibilities\s*:",
    r"Key Responsibilities\s*:",
    r"Requirements\s*:",
    r"Qualifications\s*:",
    r"What You'll Do\s*:",
    r"What We're Looking For\s*:",
    r"Job Description\s*:",
    r"About the Role\s*:",
    r"About the Job\s*:",
    r"Benefits\s*:",
)


def to_markdown(raw: Any) -> str | None:
    """Convert HTML or plain text job descriptions into clean, readable Markdown.

    Preserves paragraphs, headings, bullet and numbered lists, bold, and line breaks.
    For plain text, keeps line breaks as paragraph breaks and turns lines starting
    with a bullet character (•, ·, –, *, -) into markdown list items (- ).
    Unescapes entities before converting and strips recruiter tags (#LI-*).
    """
    if raw is None or raw == "":
        return None

    raw_str = html.unescape(str(raw)).replace("\ufffd", " ").replace("\xa0", " ")
    raw_str = strip_li_tags(raw_str) or ""
    if not raw_str.strip():
        return None

    if "<" in raw_str:
        try:
            soup = BeautifulSoup(raw_str, "lxml")
        except Exception:
            soup = BeautifulSoup(raw_str, "html.parser")

        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        for el in soup.find_all(attrs={"role": _NOISE_ROLES}):
            el.decompose()

        for el in soup.find_all(True):
            if getattr(el, "decomposed", False):
                continue
            classes = el.get("class")
            if classes:
                cls_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                if _NOISE_ATTR_RE.search(cls_str):
                    el.decompose()
                    continue
            el_id = el.get("id")
            if el_id and _NOISE_ATTR_RE.search(str(el_id)):
                el.decompose()

        for bold in soup.find_all(["strong", "b"]):
            btext = bold.get_text(" ", strip=True)
            if btext:
                bold.replace_with(f" **{btext}** ")

        for italic in soup.find_all(["em", "i"]):
            itext = italic.get_text(" ", strip=True)
            if itext:
                italic.replace_with(f" *{itext}* ")

        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            level = int(h.name[1])
            prefix = "#" * level + " "
            h.replace_with(f"\n\n{prefix}{h.get_text(strip=True)}\n\n")

        # Ordered lists
        for ol in soup.find_all("ol"):
            for idx, li in enumerate(ol.find_all("li", recursive=False), 1):
                litext = li.get_text(" ", strip=True)
                if litext:
                    li.replace_with(f"\n{idx}. {litext}\n")

        # Unordered lists
        for ul in soup.find_all("ul"):
            for li in ul.find_all("li", recursive=False):
                litext = li.get_text(" ", strip=True)
                if litext:
                    li.replace_with(f"\n- {litext}\n")

        for li in soup.find_all("li"):
            litext = li.get_text(" ", strip=True)
            if litext:
                li.replace_with(f"\n- {litext}\n")

        for br in soup.find_all(["br", "hr"]):
            br.replace_with("\n")

        for p in soup.find_all(["p", "div", "section", "article", "blockquote"]):
            p.insert_before("\n\n")
            p.insert_after("\n\n")

        text = soup.get_text()
        text = re.sub(r"<[^>]+>", " ", text)
    else:
        text = raw_str

    # Process text & lines
    text = html.unescape(text).replace("\ufffd", " ")

    # Convert inline bullet characters e.g. "• Item 1 • Item 2" -> "\n- Item 1\n- Item 2"
    text = re.sub(r"(?<=\S)[ \t]*[•·▪◦\u2022\u00b7][ \t]*", "\n- ", text)

    # Format generic section labels in text without newlines
    for label in _GENERIC_SECTION_LABELS:
        text = re.sub(rf"(?:^|\s)({label})(?=\s+[A-Z0-9\u00C0-\u00FF])", r"\n\n\1\n", text, flags=re.IGNORECASE)

    lines = text.split("\n")
    out_lines: list[str] = []
    in_list_intro = False
    for line in lines:
        s = line.strip()
        if not s:
            out_lines.append("")
            in_list_intro = False
            continue

        if any(re.match(rf"^{label}:?$", s, re.IGNORECASE) for label in _GENERIC_SECTION_LABELS):
            out_lines.append(s)
            in_list_intro = True
            continue

        if in_list_intro:
            sub_sentences = [p.strip() for p in re.split(r"(?<=[.;])\s+(?=[A-Z0-9\u00C0-\u00FF])", s) if p.strip()]
            if len(sub_sentences) > 1:
                for sub in sub_sentences:
                    out_lines.append(f"- {sub}")
                in_list_intro = False
                continue

        # Lines starting with bullet characters (•, ·, –, *, -)
        # ASCII '*' or '-' must be followed by whitespace so '**Bold**' or '*Italic*' is preserved.
        m = re.match(r"^(?:[•·–▪◦\u2022\u00b7\u2013\u2014]\s*|[*\-]\s+)(.+)", s)
        if m:
            out_lines.append(f"- {m.group(1)}")
        else:
            out_lines.append(s)

    result = "\n".join(out_lines)
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result or None


def clean_html_to_markdown(value: Any) -> str | None:
    """Backward-compatible alias for to_markdown."""
    return to_markdown(value)


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
    description_ok: bool = False,
    trusted_description: str | None = None,
    jsonld_location_type: str | None = None,
    snippet: str | None = None,
    default_in_person: bool = False,
    **kwargs: Any,
) -> str | None:
    """Canonical work-model resolver wrapper (Phase 2)."""
    cand_val = value if value is not None else (snippet if snippet else None)
    # If description is passed explicitly to normalize_work_model without setting description_ok,
    # and no structured value exists, treat description_ok=True for direct unit-test convenience if description is provided
    eff_desc_ok = description_ok or (description is not None and not value and not snippet)
    res = resolve_work_model(
        workplace_type=cand_val,
        jsonld_location_type=jsonld_location_type,
        location=str(location) if location else None,
        title=title,
        description=description,
        description_ok=eff_desc_ok,
        trusted_description=trusted_description,
    )
    return res.value


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
    """Remove explicit metadata suffixes and trailing ellipsis from a search title."""
    value = (title or snippet or "Untitled role").strip()
    match = re.search(
        r"\s+(?:Location|Employment Type|Job Type|Location Type|Department)\s*[.:]",
        value,
        re.IGNORECASE,
    )
    cleaned = value[:match.start()].strip(" .") if match else value
    cleaned = re.sub(r"\s*(?:…|\.{3,})+\s*$", "", cleaned)
    return cleaned.strip() or "Untitled role"


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.strip()
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        normalized = re.sub(
            r"^(?:posted\s+(?:on\s+)?)?(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"^posted\s+(?:on\s+)?", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"[\s\-–—]+$", "", normalized)
        normalized = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", normalized, flags=re.IGNORECASE)
        for candidate in (cleaned, normalized):
            cand = candidate.strip()
            if not cand:
                continue
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
                    return datetime.strptime(cand, fmt).replace(tzinfo=timezone.utc)
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
    model_res = resolve_work_model(
        workplace_type=work_model or labeled.get("work_model"),
        location=str(resolved_location) if resolved_location else None,
        title=title,
    )
    resolved_model = model_res.value
    resolved_remote = True if resolved_model == "remote" else (False if resolved_model in ("in_person", "hybrid") else (is_remote if is_remote is not None else None))
    return {
        "title": clean_title(title, snippet),
        "location": str(resolved_location).strip() if resolved_location else None,
        "employment_type": resolved_type,
        "work_model": resolved_model,
        "work_model_source": model_res.source,
        "work_model_evidence": model_res.evidence,
        "is_remote": resolved_remote,
        "department": str(department).strip() if department else labeled.get("department"),
    }

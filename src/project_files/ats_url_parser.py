"""
ATS URL parser — takes a raw URL from Serper and returns a structured object
with the company slug and job ID needed to call the ATS API directly.

Returns None for anything that is not a real job page URL:
  - Blog posts
  - Company homepages
  - Search result pages
  - Partial path matches

Never raises. All errors are swallowed and return None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

from loguru import logger

from src.project_files.url_safety import is_safe_public_https_url


@dataclass
class ParsedATSUrl:
    ats: str            # e.g. "greenhouse", "lever", "ashby"
    company_slug: str   # e.g. "stripe", "openai"
    job_id: str         # e.g. "4567890" or a UUID
    raw_url: str        # original URL, kept for debugging


@dataclass(frozen=True)
class WorkdayUrlParts:
    """Structured components of a verified Workday posting or /apply URL."""

    tenant: str
    tenant_raw: str
    wd_host: str | None
    netloc: str
    locale: str | None
    site_id: str
    location_segment: str | None
    job_slug: str
    had_apply_suffix: bool
    raw_url: str
    cxs_url: str
    canonical_posting_url: str
    job_id: str


SUPPORTED_ATS_PATTERNS: frozenset[str] = frozenset({
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "workable",
    "bamboohr",
    "recruitee",
    "jobvite",
    "teamtailor",
    "personio",
    "icims",
    "breezy",
    "jazzhr",
    "jobadder",
    "taleo",
    "avature",
    "workday",
    "successfactors",
})


# ---------------------------------------------------------------------------
# Compiled regex patterns (one per URL variant)
# ---------------------------------------------------------------------------

# Greenhouse — three recognized host variants:
#   https://boards.greenhouse.io/{slug}/jobs/{id}
#   https://job-boards.greenhouse.io/{slug}/jobs/{id}
#   https://job-boards.eu.greenhouse.io/{slug}/jobs/{id}
# Accepts numeric and hyphenated numeric IDs such as 5131342007-8.
GREENHOUSE_RECOGNIZED_HOSTS: frozenset[str] = frozenset({
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
})
_GREENHOUSE_JOB_ID_RE = re.compile(r"^\d+(?:-\d+)?$")
_GREENHOUSE_NON_BOARD_PATHS: frozenset[str] = frozenset({
    "embed",
    "api",
    "users",
    "assets",
    "static",
    "img",
    "images",
    "jobs",
    "search",
    "careers",
    "error",
    "auth",
})


def canonicalize_recognized_greenhouse_url(url: str) -> str:
    """
    Upgrade cleartext ``http://`` URLs on recognized Greenhouse hosts to ``https://``.

    Never generalizes to arbitrary domains.
    """
    if not url or not isinstance(url, str):
        return url
    stripped = url.strip()
    if not stripped:
        return url
    try:
        parsed = urlparse(stripped)
    except Exception:
        return url
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() == "http" and host in GREENHOUSE_RECOGNIZED_HOSTS:
        netloc = parsed.netloc.lower()
        return urlunparse(("https", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return url


_GH_BOARDS = re.compile(
    r"^https?://boards\.greenhouse\.io/([^/?#]+)/jobs/(\d+(?:-\d+)?)/?$",
    re.IGNORECASE,
)
_GH_JOB_BOARDS = re.compile(
    r"^https?://job-boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)/jobs/(\d+(?:-\d+)?)/?$",
    re.IGNORECASE,
)

# Lever:
#   https://jobs.lever.co/{slug}/{uuid}
_UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_LEVER = re.compile(
    rf"^https?://jobs\.lever\.co/([^/?#]+)/({_UUID_RE})(?:/apply)?/?$",
    re.IGNORECASE,
)
_LEVER_BOARD_ROOT = re.compile(
    r"^https?://jobs\.lever\.co/([^/?#]+)/?$",
    re.IGNORECASE,
)

# Ashby:
#   https://jobs.ashbyhq.com/{slug}/{uuid}
_ASHBY = re.compile(
    rf"^https?://jobs\.ashby(?:hq)?\.com/([^/?#]+)/({_UUID_RE})(?:/application)?/?$",
    re.IGNORECASE,
)

# SmartRecruiters:
#   https://jobs.smartrecruiters.com/{CompanyName}/{job_id}
#   job_id is a long numeric string (not UUID)
_SMARTREC = re.compile(
    r"^https?://jobs\.smartrecruiters\.com/([^/?#]+)/(\d+)(?:-[^/?#]+)?/?$",
    re.IGNORECASE,
)

# Workable — two variants:
#   https://{slug}.workable.com/jobs/{job_id}
#   https://apply.workable.com/{slug}/j/{job_id}
_WORKABLE_SUBDOMAIN = re.compile(
    r"^https?://([^./?#]+)\.workable\.com/jobs/([^/?#]+)/?$",
    re.IGNORECASE,
)
_WORKABLE_APPLY = re.compile(
    r"^https?://apply\.workable\.com/([^/?#]+)/j/([^/?#]+)/?$",
    re.IGNORECASE,
)

# BambooHR:
#   https://{slug}.bamboohr.com/careers/{job_id}
#   job_id may be numeric or alphanumeric
_BAMBOOHR = re.compile(
    r"^https?://([^./?#]+)\.bamboohr\.com/careers/(\w+)/?$",
    re.IGNORECASE,
)

# Recruitee:
#   https://{slug}.recruitee.com/o/{job_id}-{anything}
#   The job_id is numeric; the slug after the hyphen is the human-readable title
_RECRUITEE = re.compile(
    r"^https?://([^./?#]+)\.recruitee\.com/o/(\d+)-[^/?#]+/?$",
    re.IGNORECASE,
)

_JOBVITE = re.compile(r"^https?://jobs\.jobvite\.com/([^/?#]+)/job/([^/?#]+)/?$", re.IGNORECASE)
_TEAMTAILOR_RESERVED_SUBDOMAINS: frozenset[str] = frozenset({
    "www",
    "support",
    "career",
    "careers",
    "app",
    "apps",
    "jobs",
    "assets",
    "cdn",
    "api",
    "mail",
    "blog",
    "help",
    "docs",
    "go",
    "teamtailor",
})
_TEAMTAILOR = re.compile(
    r"^https?://([a-z0-9-]+(?:\.[a-z0-9-]+)*)\.teamtailor\.com/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?jobs/(\d+)(?:-[^/?#]+)?/?$",
    re.IGNORECASE,
)
_TEAMTAILOR_JOB_PATH = re.compile(
    r"^/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?jobs/(\d+)(?:-[^/?#]+)?/?$",
    re.IGNORECASE,
)
_TEAMTAILOR_HTML_EVIDENCE = re.compile(
    r"(?:(?:images|screenshots|assets-aws)\.teamtailor-cdn\.com|teamtailor\.com/jobs|data-teamtailor|Teamtailor)",
    re.IGNORECASE,
)
_PERSONIO = re.compile(r"^https?://(?:[^./?#]+\.)?jobs\.personio\.(?:com|de)/job/([^/?#]+?)(?:-(\d+))?/?$", re.IGNORECASE)
_ICIMS = re.compile(r"^https?://(?:[^./?#]+\.)?icims\.com/jobs/(\d+)/[^/?#]+/?$", re.IGNORECASE)
_BREEZY_SUBDOMAIN = re.compile(r"^https?://(?!apply\b)([^./?#]+)\.breezy\.hr/p/([^/?#]+)(?:/[^/?#]+)?/?$", re.IGNORECASE)
_BREEZY_APPLY = re.compile(r"^https?://apply\.breezy\.hr/p/([^/?#]+)/([^/?#]+)/?$", re.IGNORECASE)
_JAZZHR = re.compile(r"^https?://(?:([^./?#]+)\.)?applytojob\.com/apply/([^/?#]+)/?$", re.IGNORECASE)
_JAZZHR_SHARE = re.compile(r"^https?://([^./?#]+)\.applytojob\.com/app/share/([^/?#]+)/?$", re.IGNORECASE)
_JOBADDER = re.compile(r"^https?://apply\.jobadder\.com/[^/?#]+/[^/?#]+/([^/?#]+)/?$", re.IGNORECASE)
_TALEO = re.compile(r"^https?://[^/?#]+\.taleo\.net/careersection/[^/?#]+/jobdetail\.ftl\?job=(\d+).*$", re.IGNORECASE)
_AVATURE = re.compile(
    r"^https?://([^/?#.]+)\.avature\.net/(?:.+/)?(?:JobDetail/[^/?#]+|job)/(\d+)(?:/[^/?#]+)?/?$",
    re.IGNORECASE,
)
_WORKDAY_HOST = re.compile(r"^([^./?#]+)(?:\.(wd\d+))?\.myworkdayjobs\.com$", re.IGNORECASE)
_WORKDAY_LOCALE = re.compile(r"^[a-z]{2}(?:-[A-Za-z]{2})?$")
_WORKDAY_RESERVED_SITE_SLUGS = frozenset({"apply", "job", "wday"})
_WORKDAY_RESERVED_SLUGS = frozenset({"apply", "job", "jobs", "search"})
_SUCCESSFACTORS = re.compile(r"^https?://jobs\.sap\.com/job/([^/?#]+)/[^/?#]+/?$", re.IGNORECASE)


_GENERIC_SLUG_STOPWORDS: frozenset[str] = frozenset({
    "personio",
    "icims",
    "breezy",
    "jazzhr",
    "jobadder",
    "sap",
    "successfactors",
    "jobs",
    "careers",
    "career",
    "apply",
    "application",
    "www",
    "app",
    "default",
    "unknown",
    "postings",
    "job",
    "portal",
})

_SYNTHETIC_SLUG_RE = re.compile(
    r"^(?:company\d+|test[-_]?company\d*|fake[-_]?(?:company)?\d*|dummy[-_]?(?:company)?\d*|placeholder[-_]?\d*)$",
    re.IGNORECASE,
)


def is_valid_board_slug(ats: str, slug: str | None) -> bool:
    """
    Validates whether a company slug represents a real, distinct employer board identifier
    rather than a generic placeholder or ATS platform name.
    """
    if not slug or not slug.strip():
        return False
    cleaned = slug.strip().lower()
    if len(cleaned) < 2:
        return False
    if cleaned in _GENERIC_SLUG_STOPWORDS:
        return False
    if _SYNTHETIC_SLUG_RE.match(cleaned):
        return False
    if cleaned == ats.lower():
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_workday_url(url: str) -> WorkdayUrlParts | None:
    """
    Authoritative parser for observed Workday job and /apply URLs.

    Supports observed host forms ({tenant}.wdN.myworkdayjobs.com and
    {tenant}.myworkdayjobs.com), optional ISO locale prefixes, optional
    middle location segments after /job/, trailing /apply suffixes, and
    query/fragment parameters without inventing unsupported patterns.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    hostname = (parsed.hostname or "").lower()
    host_match = _WORKDAY_HOST.match(hostname)
    if not host_match:
        return None

    tenant_raw = host_match.group(1).lower()
    wd_host = host_match.group(2).lower() if host_match.group(2) else None
    netloc = parsed.netloc.lower()

    segments = [seg for seg in parsed.path.split("/") if seg]
    job_indices = [idx for idx, seg in enumerate(segments) if seg.lower() == "job"]
    if not job_indices:
        return None

    job_idx = job_indices[0]
    before_job = segments[:job_idx]
    after_job = segments[job_idx + 1:]

    if len(before_job) == 1:
        locale: str | None = None
        site_id = before_job[0]
    elif len(before_job) == 2 and _WORKDAY_LOCALE.match(before_job[0]):
        locale = before_job[0]
        site_id = before_job[1]
    else:
        return None

    if not site_id or site_id.lower() in _WORKDAY_RESERVED_SITE_SLUGS:
        return None

    if not after_job:
        return None

    had_apply_suffix = False
    if len(after_job) >= 2 and after_job[-1].lower() == "apply":
        had_apply_suffix = True
        after_job = after_job[:-1]

    if len(after_job) == 1:
        location_segment: str | None = None
        job_slug = after_job[0]
    elif len(after_job) == 2:
        location_segment = after_job[0]
        job_slug = after_job[1]
    else:
        return None

    if not job_slug or job_slug.lower() in _WORKDAY_RESERVED_SLUGS:
        return None

    canonical_parts = [p for p in (locale, site_id, "job", location_segment, job_slug) if p]
    canonical_posting_url = f"https://{netloc}/{'/'.join(canonical_parts)}"
    cxs_url = f"https://{netloc}/wday/cxs/{tenant_raw}/{site_id}/job/{job_slug}"

    return WorkdayUrlParts(
        tenant=tenant_raw,
        tenant_raw=tenant_raw,
        wd_host=wd_host,
        netloc=netloc,
        locale=locale,
        site_id=site_id,
        location_segment=location_segment,
        job_slug=job_slug,
        had_apply_suffix=had_apply_suffix,
        raw_url=url,
        cxs_url=cxs_url,
        canonical_posting_url=canonical_posting_url,
        job_id=f"{site_id.lower()}__{job_slug}",
    )


def build_workday_cxs_url(url: str) -> str | None:
    """Build Workday's public CXS JSON endpoint URL from any valid posting or /apply URL."""
    parts = parse_workday_url(url)
    return parts.cxs_url if parts else None


def parse_ats_url(url: str) -> ParsedATSUrl | None:
    """
    Parse a raw Serper URL into a structured ATS reference.

    Returns None if the URL does not cleanly match any known ATS job-page pattern.
    Never raises.
    """
    if not url:
        return None

    try:
        # Strip query strings and fragments before matching — we want clean paths
        canon_url = canonicalize_recognized_greenhouse_url(url)
        parsed = urlparse(canon_url)
        # Reconstruct without query/fragment for cleaner matching
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # ── Greenhouse ────────────────────────────────────────────────────────
        m = _GH_BOARDS.match(clean_url)
        if m and m.group(1).lower() not in _GREENHOUSE_NON_BOARD_PATHS:
            return ParsedATSUrl(ats="greenhouse", company_slug=m.group(1), job_id=m.group(2), raw_url=canon_url)

        m = _GH_JOB_BOARDS.match(clean_url)
        if m and m.group(1).lower() not in _GREENHOUSE_NON_BOARD_PATHS:
            return ParsedATSUrl(ats="greenhouse", company_slug=m.group(1), job_id=m.group(2), raw_url=canon_url)

        host_lower = (parsed.hostname or "").lower()
        if host_lower in GREENHOUSE_RECOGNIZED_HOSTS and parsed.query:
            q = parse_qs(parsed.query, keep_blank_values=False)
            path_clean = (parsed.path or "").strip("/")
            # Recognized embed endpoint: /embed/job_app?for={slug}&token={id} (or gh_jid)
            if path_clean.lower() == "embed/job_app":
                for_slug = (q.get("for") or [""])[0].strip()
                tok = ((q.get("token") or q.get("gh_jid") or [""])[0]).strip()
                if (
                    for_slug
                    and for_slug.lower() not in _GREENHOUSE_NON_BOARD_PATHS
                    and _GREENHOUSE_JOB_ID_RE.match(tok)
                ):
                    return ParsedATSUrl(ats="greenhouse", company_slug=for_slug, job_id=tok, raw_url=canon_url)
            # Board or listing route carrying ?gh_jid={id} as sole identifier
            gh_jid = (q.get("gh_jid") or [""])[0].strip()
            segments = [seg for seg in path_clean.split("/") if seg]
            if (
                gh_jid
                and _GREENHOUSE_JOB_ID_RE.match(gh_jid)
                and segments
                and len(segments) <= 2
                and (len(segments) == 1 or segments[1].lower() == "jobs")
                and segments[0].lower() not in _GREENHOUSE_NON_BOARD_PATHS
            ):
                return ParsedATSUrl(ats="greenhouse", company_slug=segments[0], job_id=gh_jid, raw_url=canon_url)

        # ── Lever ─────────────────────────────────────────────────────────────
        m = _LEVER.match(clean_url)
        if m and is_valid_board_slug("lever", m.group(1)):
            return ParsedATSUrl(ats="lever", company_slug=m.group(1), job_id=m.group(2).lower(), raw_url=url)

        # ── Ashby ─────────────────────────────────────────────────────────────
        m = _ASHBY.match(clean_url)
        if m:
            return ParsedATSUrl(ats="ashby", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        # ── SmartRecruiters ───────────────────────────────────────────────────
        m = _SMARTREC.match(clean_url)
        if m:
            return ParsedATSUrl(ats="smartrecruiters", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        # ── Workable ──────────────────────────────────────────────────────────
        m = _WORKABLE_SUBDOMAIN.match(clean_url)
        if m:
            return ParsedATSUrl(ats="workable", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        m = _WORKABLE_APPLY.match(clean_url)
        if m:
            return ParsedATSUrl(ats="workable", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        # ── BambooHR ──────────────────────────────────────────────────────────
        m = _BAMBOOHR.match(clean_url)
        if m:
            return ParsedATSUrl(ats="bamboohr", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        # ── Recruitee ─────────────────────────────────────────────────────────
        m = _RECRUITEE.match(clean_url)
        if m:
            return ParsedATSUrl(ats="recruitee", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        m = _JOBVITE.match(clean_url)
        if m:
            return ParsedATSUrl(ats="jobvite", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        m = _TEAMTAILOR.match(clean_url)
        if m:
            sub_chain = m.group(1).lower()
            first_label = sub_chain.split(".")[0]
            if first_label not in _TEAMTAILOR_RESERVED_SUBDOMAINS and is_valid_board_slug("teamtailor", sub_chain):
                return ParsedATSUrl(ats="teamtailor", company_slug=sub_chain, job_id=m.group(2), raw_url=url)

        m = _PERSONIO.match(clean_url)
        if m:
            netloc_parts = parsed.netloc.split(".")
            if len(netloc_parts) >= 3 and netloc_parts[0].lower() not in ("jobs", "www"):
                slug = netloc_parts[0].lower()
            else:
                raw_token = m.group(1).lower() if m.group(1) else ""
                slug = raw_token if is_valid_board_slug("personio", raw_token) else "personio"
            return ParsedATSUrl(ats="personio", company_slug=slug, job_id=m.group(2) or m.group(1), raw_url=url)

        m = _ICIMS.match(clean_url)
        if m:
            netloc_parts = parsed.netloc.split(".")
            if len(netloc_parts) >= 3 and netloc_parts[0].lower() not in ("jobs", "www"):
                slug = netloc_parts[0].lower().removeprefix("careers-")
            else:
                slug = "icims"
            return ParsedATSUrl(ats="icims", company_slug=slug, job_id=m.group(1), raw_url=url)

        m = _BREEZY_SUBDOMAIN.match(clean_url)
        if m:
            return ParsedATSUrl(ats="breezy", company_slug=m.group(1).lower(), job_id=m.group(2), raw_url=url)

        m = _BREEZY_APPLY.match(clean_url)
        if m:
            return ParsedATSUrl(ats="breezy", company_slug="breezy", job_id=m.group(1), raw_url=url)

        m = _JAZZHR.match(clean_url)
        if m:
            raw_sub = m.group(1).lower() if m.group(1) else ""
            slug = raw_sub if is_valid_board_slug("jazzhr", raw_sub) else "jazzhr"
            return ParsedATSUrl(ats="jazzhr", company_slug=slug, job_id=m.group(2), raw_url=url)

        m = _JAZZHR_SHARE.match(clean_url)
        if m:
            return ParsedATSUrl(ats="jazzhr", company_slug=m.group(1).lower(), job_id=m.group(2), raw_url=url)

        m = _JOBADDER.match(clean_url)
        if m:
            return ParsedATSUrl(ats="jobadder", company_slug="jobadder", job_id=m.group(1), raw_url=url)

        m = _TALEO.match(url)
        if m:
            netloc_parts = parsed.netloc.split(".")
            slug = netloc_parts[0].lower() if netloc_parts else parsed.netloc
            return ParsedATSUrl(ats="taleo", company_slug=slug, job_id=m.group(1), raw_url=url)

        m = _AVATURE.match(clean_url)
        if m:
            return ParsedATSUrl(ats="avature", company_slug=m.group(1), job_id=m.group(2), raw_url=url)

        wd_parts = parse_workday_url(url)
        if wd_parts is not None:
            return ParsedATSUrl(
                ats="workday",
                company_slug=wd_parts.tenant,
                job_id=wd_parts.job_id,
                raw_url=url,
            )

        m = _SUCCESSFACTORS.match(clean_url)
        if m:
            return ParsedATSUrl(ats="successfactors", company_slug="sap", job_id=m.group(1), raw_url=url)

    except Exception as exc:
        logger.warning(f"Error parsing ATS URL {url}: {exc}")
        return None

    return None


def parse_teamtailor_custom_domain_url(
    url: str,
    *,
    html_text: str | None = None,
    final_url: str | None = None,
) -> ParsedATSUrl | None:
    """
    Verify and parse a custom-domain Teamtailor posting URL (e.g. ``https://jobs.lunar.app/jobs/8614059-...``).

    Requires:
    1. A valid Teamtailor job path ``/(locale/)?jobs/{numeric_id}(-{slug})?``.
    2. Convincing Teamtailor evidence either via redirect to ``*.teamtailor.com``
       or explicit Teamtailor platform markers in the fetched HTML.
    """
    candidate = final_url or url
    if not candidate or not isinstance(candidate, str):
        return None

    direct = parse_ats_url(candidate)
    if direct is not None and direct.ats == "teamtailor":
        return ParsedATSUrl(
            ats="teamtailor",
            company_slug=direct.company_slug,
            job_id=direct.job_id,
            raw_url=url,
        )

    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None

    m = _TEAMTAILOR_JOB_PATH.match(parsed.path or "")
    if not m:
        return None

    if not html_text or not _TEAMTAILOR_HTML_EVIDENCE.search(html_text):
        return None

    # Require authentic Teamtailor CDN/asset/structured signal rather than just an accidental mention
    has_cdn_or_same_as = bool(
        re.search(r"https?://(?:images|screenshots|assets-aws)\.teamtailor-cdn\.com", html_text, re.IGNORECASE)
        or re.search(r"https?://[a-z0-9.-]+\.teamtailor\.com", html_text, re.IGNORECASE)
    )
    if not has_cdn_or_same_as:
        return None

    host = parsed.hostname.lower().removeprefix("www.")
    tenant_slug = host.removeprefix("jobs.").removeprefix("careers.").split(".")[0] or host
    if not is_valid_board_slug("teamtailor", tenant_slug):
        tenant_slug = host
    return ParsedATSUrl(ats="teamtailor", company_slug=tenant_slug, job_id=m.group(1), raw_url=url)


_LEVER_NON_BOARD_PATHS = frozenset({
    "img",
    "images",
    "assets",
    "static",
    "api",
    "apply",
    "jobs",
    "search",
    "careers",
    "client-logos",
})


def parse_lever_board_root_url(url: str) -> str | None:
    """
    Extract a validated Lever company board slug from a board-root URL
    (e.g. ``https://jobs.lever.co/palantir?lever-via=...`` -> ``"palantir"``).

    Returns None for job posting URLs, non-board paths, or invalid slugs.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        m = _LEVER_BOARD_ROOT.match(clean_url)
        if not m:
            return None
        slug = m.group(1).strip()
        if not slug or "." in slug or slug.lower() in _LEVER_NON_BOARD_PATHS:
            return None
        if not is_valid_board_slug("lever", slug):
            return None
        return slug
    except Exception:
        return None


_GREENHOUSE_BOARD_ROOT_PATH_RE = re.compile(r"^/([^/?#]+)(?:/jobs)?/?$", re.IGNORECASE)


def parse_greenhouse_board_root_url(url: str) -> str | None:
    """
    Extract a validated Greenhouse company board slug from a recognized board-root URL
    (e.g. ``https://boards.greenhouse.io/stripe`` or ``https://job-boards.eu.greenhouse.io/cognite``).

    Returns None for job posting URLs, `?gh_jid=` / `?error=` URLs, non-board paths, or invalid slugs.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        canon_url = canonicalize_recognized_greenhouse_url(url.strip())
        parsed = urlparse(canon_url)
        if parsed.scheme.lower() != "https":
            return None
        if (parsed.hostname or "").lower() not in GREENHOUSE_RECOGNIZED_HOSTS:
            return None
        q = parse_qs(parsed.query, keep_blank_values=True)
        q_lower = {k.lower() for k in q}
        if q_lower & {"gh_jid", "token", "error"}:
            return None
        m = _GREENHOUSE_BOARD_ROOT_PATH_RE.match(parsed.path or "")
        if not m:
            return None
        slug = m.group(1).strip()
        if not slug or "." in slug or slug.lower() in _GREENHOUSE_NON_BOARD_PATHS:
            return None
        if not is_valid_board_slug("greenhouse", slug):
            return None
        return slug
    except Exception:
        return None

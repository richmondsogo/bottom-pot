"""
Centralized URL normalization and provider identifier registry.

Follows Step 23 & ADR 0028 requirements:
- Lowercase schemes and hostnames.
- Strip trailing slashes from paths.
- Drop known tracking parameters: utm_*, gclid, fbclid, msclkid, mc_cid, mc_eid,
  gh_src, lever-source, lever-origin.
- Deterministically sort remaining query parameters without dropping ref or source generically.
- Preserve job identifying parameters (gh_jid, jobId, id, reqId, etc.).
- Strip known non-identifying anchor fragments (#apply, #content, etc.) while preserving
  hash-routing identifiers.
- Consult provider registry to verify whether a URL carries a distinct job identifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.project_files.ats_url_parser import SUPPORTED_ATS_PATTERNS, parse_ats_url

# ---------------------------------------------------------------------------
# Constants & Tracking Rules
# ---------------------------------------------------------------------------

KNOWN_TRACKING_PARAMS: frozenset[str] = frozenset({
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "gh_src",
    "lever-source",
    "lever-origin",
})

KNOWN_STRIP_ANCHORS: frozenset[str] = frozenset({
    "apply",
    "content",
    "application",
    "top",
    "main",
    "overview",
    "header",
})

GENERIC_JOB_QUERY_PARAMS: frozenset[str] = frozenset({
    "gh_jid",
    "jobid",
    "job_id",
    "id",
    "reqid",
    "req_id",
    "jid",
    "job",
})

NON_JOB_PATH_ENDINGS: frozenset[str] = frozenset({
    "",
    "/",
    "/jobs",
    "/careers",
    "/search",
    "/apply",
    "/jobs/apply",
    "/careers/jobs",
    "/all-jobs",
    "/open-roles",
    "/positions",
})

# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderUrlRule:
    provider: str
    job_id_params: frozenset[str] = field(default_factory=frozenset)
    tracking_params: frozenset[str] = field(default_factory=frozenset)
    strip_anchors: frozenset[str] = field(default_factory=frozenset)
    job_url_pattern: re.Pattern | None = None


_PROVIDER_RULES: dict[str, ProviderUrlRule] = {
    "greenhouse": ProviderUrlRule(
        provider="greenhouse",
        job_id_params=frozenset({"gh_jid"}),
        tracking_params=frozenset({"gh_src"}),
    ),
    "lever": ProviderUrlRule(
        provider="lever",
        tracking_params=frozenset({"lever-source", "lever-origin"}),
    ),
    "taleo": ProviderUrlRule(
        provider="taleo",
        job_id_params=frozenset({"job"}),
    ),
    "avature": ProviderUrlRule(
        provider="avature",
        job_id_params=frozenset({"jobid", "job_id"}),
    ),
    "workday": ProviderUrlRule(
        provider="workday",
        tracking_params=frozenset({"source", "ref"}),
    ),
    "jobberman": ProviderUrlRule(
        provider="jobberman",
        job_url_pattern=re.compile(
            r"^https?://(?:www\.)?jobberman\.com/listings/[^/?#]+-[a-z0-9]+/?$",
            re.IGNORECASE,
        ),
    ),
    "myjobmag": ProviderUrlRule(
        provider="myjobmag",
        job_url_pattern=re.compile(
            r"^https?://(?:www\.)?myjobmag\.com/job/[^/?#]+/?$",
            re.IGNORECASE,
        ),
    ),
    "hotnigerianjobs": ProviderUrlRule(
        provider="hotnigerianjobs",
        job_url_pattern=re.compile(
            r"^https?://(?:www\.)?hotnigerianjobs\.com/hotjobs/\d+/[^/?#]+/?$",
            re.IGNORECASE,
        ),
    ),
    "ngcareers": ProviderUrlRule(
        provider="ngcareers",
        job_url_pattern=re.compile(
            r"^https?://(?:www\.)?ngcareers\.com/job/[^/?#]+/?$",
            re.IGNORECASE,
        ),
    ),
}


def register_provider_url_rule(rule: ProviderUrlRule) -> None:
    """Register or update a provider-specific URL rule."""
    _PROVIDER_RULES[rule.provider.lower()] = rule


def get_provider_url_rule(provider: str | None) -> ProviderUrlRule | None:
    if not provider:
        return None
    return _PROVIDER_RULES.get(provider.lower())


# ---------------------------------------------------------------------------
# Normalization Implementation
# ---------------------------------------------------------------------------

def normalize_job_url(url: str, provider: str | None = None) -> str:
    """
    Deterministically normalize a job posting or application URL.

    - Lowercases scheme and netloc.
    - Strips trailing slash from path (unless path is empty or single slash).
    - Drops known tracking query params (utm_*, gclid, fbclid, msclkid, mc_cid,
      mc_eid, gh_src, lever-source, lever-origin).
    - Preserves job identifier params (gh_jid, jobId, id, etc.) and non-tracking params.
    - Sorts remaining query params deterministically.
    - Strips known non-identifying anchors (#apply, #content) while preserving
      routing fragments.
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not url:
        return ""

    try:
        parts = urlsplit(url)
    except Exception:
        return url

    # Scheme
    scheme = parts.scheme.lower() if parts.scheme else "https"

    # Netloc (hostname lowercased, standard ports omitted)
    netloc = parts.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Path (strip trailing slash; keep single slash or empty)
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Query params
    provider_rule = get_provider_url_rule(provider)
    extra_tracking = provider_rule.tracking_params if provider_rule else frozenset()

    raw_query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    kept_query_pairs: list[tuple[str, str]] = []
    for k, v in raw_query_pairs:
        k_lower = k.lower()
        if k_lower.startswith("utm_"):
            continue
        if k_lower in KNOWN_TRACKING_PARAMS or k_lower in extra_tracking:
            continue
        kept_query_pairs.append((k, v))

    # Sort deterministically by key, then value
    kept_query_pairs.sort(key=lambda kv: (kv[0], kv[1]))
    new_query = urlencode(kept_query_pairs, doseq=True) if kept_query_pairs else ""

    # Fragment
    raw_fragment = parts.fragment
    new_fragment = ""
    if raw_fragment:
        frag_clean = raw_fragment.lstrip("#").strip()
        frag_lower = frag_clean.lower()
        extra_anchors = provider_rule.strip_anchors if provider_rule else frozenset()
        if frag_lower not in KNOWN_STRIP_ANCHORS and frag_lower not in extra_anchors:
            new_fragment = frag_clean

    return urlunsplit((scheme, netloc, path, new_query, new_fragment))


# ---------------------------------------------------------------------------
# Identifier Verification & Match Key Builders
# ---------------------------------------------------------------------------

def url_carries_job_identifier(url: str, provider: str | None = None) -> bool:
    """
    Determine whether a URL carries a distinct job identifier.

    Returns False for bare board roots, search/listing pages, and generic /apply.
    Returns True for verified ATS job paths, registered Nigerian job patterns,
    or URLs containing explicit job identifier query parameters.
    """
    if not url or not isinstance(url, str):
        return False

    norm_url = normalize_job_url(url, provider)
    if not norm_url:
        return False

    # Check known ATS parser first
    parsed_ats = parse_ats_url(norm_url)
    if parsed_ats is not None:
        return True

    # Check provider registry rules
    p_rule = get_provider_url_rule(provider)
    if p_rule and p_rule.job_url_pattern:
        if p_rule.job_url_pattern.match(norm_url):
            return True

    try:
        parts = urlsplit(norm_url)
    except Exception:
        return False

    # Check if query contains provider or generic job identifier parameters
    job_params = {p.lower() for p in GENERIC_JOB_QUERY_PARAMS}
    if p_rule and p_rule.job_id_params:
        job_params = job_params | {p.lower() for p in p_rule.job_id_params}

    query_dict = {k.lower(): v for k, v in parse_qsl(parts.query, keep_blank_values=False)}
    for param in job_params:
        if param in query_dict and query_dict[param].strip():
            return True

    # Known ATS without matching job_id (e.g. boards.greenhouse.io/stripe) is a board root
    for ats in SUPPORTED_ATS_PATTERNS:
        if ats in parts.netloc:
            return False

    # Generic path checks
    path_lower = parts.path.lower().rstrip("/")
    if path_lower in NON_JOB_PATH_ENDINGS:
        return False

    segments = [s for s in path_lower.split("/") if s]
    if not segments:
        return False

    last_segment = segments[-1]
    if last_segment in {"jobs", "careers", "search", "apply", "openings", "positions"}:
        return False

    # If path has at least one segment with digits, UUID, or length > 6 not matching generic words, treat as job URL
    if any(char.isdigit() for char in last_segment) or len(segments) >= 2:
        return True

    return False


def build_id_match_key(
    provider: str | None,
    company: str | None,
    provider_job_id: str | None,
) -> tuple[str, str, str] | None:
    """
    Build a strong-match identity key (provider, company_or_tenant, provider_job_id).

    Returns None if any of the three fields is absent, blank, or 'unknown'.
    """
    if not provider or not company or not provider_job_id:
        return None

    p = provider.strip().lower()
    c = company.strip().lower()
    j = str(provider_job_id).strip()

    if not p or not c or not j:
        return None

    if c in {"unknown", "n/a", "none"}:
        return None

    return (p, c, j)


def build_url_match_key(url: str, provider: str | None = None) -> str | None:
    """
    Build a normalized URL match key if the URL carries a verified job identifier.

    Returns None if the URL is a board root, listing page, or lacks a job identifier.
    """
    if not url or not isinstance(url, str):
        return None

    if not url_carries_job_identifier(url, provider):
        return None

    return normalize_job_url(url, provider)

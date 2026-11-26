from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from src.core.models import ATSConfig, SearchParams
from src.core.settings import ATS_PLATFORMS
from src.discovery.search_canonicalizer import (
    canonicalize_country_code,
    canonicalize_exclude_keywords,
    canonicalize_location,
    canonicalize_platforms,
    canonicalize_query_text,
)

GOOGLE_BASE_URL = "https://www.google.com/search"

# ---------------------------------------------------------------------------
# ATS Domain Registry for Step 7 API Query Building
# ---------------------------------------------------------------------------
ATS_DOMAINS: dict[str, str] = {platform.name: platform.site_operator for platform in ATS_PLATFORMS}

ATS_EXCLUDED_SUBDOMAINS: dict[str, list[str]] = {
    "teamtailor": ["www.teamtailor.com", "support.teamtailor.com"],
    "pinpointhq": ["www.pinpointhq.com", "developers.pinpointhq.com", "app.pinpointhq.com"],
}

NIGERIAN_LOCATION_KEYWORDS = ("nigeria", "lagos", "abuja", "port harcourt", "ibadan")
RELAXED_NIGERIAN_ATS_LOCATION_TOKEN = '("Nigeria" OR "Lagos" OR "Remote" OR "EMEA")'


def _is_nigerian_location(loc: str | None) -> bool:
    if not loc:
        return False
    loc_clean = loc.strip().lower()
    return any(kw in loc_clean for kw in NIGERIAN_LOCATION_KEYWORDS)


def build_ats_query(domain: str, params: SearchParams, platform: str | None = None) -> str:
    """
    Build a site-scoped Google query for an ATS domain according to Step 7 rules:
    Pattern: site:{domain} {subdomain_excludes} "{job_title}" {remote_token} {location_token} {excludes}
    """
    parts: list[str] = [f"site:{domain}"]

    target_platform = platform
    if not target_platform:
        for p_name, p_domain in ATS_DOMAINS.items():
            if p_domain == domain:
                target_platform = p_name
                break

    if target_platform and target_platform in ATS_EXCLUDED_SUBDOMAINS:
        for excl in ATS_EXCLUDED_SUBDOMAINS[target_platform]:
            parts.append(f"-site:{excl}")

    parts.append(f'"{canonicalize_query_text(params.job_title)}"')

    if params.remote is True:
        parts.append('"remote"')
    elif params.remote is False:
        parts.append('-"remote"')

    loc = canonicalize_location(params.location)
    if loc:
        if _is_nigerian_location(loc) and params.remote is not False:
            parts.append(RELAXED_NIGERIAN_ATS_LOCATION_TOKEN)
        else:
            parts.append(f'"{loc}"' if " " in loc else loc)

    for cleaned in canonicalize_exclude_keywords(params.exclude_keywords):
        parts.append(f'-"{cleaned}"')

    return " ".join(parts)


def build_ats_queries(params: SearchParams, platforms: list[str] | None = None) -> dict[str, str]:
    """
    Generate query strings for all requested ATS platforms (defaulting to all 10).
    Returns a mapping of platform_name -> query_string.
    """
    canon_platforms = canonicalize_platforms(platforms)
    target_domains = (
        {k: v for k, v in ATS_DOMAINS.items() if k in set(canon_platforms)}
        if canon_platforms is not None
        else ATS_DOMAINS
    )
    return {
        platform: build_ats_query(domain, params, platform=platform)
        for platform, domain in target_domains.items()
    }


# ---------------------------------------------------------------------------
# Existing QueryBuilder class preserved for CLI / backward compatibility
# ---------------------------------------------------------------------------

class QueryBuilder:
    """
    Constructs Google search queries tailored for ATS platforms.
    Preserved for CLI compatibility.
    """

    EXPERIENCE_MAPPING = {
        "entry": "entry level",
        "mid": "mid level",
        "senior": "senior",
        "lead": "lead",
    }

    def __init__(self, ats: ATSConfig):
        self.ats = ats

    def build_query_string(self, params: SearchParams) -> str:
        parts: list[str] = [f"site:{self.ats.site_operator}"]
        for excl in ATS_EXCLUDED_SUBDOMAINS.get(self.ats.name, []):
            parts.append(f"-site:{excl}")
        title = canonicalize_query_text(params.job_title)
        parts.append(title)

        location = canonicalize_location(params.location)
        if location:
            if _is_nigerian_location(location) and params.remote is not False:
                parts.append(RELAXED_NIGERIAN_ATS_LOCATION_TOKEN)
            else:
                parts.append(f'"{location}"' if " " in location else location)

        if params.remote is True:
            parts.append('"remote"')
        elif params.remote is False:
            parts.append('-"remote"')

        if params.salary_min is not None:
            parts.append(f"${params.salary_min}")

        if params.experience_level:
            canon_exp = canonicalize_query_text(params.experience_level)
            if canon_exp:
                experience_text = self.EXPERIENCE_MAPPING.get(canon_exp, canon_exp)
                parts.append(f'"{experience_text}"')

        if params.days_back is not None and params.days_back > 0:
            cutoff_date = (
                datetime.now(timezone.utc) - timedelta(days=params.days_back)
            ).date()
            parts.append(f"after:{cutoff_date.isoformat()}")

        for cleaned in canonicalize_exclude_keywords(params.exclude_keywords):
            if " " in cleaned:
                parts.append(f'-"{cleaned}"')
            else:
                parts.append(f"-{cleaned}")

        return " ".join(parts)

    def build_serper_payload(
        self,
        params: SearchParams,
        page: int = 1,
        num: int = 10,
    ) -> dict:
        payload = {
            "q": self.build_query_string(params),
            "page": page,
            "num": num,
            "hl": "en",
        }
        canon_cc = self.normalize_country_code(params.country_code)
        if canon_cc:
            payload["gl"] = canon_cc
        return payload

    @staticmethod
    def normalize_country_code(country_code: Optional[str]) -> Optional[str]:
        return canonicalize_country_code(country_code)

    def build_debug_url(self, params: SearchParams, page: int = 0) -> str:
        query_string = self.build_query_string(params)
        url_params = {
            "q": query_string,
            "start": page * 10,
            "num": 10,
        }
        if params.country_code:
            url_params["gl"] = self.normalize_country_code(params.country_code)
        return f"{GOOGLE_BASE_URL}?{urlencode(url_params)}"

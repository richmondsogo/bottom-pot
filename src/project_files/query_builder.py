from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from src.project_files.config import ATS_PLATFORMS
from src.project_files.models import ATSConfig, SearchParams

GOOGLE_BASE_URL = "https://www.google.com/search"

# ---------------------------------------------------------------------------
# ATS Domain Registry for Step 7 API Query Building
# ---------------------------------------------------------------------------
ATS_DOMAINS: dict[str, str] = {platform.name: platform.site_operator for platform in ATS_PLATFORMS}

ATS_EXCLUDED_SUBDOMAINS: dict[str, list[str]] = {
    "teamtailor": ["www.teamtailor.com"],
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

    parts.append(f'"{params.job_title.strip()}"')

    if params.remote is True:
        parts.append('"remote"')
    elif params.remote is False:
        parts.append('-"remote"')

    if params.location:
        loc = params.location.strip()
        if loc:
            if _is_nigerian_location(loc) and params.remote is not False:
                parts.append(RELAXED_NIGERIAN_ATS_LOCATION_TOKEN)
            else:
                parts.append(f'"{loc}"' if " " in loc else loc)

    if params.exclude_keywords:
        for kw in params.exclude_keywords:
            cleaned = kw.strip()
            if cleaned:
                parts.append(f'-"{cleaned}"')

    return " ".join(parts)


def build_ats_queries(params: SearchParams, platforms: list[str] | None = None) -> dict[str, str]:
    """
    Generate query strings for all requested ATS platforms (defaulting to all 7).
    Returns a mapping of platform_name -> query_string.
    """
    target_domains = (
        {k: v for k, v in ATS_DOMAINS.items() if k in platforms}
        if platforms
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
        title = params.job_title.strip()
        parts.append(title)

        if params.location:
            location = params.location.strip()
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
            experience_text = self.EXPERIENCE_MAPPING.get(
                params.experience_level,
                params.experience_level,
            )
            parts.append(f'"{experience_text}"')

        if params.days_back is not None and params.days_back > 0:
            cutoff_date = (
                datetime.now(timezone.utc) - timedelta(days=params.days_back)
            ).date()
            parts.append(f"after:{cutoff_date.isoformat()}")

        for keyword in params.exclude_keywords or []:
            cleaned = keyword.strip()
            if not cleaned:
                continue
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
        if params.country_code:
            payload["gl"] = self.normalize_country_code(params.country_code)
        return payload

    @staticmethod
    def normalize_country_code(country_code: Optional[str]) -> Optional[str]:
        if not country_code:
            return None
        return country_code.strip().lower()

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

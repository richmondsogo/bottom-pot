"""
Shared, SSRF-safe company-logo extraction & normalization contract.

Step 35 implements Teamtailor logo extraction while keeping all other providers
optional / None-safe until enabled in subsequent provider steps.
Never makes outbound image HTTP requests; validates public HTTPS URLs only and
rejects social preview cards (og:image), body description images, favicons,
tracking pixels, and ATS platform self-logos.
"""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from src.project_files.url_safety import is_safe_public_https_url

_REJECTED_LOGO_PATTERNS = re.compile(
    r"(?:"
    r"screenshots\.teamtailor-cdn\.com/.*-facebook\.(?:png|jpe?g|webp)"
    r"|/images/og/tt-opengraph\."
    r"|/logos/teamtailor-logotype\."
    r"|/logos/tt-symbol-"
    r"|/img/lever-logo-refresh\."
    r"|jobs\.lever\.co/img/"
    r"|/lever-logo(?:_|-|\.)"
    r"|/api/images/org-theme-social/"
    r"|/api/images/org-theme-wordmark/"
    r"|/uploads/account/open_graph_logo/"
    r"|workable\.com/assets/facebook-preview"
    r"|favicon(?:-|_apple)?|apple-touch-icon"
    r"|user_picture_|/square_226-"
    r"|facebook\.com/tr\b|doubleclick\.net|google-analytics\.com|googletagmanager\.com"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LogoResult:
    url: str | None = None
    source: str | None = None
    raw_value: str | None = None
    verified: bool = False


def validate_and_normalize_logo_url(raw_url: Any) -> str | None:
    """
    Normalize a candidate company logo URL and enforce strict safety/logo quality checks.

    - Accepts strings or Schema.org ImageObject dicts (``url`` / ``contentUrl``).
    - Requires public HTTPS URL (blocks relative, http://, data:, javascript:, file:, private/loopback/metadata IPs).
    - Blocks known social share screenshots, favicons, recruiter portraits, tracking pixels, and Teamtailor branding assets.
    """
    candidate: str | None = None
    if isinstance(raw_url, str):
        candidate = html.unescape(raw_url).strip()
    elif isinstance(raw_url, dict):
        for k in ("url", "contentUrl", "@id"):
            val = raw_url.get(k)
            if isinstance(val, str) and val.strip():
                candidate = html.unescape(val).strip()
                break

    if not candidate:
        return None

    # Enforce strict SSRF-safe public HTTPS URL without relative resolution ambiguity
    if not is_safe_public_https_url(candidate, resolve_dns=False):
        return None

    # Reject non-HTTP path edge cases & known non-logo assets
    parts = urlsplit(candidate)
    if parts.netloc.lower().endswith("teamtailor.com") and _REJECTED_LOGO_PATTERNS.search(parts.path):
        return None
    if _REJECTED_LOGO_PATTERNS.search(candidate):
        return None

    return candidate


def _extract_teamtailor_logo(
    *,
    json_ld_doc: dict[str, Any] | None = None,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    company_name: str | None = None,
) -> LogoResult:
    # 1. Primary (Verified Structured JSON-LD): hiringOrganization.logo
    if isinstance(json_ld_doc, dict):
        org = json_ld_doc.get("hiringOrganization")
        if isinstance(org, dict) and org.get("logo") is not None:
            raw_logo = org.get("logo")
            norm_url = validate_and_normalize_logo_url(raw_logo)
            if norm_url:
                return LogoResult(
                    url=norm_url,
                    source="json_ld_hiring_organization_logo",
                    raw_value=norm_url,
                    verified=True,
                )

    # 2. Secondary (Structured Teamtailor Header Logotype DOM):
    # Strictly inside <header> / a.focus-visible-header, never body/prose/footer/og:image/favicon.
    if soup is not None:
        header_nodes = soup.select("header a.focus-visible-header img, header img[src*='logotype-'], a.focus-visible-header img")
        for img in header_nodes:
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            alt_text = (img.get("alt") or "").strip().lower()
            if alt_text == "teamtailor":
                continue
            norm_url = validate_and_normalize_logo_url(src)
            if not norm_url:
                continue
            # Require either explicit Teamtailor CDN logotype asset or career-site header anchor alt
            is_logotype_asset = "logotype-" in norm_url.lower()
            has_career_site_alt = "career" in alt_text or "vacantes" in alt_text or "carreira" in alt_text or (
                bool(company_name) and company_name.lower() in alt_text
            )
            if is_logotype_asset or (has_career_site_alt and img.find_parent("header") is not None):
                return LogoResult(
                    url=norm_url,
                    source="dom_header_logotype",
                    raw_value=str(src).strip(),
                    verified=bool(is_logotype_asset),
                )

    return LogoResult()


def _extract_lever_logo(
    *,
    json_ld_doc: dict[str, Any] | None = None,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    company_name: str | None = None,
) -> LogoResult:
    # 1. Primary (Verified Structured JSON-LD): hiringOrganization.logo
    if isinstance(json_ld_doc, dict):
        org = json_ld_doc.get("hiringOrganization")
        if isinstance(org, dict) and org.get("logo") is not None:
            raw_logo = org.get("logo")
            norm_url = validate_and_normalize_logo_url(raw_logo)
            if norm_url:
                return LogoResult(
                    url=norm_url,
                    source="json_ld_hiring_organization_logo",
                    raw_value=norm_url,
                    verified=True,
                )

    # 2. Secondary (Structured Lever Main Header Logo DOM):
    # Strictly inside a.main-header-logo / .main-header-logo img; rejects /img/lever-logo-refresh.svg and og:image.
    if soup is not None:
        header_nodes = soup.select("a.main-header-logo img, .main-header-logo img")
        for img in header_nodes:
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            alt_text = (img.get("alt") or "").strip().lower()
            if alt_text in ("lever", "lever logo"):
                continue
            norm_url = validate_and_normalize_logo_url(src)
            if not norm_url:
                continue
            return LogoResult(
                url=norm_url,
                source="lever_main_header_logo",
                raw_value=str(src).strip(),
                verified=True,
            )

    return LogoResult()


def _is_greenhouse_cdn_logo(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if not re.match(r"^s\d+-recruiting\.cdn\.greenhouse\.io$", host) and not host.endswith(".greenhouse.io"):
            return False
        if "banners" in path or "/job_board_configurations/banners/" in path:
            return False
        if "/external_greenhouse_job_boards/logos/" in path:
            return True
        return False
    except Exception:
        return False


def _extract_greenhouse_logo(
    *,
    json_ld_doc: dict[str, Any] | None = None,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    company_name: str | None = None,
) -> LogoResult:
    # 1. Primary: JSON-LD hiringOrganization.logo if on Greenhouse CDN
    if isinstance(json_ld_doc, dict):
        org = json_ld_doc.get("hiringOrganization")
        if isinstance(org, dict) and org.get("logo") is not None:
            raw_logo = org.get("logo")
            norm_url = validate_and_normalize_logo_url(raw_logo)
            if norm_url and _is_greenhouse_cdn_logo(norm_url):
                return LogoResult(
                    url=norm_url,
                    source="json_ld_hiring_organization_logo",
                    raw_value=norm_url,
                    verified=True,
                )

    # 2. Secondary: DOM / meta og:image on Greenhouse CDN
    if soup is not None:
        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or meta.get("name") or "").lower()
            if prop in ("og:image", "twitter:image"):
                content = meta.get("content")
                norm_url = validate_and_normalize_logo_url(content)
                if norm_url and _is_greenhouse_cdn_logo(norm_url):
                    return LogoResult(
                        url=norm_url,
                        source="greenhouse_cdn_logo",
                        raw_value=str(content).strip(),
                        verified=True,
                    )

        for img in soup.find_all("img"):
            alt_text = (img.get("alt") or "").strip().lower()
            if alt_text in ("banner", "greenhouse logo", "greenhouse", "powered by greenhouse"):
                continue
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            norm_url = validate_and_normalize_logo_url(src)
            if norm_url and _is_greenhouse_cdn_logo(norm_url):
                return LogoResult(
                    url=norm_url,
                    source="greenhouse_cdn_logo",
                    raw_value=str(src).strip(),
                    verified=True,
                )

    return LogoResult()


def extract_ashby_app_data_from_soup(soup: BeautifulSoup | None) -> dict[str, Any] | None:
    """Safely parse window.__appData JSON object embedded in an Ashby board or job page."""
    if soup is None:
        return None
    decoder = json.JSONDecoder()
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        idx = text.find("window.__appData")
        if idx == -1:
            continue
        brace_idx = text.find("{", idx)
        if brace_idx == -1:
            continue
        try:
            obj, _ = decoder.raw_decode(text[brace_idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _extract_ashby_logo(
    *,
    json_ld_doc: dict[str, Any] | None = None,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    company_name: str | None = None,
) -> LogoResult:
    # 1. Primary (Verified Structured JSON-LD): hiringOrganization.logo
    if isinstance(json_ld_doc, dict):
        org = json_ld_doc.get("hiringOrganization")
        if isinstance(org, dict) and org.get("logo") is not None:
            raw_logo = org.get("logo")
            norm_url = validate_and_normalize_logo_url(raw_logo)
            if norm_url:
                return LogoResult(
                    url=norm_url,
                    source="json_ld_hiring_organization_logo",
                    raw_value=norm_url,
                    verified=True,
                )

    # 2. Secondary (Verified Ashby window.__appData theme.logoSquareImageUrl)
    # Never use theme.logoWordmarkImageUrl or og:image (org-theme-social banners).
    app_data = extract_ashby_app_data_from_soup(soup)
    if isinstance(app_data, dict):
        org_obj = app_data.get("organization")
        if isinstance(org_obj, dict):
            theme = org_obj.get("theme")
            if isinstance(theme, dict):
                raw_sq = theme.get("logoSquareImageUrl")
                norm_url = validate_and_normalize_logo_url(raw_sq)
                if norm_url:
                    return LogoResult(
                        url=norm_url,
                        source="ashby_app_data_square_logo",
                        raw_value=str(raw_sq).strip(),
                        verified=True,
                    )

    return LogoResult()


def _extract_workable_logo(
    *,
    json_ld_doc: dict[str, Any] | None = None,
    workable_account_logo: str | None = None,
    page_url: str | None = None,
) -> LogoResult:
    """
    Workable-only verified company-logo extractor.

    Accepts:
      1. Structured JSON-LD hiringOrganization.logo
      2. Workable `/api/v1/accounts/{slug}` `.logo` (`workable_account_logo`),
         never accepting `open_graph_logo/.../social` or `facebook-preview.png` banners.
    """
    if isinstance(json_ld_doc, dict):
        org = json_ld_doc.get("hiringOrganization")
        if isinstance(org, dict) and org.get("logo") is not None:
            norm_url = validate_and_normalize_logo_url(org.get("logo"))
            if norm_url:
                return LogoResult(
                    url=norm_url,
                    source="json_ld_hiring_organization_logo",
                    raw_value=norm_url,
                    verified=True,
                )

    if isinstance(workable_account_logo, str) and workable_account_logo.strip():
        raw_logo = workable_account_logo.strip()
        validated = validate_and_normalize_logo_url(raw_logo)
        if validated:
            return LogoResult(
                url=validated,
                source="workable_account_logo",
                raw_value=raw_logo,
                verified=True,
            )

    return LogoResult()


def extract_company_logo_for_provider(
    provider: str | None,
    *,
    json_ld_doc: dict[str, Any] | None = None,
    soup: BeautifulSoup | None = None,
    page_url: str | None = None,
    company_name: str | None = None,
    workable_account_logo: str | None = None,
) -> LogoResult:
    """
    Provider-gated company-logo extraction entrypoint.

    Enabled providers: teamtailor, lever, greenhouse, ashby, workable. All other providers return an empty LogoResult
    (url=None, verified=False) until subsequent provider steps opt in.
    """
    prov = (provider or "").strip().lower()
    if prov == "teamtailor":
        return _extract_teamtailor_logo(
            json_ld_doc=json_ld_doc,
            soup=soup,
            page_url=page_url,
            company_name=company_name,
        )
    if prov == "lever":
        return _extract_lever_logo(
            json_ld_doc=json_ld_doc,
            soup=soup,
            page_url=page_url,
            company_name=company_name,
        )
    if prov == "greenhouse":
        return _extract_greenhouse_logo(
            json_ld_doc=json_ld_doc,
            soup=soup,
            page_url=page_url,
            company_name=company_name,
        )
    if prov == "ashby":
        return _extract_ashby_logo(
            json_ld_doc=json_ld_doc,
            soup=soup,
            page_url=page_url,
            company_name=company_name,
        )
    if prov == "workable":
        return _extract_workable_logo(
            json_ld_doc=json_ld_doc,
            workable_account_logo=workable_account_logo,
            page_url=page_url,
        )
    return LogoResult()

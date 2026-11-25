"""Verified employer domain extraction and fallback resolution for Logo.dev.

Per ADR 0001 ("Unknown beats wrong") and ADR 0031, never guesses a company domain
from a company name. Resolution follows this strict priority order:
  (a) curated ``company_domain`` verified on ``VERIFIED_EMPLOYER_BOARDS``
  (b) employer-owned host of ``apply_url``, after rejecting ATS/job-board hosts
      and reducing to the registrable domain via the Mozilla Public Suffix List
  (c) ``(None, None)`` -> frontend renders local square monogram
"""

from __future__ import annotations

import ipaddress
import re
from email.utils import parseaddr
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from publicsuffixlist import PublicSuffixList

_PSL = PublicSuffixList(accept_unknown=False)

_HOSTNAME_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

_FREEMAIL_AND_GENERIC_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "ymail.com",
    "gmx.com",
    "mail.com",
    "zoho.com",
})

_EXPLICIT_ATS_AND_AGGREGATOR_HOSTS: frozenset[str] = frozenset({
    # Active & legacy ATS platforms
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "recruitee.com",
    "smartrecruiters.com",
    "teamtailor.com",
    "personio.com",
    "personio.de",
    "pinpointhq.com",
    "myworkdayjobs.com",
    "myworkdaysite.com",
    "bamboohr.com",
    "jobvite.com",
    "icims.com",
    "taleo.net",
    "jobadder.com",
    "applytojob.com",
    "avature.net",
    "sap.com",
    "successfactors.com",
    "successfactors.eu",
    # Nigerian / regional boards & third-party aggregators
    "hotnigerianjobs.com",
    "jobberman.com",
    "myjobmag.com",
    "ngcareers.com",
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "wellfound.com",
    "angel.co",
    # Search / shorteners / local placeholders
    "serper.dev",
    "google.com",
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "lnkd.in",
    "example.com",
    "example.org",
    "example.net",
    "example.test",
    "localhost",
})


@lru_cache(maxsize=1)
def _ats_host_denylist() -> frozenset[str]:
    """Combine explicit ATS/aggregator domains with registrable hosts from ``ATS_PLATFORMS``."""
    denied = set(_EXPLICIT_ATS_AND_AGGREGATOR_HOSTS)
    from src.core.settings import ATS_PLATFORMS

    for cfg in ATS_PLATFORMS:
        raw_op = (cfg.site_operator or "").strip().lower().split("/")[0]
        if not raw_op:
            continue
        denied.add(raw_op)
        reg = _PSL.privatesuffix(raw_op)
        if reg:
            denied.add(reg.lower())
    return frozenset(denied)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _is_ats_or_denied_domain(host: str, registrable: str) -> bool:
    denylist = _ats_host_denylist()
    if host in denylist or registrable in denylist:
        return True
    if any(host.endswith(f".{d}") for d in denylist):
        return True
    # Catch country-TLD Personio hosts (e.g. acme.jobs.personio.de, personio.co.uk)
    labels = host.split(".")
    if "personio" in labels and not registrable.startswith("personio-"):
        if registrable.startswith("personio.") or "jobs.personio." in host:
            return True
    return False


def extract_registrable_domain(url_or_host: str | None) -> str | None:
    """
    Reduce an HTTPS/HTTP URL or bare host to a verified non-ATS registrable domain.

    Returns ``None`` for invalid URLs, IP literals, single-label hosts, unknown PSL
    suffixes, and any ATS/job-board/shortener host.
    """
    if not url_or_host or not isinstance(url_or_host, str):
        return None
    raw = url_or_host.strip()
    if not raw or any(ch.isspace() for ch in raw):
        return None

    if "://" in raw:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in ("http", "https"):
            return None
        host = (parsed.hostname or "").strip().lower().rstrip(".")
    else:
        if ":" in raw and raw.count(":") == 1 and "/" not in raw:
            # Bare host without scheme (reject embedded port/scheme confusion like javascript:1)
            return None
        parsed = urlsplit(f"https://{raw}")
        host = (parsed.hostname or "").strip().lower().rstrip(".")

    if not host or "." not in host or _is_ip_literal(host):
        return None

    labels = host.split(".")
    if any(not _HOSTNAME_LABEL_RE.match(lbl) for lbl in labels):
        return None

    registrable = _PSL.privatesuffix(host)
    if not registrable:
        return None
    registrable = registrable.lower().rstrip(".")
    if "." not in registrable or _is_ip_literal(registrable):
        return None

    if _is_ats_or_denied_domain(host, registrable):
        return None

    return registrable


@lru_cache(maxsize=1)
def _curated_catalog_domains() -> dict[tuple[str, str], str]:
    from src.monitoring.employer_board_catalog import VERIFIED_EMPLOYER_BOARDS

    mapping: dict[tuple[str, str], str] = {}
    for entry in VERIFIED_EMPLOYER_BOARDS:
        dom = extract_registrable_domain(entry.company_domain)
        if dom:
            mapping[(entry.ats_provider.strip().lower(), entry.board_token.strip().lower())] = dom
    return mapping


def lookup_curated_company_domain(provider: str | None, company_slug: str | None) -> str | None:
    """Return curated catalog domain for ``(provider, company_slug)`` or ``None``."""
    if not provider or not company_slug:
        return None
    return _curated_catalog_domains().get((provider.strip().lower(), company_slug.strip().lower()))


def extract_corporate_mailto_domain(mailto_or_email: str | None) -> str | None:
    """
    Extract a verified non-freemail registrable domain from a ``mailto:`` URI or address.

    Returns ``None`` for freemail providers (Gmail, Yahoo, Outlook, etc.) and denied hosts.
    """
    if not mailto_or_email or not isinstance(mailto_or_email, str):
        return None
    raw = mailto_or_email.strip()
    if raw.lower().startswith("mailto:"):
        raw = raw[7:]
    raw = raw.split("?", 1)[0].strip()
    _, addr = parseaddr(raw)
    candidate = (addr or raw).strip()
    if not candidate or "@" not in candidate or any(ch.isspace() for ch in candidate):
        return None
    _, _, host = candidate.rpartition("@")
    registrable = extract_registrable_domain(host)
    if not registrable or registrable in _FREEMAIL_AND_GENERIC_EMAIL_DOMAINS:
        return None
    return registrable


def resolve_company_domain(
    *,
    provider: str | None = None,
    company_slug: str | None = None,
    apply_url: str | None = None,
    catalog_domain: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Resolve ``(company_domain, company_domain_source)`` conservatively.

    Order:
      1. Explicit or curated ``catalog_domain`` -> ``(domain, "catalog_verified")``
      2. Curated ATS fallback lookup when ``apply_url`` is an ATS board URL -> ``(domain, "catalog_verified")``
      3. Non-ATS ``apply_url`` registrable host -> ``(domain, "apply_url_host")``
      4. Otherwise -> ``(None, None)``
    """
    if catalog_domain:
        validated = extract_registrable_domain(catalog_domain)
        if validated:
            return validated, "catalog_verified"

    curated = lookup_curated_company_domain(provider, company_slug)
    if curated:
        return curated, "catalog_verified"

    if apply_url and "://" in apply_url:
        from src.ats.ats_url_parser import parse_ats_url

        parsed_ats = parse_ats_url(apply_url)
        if parsed_ats and parsed_ats.company_slug:
            curated_from_url = lookup_curated_company_domain(parsed_ats.ats, parsed_ats.company_slug)
            if curated_from_url:
                return curated_from_url, "catalog_verified"

    from_apply = extract_registrable_domain(apply_url)
    if from_apply:
        return from_apply, "apply_url_host"

    return None, None


def refresh_listing_identity_from_apply_url(listing: Any) -> None:
    """Re-resolve ``company_domain``/``source`` after post-extraction ``apply_url`` enrichment."""
    apply_url = getattr(listing, "apply_url", None)
    if not apply_url:
        return
    domain, source = resolve_company_domain(
        provider=getattr(listing, "provider", None) or getattr(listing, "ats_source", None),
        company_slug=getattr(listing, "company_slug", None),
        apply_url=apply_url,
    )
    if not domain and isinstance(apply_url, str) and apply_url.strip().lower().startswith("mailto:"):
        domain = extract_corporate_mailto_domain(apply_url)
        if domain:
            source = "mailto_corporate_domain"
    if domain:
        listing.company_domain = domain
        listing.company_domain_source = source

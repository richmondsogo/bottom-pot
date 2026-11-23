"""
Human-readable eligibility scope and country-aware summary labels.

Separated from ``eligibility_extractor.py`` so summary formatting and objective
scope labels live in a concise module and remain authoritative from the backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.countries import (
    country_name_for_code,
    normalize_country_code,
    normalize_region_name,
)

if TYPE_CHECKING:
    from src.core.models import EligibilityStatus, JobEligibility, WorkArrangement


def _short_country_label(code: str) -> str:
    if code == "US":
        return "US"
    if code == "GB":
        return "UK"
    return country_name_for_code(code) or code


def _format_allowed_scope(
    allowed_codes: list[str],
    allowed_regions: list[str],
) -> str | None:
    parts: list[str] = []
    for code in allowed_codes:
        parts.append(_short_country_label(code))
    for reg in allowed_regions:
        if reg not in parts:
            parts.append(reg)
    if not parts:
        return None
    if len(parts) == 1:
        return f"{parts[0]} only"
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _split_labels(labels: list[str] | None) -> tuple[list[str], list[str]]:
    if not labels:
        return [], []
    codes: list[str] = []
    regions: list[str] = []
    for item in labels:
        reg = normalize_region_name(item)
        if reg and reg != "Worldwide":
            if reg not in regions:
                regions.append(reg)
            continue
        code = normalize_country_code(item)
        if code and code not in codes:
            codes.append(code)
    return codes, regions


def _normalize_arrangement(work_model: str | None) -> str:
    wm = (work_model or "").strip().lower().replace("-", "_").replace(" ", "_")
    if wm == "remote":
        return "remote"
    if wm == "hybrid":
        return "hybrid"
    if wm in ("in_person", "onsite", "on_site"):
        return "onsite"
    return "unknown"


def _build_summary_label(
    *,
    work_arrangement: WorkArrangement,
    status: EligibilityStatus,
    applicant_country_name: str,
    applicant_country_code: str,
    global_remote_explicit: bool | None,
    allowed_codes: list[str],
    allowed_regions: list[str],
    excluded_codes: list[str],
    excluded_regions: list[str],
    location: str | None,
    physical_country_name: str | None,
) -> str | None:
    work_prefix = {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "Onsite",
        "unknown": None,
    }[work_arrangement]

    if work_arrangement in ("onsite", "hybrid") and status == "eligible":
        place = (location or "").strip()
        if place and place.lower() not in {"africa", "global", "remote", "worldwide"}:
            return f"{work_prefix} · {place}"
        if physical_country_name:
            return f"{work_prefix} · {physical_country_name}"

    if global_remote_explicit and not allowed_codes and not allowed_regions:
        if excluded_codes or excluded_regions:
            excl = ", ".join(_short_country_label(c) for c in excluded_codes) or ", ".join(excluded_regions)
            scope = f"Worldwide (excl. {excl})"
        else:
            scope = "Worldwide"
    elif allowed_codes or allowed_regions:
        if (
            status == "eligible"
            and applicant_country_code in allowed_codes
            and len(allowed_codes) > 1
            and not allowed_regions
        ):
            scope = f"{applicant_country_name} eligible"
        elif status == "eligible" and not allowed_codes and allowed_regions:
            scope = f"{applicant_country_name} eligible"
        else:
            scope = _format_allowed_scope(allowed_codes, allowed_regions)
    elif status == "eligible":
        scope = f"{applicant_country_name} eligible"
    elif work_arrangement in ("onsite", "hybrid"):
        place = (location or "").strip() or physical_country_name
        scope = place or "Eligibility unverified"
    else:
        scope = "Eligibility unverified"

    if work_prefix and scope:
        return f"{work_prefix} · {scope}"
    return scope


def build_objective_scope_label(
    eligibility: JobEligibility | None,
    *,
    work_model: str | None = None,
    location: str | None = None,
) -> str | None:
    """
    Build a concise applicant-independent eligibility scope label
    (e.g. ``Worldwide``, ``US only``, ``Germany and EU``, ``Lagos, Nigeria``, ``Eligibility unverified``).
    Never emits ``Worldwide`` unless ``global_remote_explicit`` is True.
    """
    work_arrangement = _normalize_arrangement(work_model)

    allowed_codes = list(eligibility.allowed_country_codes or []) if eligibility else []
    allowed_regions = list(eligibility.allowed_regions or []) if eligibility else []
    if (
        eligibility
        and not allowed_codes
        and not allowed_regions
        and eligibility.allowed_residence_countries
    ):
        allowed_codes, allowed_regions = _split_labels(eligibility.allowed_residence_countries)

    excluded_codes = list(eligibility.excluded_country_codes or []) if eligibility else []
    excluded_regions = list(eligibility.excluded_regions or []) if eligibility else []
    if (
        eligibility
        and not excluded_codes
        and not excluded_regions
        and eligibility.excluded_residence_countries
    ):
        excluded_codes, excluded_regions = _split_labels(eligibility.excluded_residence_countries)

    phys_name = eligibility.physical_location_country if eligibility else None
    if not phys_name and eligibility and eligibility.physical_location_country_code:
        phys_name = country_name_for_code(eligibility.physical_location_country_code)

    if eligibility and eligibility.global_remote_explicit and not allowed_codes and not allowed_regions:
        if excluded_codes or excluded_regions:
            excl = ", ".join(_short_country_label(c) for c in excluded_codes) or ", ".join(excluded_regions)
            return f"Worldwide (excl. {excl})"
        return "Worldwide"

    if allowed_codes or allowed_regions:
        return _format_allowed_scope(allowed_codes, allowed_regions)

    if work_arrangement in ("onsite", "hybrid"):
        trimmed = (location or "").strip()
        if trimmed and trimmed.lower() not in {"africa", "global", "remote", "worldwide"}:
            return trimmed
        return phys_name or "Eligibility unverified"

    if work_arrangement == "remote":
        return "Eligibility unverified"

    return None

"""Deterministic field confidence policy and scoring constants.

Governed by ADR 0028.
Properties:
- Confidence is derived from evidence quality, specificity, and agreement between independent signals.
- Decouples source reliability from field confidence.
- Strict score limits: max is 0.95; 1.0 is never used.
- Unknown/missing fields strictly receive None (never 0.0 or low numbers).
- Zero randomness, zero wall-clock dependence.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from src.project_files.models import CanonicalJobField, FieldConfidence, JobSalary


class EvidenceType(str, Enum):
    TYPED_ENUM = "typed_enum"
    STRUCTURED_FREE_TEXT = "structured_free_text"
    EXPLICIT_LABEL = "explicit_label"
    UNLABELLED_TEXT = "unlabelled_text"
    SNIPPET = "snippet"


# Base confidence scores per (CanonicalJobField, EvidenceType)
# Note: Specific fields (salary, description) apply custom property constraints.
BASE_CONFIDENCE_TABLE: dict[tuple[CanonicalJobField, EvidenceType], float] = {
    # Title
    (CanonicalJobField.TITLE, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.TITLE, EvidenceType.STRUCTURED_FREE_TEXT): 0.90,
    (CanonicalJobField.TITLE, EvidenceType.EXPLICIT_LABEL): 0.70,
    (CanonicalJobField.TITLE, EvidenceType.UNLABELLED_TEXT): 0.50,
    (CanonicalJobField.TITLE, EvidenceType.SNIPPET): 0.30,
    # Company
    (CanonicalJobField.COMPANY, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.COMPANY, EvidenceType.STRUCTURED_FREE_TEXT): 0.90,
    (CanonicalJobField.COMPANY, EvidenceType.EXPLICIT_LABEL): 0.70,
    (CanonicalJobField.COMPANY, EvidenceType.UNLABELLED_TEXT): 0.50,
    (CanonicalJobField.COMPANY, EvidenceType.SNIPPET): 0.30,
    # Location
    (CanonicalJobField.LOCATION, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.LOCATION, EvidenceType.STRUCTURED_FREE_TEXT): 0.70,
    (CanonicalJobField.LOCATION, EvidenceType.EXPLICIT_LABEL): 0.70,
    (CanonicalJobField.LOCATION, EvidenceType.UNLABELLED_TEXT): 0.50,
    (CanonicalJobField.LOCATION, EvidenceType.SNIPPET): 0.30,
    # Work Model
    (CanonicalJobField.WORK_MODEL, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.WORK_MODEL, EvidenceType.EXPLICIT_LABEL): 0.70,  # e.g. #LI-Remote
    (CanonicalJobField.WORK_MODEL, EvidenceType.UNLABELLED_TEXT): 0.50,  # description scan
    # Employment Type
    (CanonicalJobField.EMPLOYMENT_TYPE, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.EMPLOYMENT_TYPE, EvidenceType.EXPLICIT_LABEL): 0.70,
    (CanonicalJobField.EMPLOYMENT_TYPE, EvidenceType.UNLABELLED_TEXT): 0.50,
    # Salary
    (CanonicalJobField.SALARY, EvidenceType.TYPED_ENUM): 0.90,  # Structured API object
    (CanonicalJobField.SALARY, EvidenceType.EXPLICIT_LABEL): 0.70,  # e.g. "Salary: $120k"
    (CanonicalJobField.SALARY, EvidenceType.UNLABELLED_TEXT): 0.50,
    # Description
    (CanonicalJobField.DESCRIPTION, EvidenceType.STRUCTURED_FREE_TEXT): 0.90,
    # Posted At
    (CanonicalJobField.POSTED_AT, EvidenceType.TYPED_ENUM): 0.90,
    # Apply URL
    (CanonicalJobField.APPLY_URL, EvidenceType.TYPED_ENUM): 0.90,
    (CanonicalJobField.APPLY_URL, EvidenceType.STRUCTURED_FREE_TEXT): 0.90,
    (CanonicalJobField.APPLY_URL, EvidenceType.SNIPPET): 0.70,
}

AGREEMENT_BONUS = 0.05
CONFLICT_PENALTY = -0.20
CONFIDENCE_CEILING = 0.95
SALARY_INCOMPLETE_CAP = 0.60


def sanitize_source_url(url: str | None) -> str | None:
    """Strip query strings and fragments from URLs stored in evidence to prevent leaking tokens."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed._replace(query="", fragment="").geturl()
    except Exception:
        return url.split("?")[0].split("#")[0]


def sanitize_raw_evidence(val: object, max_len: int = 200) -> str:
    """Format and cap raw evidence snippet at max_len characters."""
    if val is None:
        return ""
    text = str(val).strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def compute_field_confidence(
    field: CanonicalJobField,
    evidence_type: EvidenceType,
    *,
    has_value: bool = True,
    has_agreement: bool = False,
    has_conflict: bool = False,
    salary: Optional[JobSalary] = None,
    description_ok: bool = True,
    is_authentic_desc: bool = True,
) -> tuple[Optional[float], Optional[str]]:
    """Deterministically compute field confidence score and explanation."""
    if not has_value:
        return None, "Field is not populated"

    # Description quality gating
    if field == CanonicalJobField.DESCRIPTION:
        if not is_authentic_desc:
            return None, "Snippet or unauthentic description cannot populate description confidence"
        score = 0.90 if description_ok else 0.70
        reason = "Authentic description (full display quality)" if description_ok else "Authentic description (<300 chars, short)"
        return score, reason

    base_score = BASE_CONFIDENCE_TABLE.get((field, evidence_type))
    if base_score is None:
        base_score = 0.50

    reasons: list[str] = [f"Base score {base_score:.2f} ({evidence_type.value})"]

    score = base_score

    # Salary completeness guard
    if field == CanonicalJobField.SALARY and salary is not None:
        if not salary.currency or not salary.period:
            if score > SALARY_INCOMPLETE_CAP:
                score = SALARY_INCOMPLETE_CAP
                reasons.append(f"Capped at {SALARY_INCOMPLETE_CAP:.2f} due to missing currency or period")

    # Agreement bonus
    if has_agreement:
        score += AGREEMENT_BONUS
        reasons.append(f"+{AGREEMENT_BONUS:.2f} agreeing signals")

    # Conflict penalty
    if has_conflict:
        score += CONFLICT_PENALTY
        reasons.append(f"{CONFLICT_PENALTY:.2f} conflicting signal penalty")

    # Hard bounds: strictly cap at CONFIDENCE_CEILING (0.95), never 1.0, minimum 0.1
    score = min(score, CONFIDENCE_CEILING)
    score = max(score, 0.10)
    score = round(score, 2)

    return score, "; ".join(reasons)


CORE_FIELD_WEIGHTS: dict[CanonicalJobField, float] = {
    CanonicalJobField.TITLE: 0.20,
    CanonicalJobField.COMPANY: 0.20,
    CanonicalJobField.LOCATION: 0.20,
    CanonicalJobField.APPLY_URL: 0.20,
    CanonicalJobField.DESCRIPTION: 0.20,
}


def compute_legacy_scalar_confidence(
    field_scores: dict[CanonicalJobField, float] | list[FieldConfidence],
) -> float:
    """Derive legacy scalar confidence via weighted mean over fixed core fields.
    Core fields: title, company, location, apply_url, description (weight 0.20 each).
    Missing core fields evaluate to 0.0. Optional fields (salary, work_model, employment_type)
    are excluded because absence of disclosure is not a quality defect.
    Property: adding any populated core field never lowers the scalar.
    """
    if isinstance(field_scores, list):
        scores_map = {fc.field: fc.score for fc in field_scores}
    else:
        scores_map = field_scores

    total = sum(
        weight * scores_map.get(field, 0.0)
        for field, weight in CORE_FIELD_WEIGHTS.items()
    )
    return max(0.0, min(1.0, round(total, 2)))


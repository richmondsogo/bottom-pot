"""
Deterministic Career-Stage Classification Utility (Step 56).

Provides consistent title-based career-stage classification without letting
Senior/Staff/Principal level-I suffixes (e.g. ``Principal Software Engineer I``)
pollute early-career metrics.
"""

from __future__ import annotations

import re
from typing import Literal

CareerStage = Literal[
    "intern",
    "graduate",
    "junior",
    "apprenticeship",
    "senior_plus",
    "mid_or_unspecified",
]

EARLY_CAREER_STAGES: frozenset[str] = frozenset({
    "intern",
    "graduate",
    "junior",
    "apprenticeship",
})

_INTERN_RE = re.compile(r"\b(?:intern|internship|co[- ]?op)\b", re.IGNORECASE)
_GRADUATE_RE = re.compile(
    r"\b(?:new\s+grad|new\s+graduate|graduate\s+(?:programme|program|developer|engineer|trainee)|"
    r"grad\s+(?:programme|program|trainee)|recent\s+graduate)\b",
    re.IGNORECASE,
)
_APPRENTICESHIP_RE = re.compile(r"\b(?:apprentice(?:ship)?|trainee(?:ship)?)\b", re.IGNORECASE)
_EXPLICIT_JUNIOR_RE = re.compile(r"\b(?:junior|jr\.?|entry[- ]?level|early\s+career)\b", re.IGNORECASE)
_SENIOR_RE = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|lead\b|manager|director|head\s+of|vp\b|distinguished|chief|iii\b|iv\b)\b",
    re.IGNORECASE,
)
_LEVEL_ONE_RE = re.compile(
    r"\b(?:software\s+engineer\s+i|engineer\s+i|developer\s+i|swe\s+i)\b",
    re.IGNORECASE,
)


def classify_career_stage(title: str | None) -> CareerStage:
    """Classify a normalized job title into a deterministic career stage."""
    cleaned = (title or "").strip()
    if not cleaned:
        return "mid_or_unspecified"
    if _INTERN_RE.search(cleaned):
        return "intern"
    if _GRADUATE_RE.search(cleaned):
        return "graduate"
    if _APPRENTICESHIP_RE.search(cleaned):
        return "apprenticeship"
    if _EXPLICIT_JUNIOR_RE.search(cleaned):
        return "junior"
    if _SENIOR_RE.search(cleaned):
        return "senior_plus"
    if _LEVEL_ONE_RE.search(cleaned):
        return "junior"
    return "mid_or_unspecified"


def is_early_career_stage(stage: str | None) -> bool:
    """Return True when ``stage`` represents an early-career band."""
    return (stage or "") in EARLY_CAREER_STAGES

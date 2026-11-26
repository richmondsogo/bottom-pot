from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import timezone
from enum import Enum
from typing import Any, Callable, Sequence, TypeVar

from src.core.settings import settings
from src.extraction.freshness import compute_freshness, freshness_rank_key

T = TypeVar("T")


class RelevanceLevel(str, Enum):
    STRONG = "strong"          # Exact/full title match, exact company match, or strong title variant
    RELATED = "related"        # Related role specialization within same discipline (title-based)
    WEAK = "weak"              # Reserved enum value (no longer promoted from body-only matches)
    IRRELEVANT = "irrelevant"  # Unrelated discipline or body-only mention


@dataclass(frozen=True)
class RelevanceResult:
    level: RelevanceLevel
    score: float
    matched_tokens: list[str]
    reason: str


_FILLER_WORDS: frozenset[str] = frozenset({
    "job",
    "jobs",
    "role",
    "roles",
    "position",
    "positions",
    "opening",
    "openings",
})

_UNICODE_DASH_RE = re.compile(r"[\u2010-\u2015\u2212]")
_APOSTROPHE_RE = re.compile(r"['\u2018\u2019]")
_NON_TOKEN_PUNCT_RE = re.compile(r"(?<!\w)-|-(?!\w)|[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_unicode_and_punct(text: str) -> str:
    """Apply Unicode NFKC, lowercase, preserve intra-word hyphens, strip punctuation."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _UNICODE_DASH_RE.sub("-", normalized)
    normalized = _APOSTROPHE_RE.sub("", normalized)
    normalized = _NON_TOKEN_PUNCT_RE.sub(" ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _normalize_phrase(text: str) -> str:
    """Normalize text to space-separated lowercase words (punctuation and hyphens become spaces)."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _UNICODE_DASH_RE.sub(" ", normalized)
    normalized = _APOSTROPHE_RE.sub("", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _light_stem(token: str) -> str:
    """Domain-agnostic plural and conservative suffix normalization."""
    if len(token) <= 3:
        return token

    stem = token
    if len(stem) > 4 and stem.endswith("ies"):
        stem = stem[:-3] + "y"
    elif len(stem) > 4 and stem.endswith(("ches", "shes", "xes", "zes", "sses")):
        stem = stem[:-2]
    elif stem.endswith("s") and not stem.endswith(("ss", "us", "is", "os")):
        stem = stem[:-1]

    if len(stem) >= 8 and stem.endswith("eering"):
        return stem[:-3]
    if len(stem) >= 8 and stem.endswith(("ational", "ional")):
        return stem[:-2]
    if len(stem) >= 7 and stem.endswith("ical"):
        return stem[:-2]
    return stem


def extract_query_units(query: str) -> list[tuple[str, tuple[str, ...]]]:
    """Extract normalized query units `(collapsed_stem, part_stems)` with filler words stripped."""
    cleaned = _normalize_unicode_and_punct(query)
    if not cleaned:
        return []
    raw_tokens = [tok for tok in cleaned.split() if tok]
    kept_tokens = [
        tok for tok in raw_tokens
        if tok not in _FILLER_WORDS and _light_stem(tok) not in _FILLER_WORDS
    ]
    if not kept_tokens:
        kept_tokens = raw_tokens

    units: list[tuple[str, tuple[str, ...]]] = []
    for tok in kept_tokens:
        if "-" in tok:
            raw_parts = [p for p in tok.split("-") if p]
            if not raw_parts:
                continue
            part_stems = tuple(_light_stem(p) for p in raw_parts)
            collapsed = _light_stem("".join(raw_parts))
            units.append((collapsed, part_stems))
        else:
            stem = _light_stem(tok)
            units.append((stem, (stem,)))
    return units


def _extract_title_terms(title: str) -> set[str]:
    """Extract normalized title stems, hyphen-collapsed forms, and adjacent compound forms."""
    cleaned = _normalize_unicode_and_punct(title)
    if not cleaned:
        return set()

    terms: set[str] = set()
    flat_tokens: list[str] = []
    raw_flat: list[str] = []

    for tok in cleaned.split():
        if "-" in tok:
            raw_parts = [p for p in tok.split("-") if p]
            for p in raw_parts:
                stem = _light_stem(p)
                terms.add(stem)
                flat_tokens.append(stem)
                raw_flat.append(p)
            if raw_parts:
                terms.add(_light_stem("".join(raw_parts)))
        else:
            stem = _light_stem(tok)
            terms.add(stem)
            flat_tokens.append(stem)
            raw_flat.append(tok)

    for idx in range(len(flat_tokens) - 1):
        terms.add(_light_stem(flat_tokens[idx] + flat_tokens[idx + 1]))
        terms.add(_light_stem(raw_flat[idx] + raw_flat[idx + 1]))

    return terms


def _match_query_units_against_terms(
    query_units: list[tuple[str, tuple[str, ...]]],
    title_terms: set[str],
) -> tuple[int, int, list[str], list[str]]:
    """Match normalized query units against title terms, collapsing adjacent compound words."""
    matched_units = 0
    total_units = 0
    matched: list[str] = []
    unmatched: list[str] = []

    i = 0
    while i < len(query_units):
        collapsed, parts = query_units[i]
        if collapsed in title_terms or (len(parts) > 1 and all(p in title_terms for p in parts)):
            matched_units += 1
            total_units += 1
            matched.append(collapsed)
            i += 1
        elif (
            i + 1 < len(query_units)
            and len(parts) == 1
            and len(query_units[i + 1][1]) == 1
        ):
            joined = _light_stem(collapsed + query_units[i + 1][0])
            if joined in title_terms:
                matched_units += 1
                total_units += 1
                matched.append(joined)
                i += 2
            else:
                total_units += 1
                unmatched.append(collapsed)
                i += 1
        else:
            total_units += 1
            unmatched.append(collapsed)
            i += 1

    return matched_units, total_units, matched, unmatched


def _has_whole_phrase(phrase_text: str, needle: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", phrase_text))


def _query_without_fillers_phrase(query: str) -> str:
    tokens = [
        tok for tok in _normalize_phrase(query).split()
        if tok not in _FILLER_WORDS and _light_stem(tok) not in _FILLER_WORDS
    ]
    if not tokens:
        return _normalize_phrase(query)
    return " ".join(tokens)


def classify_relevance(
    query: str,
    title: str,
    department: str | None = None,
    responsibilities: str | None = None,
    qualifications: str | None = None,
    company_description: str | None = None,  # Excluded from role evidence
    company: str | None = None,
) -> RelevanceResult:
    """Classify job relevance against the search query using a domain-agnostic title-first rule.

    Tier 1: Every normalized query token appears in the job title (any order), or the
    company name exactly matches the query.
    Tier 2: Multi-word queries matching cleanly on the title via company-qualified match,
    high title token overlap, or title-only role specialization clusters.
    Body/description text never promotes an unrelated role.
    """
    _ = department, responsibilities, qualifications, company_description
    if not query or not query.strip() or not title or not title.strip():
        return RelevanceResult(
            level=RelevanceLevel.IRRELEVANT,
            score=0.0,
            matched_tokens=[],
            reason="Missing query or title",
        )

    query_units = extract_query_units(query)
    if not query_units:
        return RelevanceResult(
            level=RelevanceLevel.IRRELEVANT,
            score=0.0,
            matched_tokens=[],
            reason="Empty normalized query",
        )

    title_terms = _extract_title_terms(title)
    matched_count, total_units, matched_tokens, unmatched_tokens = _match_query_units_against_terms(
        query_units,
        title_terms,
    )

    # Tier 1a: Every normalized query token appears in the title (any order)
    if total_units > 0 and matched_count == total_units:
        return RelevanceResult(
            level=RelevanceLevel.STRONG,
            score=0.95,
            matched_tokens=matched_tokens,
            reason=f"All query tokens matched in title: {matched_tokens}",
        )

    # Tier 1b: Company name exactly matches the normalized query
    norm_company = _normalize_phrase(company or "")
    norm_query_core = _query_without_fillers_phrase(query)
    if norm_company and norm_query_core and norm_company == norm_query_core:
        return RelevanceResult(
            level=RelevanceLevel.STRONG,
            score=0.92,
            matched_tokens=[norm_company],
            reason=f"Exact company name match: '{norm_company}'",
        )

    # Single-word queries require an exact/normalized title or company match
    if total_units <= 1:
        return RelevanceResult(
            level=RelevanceLevel.IRRELEVANT,
            score=0.15,
            matched_tokens=[],
            reason=f"Title '{title}' does not contain query '{query}'",
        )

    # Tier 2a: Company-prefixed multi-word query where remaining tokens all match the title
    if norm_company and matched_count >= 1 and unmatched_tokens:
        company_stems = [_light_stem(t) for t in norm_company.split() if t]
        if (
            len(unmatched_tokens) <= len(company_stems)
            and company_stems[: len(unmatched_tokens)] == unmatched_tokens
        ):
            return RelevanceResult(
                level=RelevanceLevel.STRONG,
                score=0.88,
                matched_tokens=matched_tokens + unmatched_tokens,
                reason=f"Company-qualified title match for '{company}'",
            )

    # Tier 2b: High title token overlap (>= 80% of query units in title)
    overlap_ratio = matched_count / total_units if total_units else 0.0
    if overlap_ratio >= 0.8:
        return RelevanceResult(
            level=RelevanceLevel.STRONG,
            score=0.86,
            matched_tokens=matched_tokens,
            reason=f"High title token overlap: {matched_tokens}",
        )

    # Tier 2c: Full-stack role title variant (e.g. "Full-Stack Developer" -> "Senior Full-Stack Engineer")
    has_query_fullstack = any(u[0] == "fullstack" for u in query_units) or (
        any(u[0] == "full" for u in query_units) and any(u[0] == "stack" for u in query_units)
    )
    if (
        has_query_fullstack
        and "fullstack" in title_terms
        and any(t in title_terms for t in ("developer", "engineer", "specialist"))
    ):
        return RelevanceResult(
            level=RelevanceLevel.STRONG,
            score=0.88,
            matched_tokens=["fullstack"],
            reason="Full-stack variant match in title",
        )

    # Tier 2d: Title-only related role specialization clusters (whole-word/phrase bounded)
    norm_query_phrase = _normalize_phrase(query)
    norm_title_phrase = _normalize_phrase(title)
    title_words = set(norm_title_phrase.split())

    is_related = False
    matched_related: list[str] = []

    if any(
        _has_whole_phrase(norm_query_phrase, q)
        for q in ("full stack", "fullstack", "software", "web developer", "developer")
    ):
        software_related = (
            "frontend",
            "front end",
            "backend",
            "back end",
            "software engineer",
            "software developer",
            "web developer",
            "platform engineer",
            "systems engineer",
            "android",
            "ios",
            "mobile developer",
        )
        for rel in software_related:
            if _has_whole_phrase(norm_title_phrase, rel):
                is_related = True
                matched_related.append(rel)
                break

    if not is_related and any(
        _has_whole_phrase(norm_query_phrase, q)
        for q in ("machine learning", "ml", "ai", "artificial intelligence")
    ):
        ml_related = (
            "computer vision",
            "nlp",
            "data scientist",
            "deep learning",
            "ai engineer",
            "ai systems",
            "machine learning",
        )
        for rel in ml_related:
            if _has_whole_phrase(norm_title_phrase, rel):
                is_related = True
                matched_related.append(rel)
                break

    if not is_related and any(
        _has_whole_phrase(norm_query_phrase, q)
        for q in ("devops", "sre", "site reliability", "infrastructure", "platform engineer", "cloud engineer")
    ):
        devops_related = (
            "devops",
            "sre",
            "site reliability",
            "infrastructure",
            "platform engineer",
            "cloud engineer",
            "kubernetes",
        )
        for rel in devops_related:
            if _has_whole_phrase(norm_title_phrase, rel):
                is_related = True
                matched_related.append(rel)
                break

    if is_related:
        score = 0.75 if ("engineer" in title_words or "developer" in title_words) else 0.65
        return RelevanceResult(
            level=RelevanceLevel.RELATED,
            score=score,
            matched_tokens=matched_related,
            reason=f"Related title specialization: {matched_related}",
        )

    return RelevanceResult(
        level=RelevanceLevel.IRRELEVANT,
        score=0.15,
        matched_tokens=[],
        reason=f"Title '{title}' does not match query '{query}'",
    )


def relevance_tier(
    query: str,
    title: str,
    company: str | None = None,
) -> tuple[int | None, RelevanceResult]:
    """Return `(tier, result)` where tier is 1 (exact/full title or company), 2 (close title), or None."""
    res = classify_relevance(query=query, title=title, company=company)
    if res.level == RelevanceLevel.STRONG and res.score >= 0.90:
        return (1, res)
    if res.level in (RelevanceLevel.STRONG, RelevanceLevel.RELATED):
        return (2, res)
    return (None, res)


def _freshness_tiebreak_key(item: Any) -> tuple[int, float]:
    posted_at = getattr(item, "posted_at", None)
    first_seen_at = getattr(item, "first_seen_at", None)
    evergreen_signal = getattr(item, "evergreen_signal", None)
    explicit_freshness = getattr(item, "freshness", None)
    computed = compute_freshness(
        posted_at=posted_at,
        first_seen_at=first_seen_at,
        evergreen_signal=evergreen_signal,
        explicit_freshness=explicit_freshness,
    )
    if hasattr(item, "freshness"):
        setattr(item, "freshness", computed)
    tier_rank = freshness_rank_key(item)
    if not posted_at:
        return (tier_rank, float("inf"))
    dt = posted_at if posted_at.tzinfo is not None else posted_at.replace(tzinfo=timezone.utc)
    return (tier_rank, -dt.timestamp())


def filter_and_rank_by_relevance(
    query: str,
    listings: Sequence[T],
    *,
    mode: str | None = None,
    on_drop: Callable[[T, RelevanceResult], None] | None = None,
) -> list[T]:
    """Single shared relevance gate and ranker for all search paths.

    - ``RELEVANCE_MODE=off`` bypasses filtering and preserves input list.
    - Tier 1 (exact/full title or exact company) ranks ahead of Tier 2 (close title match),
      sorted by freshness within each tier.
    """
    effective_mode = (mode if mode is not None else settings.relevance_mode).strip().lower()
    if effective_mode == "off" or not query or not query.strip():
        return list(listings)

    ranked: list[tuple[int, int, float, T]] = []
    for job in listings:
        title = getattr(job, "title", "") or ""
        company = getattr(job, "company", None)
        tier, res = relevance_tier(query, title, company=company)
        if tier is None:
            if on_drop is not None:
                on_drop(job, res)
            continue
        f_tier, f_ts = _freshness_tiebreak_key(job)
        ranked.append((tier, f_tier, f_ts, job))

    ranked.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
    return [entry[3] for entry in ranked]

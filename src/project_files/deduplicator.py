"""
Conservative, order-independent deduplicator with field-level progressive merging.

Follows Step 23, ADR 0028, and Operating Agreement:
- Strong matches only:
  1. ID match: (provider, company_or_tenant, provider_job_id)
  2. URL match: normalized URL carrying a verified job identifier
- Uncertain matches (same company + title, different location/URL) stay separate.
  Never merge on title and company alone.
- Order-independent merge identity:
  Highest source rank wins (API > fetched page body / scrape > snippet).
  Tie goes to the lexicographically smallest ID.
  Losing IDs are kept in aliases.
- Progressive field-level merge:
  Missing fields filled; higher confidence replaces lower confidence.
  Evidence preserved across all source observations.
"""

from __future__ import annotations

from typing import Any
from loguru import logger

from src.project_files.ats_url_parser import parse_ats_url
from src.project_files.confidence_policy import (
    compute_legacy_scalar_confidence,
    sanitize_source_url,
)
from src.project_files.models import (
    CanonicalJobField,
    ExtractionMethod,
    FieldEvidence,
    JobListing,
    JobSalary,
    ValidationStatus,
)
from src.project_files.url_normalizer import (
    build_id_match_key,
    build_url_match_key,
    normalize_job_url,
)

# ---------------------------------------------------------------------------
# Source Ranking
# ---------------------------------------------------------------------------

SOURCE_RANKS: dict[str, int] = {
    "api": 3,
    "ats_api": 3,
    "scrape": 2,
    "scraped": 2,
    "enricher": 2,
    "dom": 2,
    "json_ld": 2,
    "snippet": 1,
}


def get_source_rank(listing: JobListing) -> int:
    """Return numeric rank for listing source (3: API, 2: Page scrape/enricher, 1: Snippet)."""
    ds = (listing.data_source or "").lower().strip()
    return SOURCE_RANKS.get(ds, 1)


# ---------------------------------------------------------------------------
# Match Key Extraction
# ---------------------------------------------------------------------------

def extract_id_match_key(listing: JobListing) -> tuple[str, str, str] | None:
    """Extract strong ID match key (provider, company, provider_job_id)."""
    # 1. Check if apply_url or source_url parses cleanly into known ATS reference
    for u in (listing.apply_url, listing.source_url):
        if u:
            parsed = parse_ats_url(u)
            if parsed is not None:
                return build_id_match_key(parsed.ats, parsed.company_slug, parsed.job_id)

    # 2. Check source_record_id
    if listing.source_record_id:
        parts = listing.source_record_id.split(":")
        if len(parts) == 3:
            return build_id_match_key(parts[0], parts[1], parts[2])
        elif len(parts) == 2:
            return build_id_match_key(parts[0], listing.company_slug or listing.company, parts[1])

    # 3. Check listing.id
    if listing.id:
        parts = listing.id.split(":")
        if len(parts) == 3:
            return build_id_match_key(parts[0], parts[1], parts[2])
        elif len(parts) == 2:
            return build_id_match_key(parts[0], listing.company_slug or listing.company, parts[1])

    return None


def extract_url_match_key(listing: JobListing) -> str | None:
    """Extract strong URL match key if URL carries a verified job identifier."""
    for u in (listing.apply_url, listing.source_url):
        if u:
            key = build_url_match_key(u, listing.provider)
            if key is not None:
                return key
    return None


def listings_match(a: JobListing, b: JobListing) -> bool:
    """
    Evaluate whether two listings qualify for strong auto-merge.
    Never merges on company and title alone.
    """
    id_a = extract_id_match_key(a)
    id_b = extract_id_match_key(b)
    if id_a is not None and id_b is not None and id_a == id_b:
        return True

    url_a = extract_url_match_key(a)
    url_b = extract_url_match_key(b)
    if url_a is not None and url_b is not None and url_a == url_b:
        return True

    return False


# ---------------------------------------------------------------------------
# Field Confidence Lookup & Merging
# ---------------------------------------------------------------------------

def _get_field_confidence(listing: JobListing, field_name: str) -> float | None:
    """Find the highest confidence score for a given field from field_evidence."""
    if not listing.field_evidence:
        # Fall back to heuristic defaults based on data_source
        is_snippet = listing.data_source == "snippet"
        if field_name in ("title", "company"):
            return 0.30 if is_snippet else 0.90
        if field_name == "location":
            return 0.30 if is_snippet else 0.70
        if field_name == "apply_url":
            return 0.70 if is_snippet else 0.90
        if field_name == "description":
            return 0.90 if listing.description_ok else (None if is_snippet else 0.70)
        return None

    scores: list[float] = []
    for ev in listing.field_evidence:
        ev_field_str = ev.field.value if hasattr(ev.field, "value") else str(ev.field)
        if ev_field_str == field_name and ev.confidence_score is not None:
            scores.append(ev.confidence_score)

    return max(scores) if scores else None


def merge_listings(record_a: JobListing, record_b: JobListing) -> JobListing:
    """
    Progressively merge two matching listings in a strictly order-independent manner.
    """
    rank_a = get_source_rank(record_a)
    rank_b = get_source_rank(record_b)

    # 1. Determine surviving identity & base record
    if rank_a > rank_b:
        surviving_id = record_a.id
        losing_id = record_b.id
        base = record_a.model_copy(deep=True)
        donor = record_b
    elif rank_b > rank_a:
        surviving_id = record_b.id
        losing_id = record_a.id
        base = record_b.model_copy(deep=True)
        donor = record_a
    else:
        # Equal rank: tie-break by lexicographically smallest ID
        if record_a.id <= record_b.id:
            surviving_id = record_a.id
            losing_id = record_b.id
            base = record_a.model_copy(deep=True)
            donor = record_b
        else:
            surviving_id = record_b.id
            losing_id = record_a.id
            base = record_b.model_copy(deep=True)
            donor = record_a

    # 2. Update aliases
    combined_aliases = set(base.aliases) | set(donor.aliases) | {losing_id}
    combined_aliases.discard(surviving_id)
    base.aliases = sorted(combined_aliases)
    base.id = surviving_id

    # 3. Field-by-field progressive replacement
    fields_to_check = [
        "title",
        "company",
        "company_slug",
        "location",
        "work_model",
        "work_model_source",
        "work_model_evidence",
        "raw_workplace_type",
        "employment_type",
        "salary",
        "description",
        "requirements",
        "posted_at",
        "apply_url",
    ]

    fields_updated: list[str] = []
    for field in fields_to_check:
        val_base = getattr(base, field, None)
        val_donor = getattr(donor, field, None)

        if val_base is None or val_base == "":
            if val_donor is not None and val_donor != "":
                setattr(base, field, val_donor)
                fields_updated.append(field)
        elif val_donor is not None and val_donor != "":
            conf_base = _get_field_confidence(base, field) or 0.0
            conf_donor = _get_field_confidence(donor, field) or 0.0
            if conf_donor > conf_base:
                setattr(base, field, val_donor)
                fields_updated.append(field)

    # 4. Evidence aggregation & merge provenance record
    all_evidence = list(base.field_evidence or [])
    donor_evidence = list(donor.field_evidence or [])

    # Keep unique donor evidence items
    existing_ev_keys = {
        (ev.field.value if hasattr(ev.field, "value") else str(ev.field), str(ev.raw_value)[:100])
        for ev in all_evidence
    }
    for dev in donor_evidence:
        d_key = (dev.field.value if hasattr(dev.field, "value") else str(dev.field), str(dev.raw_value)[:100])
        if d_key not in existing_ev_keys:
            all_evidence.append(dev)
            existing_ev_keys.add(d_key)

    # Record merge provenance
    log_msg = f"Merged {losing_id} into {surviving_id}. Fields updated: {fields_updated}"
    logger.info(f"Deduplicator: {log_msg}")

    donor_meth = (
        ExtractionMethod.ATS_API
        if get_source_rank(donor) == 3
        else (ExtractionMethod.SCRAPE if get_source_rank(donor) == 2 else ExtractionMethod.SNIPPET)
    )
    all_evidence.append(
        FieldEvidence(
            field=CanonicalJobField.APPLY_URL,
            normalized_value=normalize_job_url(donor.apply_url),
            raw_value=sanitize_source_url(donor.apply_url),
            method=donor_meth,
            provider=donor.provider,
            source_url=sanitize_source_url(donor.source_url),
            validation_status=ValidationStatus.ACCEPTED,
            confidence_score=_get_field_confidence(donor, "apply_url"),
            reason=f"Merged {losing_id} into {surviving_id}. Updated fields: {', '.join(fields_updated) if fields_updated else 'none'}",
        )
    )
    base.field_evidence = all_evidence

    # 5. Maintenance
    if base.description:
        base.description_ok = len(base.description) > 50

    # Deterministically update scalar confidence from core fields
    core_confidences: dict[CanonicalJobField, float] = {}
    is_snippet = base.data_source == "snippet"
    for core_field in (
        CanonicalJobField.TITLE,
        CanonicalJobField.COMPANY,
        CanonicalJobField.LOCATION,
        CanonicalJobField.APPLY_URL,
        CanonicalJobField.DESCRIPTION,
    ):
        conf = _get_field_confidence(base, core_field.value)
        if conf is not None:
            core_confidences[core_field] = conf
        elif getattr(base, core_field.value, None):
            if core_field in (CanonicalJobField.TITLE, CanonicalJobField.COMPANY):
                core_confidences[core_field] = 0.30 if is_snippet else 0.90
            elif core_field == CanonicalJobField.LOCATION:
                core_confidences[core_field] = 0.30 if is_snippet else 0.70
            elif core_field == CanonicalJobField.APPLY_URL:
                core_confidences[core_field] = 0.70 if is_snippet else 0.90
            elif core_field == CanonicalJobField.DESCRIPTION and not is_snippet:
                core_confidences[core_field] = 0.90 if base.description_ok else 0.70

    base.extraction_confidence = compute_legacy_scalar_confidence(core_confidences)
    return base


# ---------------------------------------------------------------------------
# Material Improvement Evaluation
# ---------------------------------------------------------------------------

def is_material_improvement(existing: JobListing, merged: JobListing) -> bool:
    """Evaluate whether merged listing contains material improvements over existing emitted record.

    Prevents emitting duplicate SSE updates when incoming duplicates add no new information,
    while guaranteeing that valuable additions (description, requirements, salary, etc.)
    reach SearchOrchestrator and downstream SSE clients.
    """
    # 1. Description improvement
    if not existing.description and bool(merged.description):
        return True
    if not existing.description_ok and bool(merged.description_ok):
        return True
    if bool(merged.description) and len(merged.description) >= len(existing.description or "") + 50:
        return True

    # 2. Requirements improvement
    if not existing.requirements and bool(merged.requirements):
        return True
    if bool(merged.requirements) and merged.requirements != existing.requirements and len(merged.requirements) > len(existing.requirements or ""):
        return True

    # 3. Salary improvement
    if existing.salary is None and merged.salary is not None:
        return True
    if existing.salary != merged.salary and bool(merged.salary):
        return True

    # 4. Location improvement
    if not existing.location and bool(merged.location):
        return True

    # 5. Work model resolution
    if (existing.work_model is None or existing.work_model == "unknown") and merged.work_model in ("remote", "hybrid", "onsite"):
        return True

    # 6. Raw workplace type improvement
    if not existing.raw_workplace_type and bool(merged.raw_workplace_type):
        return True

    # 7. Employment type improvement
    if not existing.employment_type and bool(merged.employment_type):
        return True

    # 8. Authoritative posting date improvement
    if existing.posted_at is None and merged.posted_at is not None:
        return True

    # 9. Company slug improvement
    if not existing.company_slug and bool(merged.company_slug):
        return True

    # 10. Remote resolution
    if existing.is_remote is None and merged.is_remote is not None:
        return True

    # 11. Material confidence gain
    if (merged.extraction_confidence or 0.0) >= (existing.extraction_confidence or 0.0) + 0.10:
        return True

    return False


# ---------------------------------------------------------------------------
# Global Deduplicator Class
# ---------------------------------------------------------------------------

class GlobalDeduplicator:
    """
    Conservative, order-independent deduplicator with progressive merging.
    Maintains backward compatibility with search_pipeline streaming loops.
    """

    def __init__(self):
        self._emitted: list[JobListing] = []
        self._seen_ids: set[str] = set()

    def deduplicate(self, listings: list[JobListing]) -> list[JobListing]:
        """
        Deduplicate an entire list of listings order-independently with progressive merging.
        """
        if not listings:
            return []

        merged_results: list[JobListing] = []
        for item in listings:
            matched_idx = -1
            for idx, existing in enumerate(merged_results):
                if listings_match(item, existing):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                merged_results[matched_idx] = merge_listings(merged_results[matched_idx], item)
            else:
                merged_results.append(item.model_copy(deep=True))

        return merged_results

    def filter(self, listings: list[JobListing]) -> list[JobListing]:
        """
        Progressive streaming deduplication filter.
        Merges batch items before emission. Returns only newly discovered listings or
        materially upgraded representations.
        """
        if not listings:
            return []

        # 1. Deduplicate the incoming batch internally first
        deduped_batch = self.deduplicate(listings)

        new_emissions: list[JobListing] = []
        for item in deduped_batch:
            # 2. Check if item matches any already-emitted record
            matched_idx = -1
            for idx, emitted in enumerate(self._emitted):
                if (
                    item.id == emitted.id
                    or item.id in emitted.aliases
                    or emitted.id in item.aliases
                    or listings_match(item, emitted)
                ):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                existing = self._emitted[matched_idx]
                rank_existing = get_source_rank(existing)
                rank_incoming = get_source_rank(item)

                # Merge into internal emitted record state (order-independent)
                merged = merge_listings(existing, item)
                self._emitted[matched_idx] = merged
                self._seen_ids.add(item.id)
                self._seen_ids.update(item.aliases)

                # Upgrade: emit if incoming arrival is strictly higher-ranked OR
                # if duplicate materially improves the record (description, requirements, salary, etc.)
                if rank_incoming > rank_existing or is_material_improvement(existing, merged):
                    new_emissions.append(merged)
            else:
                self._emitted.append(item)
                self._seen_ids.add(item.id)
                self._seen_ids.update(item.aliases)
                new_emissions.append(item)

        return new_emissions

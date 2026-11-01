from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.project_files.confidence_policy import compute_legacy_scalar_confidence
from src.project_files.field_normalizer import description_quality
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    ExtractionMethod,
    FieldEvidence,
    JobListing,
    JobSalary,
)


class CanonicalJobAdapter:
    """Bi-directional adapter between CanonicalJob and external JobListing wire format."""

    @staticmethod
    def to_listing(canonical: CanonicalJob) -> JobListing:
        """Translate a CanonicalJob into a JobListing for external serialization."""
        # Derive legacy is_remote boolean
        is_remote: Optional[bool]
        if canonical.work_model == "remote":
            is_remote = True
        elif canonical.work_model in ("in_person", "hybrid"):
            is_remote = False
        else:
            is_remote = None

        # Derive legacy description and description_ok
        desc_ok = bool(canonical.description and description_quality(canonical.description))
        listing_desc = canonical.description

        # Derive data_source from evidence if available, defaulting to "api"
        data_source = "api"
        for ev in canonical.field_evidence:
            if ev.method == ExtractionMethod.SCRAPE:
                data_source = "scrape"
                break
            elif ev.method == ExtractionMethod.SNIPPET:
                data_source = "snippet"
                break

        provider = canonical.source
        apply_url = canonical.application_url
        source_url = canonical.source_url
        job_id = canonical.id or f"{provider}:{canonical.company_slug or 'unknown'}:{hash(apply_url)}"

        # Derive legacy scalar confidence from core field confidences
        if canonical.field_confidence:
            conf_by_field = {fc.field: fc.score for fc in canonical.field_confidence}
            scalar_confidence = compute_legacy_scalar_confidence(conf_by_field)
        elif canonical.extraction_confidence is not None:
            scalar_confidence = canonical.extraction_confidence
        else:
            # Fall back to deriving from populated canonical core fields
            scores: dict[CanonicalJobField, float] = {}
            is_snippet = data_source == "snippet"
            if canonical.title:
                scores[CanonicalJobField.TITLE] = 0.30 if is_snippet else 0.90
            if canonical.company and canonical.company != "Unknown":
                scores[CanonicalJobField.COMPANY] = 0.30 if is_snippet else 0.90
            if canonical.location:
                scores[CanonicalJobField.LOCATION] = 0.30 if is_snippet else 0.70
            if canonical.application_url:
                scores[CanonicalJobField.APPLY_URL] = 0.70 if is_snippet else 0.90
            if canonical.description and not is_snippet:
                scores[CanonicalJobField.DESCRIPTION] = 0.90 if desc_ok else 0.70
            scalar_confidence = compute_legacy_scalar_confidence(scores)

        listing = JobListing(
            id=job_id,
            provider=provider,
            data_source=data_source,
            title=canonical.title,
            company=canonical.company,
            company_slug=canonical.company_slug,
            location=canonical.location,
            is_remote=is_remote,
            employment_type=canonical.employment_type,
            work_model=canonical.work_model,
            work_model_source=canonical.work_model_source,
            work_model_evidence=canonical.work_model_evidence,
            raw_workplace_type=canonical.raw_workplace_type,
            department=canonical.department,
            salary=canonical.salary,
            description=listing_desc,
            description_ok=desc_ok,
            requirements=canonical.requirements,
            extraction_confidence=scalar_confidence,
            field_evidence=canonical.field_evidence,
            posted_at=canonical.posted_at,
            scraped_at=canonical.scraped_at or datetime.now(timezone.utc),
            apply_url=apply_url,
            source_url=source_url,
            query_used=canonical.query_used or "",
            ats_source=canonical.ats_source or provider,
            source_record_id=canonical.source_record_id,
            aliases=list(canonical.aliases),
        )
        for k in ("extraction_outcome", "degraded_from"):
            val = getattr(canonical, k, None)
            if val is not None:
                setattr(listing, k, val)
        return listing

    @staticmethod
    def from_listing(listing: JobListing) -> CanonicalJob:
        """Translate a legacy JobListing into a CanonicalJob."""
        salary: JobSalary | None = None
        if isinstance(listing.salary, JobSalary):
            salary = listing.salary
        elif isinstance(listing.salary, str) and listing.salary.strip():
            from src.project_files.salary_parser import parse_text_salary
            salary = parse_text_salary(listing.salary, bare_n_is_ngn=True)

        evidence: list[FieldEvidence] = []
        if listing.field_evidence:
            evidence = list(listing.field_evidence)
        elif listing.title:
            meth = (
                ExtractionMethod.ATS_API
                if listing.data_source == "api"
                else (ExtractionMethod.SCRAPE if listing.data_source == "scrape" else ExtractionMethod.SNIPPET)
            )
            evidence.append(
                FieldEvidence(
                    field=CanonicalJobField.TITLE,
                    raw_value=listing.title,
                    method=meth,
                    source_url=listing.source_url,
                )
            )

        extra_attrs = {
            k: getattr(listing, k)
            for k in ("extraction_outcome", "degraded_from")
            if getattr(listing, k, None) is not None
        }

        return CanonicalJob(
            id=listing.id,
            source=listing.provider,
            source_url=listing.source_url,
            application_url=listing.apply_url,
            title=listing.title,
            company=listing.company,
            company_slug=listing.company_slug,
            location=listing.location,
            work_model=listing.work_model,
            work_model_source=listing.work_model_source,
            work_model_evidence=listing.work_model_evidence,
            raw_workplace_type=listing.raw_workplace_type,
            department=listing.department,
            employment_type=listing.employment_type,
            salary=salary,
            description=listing.description,
            requirements=listing.requirements,
            posted_at=listing.posted_at,
            scraped_at=listing.scraped_at,
            query_used=listing.query_used or "",
            ats_source=listing.ats_source or listing.provider,
            source_record_id=listing.source_record_id,
            aliases=list(listing.aliases),
            extraction_confidence=listing.extraction_confidence,
            field_evidence=evidence,
            **extra_attrs,
        )

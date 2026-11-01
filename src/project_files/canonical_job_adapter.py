from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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
        listing_desc = canonical.description if desc_ok else None

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

        return JobListing(
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
            posted_at=canonical.posted_at,
            scraped_at=canonical.scraped_at or datetime.now(timezone.utc),
            apply_url=apply_url,
            source_url=source_url,
            query_used=canonical.query_used or "",
            ats_source=canonical.ats_source or provider,
        )

    @staticmethod
    def from_listing(listing: JobListing) -> CanonicalJob:
        """Translate a legacy JobListing into a CanonicalJob."""
        salary = listing.salary if isinstance(listing.salary, JobSalary) else None

        evidence: list[FieldEvidence] = []
        if listing.title:
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
            field_evidence=evidence,
        )

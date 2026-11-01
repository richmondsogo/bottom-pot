from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.project_files.field_normalizer import (
    humanize_slug,
    normalize_job_type,
    normalize_job_type_from_text,
    strip_li_tags,
    to_markdown,
)
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    ExtractionMethod,
    FieldEvidence,
    ValidationStatus,
)
from src.project_files.salary_parser import extract_salary
from src.project_files.work_model import resolve_work_model


class RawJobPosting(BaseModel):
    """Immutable acquisition envelope capturing raw fetched fields before extraction."""

    provider: str
    source_url: str
    provider_job_id: Optional[str] = None
    company_slug: Optional[str] = None
    apply_url: Optional[str] = None
    raw_title: Optional[str] = None
    raw_company: Optional[str] = None
    raw_location: Optional[str] = None
    raw_workplace_type: Optional[str] = None
    raw_department: Optional[str] = None
    raw_employment_type: Optional[str] = None
    raw_date: Optional[str | int | float | datetime] = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    raw_description: Optional[str] = None
    description_is_authentic: bool = True
    query_used: str = ""
    scraped_at: Optional[datetime] = None


def parse_tz_aware_date(raw_date: str | int | float | datetime | None) -> Optional[datetime]:
    """Centralized timezone-aware UTC date parser."""
    if raw_date is None:
        return None

    if isinstance(raw_date, datetime):
        return raw_date if raw_date.tzinfo is not None else raw_date.replace(tzinfo=timezone.utc)

    if isinstance(raw_date, (int, float)):
        # Epoch ms vs epoch seconds
        val = float(raw_date)
        if val > 1e11:  # Milliseconds
            val /= 1000.0
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    if isinstance(raw_date, str):
        clean_str = raw_date.strip()
        if not clean_str:
            return None
        # Handle ISO strings
        try:
            iso_str = clean_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


class JobExtractionService:
    """Centralized shared extraction and normalization service.
    Owns description cleaning, work-model resolution, salary extraction, and tz date parsing.
    """

    @classmethod
    def extract(cls, raw: RawJobPosting) -> CanonicalJob:
        # 1. Clean description
        cleaned_description: Optional[str] = None
        if raw.raw_description:
            # Strip recruiter tags and convert HTML to markdown
            cleaned_description = to_markdown(strip_li_tags(raw.raw_description))

        # 2. Title & Company
        title = (raw.raw_title or raw.raw_fields.get("title") or raw.raw_fields.get("text") or "").strip()
        company = (
            raw.raw_company
            or raw.raw_fields.get("company_name")
            or raw.raw_fields.get("company")
            or humanize_slug(raw.company_slug)
            or "Unknown"
        ).strip()

        location = raw.raw_location if raw.raw_location is not None else (
            (raw.raw_fields.get("location") or {}).get("name")
            if isinstance(raw.raw_fields.get("location"), dict)
            else raw.raw_fields.get("location")
        )

        # 3. Employment Type
        raw_emp = raw.raw_employment_type or raw.raw_fields.get("employment_type") or raw.raw_fields.get("employmentType")
        employment = normalize_job_type(raw_emp)
        if employment is None and cleaned_description and raw.description_is_authentic:
            employment = normalize_job_type_from_text(cleaned_description)

        # 4. Work Model Resolution
        wm_res = resolve_work_model(
            workplace_type=raw.raw_workplace_type,
            location=location,
            title=title,
            description=cleaned_description,
            description_eligible=raw.description_is_authentic,
            trusted_description=raw.raw_description,
        )

        # 5. Salary Extraction
        salary = extract_salary(
            provider=raw.provider,
            raw_fields=raw.raw_fields,
            description=cleaned_description,
            location_hint=location,
        )

        # 6. Datetime Parsing
        posted_at = parse_tz_aware_date(raw.raw_date)

        # 7. Identity & URLs
        job_id = ""
        if raw.provider_job_id and raw.company_slug:
            job_id = f"{raw.provider}:{raw.company_slug}:{raw.provider_job_id}"
        elif raw.provider_job_id:
            job_id = f"{raw.provider}:{raw.provider_job_id}"

        apply_url = raw.apply_url or raw.source_url

        # 8. Field Evidence
        evidence: list[FieldEvidence] = []
        meth = ExtractionMethod.ATS_API if raw.description_is_authentic else ExtractionMethod.SNIPPET
        if title:
            evidence.append(FieldEvidence(field=CanonicalJobField.TITLE, raw_value=title, method=meth, source_url=raw.source_url))
        if wm_res.value:
            evidence.append(FieldEvidence(
                field=CanonicalJobField.WORK_MODEL,
                raw_value=wm_res.evidence or wm_res.value,
                method=meth,
                source_url=raw.source_url,
            ))
        if salary:
            evidence.append(FieldEvidence(
                field=CanonicalJobField.SALARY,
                raw_value=salary.raw_text or str(salary.model_dump()),
                method=meth,
                source_url=raw.source_url,
            ))

        return CanonicalJob(
            id=job_id,
            source=raw.provider,
            source_url=raw.source_url,
            application_url=apply_url,
            title=title,
            company=company,
            company_slug=raw.company_slug,
            location=location,
            work_model=wm_res.value,
            work_model_source=wm_res.source,
            work_model_evidence=wm_res.evidence,
            raw_workplace_type=raw.raw_workplace_type,
            department=raw.raw_department,
            employment_type=employment,
            salary=salary,
            description=cleaned_description,
            posted_at=posted_at,
            scraped_at=raw.scraped_at or datetime.now(timezone.utc),
            query_used=raw.query_used,
            ats_source=raw.provider,
            field_evidence=evidence,
        )

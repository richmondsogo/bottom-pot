from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.project_files.field_normalizer import (
    humanize_slug,
    normalize_job_type,
    normalize_job_type_from_text,
    parse_datetime,
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
from src.project_files.work_model import _scan, resolve_work_model


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
    raw_salary: Optional[str] = None
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
        return parse_datetime(clean_str)

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

        # Location and JSON-LD applicantLocationRequirements
        applicant_req = raw.raw_fields.get("applicantLocationRequirements")
        if not applicant_req and isinstance(raw.raw_fields.get("json_ld"), dict):
            applicant_req = raw.raw_fields["json_ld"].get("applicantLocationRequirements")

        applicant_req_str: str | None = None
        if isinstance(applicant_req, dict):
            applicant_req_str = applicant_req.get("name") or applicant_req.get("@id")
        elif isinstance(applicant_req, list):
            applicant_req_str = ", ".join(filter(None, [r.get("name") if isinstance(r, dict) else str(r) for r in applicant_req]))
        elif isinstance(applicant_req, str) and applicant_req.strip():
            applicant_req_str = applicant_req.strip()

        location = raw.raw_location
        if not location:
            if applicant_req_str:
                location = f"{applicant_req_str} (Remote)"
        elif applicant_req_str and applicant_req_str.lower() not in location.lower():
            location = f"{location} ({applicant_req_str})"

        # 3. Employment Type
        raw_emp = raw.raw_employment_type or raw.raw_fields.get("employment_type") or raw.raw_fields.get("employmentType")
        if not raw_emp and isinstance(raw.raw_fields.get("json_ld"), dict):
            raw_emp = raw.raw_fields["json_ld"].get("employmentType")
        employment = normalize_job_type(raw_emp)
        if employment is None and cleaned_description and raw.description_is_authentic:
            employment = normalize_job_type_from_text(cleaned_description)

        # 4. Work Model Resolution
        workplace_type_for_resolver = raw.raw_workplace_type
        if raw.raw_workplace_type and raw.raw_workplace_type.startswith("remote="):
            if "hybrid=True" in raw.raw_workplace_type:
                workplace_type_for_resolver = "hybrid"
            elif "remote=True" in raw.raw_workplace_type:
                workplace_type_for_resolver = "remote"
            else:
                workplace_type_for_resolver = None

        jsonld_loc_type = raw.raw_fields.get("jobLocationType")
        if not jsonld_loc_type and isinstance(raw.raw_fields.get("json_ld"), dict):
            jsonld_loc_type = raw.raw_fields["json_ld"].get("jobLocationType")
        if isinstance(jsonld_loc_type, str):
            jsonld_loc_type = jsonld_loc_type.strip()

        title_for_wm = raw.raw_fields.get("title_for_wm") if (raw.raw_fields and raw.raw_fields.get("title_for_wm")) else title
        wm_res = resolve_work_model(
            workplace_type=workplace_type_for_resolver,
            jsonld_location_type=jsonld_loc_type,
            location=location,
            title=title_for_wm,
            description=cleaned_description,
            description_eligible=raw.description_is_authentic,
            trusted_description=raw.raw_description,
        )
        work_model_evidence = (
            raw.raw_workplace_type
            if raw.raw_workplace_type and raw.raw_workplace_type.startswith("remote=") and wm_res.source == "api_enum"
            else wm_res.evidence
        )

        # Detect description conflict with structured work model
        desc_conflicts: dict[str, str] = {}
        if cleaned_description and raw.description_is_authentic and wm_res.value:
            desc_scan = _scan(cleaned_description)
            for m, snippet in desc_scan.items():
                if m != wm_res.value:
                    desc_conflicts[m] = snippet

        # 5. Salary Extraction (snippets with description_is_authentic=False never extract salary from description)
        if raw.raw_salary and "salary" not in raw.raw_fields:
            raw.raw_fields["salary"] = raw.raw_salary
        salary = extract_salary(
            provider=raw.provider,
            raw_fields=raw.raw_fields,
            description=cleaned_description if raw.description_is_authentic else None,
            location_hint=location,
            bare_n_is_ngn=bool(raw.raw_fields.get("bare_n_is_ngn", False)),
        )

        # 6. Datetime Parsing
        raw_date = raw.raw_date
        if not raw_date:
            raw_date = raw.raw_fields.get("datePosted")
            if not raw_date and isinstance(raw.raw_fields.get("json_ld"), dict):
                raw_date = raw.raw_fields["json_ld"].get("datePosted")
        posted_at = parse_tz_aware_date(raw_date)

        # 7. Identity & URLs
        job_id = ""
        if raw.provider_job_id and raw.company_slug:
            job_id = f"{raw.provider}:{raw.company_slug}:{raw.provider_job_id}"
        elif raw.provider_job_id:
            job_id = f"{raw.provider}:{raw.provider_job_id}"

        apply_url = raw.apply_url or raw.source_url

        # 8. Field Evidence
        evidence: list[FieldEvidence] = []
        meth = ExtractionMethod.SCRAPE if (raw.provider == "workable" or not raw.description_is_authentic) else ExtractionMethod.ATS_API
        if title:
            evidence.append(FieldEvidence(field=CanonicalJobField.TITLE, raw_value=title, method=meth, source_url=raw.source_url))
        if location:
            loc_meth = ExtractionMethod.JSON_LD if applicant_req_str else meth
            evidence.append(FieldEvidence(field=CanonicalJobField.LOCATION, raw_value=location, method=loc_meth, source_url=raw.source_url))
        if applicant_req_str:
            evidence.append(FieldEvidence(
                field=CanonicalJobField.LOCATION,
                raw_value=f"applicantLocationRequirements: {applicant_req_str}",
                method=ExtractionMethod.JSON_LD,
                source_url=raw.source_url,
            ))
        if wm_res.value:
            wm_meth = ExtractionMethod.JSON_LD if wm_res.source == "jsonld" else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.WORK_MODEL,
                raw_value=wm_res.evidence or wm_res.value,
                method=wm_meth,
                source_url=raw.source_url,
            ))
            for m, snippet in desc_conflicts.items():
                evidence.append(FieldEvidence(
                    field=CanonicalJobField.WORK_MODEL,
                    raw_value=f"description_conflict: {snippet}",
                    method=ExtractionMethod.DOM,
                    source_url=raw.source_url,
                ))
        if salary:
            sal_meth = ExtractionMethod.JSON_LD if salary.source == "json_ld" else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.SALARY,
                raw_value=salary.raw_text or str(salary.model_dump()),
                method=sal_meth,
                source_url=raw.source_url,
            ))
        if employment:
            emp_meth = ExtractionMethod.JSON_LD if (raw.raw_fields.get("employmentType") or (isinstance(raw.raw_fields.get("json_ld"), dict) and raw.raw_fields["json_ld"].get("employmentType"))) else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.EMPLOYMENT_TYPE,
                raw_value=raw_emp or employment,
                method=emp_meth,
                source_url=raw.source_url,
            ))
        if posted_at:
            date_meth = ExtractionMethod.JSON_LD if (raw.raw_fields.get("datePosted") or (isinstance(raw.raw_fields.get("json_ld"), dict) and raw.raw_fields["json_ld"].get("datePosted"))) else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.POSTED_AT,
                raw_value=posted_at.isoformat(),
                method=date_meth,
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
            work_model_evidence=work_model_evidence,
            raw_workplace_type=raw.raw_workplace_type,
            department=raw.raw_department or (raw.raw_fields.get("department") if raw.raw_fields else None),
            employment_type=employment,
            salary=salary,
            description=cleaned_description,
            posted_at=posted_at,
            scraped_at=raw.scraped_at or datetime.now(timezone.utc),
            query_used=raw.query_used,
            ats_source=raw.provider,
            field_evidence=evidence,
        )

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.project_files.eligibility_extractor import extract_eligibility, normalize_country_name

from src.project_files.field_normalizer import (
    description_quality,
    humanize_slug,
    normalize_job_type,
    normalize_job_type_from_text,
    parse_datetime,
    strip_li_tags,
    to_markdown,
)
from src.project_files.confidence_policy import (
    EvidenceType,
    compute_field_confidence,
    sanitize_raw_evidence,
    sanitize_source_url,
)
from src.project_files.url_normalizer import normalize_job_url
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    ExtractionMethod,
    FieldConfidence,
    FieldEvidence,
    ValidationStatus,
)
from src.project_files.salary_parser import extract_salary
from src.project_files.work_model import _scan, resolve_work_model


class RawJobPosting(BaseModel):
    """Immutable acquisition envelope capturing raw fetched fields before extraction."""

    provider: str
    source_url: str
    source_record_id: Optional[str] = None
    provider_job_id: Optional[str] = None
    company_slug: Optional[str] = None
    apply_url: Optional[str] = None
    raw_title: Optional[str] = None
    raw_company: Optional[str] = None
    raw_location: Optional[str] = None
    raw_workplace_type: Optional[str] = None
    workplace_type: Optional[str] = None
    workplace_type_resolved: bool = False
    work_model_evidence: Optional[str] = None
    extraction_method: Optional[ExtractionMethod] = None
    raw_department: Optional[str] = None
    raw_employment_type: Optional[str] = None
    raw_salary: Optional[str] = None
    raw_date: Optional[str | int | float | datetime] = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    raw_description: Optional[str] = None
    raw_requirements: Optional[str] = None
    description_is_authentic: bool = True
    query_used: str = ""
    scraped_at: Optional[datetime] = None


_REQUIREMENT_HEADER_TITLES = (
    r"requirements?|qualifications?(?:\s*(?:&|and)\s*experience)?|what you(?:'ll| will) need|what we(?:'re| are) looking for|"
    r"what you(?:'ll| will)?\s+bring|what makes you a great fit|required experience|you need to have|we believe you have|"
    r"if you have the following|your qualifications|knowledge(?:\s*(?:&|and))?\s*experience|"
    r"your areas of expertise|skills?(?:\s*(?:&|and)\s*experience)?|who you are(?:\s*/\s*key\s+requirements?)?|"
    r"minimum\s+requirements?|preferred\s+requirements?|eligibility\s*(?:&|and)\s*qualifications?|preferred\s+experience|"
    r"what\s+you(?:'ve|\s+have)\s+done|what\s+you\s+have|what\s+you\s+need(?:\s+to\s+be\s+successful)?|"
    r"you(?:'re|\s+are)\s+(?:a\s+great\s+fit|the\s+right\s+person)\s+if|you\s+should\s+apply\s+if|"
    r"minimum qualifications?|basic qualifications?|required qualifications?|"
    r"required skills?|prerequisites?|your profile(?:\s+for\s+this\s+(?:job|role|position))?|about you|profile|"
    r"what you should have|what we look for|who we(?:'re| are) looking for|"
    r"what makes a great candidate|must[- ]haves?|(?:our\s+)?ideal candidate(?:'s)?(?:\s+has)?|"
    r"we(?:'d| would)\s+love to hear from you if you have|here(?:'s| is)\s+what we(?:'re| are) looking for|"
    r"required knowledge(?:,\s*|\s*(?:&|and)\s*)skills(?:,\s*|\s*(?:&|and)\s*)and abilities|"
    r"experience\s+(?:&|and)\s+qualifications|essential qualifications?|"
    r"skills?\s*(?:&|and)\s*requirements?|requirements?\s*(?:&|and)\s*skills?|non-negotiables|"
    r"to\s+be\s+successful\s+in\s+this\s+(?:role|job|position),?\s+you\s+(?:are\s+likely\s+to|will|should)\s+(?:have|bring)"
    r"(?:\s+the\s+following)?\s+(?:skills?(?:\s*/\s*experience|\s*(?:&|and)\s*experience)?|experience|qualifications?|requirements?)|"
    r"qu[eé]\s+buscamos|requisitos(?:\s+m[ií]nimos)?|cualificaciones|anforderungen|qualifikationen|comp[eé]tences|profil\s+recherch[eé]"
)

_NON_REQUIREMENT_STOP_HEADING_RE = re.compile(
    r"^(?:[¿¡]?(?:"
    r"what we(?:'re| are) offering|what we offer|our offer|what's in it for you|what we can offer you|"
    r"what you(?:'ll| will) do|responsibilit(?:y|ies)|your mission|overview|"
    r"benefits?(?:\s*(?:&|and)\s*(?:perks|work environment))?|perks|our benefits|"
    r"compensation(?:\s*(?:&|and)\s*benefits)?|salary(?:\s*(?:&|and)\s*benefits)?|remuneration|"
    r"pay\s+(?:range\s+)?transparency(?:\s+disclosure)?|pay\s+transparency|pay\s+range|"
    r"diversity(?:\s*(?:&|and)\s*inclusion)?|equal\s+(?:opportunity|employment)(?:\s+employer)?|inclusion|"
    r"equity,?\s+diversity\s+and\s+inclusion|our\s+commitment\s+to\s+diversity[^\n]*|"
    r"why\s+(?:work|you(?:'ll| will)\s+love\s+working|join)[^\n]*|join\s+[^\n]+|"
    r"about\s+(?!you\b)(?:us|the\s+(?:company|team)|[A-Za-z0-9._&-]+)|who\s+we\s+are|our\s+culture|the\s+[A-Za-z0-9._&-]+\s+experience|"
    r"how\s+[A-Za-z0-9._&-]+\s+supports[^\n]*|"
    r"compliance|itar\s+requirements|application\s+limits|country\s+hiring\s+guidelines|privacy\s+policy|"
    r"(?:recruitment|hiring|selection|interview)\s+process|how\s+to\s+apply|here\s+are\s+the\s+stages[^\n]*|next\s+steps|"
    r"qu[eé]\s+ofrecemos|lo\s+que\s+ofrecemos|unser\s+angebot|was\s+wir\s+bieten|nous\s+proposons|ce\s+que\s+nous\s+offrons|"
    r"additional\s+information|note\s+to\s+recruiters"
    r")[.…?:\s]*)$",
    re.IGNORECASE,
)

_HEADING_LINE_RE = re.compile(
    r"^[ \t]*(?:#{1,6}\s+(?:\*\*\s*)?(.+?)(?:\s*\*\*)?[ \t]*$|\*\*\s*([^*\n]{2,120}?)\s*\*\*)[ \t]*$"
)

_WORKDAY_CITY_STATE_RE = re.compile(r"^[^,]+,\s*[A-Z]{2}$")
_WORKDAY_FACILITY_CODE_RE = re.compile(r"\b[A-Z0-9]{2,}\b")


def _extract_structured_country_descriptor(raw_fields: dict[str, Any] | None) -> str | None:
    if not raw_fields:
        return None
    for candidate in (
        raw_fields.get("country"),
        (raw_fields.get("jobRequisitionLocation") or {}).get("country")
        if isinstance(raw_fields.get("jobRequisitionLocation"), dict)
        else None,
    ):
        if isinstance(candidate, dict):
            desc = candidate.get("descriptor") or candidate.get("name")
            if isinstance(desc, str) and desc.strip():
                return normalize_country_name(desc)
        elif isinstance(candidate, str) and candidate.strip():
            return normalize_country_name(candidate)
    return None


def _normalize_workday_location(raw_location: str | None, structured_country: str | None) -> str | None:
    """
    Normalize Workday location strings cleanly while upholding Decision 1 (Option A):
    - Deduplicate repeated trailing country suffixes (e.g. "Pune, India, India" -> "Pune, India").
    - Append verified structured CXS country descriptor to opaque facility codes when absent.
    - Never guess city names from facility codes or drop UTF-8 diacritics.
    """
    if not raw_location or not isinstance(raw_location, str):
        return None
    cleaned = re.sub(r"\s+", " ", raw_location).strip()
    if not cleaned:
        return None

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) >= 2:
        last_lower = parts[-1].lower()
        if len(last_lower) > 2:
            prior_tokens: set[str] = set()
            for prior in parts[:-1]:
                prior_tokens.add(prior.lower())
                for sub in re.split(r"\s*-\s*", prior):
                    if sub.strip():
                        prior_tokens.add(sub.strip().lower())
            if last_lower in prior_tokens:
                cleaned = ", ".join(parts[:-1])
                parts = parts[:-1]

    if structured_country:
        norm_country = normalize_country_name(structured_country) or structured_country
        lower_cleaned = cleaned.lower()
        country_tokens = {norm_country.lower()}
        if norm_country == "United States":
            country_tokens.update({"usa", "u.s.a.", "u.s.", "united states of america"})
        elif norm_country == "United Kingdom":
            country_tokens.update({"uk", "u.k.", "great britain"})

        already_has_country = any(tok in lower_cleaned for tok in country_tokens)
        if not already_has_country and len(parts) >= 2:
            tail_norm = normalize_country_name(parts[-1])
            if tail_norm and tail_norm.lower() == norm_country.lower():
                already_has_country = True

        if not already_has_country and not _WORKDAY_CITY_STATE_RE.match(cleaned):
            # Append verified structured country on opaque facility codes (e.g. ESP - MD - LAS ROZAS, US FL JAX 347, IND BNGL FL2-3 TWR 3)
            code_tokens = _WORKDAY_FACILITY_CODE_RE.findall(cleaned)
            if len(code_tokens) >= 2 or "-" in cleaned:
                cleaned = f"{cleaned}, {norm_country}"

    return cleaned


def _collect_nested_requirements(markdown_text: str, normalized_text: str, start_idx: int) -> str | None:
    """
    Collect nested requirement subsections (when a parent requirement heading is
    immediately followed by child subheadings) until a clear non-requirement stop
    heading is reached.
    """
    offset = start_idx
    end_idx = len(normalized_text)
    for line in normalized_text[start_idx:].splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            heading_match = _HEADING_LINE_RE.match(stripped)
            if heading_match:
                heading_text = (heading_match.group(1) or heading_match.group(2) or "").strip()
                if _NON_REQUIREMENT_STOP_HEADING_RE.match(heading_text):
                    end_idx = offset
                    break
        offset += len(line)

    reqs = markdown_text[start_idx:end_idx].strip()
    return reqs or None


def extract_requirements(markdown_text: str | None) -> str | None:
    """Extract requirements / qualifications section from clean markdown description."""
    if not markdown_text or not isinstance(markdown_text, str):
        return None

    # Normalize curly apostrophes with a 1:1 length-preserving replacement so regex match
    # offsets map identically back onto the original markdown string.
    normalized_text = markdown_text.replace("\u2019", "'")

    # 1. Standard Markdown ATX headings (#..######, optional **...**, optional leading symbol/emoji, trailing '?' or ':')
    atx_pattern = re.compile(
        rf"(?:^|\n)#{{1,6}}\s*(?:\*\*\s*)?(?:[^\w\s#*\n]+\s*)?(?:{_REQUIREMENT_HEADER_TITLES})[.…?:\s]*(?:\*\*)?[.…?:\s]*(?:\n|$)([\s\S]*?)(?=(?:\n#{{1,6}}\s+[^\n]+)|\Z)",
        re.IGNORECASE,
    )

    # 2. Bold or colon-delimited paragraph headers (common in Workday CXS, Teamtailor, & HTML descriptions)
    bold_pattern = re.compile(
        rf"(?:^|\n)(?:[^\w\s#*\-\+\[\]\(\)\n]{{1,4}}\s*)?(?:\*\*\s*(?:[^\w\s#*\n]+\s*)?(?:{_REQUIREMENT_HEADER_TITLES})[.…?:\s]*\*\*|(?:[^\w\s#*\-\+\[\]\(\)\n]+\s*)?(?:{_REQUIREMENT_HEADER_TITLES})[.…]*:)[ \t]*\n([\s\S]*?)"
        r"(?=(?:\n#{1,6}\s+[^\n]+|\n\*\*[^*\n]{2,80}:?\*\*[ \t]*(?:\n|$))|\Z)",
        re.IGNORECASE,
    )

    for pattern in (atx_pattern, bold_pattern):
        match = pattern.search(normalized_text)
        if not match:
            continue
        reqs = markdown_text[match.start(1):match.end(1)].strip()
        if reqs:
            first_line = next((ln.strip() for ln in reqs.splitlines() if ln.strip()), "")
            if not _HEADING_LINE_RE.match(first_line):
                return reqs
            # Parent requirement heading immediately followed by nested subheading (e.g. #### Education)
            return _collect_nested_requirements(markdown_text, normalized_text, match.start(1)) or reqs
        nested_reqs = _collect_nested_requirements(markdown_text, normalized_text, match.start(1))
        if nested_reqs:
            return nested_reqs

    return None


_LEVER_NON_REQ_HEADING_RE = re.compile(
    r"\b(?:responsibilit\w*|duties|what\s+you['\u2019]?(?:ll|\s+will)\s+do|in\s+this\s+role|"
    r"about\s+(?:this\s+role|the\s+\w+)|position\s+summary|program\s+details|"
    r"working\s+conditions|perks|benefits?|what['\u2019]?s\s+in\s+it\s+for\s+you|"
    r"our\s+(?:values|partnerships|culture|benefits)|what\s+we\s+do|"
    r"where\s+you['\u2019]?(?:ll|\s+will)\s+be|accountabilit\w*|no\s+two\s+days|"
    r"closing|to\s+apply|application|compensation|salary)\b",
    re.IGNORECASE,
)

_LEVER_REQ_HEADING_RE = re.compile(
    r"\b(?:qualifications?|requirements?|required\s+(?:skills?|experience)|"
    r"skills?(?:\s*,\s*knowledge)?|hard\s+skills?|soft\s+skills?|"
    r"must[- ]haves?|nice[- ]to[- ]haves?|preferred\s+experience|"
    r"who\s+you\s+are|what\s+we['\u2019]?(?:re|\s+are)\s+looking\s+for|"
    r"what\s+we\s+require|what\s+we\s+value|what\s+you(?:'ll|\s+will)?\s+bring|"
    r"what\s+you\s+have|your\s+(?:background|profile|experience|skills)|"
    r"education|bonus\s+(?:if\s+you\s+have|qualifications?))\b",
    re.IGNORECASE,
)


def _extract_lever_lists_requirements(raw_fields: dict[str, Any] | None) -> str | None:
    """Extract structured requirement/qualification sections from Lever API ``lists[]``."""
    if not isinstance(raw_fields, dict):
        return None
    lists = raw_fields.get("lists")
    if not isinstance(lists, list) or not lists:
        return None

    sections: list[str] = []
    for item in lists:
        if not isinstance(item, dict):
            continue
        header = (item.get("text") or "").strip()
        content = (item.get("content") or "").strip()
        if not header or not content:
            continue
        hdr_norm = header.replace("\u2019", "'")
        if _LEVER_NON_REQ_HEADING_RE.search(hdr_norm):
            continue
        if not _LEVER_REQ_HEADING_RE.search(hdr_norm):
            continue
        lower_c = content.lower()
        html_content = f"<ul>{content}</ul>" if ("<li" in lower_c and "<ul" not in lower_c and "<ol" not in lower_c) else content
        body_md = to_markdown(strip_li_tags(html_content))
        if not body_md or not body_md.strip():
            continue
        clean_hdr = header.rstrip(":").strip()
        sections.append(f"**{clean_hdr}:**\n{body_md.strip()}")

    return "\n\n".join(sections) if sections else None


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

        raw_location_preserved = raw.raw_fields.get("raw_location_preserved") or (
            raw.raw_location if raw.provider == "workday" else None
        )
        structured_country = _extract_structured_country_descriptor(raw.raw_fields) if raw.provider == "workday" else None
        location = (
            _normalize_workday_location(raw.raw_location, structured_country)
            if raw.provider == "workday"
            else raw.raw_location
        )
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
        workplace_type_for_resolver = raw.workplace_type if raw.workplace_type_resolved else raw.raw_workplace_type

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
            raw.work_model_evidence
            if raw.work_model_evidence and wm_res.source == "api_enum"
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

        # 6. Datetime Parsing & Reference-Clock Validation
        ref_scraped_at = raw.scraped_at or datetime.now(timezone.utc)
        raw_date = raw.raw_date
        date_field_name = raw.raw_fields.get("date_field_name") if raw.raw_fields else None
        if not raw_date:
            raw_date = raw.raw_fields.get("datePosted")
            if raw_date and not date_field_name:
                date_field_name = "datePosted"
            if not raw_date and isinstance(raw.raw_fields.get("json_ld"), dict):
                raw_date = raw.raw_fields["json_ld"].get("datePosted")
                if raw_date and not date_field_name:
                    date_field_name = "datePosted"
        posted_at = parse_tz_aware_date(raw_date)
        rejected_date_reason: str | None = None
        if raw_date and posted_at is None:
            rejected_date_reason = "Unparseable or coarse relative posting date rejected"
        elif posted_at is not None and raw.provider == "workday" and posted_at > ref_scraped_at + timedelta(days=1):
            posted_at = None
            rejected_date_reason = f"Future {date_field_name or 'startDate'} (> scraped_at + 1d) rejected"

        # 6.5 Eligibility Extraction (Workday full path; JSON-LD applicantLocationRequirements across providers)
        elig_raw_fields = dict(raw.raw_fields or {})
        if isinstance(raw.raw_fields.get("json_ld"), dict):
            for k in ("applicantLocationRequirements", "jobLocationType", "jobLocation"):
                if k not in elig_raw_fields and k in raw.raw_fields["json_ld"]:
                    elig_raw_fields[k] = raw.raw_fields["json_ld"][k]

        prelim_meth = raw.extraction_method or (
            ExtractionMethod.SCRAPE if not raw.description_is_authentic else ExtractionMethod.ATS_API
        )
        eligibility = None
        if raw.provider in ("workday", "teamtailor", "lever", "greenhouse", "ashby") or applicant_req is not None:
            eligibility = extract_eligibility(
                provider=raw.provider,
                raw_workplace_type=raw.raw_workplace_type,
                work_model=wm_res.value,
                location=location,
                raw_location=raw.raw_location,
                description=cleaned_description,
                raw_fields=elig_raw_fields,
                description_is_authentic=raw.description_is_authentic,
                method=prelim_meth,
            )

        # 7. Identity & URLs
        source_record_id = raw.source_record_id
        if not source_record_id:
            if raw.provider_job_id and raw.company_slug:
                source_record_id = f"{raw.provider}:{raw.company_slug}:{raw.provider_job_id}"
            elif raw.provider_job_id:
                source_record_id = f"{raw.provider}:{raw.provider_job_id}"
            else:
                norm_u = normalize_job_url(raw.source_url or raw.apply_url or "", raw.provider)
                source_record_id = f"{raw.provider}:{norm_u}"

        job_id = source_record_id
        apply_url = raw.apply_url or raw.source_url

        # 8. Field Evidence and Confidence
        evidence: list[FieldEvidence] = []
        confidences: list[FieldConfidence] = []
        meth = raw.extraction_method or (ExtractionMethod.SCRAPE if not raw.description_is_authentic else ExtractionMethod.ATS_API)
        clean_url = sanitize_source_url(raw.source_url)
        is_snippet = bool(not raw.description_is_authentic and meth == ExtractionMethod.SNIPPET)

        # 8.1 Title
        if title:
            title_ev_type = EvidenceType.SNIPPET if is_snippet else EvidenceType.STRUCTURED_FREE_TEXT
            score, reason = compute_field_confidence(CanonicalJobField.TITLE, title_ev_type, has_value=True)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.TITLE,
                normalized_value=title,
                raw_value=sanitize_raw_evidence(raw.raw_title or raw.raw_fields.get("title") or title),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="title" if (raw.raw_title or raw.raw_fields.get("title")) else None,
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.TITLE, score=score, reason=reason))

        # 8.2 Company
        if company and company != "Unknown":
            comp_ev_type = EvidenceType.SNIPPET if is_snippet else EvidenceType.STRUCTURED_FREE_TEXT
            score, reason = compute_field_confidence(CanonicalJobField.COMPANY, comp_ev_type, has_value=True)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.COMPANY,
                normalized_value=company,
                raw_value=sanitize_raw_evidence(raw.raw_company or raw.company_slug or company),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="company" if raw.raw_company else ("company_slug" if raw.company_slug else None),
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.COMPANY, score=score, reason=reason))
        else:
            evidence.append(FieldEvidence(
                field=CanonicalJobField.COMPANY,
                normalized_value=None,
                raw_value=sanitize_raw_evidence(raw.raw_company or raw.company_slug or ""),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="company",
                validation_status=ValidationStatus.REJECTED,
                confidence_score=None,
                reason="Company name unknown or missing",
            ))

        # 8.3 Location
        has_loc_agreement = bool(raw.raw_location and applicant_req_str)
        if location:
            loc_meth = ExtractionMethod.JSON_LD if applicant_req_str else meth
            loc_ev_type = EvidenceType.SNIPPET if is_snippet else EvidenceType.STRUCTURED_FREE_TEXT
            score, reason = compute_field_confidence(CanonicalJobField.LOCATION, loc_ev_type, has_value=True, has_agreement=has_loc_agreement)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.LOCATION,
                normalized_value=location,
                raw_value=sanitize_raw_evidence(location),
                method=loc_meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="applicantLocationRequirements" if applicant_req_str else "location",
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.LOCATION, score=score, reason=reason))
            if applicant_req_str and raw.raw_location:
                evidence.append(FieldEvidence(
                    field=CanonicalJobField.LOCATION,
                    normalized_value=location,
                    raw_value=sanitize_raw_evidence(f"applicantLocationRequirements: {applicant_req_str}"),
                    method=ExtractionMethod.JSON_LD,
                    provider=raw.provider,
                    source_url=clean_url,
                    provider_field_name="applicantLocationRequirements",
                    validation_status=ValidationStatus.ACCEPTED,
                    confidence_score=score,
                    reason="Structured applicant location requirement agreement",
                ))
            elif applicant_req_str and not raw.raw_location:
                evidence.append(FieldEvidence(
                    field=CanonicalJobField.LOCATION,
                    normalized_value=location,
                    raw_value=sanitize_raw_evidence(f"applicantLocationRequirements: {applicant_req_str}"),
                    method=ExtractionMethod.JSON_LD,
                    provider=raw.provider,
                    source_url=clean_url,
                    provider_field_name="applicantLocationRequirements",
                    validation_status=ValidationStatus.ACCEPTED,
                    confidence_score=score,
                    reason=reason,
                ))

        if raw_location_preserved:
            raw_loc_ev_type = EvidenceType.SNIPPET if is_snippet else EvidenceType.STRUCTURED_FREE_TEXT
            rl_score, rl_reason = compute_field_confidence(
                CanonicalJobField.RAW_LOCATION,
                raw_loc_ev_type,
                has_value=True,
            )
            evidence.append(FieldEvidence(
                field=CanonicalJobField.RAW_LOCATION,
                normalized_value=raw_location_preserved,
                raw_value=sanitize_raw_evidence(raw_location_preserved),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="location",
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=rl_score,
                reason=rl_reason,
            ))
            if rl_score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.RAW_LOCATION, score=rl_score, reason=rl_reason))

        # 8.4 Work Model
        if wm_res.value:
            has_wm_conflict = bool(desc_conflicts)
            has_wm_agreement = bool(
                wm_res.source in ("api_enum", "jsonld")
                and (
                    ("remote" in (location or "").lower() and wm_res.value == "remote")
                    or ("remote" in (title or "").lower() and wm_res.value == "remote")
                )
            )
            if wm_res.source in ("api_enum", "jsonld"):
                wm_ev_type = EvidenceType.TYPED_ENUM
            elif wm_res.source == "li_tag" or "#LI-Remote" in (work_model_evidence or ""):
                wm_ev_type = EvidenceType.EXPLICIT_LABEL
            elif wm_res.source == "description":
                wm_ev_type = EvidenceType.UNLABELLED_TEXT
            elif is_snippet:
                wm_ev_type = EvidenceType.SNIPPET
            else:
                wm_ev_type = EvidenceType.STRUCTURED_FREE_TEXT
            score, reason = compute_field_confidence(
                CanonicalJobField.WORK_MODEL,
                wm_ev_type,
                has_value=True,
                has_agreement=has_wm_agreement,
                has_conflict=has_wm_conflict,
            )
            wm_meth = ExtractionMethod.JSON_LD if wm_res.source == "jsonld" else (ExtractionMethod.DOM if wm_res.source == "description" else meth)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.WORK_MODEL,
                normalized_value=wm_res.value,
                raw_value=sanitize_raw_evidence(work_model_evidence or wm_res.evidence or wm_res.value),
                method=wm_meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="workplace_type" if raw.raw_workplace_type else ("jobLocationType" if jsonld_loc_type else wm_res.source),
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.WORK_MODEL, score=score, reason=reason))
            for m, snippet in desc_conflicts.items():
                evidence.append(FieldEvidence(
                    field=CanonicalJobField.WORK_MODEL,
                    normalized_value=m,
                    raw_value=sanitize_raw_evidence(f"description_conflict: {snippet}"),
                    method=ExtractionMethod.DOM,
                    provider=raw.provider,
                    source_url=clean_url,
                    provider_field_name="description",
                    validation_status=ValidationStatus.SUSPECT,
                    confidence_score=round(max(0.1, (score or 0.5) - 0.2), 2),
                    reason=f"Conflicting unlabelled description text matches {m}",
                ))

        # 8.5 Employment Type
        if employment:
            is_enum = bool(raw_emp or (isinstance(raw.raw_fields.get("json_ld"), dict) and raw.raw_fields["json_ld"].get("employmentType")))
            emp_ev_type = EvidenceType.TYPED_ENUM if is_enum else (EvidenceType.UNLABELLED_TEXT if cleaned_description else EvidenceType.SNIPPET)
            score, reason = compute_field_confidence(CanonicalJobField.EMPLOYMENT_TYPE, emp_ev_type, has_value=True)
            emp_meth = ExtractionMethod.JSON_LD if (raw.raw_fields.get("employmentType") or (isinstance(raw.raw_fields.get("json_ld"), dict) and raw.raw_fields["json_ld"].get("employmentType"))) else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.EMPLOYMENT_TYPE,
                normalized_value=employment,
                raw_value=sanitize_raw_evidence(raw_emp or employment),
                method=emp_meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="employmentType" if raw_emp else None,
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.EMPLOYMENT_TYPE, score=score, reason=reason))

        # 8.6 Salary
        if salary:
            src_str = (salary.source or "").lower()
            is_structured = bool("structured" in src_str or src_str in ("api", "json_ld"))
            is_labeled = bool("label" in src_str or (salary.raw_text and any(k in salary.raw_text.lower() for k in ("salary", "pay", "compensation"))))
            if is_structured:
                sal_ev_type = EvidenceType.TYPED_ENUM
            elif is_labeled:
                sal_ev_type = EvidenceType.EXPLICIT_LABEL
            else:
                sal_ev_type = EvidenceType.UNLABELLED_TEXT
            score, reason = compute_field_confidence(CanonicalJobField.SALARY, sal_ev_type, has_value=True, salary=salary)
            sal_meth = ExtractionMethod.JSON_LD if src_str == "json_ld" else (ExtractionMethod.ATS_API if is_structured else meth)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.SALARY,
                normalized_value=salary.model_dump(),
                raw_value=sanitize_raw_evidence(salary.raw_text or str(salary.model_dump())),
                method=sal_meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="compensation" if salary.source == "api" else ("baseSalary" if salary.source == "json_ld" else "salary"),
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.SALARY, score=score, reason=reason))
        else:
            raw_sal_candidate = raw.raw_salary or raw.raw_fields.get("salary") or raw.raw_fields.get("compensation")
            if raw_sal_candidate:
                evidence.append(FieldEvidence(
                    field=CanonicalJobField.SALARY,
                    normalized_value=None,
                    raw_value=sanitize_raw_evidence(raw_sal_candidate),
                    method=meth,
                    provider=raw.provider,
                    source_url=clean_url,
                    provider_field_name="salary" if raw.raw_salary else "compensation",
                    validation_status=ValidationStatus.REJECTED,
                    confidence_score=None,
                    reason="Unparseable salary text or non-numeric compensation",
                ))

        # 8.7 Description
        if cleaned_description and raw.description_is_authentic:
            desc_ok = bool(description_quality(cleaned_description))
            score, reason = compute_field_confidence(
                CanonicalJobField.DESCRIPTION,
                EvidenceType.STRUCTURED_FREE_TEXT,
                has_value=True,
                description_ok=desc_ok,
                is_authentic_desc=True,
            )
            evidence.append(FieldEvidence(
                field=CanonicalJobField.DESCRIPTION,
                normalized_value=None,
                raw_value=sanitize_raw_evidence(f"Description length: {len(cleaned_description)} chars, markdown"),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="description",
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.DESCRIPTION, score=score, reason=reason))

        # 8.8 Posted At
        if posted_at:
            score, reason = compute_field_confidence(CanonicalJobField.POSTED_AT, EvidenceType.TYPED_ENUM, has_value=True)
            date_meth = ExtractionMethod.JSON_LD if (raw.raw_fields.get("datePosted") or (isinstance(raw.raw_fields.get("json_ld"), dict) and raw.raw_fields["json_ld"].get("datePosted"))) else meth
            evidence.append(FieldEvidence(
                field=CanonicalJobField.POSTED_AT,
                normalized_value=posted_at.isoformat(),
                raw_value=sanitize_raw_evidence(str(raw_date or posted_at.isoformat())),
                method=date_meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name=date_field_name or ("datePosted" if raw.raw_fields.get("datePosted") else "updated_at"),
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.POSTED_AT, score=score, reason=reason))
        elif rejected_date_reason and raw_date:
            evidence.append(FieldEvidence(
                field=CanonicalJobField.POSTED_AT,
                normalized_value=None,
                raw_value=sanitize_raw_evidence(str(raw_date)),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name=date_field_name or "postedOn",
                validation_status=ValidationStatus.REJECTED,
                confidence_score=None,
                reason=rejected_date_reason,
            ))

        # 8.10 Eligibility
        if eligibility is not None and (eligibility.facts or eligibility.nigeria_eligible is not None):
            elig_ev_type = EvidenceType.TYPED_ENUM if any(
                f.dimension in ("allowed_residence", "physical_location") and f.method in (ExtractionMethod.ATS_API, ExtractionMethod.JSON_LD)
                for f in eligibility.facts
            ) else EvidenceType.EXPLICIT_LABEL
            el_score, el_reason = compute_field_confidence(CanonicalJobField.ELIGIBILITY, elig_ev_type, has_value=True)
            el_summary = eligibility.nigeria_eligibility_reason or (
                eligibility.facts[0].raw_snippet if eligibility.facts else str(eligibility.nigeria_eligible)
            )
            evidence.append(FieldEvidence(
                field=CanonicalJobField.ELIGIBILITY,
                normalized_value="eligible" if eligibility.nigeria_eligible is True else ("ineligible" if eligibility.nigeria_eligible is False else "undetermined"),
                raw_value=sanitize_raw_evidence(el_summary),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name=eligibility.facts[0].provider_field_name if eligibility.facts else None,
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=el_score,
                reason=el_reason,
            ))
            if el_score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.ELIGIBILITY, score=el_score, reason=el_reason))

        # 8.9 Apply URL
        if apply_url:
            url_ev_type = EvidenceType.SNIPPET if is_snippet else EvidenceType.STRUCTURED_FREE_TEXT
            score, reason = compute_field_confidence(CanonicalJobField.APPLY_URL, url_ev_type, has_value=True)
            evidence.append(FieldEvidence(
                field=CanonicalJobField.APPLY_URL,
                normalized_value=apply_url,
                raw_value=sanitize_raw_evidence(apply_url),
                method=meth,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name="apply_url" if raw.apply_url else "source_url",
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=score,
                reason=reason,
            ))
            if score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.APPLY_URL, score=score, reason=reason))

        extracted_reqs: Optional[str] = None
        raw_req = raw.raw_requirements or (raw.raw_fields.get("qualifications") if raw.raw_fields else None)
        if raw_req and isinstance(raw_req, str):
            req_md = to_markdown(strip_li_tags(raw_req)).strip()
            extracted_reqs = req_md or raw_req.strip()
        elif (
            (raw.provider in ("workday", "teamtailor", "lever", "greenhouse", "ashby") or (raw.raw_fields and raw.raw_fields.get("is_board_monitor")))
            and cleaned_description
            and raw.description_is_authentic
        ):
            if raw.provider == "lever":
                extracted_reqs = _extract_lever_lists_requirements(raw.raw_fields)
            if not extracted_reqs:
                extracted_reqs = extract_requirements(cleaned_description)

        company_logo_url = raw.raw_fields.get("company_logo_url") if raw.raw_fields else None
        company_logo_source = raw.raw_fields.get("company_logo_source") if raw.raw_fields else None
        company_logo_verified = bool(raw.raw_fields.get("company_logo_verified")) if raw.raw_fields else False
        if company_logo_url:
            if company_logo_source == "json_ld_hiring_organization_logo":
                logo_ev_type = EvidenceType.TYPED_ENUM
                logo_method = ExtractionMethod.JSON_LD
            elif company_logo_source in ("dom_header_logotype", "lever_main_header_logo", "ashby_app_data_square_logo"):
                logo_ev_type = EvidenceType.STRUCTURED_FREE_TEXT
                logo_method = ExtractionMethod.DOM
            else:
                logo_ev_type = EvidenceType.EXPLICIT_LABEL
                logo_method = (
                    ExtractionMethod.DOM
                    if company_logo_source and company_logo_source.startswith("dom_")
                    else meth
                )
            logo_score, logo_reason = compute_field_confidence(
                CanonicalJobField.COMPANY_LOGO, logo_ev_type, has_value=True
            )
            evidence.append(FieldEvidence(
                field=CanonicalJobField.COMPANY_LOGO,
                normalized_value=company_logo_url,
                raw_value=sanitize_raw_evidence(company_logo_url),
                method=logo_method,
                provider=raw.provider,
                source_url=clean_url,
                provider_field_name=company_logo_source or "company_logo_url",
                validation_status=ValidationStatus.ACCEPTED,
                confidence_score=logo_score,
                reason=logo_reason,
            ))
            if logo_score is not None:
                confidences.append(FieldConfidence(field=CanonicalJobField.COMPANY_LOGO, score=logo_score, reason=logo_reason))

        return CanonicalJob(
            id=job_id,
            source_record_id=source_record_id,
            aliases=[],
            source=raw.provider,
            source_url=raw.source_url,
            application_url=apply_url,
            title=title,
            company=company,
            company_slug=raw.company_slug,
            company_logo_url=company_logo_url,
            company_logo_source=company_logo_source,
            company_logo_verified=company_logo_verified,
            location=location,
            raw_location=raw_location_preserved,
            work_model=wm_res.value,
            work_model_source=wm_res.source,
            work_model_evidence=work_model_evidence,
            raw_workplace_type=raw.raw_workplace_type,
            department=raw.raw_department or (raw.raw_fields.get("department") if raw.raw_fields else None),
            employment_type=employment,
            salary=salary,
            description=cleaned_description,
            requirements=extracted_reqs,
            posted_at=posted_at,
            scraped_at=ref_scraped_at,
            query_used=raw.query_used,
            ats_source=raw.provider,
            field_evidence=evidence,
            field_confidence=confidences,
            eligibility=eligibility,
        )

"""
Geographic and employment eligibility extraction with strict provenance tracking.

Upgrades Workday and structured JSON-LD job records into typed `JobEligibility`
assessments while strictly obeying ADR 0001 (unknown beats wrong) and separating:
  - applicant residence rules
  - physical office country & hybrid attendance obligations
  - citizenship & security clearances
  - statutory domestic work authorization & visa sponsorship
  - payroll requirements
  - relocation requirement vs assistance
  - employee vs contractor vs EOR arrangements
  - timezone constraints
"""

from __future__ import annotations

import re
from typing import Any

from src.project_files.models import (
    EligibilityFact,
    EligibilityFactDimension,
    EmploymentArrangement,
    ExtractionMethod,
    JobEligibility,
    VisaSponsorshipStatus,
)

_COUNTRY_ALIASES: dict[str, str] = {
    "us": "United States",
    "u.s": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "u.s.a": "United States",
    "u.s.a.": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k": "United Kingdom",
    "u.k.": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "canada": "Canada",
    "spain": "Spain",
    "españa": "Spain",
    "espagne": "Spain",
    "tunisia": "Tunisia",
    "tunisie": "Tunisia",
    "nigeria": "Nigeria",
    "germany": "Germany",
    "deutschland": "Germany",
    "france": "France",
    "india": "India",
    "ireland": "Ireland",
    "netherlands": "Netherlands",
    "poland": "Poland",
    "brazil": "Brazil",
    "sweden": "Sweden",
    "pakistan": "Pakistan",
    "eu": "EU",
    "european union": "EU",
    "eea": "EEA",
    "europe": "Europe",
    "emea": "EMEA",
    "latam": "LATAM",
    "apac": "APAC",
    "north america": "North America",
    "worldwide": "Worldwide",
    "global": "Worldwide",
    "anywhere": "Worldwide",
}

_ISO2_COUNTRIES: dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "CA": "Canada",
    "ES": "Spain",
    "TN": "Tunisia",
    "NG": "Nigeria",
    "DE": "Germany",
    "FR": "France",
    "IN": "India",
    "IE": "Ireland",
    "NL": "Netherlands",
    "PL": "Poland",
    "BR": "Brazil",
    "SE": "Sweden",
    "PK": "Pakistan",
}

_EEO_SENTENCE_RE = re.compile(
    r"(?:equal\s+opportunity\s+employer|without\s+regard\s+to|non-?discriminatory\s+basis\s+without\s+regard\s+to|"
    r"regardless\s+of\s+(?:race|color|religion|sex|gender|national\s+origin|citizenship))",
    re.IGNORECASE,
)

_GLOBAL_REMOTE_RE = re.compile(
    r"\b(?:work\s+from\s+anywhere|anywhere\s+in\s+the\s+world|"
    r"open\s+to\s+(?:candidates|applicants)\s+worldwide|"
    r"engaged\s+globally|hired?\s+(?:globally|worldwide)|global\s+remote|"
    r"remote\s*[\(\[\-–,/\s]+\s*worldwide\s*[\)\]]?|"
    r"worldwide\s+(?:remote|applicants|candidates))\b",
    re.IGNORECASE,
)
_GLOBAL_NEGATIVE_RE = re.compile(r"\bnot\s+(?:available\s+)?(?:worldwide|global)\b", re.IGNORECASE)

_GEO_TOKEN = (
    r"United\s+States(?:\s+of\s+America)?|U\.S\.A?\.?|USA|(?-i:\bUS\b)|United\s+Kingdom|U\.K\.?|(?-i:\bUK\b)|Great\s+Britain|"
    r"Canada|Germany|Deutschland|France|Spain|España|Tunisia|Nigeria|India|Ireland|Netherlands|"
    r"Poland|Brazil|Sweden|Pakistan|European\s+Union|(?-i:\bEU\b|\bEEA\b|\bEMEA\b|\bLATAM\b|\bAPAC\b)|Europe|North\s+America"
)

_RESIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:candidates?|applicants?)\s+must\s+(?:reside|live|be\s+located|be\s+based)\s+in\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:must|required\s+to)\s+(?:reside|live|be\s+located|be\s+based)\s+(?:in|within)\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:remote\s+(?:only\s+)?within|work\s+(?:remotely\s+)?from\s+within|open\s+only\s+to\s+residents\s+of)\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bresidents\s+of\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\s+only\b",
        re.IGNORECASE,
    ),
)

_EXCLUDED_RESIDENCE_RE = re.compile(
    rf"\b(?:unable\s+to\s+hire|cannot\s+hire|excludes?|not\s+available)\s+(?:candidates\s+)?in\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\b",
    re.IGNORECASE,
)

_CITIZENSHIP_RE = re.compile(
    rf"\bmust\s+be\s+(?:a\s+)?(?P<geo>{_GEO_TOKEN})\s+citizen(?:\s+or\s+national)?\b|"
    rf"\b(?P<geo2>{_GEO_TOKEN})\s+citizenship\s+(?:is\s+)?required\b",
    re.IGNORECASE,
)

_CLEARANCE_RE = re.compile(
    r"\b(?:TS/SCI(?:\s+clearance)?(?:\s+with\s+(?:a\s+)?polygraph)?|"
    r"Top\s+Secret(?:/SCI)?\s+clearance|"
    r"(?:active|current|ability\s+to\s+obtain\s+(?:a\s+)?)(?:security|secret|public\s+trust)\s+clearance|"
    r"security\s+clearance\s+(?:is\s+)?required)\b",
    re.IGNORECASE,
)

_WORK_AUTH_RE = re.compile(
    rf"\b(?:legally\s+)?(?:authorized|authorised|eligible|eligibility)\s+to\s+work\s+in\s+(?:the\s+)?(?P<geo>{_GEO_TOKEN})\b|"
    rf"\bright\s+to\s+work\s+in\s+(?:the\s+)?(?P<geo2>{_GEO_TOKEN})\b|"
    rf"\bwork\s+authori[sz]ation\s+(?:in|for)\s+(?:the\s+)?(?P<geo3>{_GEO_TOKEN})\b",
    re.IGNORECASE,
)

_SPONSORSHIP_UNAVAILABLE_RE = re.compile(
    r"\b(?:visa\s+sponsorship\s+(?:is\s+)?not\s+available|"
    r"without\s+(?:visa\s+)?sponsorship|"
    r"no\s+visa\s+sponsorship|"
    r"(?:unable|not\s+able|will\s+not|does\s+not|cannot)\s+to?\s*sponsor(?:\s+(?:work\s+)?visas?)?)\b",
    re.IGNORECASE,
)
_SPONSORSHIP_CONDITIONAL_RE = re.compile(
    r"\b(?:limited\s+(?:visa\s+)?sponsorship|may\s+(?:consider\s+)?sponsor(?:ing)?\s+case[-\s]by[-\s]case)\b",
    re.IGNORECASE,
)
_SPONSORSHIP_AVAILABLE_RE = re.compile(
    r"\b(?:visa\s+sponsorship\s+(?:is\s+)?available|will\s+consider\s+sponsoring)\b",
    re.IGNORECASE,
)

_PAYROLL_RE = re.compile(
    rf"\b(?:must\s+be\s+(?:on|hired\s+on)|hired\s+on|paid\s+(?:via|through|on)\s+(?:a\s+)?|require[sd]?\s+(?:to\s+be\s+on\s+)?)\s*(?P<geo>{_GEO_TOKEN})\s*(?:W-?2\s+)?payroll\b",
    re.IGNORECASE,
)

_RELOCATION_REQUIRED_RE = re.compile(
    r"\b(?:must\s+relocate|relocation\s+(?:is\s+)?required|required\s+to\s+relocate|willingness\s+to\s+relocate\s+(?:is\s+)?required)\b",
    re.IGNORECASE,
)
_RELOCATION_ASSISTANCE_RE = re.compile(
    r"\b(?:relocation\s+(?:assistance|support|package|stipend)\s+(?:is\s+)?(?:available|provided|offered)|assistance\s+with\s+relocation)\b",
    re.IGNORECASE,
)

_CONTRACTOR_RE = re.compile(
    r"\b(?:independent\s+contractor|contractor\s+arrangement|b2b\s+contract|\bb2b\b|\b1099\b|\bc2c\b|consultancy\s+contract)\b",
    re.IGNORECASE,
)
_EOR_RE = re.compile(
    r"\b(?:employer\s+of\s+record|\beor\b|(?:via|through|using)\s+(?:Deel|Remote\.com|Oyster|Papaya\s+Global))\b",
    re.IGNORECASE,
)
_EMPLOYEE_PAYROLL_RE = re.compile(r"\b(?:w-?2\s+employee|direct\s+fte\s+employee)\b", re.IGNORECASE)

_TIMEZONE_RE = re.compile(
    r"(?:\b\d+\+?\s+hours?\s+(?:of\s+)?overlap\s+with\s+(?:[A-Z]{2,5}|US\s+(?:Eastern|Pacific|Central|Mountain)|EMEA|Americas)\b(?:\s+business\s+hours)?|"
    r"\bmust\s+work\s+(?:within\s+)?(?:[A-Z]{2,5}|EMEA|Americas)\s+(?:business\s+hours|time\s*zones?)\b)",
    re.IGNORECASE,
)

_HYBRID_ATTENDANCE_RE = re.compile(
    r"(?:\b(?:expected|required)\s+to\s+(?:report|come|be)\s+(?:to|in)\s+(?:the\s+)?office\b|"
    r"\bcategori[sz]ed\s+as\s+on[- ]?site\b|"
    r"\b\d+\s*(?:days?|d)\s*(?:per\s+week|a\s+week|/wk|/week)?\s*(?:in[- ]office|(?:in|at)\s+(?:the\s+|our\s+)?(?:[A-Za-zÀ-ÖØ-öø-ÿ-]+\s+){0,2}office|on[- ]?site|onsite)\b|"
    r"\boffice[- ]based\s+in\s+[^.\n]+\d+\s*days?\b|"
    r"\bregular\s+(?:in[- ]person|on[- ]?site)\s+(?:attendance|presence|collaboration)\b|"
    r"\bcollaboration\s+at\s+[^.\n]+facilities\b)",
    re.IGNORECASE,
)


def normalize_country_name(raw_country: str | None) -> str | None:
    """Normalize known country/region strings into canonical display names."""
    if not raw_country or not isinstance(raw_country, str):
        return None
    cleaned = re.sub(r"\s+", " ", raw_country).strip(" ,.;:-")
    if not cleaned:
        return None
    iso = _ISO2_COUNTRIES.get(cleaned.upper())
    if iso:
        return iso
    alias = _COUNTRY_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return cleaned


def _strip_eeo_sentences(text: str) -> str:
    """Remove standard non-discrimination EEO statements before scanning requirements."""
    kept: list[str] = []
    for line in text.splitlines():
        if _EEO_SENTENCE_RE.search(line):
            # Preserve prefix before an EEO sentence if same line has non-EEO clauses.
            sentences = re.split(r"(?<=[.!?])\s+", line)
            kept.extend(s for s in sentences if s.strip() and not _EEO_SENTENCE_RE.search(s))
        else:
            kept.append(line)
    return "\n".join(kept)


def _add_fact(
    facts: list[EligibilityFact],
    dimension: EligibilityFactDimension,
    value: str,
    raw_snippet: str,
    method: ExtractionMethod,
    provider_field_name: str | None = None,
) -> None:
    facts.append(
        EligibilityFact(
            dimension=dimension,
            value=value,
            raw_snippet=raw_snippet.strip()[:300],
            method=method,
            provider_field_name=provider_field_name,
        )
    )


def _extract_descriptor(val: Any) -> str | None:
    if isinstance(val, dict):
        desc = val.get("descriptor") or val.get("name") or val.get("alpha2Code")
        return str(desc).strip() if desc else None
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def _extract_structured_physical_country(raw_fields: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    """Return (canonical_country, raw_snippet, provider_field_name) from structured fields."""
    if not raw_fields:
        return None, None, None

    for field_name, candidate in (
        ("country", raw_fields.get("country")),
        (
            "jobRequisitionLocation.country",
            (raw_fields.get("jobRequisitionLocation") or {}).get("country")
            if isinstance(raw_fields.get("jobRequisitionLocation"), dict)
            else None,
        ),
    ):
        desc = _extract_descriptor(candidate)
        if desc:
            return normalize_country_name(desc), desc, field_name

    # JSON-LD jobLocation.address.addressCountry
    job_loc = raw_fields.get("jobLocation")
    if isinstance(job_loc, list) and job_loc:
        job_loc = job_loc[0]
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            country_val = addr.get("addressCountry")
            desc = _extract_descriptor(country_val)
            if desc:
                return normalize_country_name(desc), desc, "jobLocation.address.addressCountry"

    return None, None, None


def _extract_applicant_location_reqs(raw_fields: dict[str, Any] | None) -> tuple[list[str], bool, list[str]]:
    """Extract (countries, global_explicit, raw_snippets) from JSON-LD applicantLocationRequirements."""
    if not raw_fields:
        return [], False, []
    req = raw_fields.get("applicantLocationRequirements")
    if not req:
        return [], False, []

    items = req if isinstance(req, list) else [req]
    countries: list[str] = []
    snippets: list[str] = []
    global_explicit = False

    for item in items:
        raw_name: str | None = None
        if isinstance(item, dict):
            raw_name = _extract_descriptor(item)
        elif isinstance(item, str):
            raw_name = item.strip()
        if not raw_name:
            continue
        norm = normalize_country_name(raw_name)
        if not norm:
            continue
        snippets.append(raw_name)
        if norm == "Worldwide":
            global_explicit = True
        elif norm not in countries:
            countries.append(norm)

    return countries, global_explicit, snippets


def _append_unique(target: list[str] | None, item: str | None) -> list[str] | None:
    if not item:
        return target
    if target is None:
        return [item]
    if item not in target:
        target.append(item)
    return target


def extract_eligibility(
    *,
    provider: str,
    raw_workplace_type: str | None = None,
    work_model: str | None = None,
    location: str | None = None,
    raw_location: str | None = None,
    description: str | None = None,
    raw_fields: dict[str, Any] | None = None,
    description_is_authentic: bool = True,
    method: ExtractionMethod = ExtractionMethod.ATS_API,
) -> JobEligibility | None:
    """
    Extract conservative geographic and employment eligibility facts and assess
    whether an applicant ordinarily residing in Nigeria can perform the role
    from Nigeria without relocating.
    """
    has_structured_fields = bool(
        raw_fields
        and (
            raw_fields.get("applicantLocationRequirements")
            or raw_fields.get("country")
            or raw_fields.get("jobRequisitionLocation")
            or raw_fields.get("jobLocation")
        )
    )

    if (not description_is_authentic or method == ExtractionMethod.SNIPPET) and not has_structured_fields:
        return None

    facts: list[EligibilityFact] = []
    physical_country, physical_snip, physical_field = _extract_structured_physical_country(raw_fields)
    if physical_country and physical_snip:
        _add_fact(
            facts,
            "physical_location",
            physical_country,
            physical_snip,
            method,
            physical_field,
        )
    elif location:
        # Fallback only if normalized location clearly ends in an unambiguous country
        loc_tail = location.split(",")[-1].strip()
        loc_norm = _COUNTRY_ALIASES.get(loc_tail.lower())
        if loc_norm and loc_norm != "Worldwide":
            physical_country = loc_norm
            _add_fact(facts, "physical_location", physical_country, location, method, "location")

    req_countries, req_global, req_snips = _extract_applicant_location_reqs(raw_fields)
    allowed_residence: list[str] | None = req_countries if req_countries else None
    excluded_residence: list[str] | None = None
    residence_confirmed: bool | None = True if req_countries else None
    global_remote_explicit: bool | None = True if req_global else None

    for c, snip in zip(req_countries, req_snips):
        _add_fact(
            facts,
            "allowed_residence",
            c,
            snip,
            ExtractionMethod.JSON_LD,
            "applicantLocationRequirements",
        )
    if req_global:
        _add_fact(
            facts,
            "global_remote",
            "Worldwide",
            ", ".join(req_snips) or "Worldwide",
            ExtractionMethod.JSON_LD,
            "applicantLocationRequirements",
        )

    citizenship: list[str] | None = None
    clearance: str | None = None
    work_auth: list[str] | None = None
    visa_status: VisaSponsorshipStatus | None = None
    payroll_reqs: list[str] | None = None
    relocation_required: bool | None = None
    relocation_assistance: bool | None = None
    arrangement: EmploymentArrangement | None = None
    timezone_req: str | None = None
    hybrid_attendance_confirmed = False

    if description and description_is_authentic and method != ExtractionMethod.SNIPPET:
        cleaned_desc = _strip_eeo_sentences(description)
        text_method = method

        if not _GLOBAL_NEGATIVE_RE.search(cleaned_desc):
            if m_glob := _GLOBAL_REMOTE_RE.search(cleaned_desc):
                global_remote_explicit = True
                _add_fact(facts, "global_remote", "Worldwide", m_glob.group(0), text_method, "description")

        for pat in _RESIDENCE_PATTERNS:
            for m in pat.finditer(cleaned_desc):
                norm_geo = normalize_country_name(m.group("geo"))
                if norm_geo and norm_geo != "Worldwide":
                    allowed_residence = _append_unique(allowed_residence, norm_geo)
                    residence_confirmed = True
                    _add_fact(facts, "allowed_residence", norm_geo, m.group(0), text_method, "description")

        for m in _EXCLUDED_RESIDENCE_RE.finditer(cleaned_desc):
            norm_geo = normalize_country_name(m.group("geo"))
            if norm_geo:
                excluded_residence = _append_unique(excluded_residence, norm_geo)
                _add_fact(facts, "excluded_residence", norm_geo, m.group(0), text_method, "description")

        for m in _CITIZENSHIP_RE.finditer(cleaned_desc):
            raw_geo = m.group("geo") or m.group("geo2")
            norm_geo = normalize_country_name(raw_geo)
            if norm_geo:
                citizenship = _append_unique(citizenship, norm_geo)
                _add_fact(facts, "citizenship", norm_geo, m.group(0), text_method, "description")

        if m_clr := _CLEARANCE_RE.search(cleaned_desc):
            clearance = m_clr.group(0).strip()
            _add_fact(facts, "security_clearance", clearance, m_clr.group(0), text_method, "description")

        for m in _WORK_AUTH_RE.finditer(cleaned_desc):
            raw_geo = m.group("geo") or m.group("geo2") or m.group("geo3")
            norm_geo = normalize_country_name(raw_geo)
            if norm_geo:
                work_auth = _append_unique(work_auth, norm_geo)
                _add_fact(facts, "work_authorization", norm_geo, m.group(0), text_method, "description")

        if m_unavail := _SPONSORSHIP_UNAVAILABLE_RE.search(cleaned_desc):
            visa_status = "not_available"
            _add_fact(facts, "visa_sponsorship", "not_available", m_unavail.group(0), text_method, "description")
        elif m_cond := _SPONSORSHIP_CONDITIONAL_RE.search(cleaned_desc):
            visa_status = "conditional"
            _add_fact(facts, "visa_sponsorship", "conditional", m_cond.group(0), text_method, "description")
        elif m_avail := _SPONSORSHIP_AVAILABLE_RE.search(cleaned_desc):
            visa_status = "available"
            _add_fact(facts, "visa_sponsorship", "available", m_avail.group(0), text_method, "description")

        for m in _PAYROLL_RE.finditer(cleaned_desc):
            norm_geo = normalize_country_name(m.group("geo"))
            if norm_geo:
                payroll_reqs = _append_unique(payroll_reqs, norm_geo)
                _add_fact(facts, "payroll_requirement", norm_geo, m.group(0), text_method, "description")

        if m_rel_req := _RELOCATION_REQUIRED_RE.search(cleaned_desc):
            relocation_required = True
            _add_fact(facts, "relocation_required", "true", m_rel_req.group(0), text_method, "description")
        if m_rel_ast := _RELOCATION_ASSISTANCE_RE.search(cleaned_desc):
            relocation_assistance = True
            _add_fact(facts, "relocation_assistance", "true", m_rel_ast.group(0), text_method, "description")

        # Distinguish EOR before generic contractor/employee
        if m_eor := _EOR_RE.search(cleaned_desc):
            arrangement = "eor"
            _add_fact(facts, "employment_arrangement", "eor", m_eor.group(0), text_method, "description")
        elif m_ctr := _CONTRACTOR_RE.search(cleaned_desc):
            arrangement = "contractor"
            _add_fact(facts, "employment_arrangement", "contractor", m_ctr.group(0), text_method, "description")
        elif m_emp := _EMPLOYEE_PAYROLL_RE.search(cleaned_desc):
            arrangement = "employee"
            _add_fact(facts, "employment_arrangement", "employee", m_emp.group(0), text_method, "description")

        if m_tz := _TIMEZONE_RE.search(cleaned_desc):
            timezone_req = m_tz.group(0).strip()
            _add_fact(facts, "timezone", timezone_req, m_tz.group(0), text_method, "description")

        if work_model == "hybrid":
            if m_hyb := _HYBRID_ATTENDANCE_RE.search(cleaned_desc):
                hybrid_attendance_confirmed = True
                _add_fact(facts, "hybrid_attendance", "required", m_hyb.group(0), text_method, "description")

    nigeria_eligible, reason = _resolve_nigeria_eligibility(
        work_model=work_model,
        physical_country=physical_country,
        allowed_residence=allowed_residence,
        excluded_residence=excluded_residence,
        residence_confirmed=residence_confirmed,
        global_remote_explicit=global_remote_explicit,
        payroll_reqs=payroll_reqs,
        relocation_required=relocation_required,
        hybrid_attendance_confirmed=hybrid_attendance_confirmed,
        work_auth=work_auth,
        visa_status=visa_status,
        citizenship=citizenship,
        clearance=clearance,
    )

    return JobEligibility(
        physical_location_country=physical_country,
        allowed_residence_countries=allowed_residence,
        excluded_residence_countries=excluded_residence,
        residence_restriction_confirmed=residence_confirmed,
        global_remote_explicit=global_remote_explicit,
        citizenship_requirements=citizenship,
        security_clearance_required=clearance,
        work_authorization_required=work_auth,
        visa_sponsorship_status=visa_status,
        payroll_requirements=payroll_reqs,
        relocation_required=relocation_required,
        relocation_assistance=relocation_assistance,
        employment_arrangement=arrangement,
        timezone_requirements=timezone_req,
        nigeria_eligible=nigeria_eligible,
        nigeria_eligibility_reason=reason,
        facts=facts,
    )


def _resolve_nigeria_eligibility(
    *,
    work_model: str | None,
    physical_country: str | None,
    allowed_residence: list[str] | None,
    excluded_residence: list[str] | None,
    residence_confirmed: bool | None,
    global_remote_explicit: bool | None,
    payroll_reqs: list[str] | None,
    relocation_required: bool | None,
    hybrid_attendance_confirmed: bool,
    work_auth: list[str] | None,
    visa_status: VisaSponsorshipStatus | None,
    citizenship: list[str] | None,
    clearance: str | None,
) -> tuple[bool | None, str | None]:
    """Resolve conservative nigeria_eligible outcome honoring ADR 0001 and Decision 2."""
    foreign_physical = bool(physical_country and physical_country != "Nigeria")
    allowed_contains_nigeria = bool(
        allowed_residence and any(c in {"Nigeria", "Worldwide"} for c in allowed_residence)
    )
    foreign_residence_ban = bool(residence_confirmed and allowed_residence and not allowed_contains_nigeria)

    if excluded_residence and "Nigeria" in excluded_residence:
        return False, "Role explicitly excludes applicants residing in Nigeria."

    if foreign_residence_ban and allowed_residence:
        return False, f"Applicant residence restricted to {', '.join(allowed_residence)}."

    if relocation_required and foreign_physical:
        return False, f"Relocation to {physical_country} is required."

    if work_model == "in_person" and foreign_physical:
        return False, f"On-site role in {physical_country} requires physical attendance outside Nigeria."

    if work_model == "hybrid" and foreign_physical and hybrid_attendance_confirmed:
        return False, f"Hybrid role requires in-office attendance in {physical_country}."

    if payroll_reqs and not any(c in {"Nigeria", "Worldwide"} for c in payroll_reqs):
        return False, f"Employment restricted to local {', '.join(payroll_reqs)} payroll."

    if allowed_contains_nigeria:
        return True, "Explicitly permits applicants in Nigeria."

    if global_remote_explicit:
        return True, "Explicitly open worldwide / work from anywhere."

    if work_auth and visa_status == "not_available":
        return (
            None,
            f"Discloses {', '.join(work_auth)} work authorization / no sponsorship without confirmed residence or physical attendance restriction.",
        )

    if work_auth:
        return (
            None,
            f"Discloses {', '.join(work_auth)} work authorization without confirmed residence or physical attendance restriction.",
        )

    if visa_status == "not_available":
        return None, "Visa sponsorship unavailable; geographic residence eligibility undisclosed."

    if citizenship or clearance:
        return None, "Citizenship or security clearance requirement disclosed without residence ban."

    if work_model == "hybrid" and foreign_physical:
        return None, f"Hybrid role in {physical_country}; physical attendance frequency undisclosed."

    return None, None

"""
Geographic and employment eligibility extraction with strict provenance tracking.

Separates independent dimensions per ADR 0001 (Unknown beats wrong):
  - Work arrangement: onsite | hybrid | remote | unknown
  - Job geography: physical location / country / region
  - Applicant eligibility: worldwide, allowed/excluded ISO-2 countries,
    allowed/excluded regions, work authorization, visa sponsorship, payroll,
    relocation, employment arrangement, timezone, and hybrid attendance.

Evaluates compatibility dynamically for any selectable ISO 3166-1 alpha-2
applicant country without equating remote work with worldwide eligibility or
hard-coding Nigeria as the product boundary.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.core.countries import (
    ISO2_TO_COUNTRY,
    UNIFORM_CAPABLE_REGIONS,
    country_name_for_code,
    is_country_in_region,
    normalize_country_code,
    normalize_geo_label,
    normalize_region_name,
)
from src.core.models import (
    ApplicantEligibilityAssessment,
    EligibilityClassification,
    EligibilityFact,
    EligibilityFactDimension,
    EligibilityStatus,
    EmploymentArrangement,
    ExtractionMethod,
    JobEligibility,
    JobListing,
    VisaSponsorshipStatus,
    WorkArrangement,
)
from src.extraction.eligibility_labels import (
    _build_summary_label,
    build_objective_scope_label,
)

NIGERIAN_BOARD_PROVIDERS: frozenset[str] = frozenset({
    "jobberman",
    "myjobmag",
    "hotnigerianjobs",
})
_NG_BOARD_ELIGIBLE_REASON = "Listed on a Nigerian job board (workable from Nigeria)."

_US_STATE_CODES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA",
    "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
    "UT", "VT", "VA", "WA", "WV", "WI", "WY",
})

_CANADIAN_PROVINCE_TOKENS: frozenset[str] = frozenset({
    "ON", "BC", "QC", "AB", "MB", "SK", "NS", "NB", "PE", "NL", "YT", "NT", "NU",
    "ontario", "quebec", "british columbia", "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick",
})

_PERKS_CULTURE_HEADING_RE = re.compile(
    r"(?:perks?|benefits?|our\s+(?:values|culture|benefits)|what['\u2019]?s\s+in\s+it\s+for\s+you|what\s+we\s+offer)",
    re.IGNORECASE,
)
_HEADING_SCAN_RE = re.compile(
    r"^\s*(?:#{1,6}\s+([^\n]+)|\*\*([^*\n]{2,80})\*\*[:\s]*|"
    r"((?:WHAT\s+WE\s+OFFER|PERKS(?:\s*&\s*BENEFITS)?|BENEFITS(?:\s*&\s*PERKS)?|OUR\s+(?:VALUES|CULTURE|BENEFITS)|WHAT['\u2019]?S\s+IN\s+IT\s+FOR\s+YOU))[:\s]*)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _is_perks_or_culture_context(text: str, pos: int) -> bool:
    """Return True when pos sits on a culture/perks slogan or under a Perks/Benefits heading."""
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end == -1:
        line_end = len(text)
    line_text = text[line_start:line_end]
    if re.search(r"\bremote[- ]first\s+culture\b", line_text, re.IGNORECASE):
        return True
    last_heading: str | None = None
    for hm in _HEADING_SCAN_RE.finditer(text[:pos]):
        last_heading = (hm.group(1) or hm.group(2) or hm.group(3) or "").strip()
    if last_heading and _PERKS_CULTURE_HEADING_RE.search(last_heading):
        return True
    return False


def _is_product_marketing_context(text: str, pos: int) -> bool:
    """Return True when pos refers to product/platform capabilities or mission delivery rather than job eligibility."""
    window = text[max(0, pos - 160):min(len(text), pos + 100)]
    return bool(
        re.search(
            r"\b(?:empowers?|enables?|allows?|helps?|supports?|platform|software|tools?|products?|customers?|users?|schools?|districts?|clients?|brands?|organizations?|disaster[- ]affected|communit(?:y|ies)|recipients?|beneficiar(?:y|ies)|crisis)\b[^.\n]{0,90}\b(?:teams?\s+to\s+)?(?:work\s+(?:together\s+)?(?:in\s+real\s+time\s+)?(?:from\s+)?)?",
            window,
            re.IGNORECASE,
        )
    )


def _is_privacy_or_legal_disclaimer(text: str, pos: int) -> bool:
    """Return True when pos sits inside privacy notices, candidate retention disclosures, or CCPA boilerplate."""
    window = text[max(0, pos - 200):min(len(text), pos + 200)]
    return bool(
        re.search(
            r"\b(?:privacy\s+policy|personal\s+information|ccpa|california\s+consumer|recording\s+of\s+your\s+interview|"
            r"evaluate\s+your\s+application\s+for\s+employment\s+or\s+an\s+independent\s+contractor|as\s+applicable)\b",
            window,
            re.IGNORECASE,
        )
    )


_EEO_SENTENCE_RE = re.compile(
    r"(?:equal\s+opportunity\s+employer|without\s+regard\s+to|non-?discriminatory\s+basis\s+without\s+regard\s+to|"
    r"regardless\s+of\s+(?:race|color|religion|sex|gender|national\s+origin|citizenship))",
    re.IGNORECASE,
)

_GLOBAL_REMOTE_RE = re.compile(
    r"\b(?:work\s+(?:remotely\s+)?(?:from\s+)?anywhere(?:\s+in\s+the\s+world)?|anywhere\s+in\s+the\s+world|"
    r"can\s+be\s+executed\s+globally|can\s+be\s+executed\s+from\s+anywhere|"
    r"open\s+to\s+(?:remote\s+)?(?:candidates|applicants)\s+(?:worldwide|globally)|"
    r"engaged\s+globally|hir(?:e|ed|ing)\s+(?:globally|worldwide)|global\s+remote|"
    r"remote\s*[\(\[\-–,/\s]+\s*worldwide\s*[\)\]]?|"
    r"worldwide\s+(?:remote|applicants|candidates))\b",
    re.IGNORECASE,
)
_EXPLICIT_ROLE_GLOBAL_EXEC_RE = re.compile(
    r"\bthis\s+role\s+is\s+remote(?:[- ]first)?[^.\n]{0,40}\b"
    r"(?:can\s+be\s+executed\s+globally|"
    r"can\s+be\s+executed\s+from\s+anywhere(?![ \t]+(?:in|within|across|between|on)\b))",
    re.IGNORECASE,
)
_GLOBAL_NEGATIVE_RE = re.compile(
    r"\b(?:not\s+(?:available\s+)?(?:worldwide|global)|"
    r"based\s+in\s+one\s+of\s+the\s+(?:listed\s+|following\s+)?countries|"
    r"countries\s+on\s+(?:this|our)\s+list)\b",
    re.IGNORECASE,
)

_GEO_TOKEN = (
    r"United\s+States(?:\s+of\s+America)?|U\.S\.A?\.?|USA|(?-i:\bUS\b)|"
    r"United\s+Kingdom|U\.K\.?|(?-i:\bUK\b)|Great\s+Britain|"
    r"United\s+Arab\s+Emirates|(?-i:\bUAE\b)|Saudi\s+Arabia|South\s+Africa|South\s+Korea|New\s+Zealand|"
    r"Sub-Saharan\s+Africa|(?-i:\bSSA\b)|Latin\s+America|North\s+America|European\s+Union|Czech\s+Republic|"
    r"Canada|Germany|Deutschland|France|Spain|España|Tunisia|Nigeria|Ghana|Kenya|Egypt|Morocco|"
    r"Uganda|Rwanda|Tanzania|Senegal|Ethiopia|Cameroon|India|Ireland|Netherlands|"
    r"Poland|Brazil|Brasil|Sweden|Pakistan|Malaysia|Bulgaria|Thailand|Argentina|Malta|Denmark|"
    r"Estonia|Lithuania|Latvia|Norway|Finland|Switzerland|Iceland|Portugal|Italy|Austria|Belgium|"
    r"Singapore|Australia|Mexico|Colombia|Chile|Peru|Uruguay|Philippines|Vietnam|Indonesia|Japan|"
    r"Israel|Jordan|Czechia|Hungary|Romania|Greece|Croatia|Ukraine|"
    r"(?-i:\bEU\b|\bEEA\b|\bEMEA\b|\bAPAC\b|\bMENA\b|\bAMER\b|\bNAMER\b|\bNORAM\b)|LATAM|Europe|Africa|Americas"
)

_GEO_SCOPE = rf"(?:(?:{_GEO_TOKEN})(?:\s*(?:,?\s*\b(?:and|or)\b|[,/])\s*(?:the\s+)?(?:{_GEO_TOKEN}))*)"
_GEO_SCOPE_FOOTNOTE = rf"(?:(?:{_GEO_TOKEN})\*?(?:\s*(?:,?\s*\b(?:and|or)\b|[,/])\s*(?:the\s+)?(?:{_GEO_TOKEN})\*?)*)"

_WORK_ANYWHERE_SCOPED_RE = re.compile(
    rf"\b(?:work\s+(?:remotely\s+)?(?:from\s+)?anywhere|can\s+be\s+executed\s+(?:from\s+)?anywhere)\s+(?:in|within|across)\s+(?:the\s+)?(?P<scope>{_GEO_SCOPE})",
    re.IGNORECASE,
)

_RESIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bcan\s+be\s+executed\s+(?:from\s+)?(?:anywhere\s+(?:in|within|across)|from)\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})(?![ \t]+(?:East|West)\s+Coast\b)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:successful\s+)?(?:candidates?|applicants?)\s+(?:must\s+|should\s+|currently\s+)?(?:reside|live|be\s+located|be\s+based)\s+in\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\brequire\s+(?:successful\s+)?(?:candidates?|applicants?)\s+to\s+(?:reside|live|be\s+located|be\s+based)\s+in\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bopen\s+(?:only\s+)?to\s+(?:remote\s+)?(?:candidates|applicants)\s+(?:who\s+are\s+)?(?:(?:based|located|residing|living)\s+in|in|within|across|from)\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bresiding\s+in\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})(?=\s+(?:only|with\s+full\s+working\s+rights)\b|[.,;)\n]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:must|required\s+to)\s+(?:reside|live|be\s+located|be\s+based)\s+(?:in|within)\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:remote\s+(?:role|position|job)?\s*(?:only\s+)?(?:based|located|available)?\s*(?:in|within|across)|work\s+(?:remotely\s+)?from\s+(?:anywhere\s+in|within|across)|open\s+only\s+to\s+residents\s+of)\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:100%\s+)?\bremote\s*\(\s*(?P<geo>{_GEO_SCOPE})\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:\bcurrently\s+able\s+to\s+hire\s+in\s+the\s+following[^:\n]*:[^\n]*\n\s*|^\s*\*{{0,2}}Countries(?:\s*:\s*\*{{0,2}}|\*{{0,2}}\s*:)\s*)(?P<geo>{_GEO_SCOPE_FOOTNOTE})",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*\*{0,2}(?P<geo>US)\s+States(?:\s*:\s*\*{0,2}|\*{0,2}\s*:)\s*",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        rf"\b(?:residents|citizens\s+or\s+permanent\s+residents|permanent\s+residents)\s+of\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})(?:\s+only)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\blimited\s+to\s+(?:permanent\s+)?residents\s+of\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
        re.IGNORECASE,
    ),
)

_PAN_REGIONAL_REMOTE_RE = re.compile(
    r"\b(?:work\s+(?:remotely\s+)?(?:from\s+)?anywhere\s+(?:in|within|across)|"
    r"open\s+to\s+(?:remote\s+)?(?:candidates|applicants)\s+(?:in|within|across|from)|"
    r"remote\s+(?:across|throughout|anywhere\s+in|within)|"
    r"remotely\s+(?:from|in|across|within))\s+(?:the\s+)?(?:[A-Za-z]+\s+(?:and|or)\s+(?:the\s+)?)?"
    r"(?:Africa|Sub-Saharan\s+Africa|EU|European\s+Union|EEA)\b",
    re.IGNORECASE,
)

_LOCATION_HEADER_LINE_RE = re.compile(
    r"^\s*\*{0,2}(?:job\s+)?location\*{0,2}\s*[:\-–]\s*(?P<line>[^\n]{3,160})$",
    re.IGNORECASE | re.MULTILINE,
)

_EXCLUDED_RESIDENCE_RE = re.compile(
    rf"\b(?:unable\s+to\s+hire|cannot\s+hire|excludes?|not\s+available|not\s+hiring)\s+(?:candidates\s+|applicants\s+)?in\s+(?:the\s+)?(?P<geo>{_GEO_SCOPE})\b",
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
    r"\b(?:(?:work\s+)?visa\s+sponsorship\s+(?:is\s+)?available|will\s+consider\s+sponsoring|offer(?:s|ing)?\s+(?:work\s+)?visa\s+sponsorship)\b",
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
    r"\b(?:independent\s+contractor|contractor\s+arrangement|b2b\s+contract|\bb2b\s+(?:contract|agreement|invoicing|arrangements?)\b|\b1099\b|\bc2c\b|consultancy\s+contract)\b",
    re.IGNORECASE,
)
_EOR_RE = re.compile(
    r"\b(?:employer\s+of\s+record|\beor\b|(?:via|through|using)\s+(?:Deel|Remote\.com|Oyster|Papaya\s+Global))\b",
    re.IGNORECASE,
)
_EMPLOYEE_PAYROLL_RE = re.compile(r"\b(?:w-?2\s+employee|direct\s+fte\s+employee)\b", re.IGNORECASE)

_TIMEZONE_RE = re.compile(
    r"(?:\b\d+\+?\s+hours?\s+(?:of\s+)?overlap\s+with\s+(?:[A-Z]{2,5}|US\s+(?:Eastern|Pacific|Central|Mountain)|EMEA|Americas)\b(?:\s+business\s+hours)?|"
    r"\bmust\s+work\s+(?:within\s+)?(?:[A-Z]{2,5}|EMEA|Americas)\s+(?:business\s+hours|time\s*zones?)\b|"
    r"\b(?:within\s+)?UTC\s*[+-]\s*\d{1,2}\s*(?:to|[-–])\s*UTC\s*[+-]\s*\d{1,2}\b(?:\s*time\s*zones?)?)",
    re.IGNORECASE,
)

_HYBRID_ATTENDANCE_RE = re.compile(
    r"(?:\b(?:expected|required)\s+to\s+(?:report|come|be)\s+(?:to|in)\s+(?:(?:the|our|an|[A-Za-zÀ-ÖØ-öø-ÿ-]+)\s+){0,3}office\b|"
    r"\bcategori[sz]ed\s+as\s+on[- ]?site\b|"
    r"\b\d+\s*(?:days?|d)\s*(?:per\s+week|a\s+week|/wk|/week)?\s*(?:worked\s+)?(?:in[- ]office|(?:from|in|at)\s+(?:the\s+|our\s+)?(?:[A-Za-zÀ-ÖØ-öø-ÿ-]+\s+){0,3}office|on[- ]?site|onsite)\b|"
    r"\boffice[- ]based\s+in\s+[^.\n]+\d+\s*days?\b|"
    r"\bregular\s+(?:in[- ]person|on[- ]?site)\s+(?:attendance|presence|collaboration)\b|"
    r"\bcollaboration\s+(?:at|with)\s+(?:[^.\n]+facilities|regional\s+teams)\b)",
    re.IGNORECASE,
)

_NON_COUNTRY_REGIONS: frozenset[str] = frozenset({
    "Worldwide", "Africa", "Sub-Saharan Africa", "EMEA", "Europe",
    "EU", "EEA", "LATAM", "APAC", "North America", "Americas", "MENA",
})


def normalize_country_name(raw_country: str | None) -> str | None:
    """Normalize known country/region strings into canonical display names."""
    return normalize_geo_label(raw_country)


def _strip_eeo_sentences(text: str) -> str:
    """Remove standard non-discrimination EEO statements before scanning requirements."""
    kept: list[str] = []
    for line in text.splitlines():
        if _EEO_SENTENCE_RE.search(line):
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
            norm = normalize_country_name(desc)
            if norm and norm not in _NON_COUNTRY_REGIONS:
                return norm, desc, field_name

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
                norm = normalize_country_name(desc)
                if norm and norm not in _NON_COUNTRY_REGIONS:
                    return norm, desc, "jobLocation.address.addressCountry"

    # Ashby address.postalAddress.addressCountry
    ashby_addr = raw_fields.get("address")
    if isinstance(ashby_addr, dict):
        postal = ashby_addr.get("postalAddress")
        if isinstance(postal, dict):
            country_val = postal.get("addressCountry")
            desc = _extract_descriptor(country_val)
            if desc:
                norm = normalize_country_name(desc)
                if norm and norm not in _NON_COUNTRY_REGIONS:
                    return norm, desc, "address.postalAddress.addressCountry"

    # Workable location: {"city": ..., "country": "Jordan", "countryCode": "JO", "region": ...}
    wk_loc = raw_fields.get("location")
    if isinstance(wk_loc, dict):
        for k in ("country", "countryCode"):
            desc = _extract_descriptor(wk_loc.get(k))
            if desc:
                norm = normalize_country_name(desc)
                if norm and norm not in _NON_COUNTRY_REGIONS:
                    return norm, desc, f"location.{k}"

    return None, None, None


def _extract_structured_region(raw_fields: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    """Return (canonical_region, raw_snippet, provider_field_name) when structured country is a macro-region."""
    if not raw_fields:
        return None, None, None
    ashby_addr = raw_fields.get("address")
    if isinstance(ashby_addr, dict):
        postal = ashby_addr.get("postalAddress")
        if isinstance(postal, dict):
            desc = _extract_descriptor(postal.get("addressCountry"))
            if desc:
                norm = normalize_country_name(desc)
                if norm in _NON_COUNTRY_REGIONS and norm != "Worldwide":
                    return norm, desc, "address.postalAddress.addressCountry"
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


def _split_countries_and_regions(labels: list[str] | None) -> tuple[list[str] | None, list[str] | None]:
    """Partition mixed country/region labels into deduped ISO-2 country codes and region labels."""
    if not labels:
        return None, None
    codes: list[str] = []
    regions: list[str] = []
    for item in labels:
        reg = normalize_region_name(item)
        if reg and reg != "Worldwide":
            if reg not in regions:
                regions.append(reg)
            continue
        code = normalize_country_code(item)
        if code and code not in codes:
            codes.append(code)
    return (codes or None), (regions or None)


def _normalize_work_arrangement(work_model: str | None) -> WorkArrangement:
    wm = (work_model or "").strip().lower().replace("-", "_").replace(" ", "_")
    if wm == "remote":
        return "remote"
    if wm == "hybrid":
        return "hybrid"
    if wm in ("in_person", "onsite", "on_site"):
        return "onsite"
    return "unknown"


_MORE_SUFFIX_RE = re.compile(r"\s*\(\+\d+\s+more\)\s*$", re.IGNORECASE)
_LOCAL_MODE_PREFIX_RE = re.compile(r"^(?:hybrid|on[- ]?site|in[- ]?person)\s*[-–:,/]\s*", re.IGNORECASE)
_LOCAL_MODE_PARENS_RE = re.compile(r"\s*\((?:hybrid|on[- ]?site|in[- ]?person)\)\s*$", re.IGNORECASE)

_MAJOR_CITY_TO_COUNTRY_CODE: dict[str, str] = {
    "london": "GB",
    "berlin": "DE",
    "munich": "DE",
    "münchen": "DE",
    "paris": "FR",
    "amsterdam": "NL",
    "dublin": "IE",
    "brussels": "BE",
    "barcelona": "ES",
    "madrid": "ES",
    "milan": "IT",
    "vienna": "AT",
    "zurich": "CH",
    "zürich": "CH",
    "stockholm": "SE",
    "warsaw": "PL",
    "lagos": "NG",
    "abuja": "NG",
    "nairobi": "KE",
    "accra": "GH",
    "cairo": "EG",
    "cape town": "ZA",
    "johannesburg": "ZA",
    "toronto": "CA",
    "montreal": "CA",
    "vancouver": "CA",
    "singapore": "SG",
    "bengaluru": "IN",
    "bangalore": "IN",
    "mumbai": "IN",
    "new delhi": "IN",
    "hyderabad": "IN",
    "sydney": "AU",
    "melbourne": "AU",
    "tokyo": "JP",
    "dubai": "AE",
    "amman": "JO",
    "riyadh": "SA",
    "doha": "QA",
    "são paulo": "BR",
    "sao paulo": "BR",
    "mexico city": "MX",
}


def _strip_more_suffix(value: str) -> str:
    cleaned = _MORE_SUFFIX_RE.sub("", value.strip())
    cleaned = _LOCAL_MODE_PREFIX_RE.sub("", cleaned)
    cleaned = _LOCAL_MODE_PARENS_RE.sub("", cleaned)
    return cleaned.strip()


def _extract_country_from_location_segment(seg: str) -> str | None:
    """Resolve one city/state/country segment (e.g. 'San Francisco, CA', 'London') to ISO country name."""
    cleaned = _strip_more_suffix(seg)
    if not cleaned:
        return None
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    tail = parts[-1] if parts else cleaned
    has_canada = any(
        p.lower() == "canada"
        or p.upper() in _CANADIAN_PROVINCE_TOKENS
        or p.lower() in _CANADIAN_PROVINCE_TOKENS
        for p in parts[:-1]
    )
    if len(parts) >= 2 and tail.upper() in _US_STATE_CODES and not has_canada:
        return "United States"
    c_code = normalize_country_code(tail)
    if not c_code:
        c_code = _MAJOR_CITY_TO_COUNTRY_CODE.get(tail.lower()) or _MAJOR_CITY_TO_COUNTRY_CODE.get(cleaned.lower())
    return ISO2_TO_COUNTRY[c_code] if c_code else None


def _collect_multihub_countries(
    location: str | None,
    raw_fields: dict[str, Any] | None,
) -> tuple[list[str], str]:
    """Collect distinct country names across Teamtailor/Personio all_locations, Workable locations, or [;|] segments."""
    if isinstance(raw_fields, dict):
        all_locs = raw_fields.get("all_locations")
        if isinstance(all_locs, list) and all_locs:
            from_all: list[str] = []
            for seg in all_locs:
                if isinstance(seg, str):
                    c_name = _extract_country_from_location_segment(seg)
                    if c_name and c_name not in from_all:
                        from_all.append(c_name)
            if len(from_all) >= 2:
                return from_all, "all_locations"

        wk_locs = raw_fields.get("locations")
        if isinstance(wk_locs, list) and wk_locs:
            from_wk: list[str] = []
            for entry in wk_locs:
                c_name: str | None = None
                if isinstance(entry, dict):
                    raw_c = _extract_descriptor(entry.get("countryCode")) or _extract_descriptor(entry.get("country"))
                    if raw_c:
                        c_code = normalize_country_code(raw_c)
                        c_name = ISO2_TO_COUNTRY[c_code] if c_code else None
                elif isinstance(entry, str):
                    c_name = _extract_country_from_location_segment(entry)
                if c_name and c_name not in from_wk:
                    from_wk.append(c_name)
            if len(from_wk) >= 2:
                return from_wk, "locations"

    if location and (";" in location or "|" in location):
        from_loc: list[str] = []
        for seg in re.split(r"[;|]", location):
            c_name = _extract_country_from_location_segment(seg)
            if c_name and c_name not in from_loc:
                from_loc.append(c_name)
        if len(from_loc) >= 2:
            return from_loc, "location"

    return [], "location"


def _extract_remote_entry_geo(raw_entry: str) -> str | None:
    """Resolve one cleaned remote location entry strictly to a canonical country or non-Worldwide macro-region."""
    cleaned = re.sub(r"\(\s*(?:remote|home[- ]?based)\s*\)", "", raw_entry, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:remote|home[- ]?based)\s*[-–,:]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" ,.;:-–/()")
    if not cleaned:
        return None
    reg = normalize_region_name(cleaned)
    if reg and reg != "Worldwide":
        return reg
    code = normalize_country_code(cleaned)
    return ISO2_TO_COUNTRY[code] if code else None


def _collect_remote_structured_geos(
    location: str | None,
    raw_fields: dict[str, Any] | None,
) -> tuple[list[str], str]:
    """Resolve Ashby multi-country remote secondaryLocations (or delimited country lists) conservatively."""
    sec_locs = raw_fields.get("secondaryLocations") if isinstance(raw_fields, dict) else None
    has_secondary = isinstance(sec_locs, list) and len(sec_locs) > 0
    if not has_secondary:
        return [], "location"

    raw_entries: list[str] = []
    primary = raw_fields.get("location") or raw_fields.get("locationName") or location
    if isinstance(primary, str) and primary.strip():
        raw_entries.extend(seg.strip() for seg in re.split(r"[;|]", primary) if seg.strip())

    for item in sec_locs:
        loc_str: str | None = None
        if isinstance(item, dict):
            loc_str = item.get("location") or item.get("locationName")
            if not loc_str and isinstance(item.get("address"), dict):
                postal = item["address"].get("postalAddress")
                if isinstance(postal, dict):
                    loc_str = _extract_descriptor(postal.get("addressCountry"))
        elif isinstance(item, str):
            loc_str = item
        if isinstance(loc_str, str) and loc_str.strip():
            raw_entries.append(loc_str.strip())

    # Require every meaningful token in the multi-location list to resolve strictly as a country or region
    # (never trigger on city/office names or bare single-country HQ).
    resolved: list[str] = []
    meaningful = 0
    for entry in raw_entries:
        if entry.strip().lower() in {"remote", "home-based", "home based"}:
            continue
        meaningful += 1
        geo = _extract_remote_entry_geo(entry)
        if not geo:
            return [], "secondaryLocations"
        if geo not in resolved:
            resolved.append(geo)
    if meaningful >= 2 and resolved:
        return resolved, "secondaryLocations"
    return [], "secondaryLocations"


def _infer_physical_country_code(eligibility: JobEligibility, location: str | None) -> str | None:
    if eligibility.physical_location_country_code:
        norm = normalize_country_code(eligibility.physical_location_country_code)
        if norm:
            return norm
    if eligibility.physical_location_country:
        norm = normalize_country_code(eligibility.physical_location_country)
        if norm:
            return norm
    if location:
        first_loc = re.split(r"[;|]", location)[0].strip()
        country_name = _extract_country_from_location_segment(first_loc)
        if country_name:
            return normalize_country_code(country_name)
    return None


def evaluate_eligibility_for_country(
    eligibility: JobEligibility | None,
    applicant_country: str,
    *,
    work_model: str | None = None,
    location: str | None = None,
    provider: str | None = None,
) -> ApplicantEligibilityAssessment:
    """
    Evaluate job compatibility for a specific ISO 3166-1 alpha-2 applicant country.

    Preserves conservative ADR 0001 semantics:
    - Never converts missing eligibility metadata or generic 'remote' into worldwide.
    - Never assumes broad business regions (EMEA, Europe, APAC, LATAM) confer uniform
      eligibility across all member countries.
    - Gives explicit country/payroll/attendance restrictions precedence over generic claims.
    """
    cc = normalize_country_code(applicant_country)
    if not cc:
        raise ValueError(f"Unsupported applicant country code: {applicant_country!r}")
    country_name = ISO2_TO_COUNTRY[cc]
    work_arrangement = _normalize_work_arrangement(work_model)
    is_ng_board = cc == "NG" and (provider or "").strip().lower() in NIGERIAN_BOARD_PROVIDERS

    if eligibility is None:
        if is_ng_board:
            summary = _build_summary_label(
                work_arrangement=work_arrangement,
                status="eligible",
                applicant_country_name=country_name,
                applicant_country_code=cc,
                global_remote_explicit=None,
                allowed_codes=[],
                allowed_regions=[],
                excluded_codes=[],
                excluded_regions=[],
                location=location,
                physical_country_name=None,
            )
            return ApplicantEligibilityAssessment(
                applicant_country_code=cc,
                applicant_country_name=country_name,
                status="eligible",
                reason=_NG_BOARD_ELIGIBLE_REASON,
                work_arrangement=work_arrangement,
                summary_label=summary,
            )
        summary = (
            "Remote · Eligibility unverified"
            if work_arrangement == "remote"
            else (
                f"{work_arrangement.capitalize()} · {location.strip()}"
                if work_arrangement in ("onsite", "hybrid") and location and location.strip()
                else None
            )
        )
        return ApplicantEligibilityAssessment(
            applicant_country_code=cc,
            applicant_country_name=country_name,
            status="unknown",
            reason=None,
            work_arrangement=work_arrangement,
            summary_label=summary,
        )

    allowed_codes = list(eligibility.allowed_country_codes or [])
    allowed_regions = list(eligibility.allowed_regions or [])
    if not allowed_codes and not allowed_regions and eligibility.allowed_residence_countries:
        fb_codes, fb_regs = _split_countries_and_regions(eligibility.allowed_residence_countries)
        allowed_codes = fb_codes or []
        allowed_regions = fb_regs or []

    excluded_codes = list(eligibility.excluded_country_codes or [])
    excluded_regions = list(eligibility.excluded_regions or [])
    if not excluded_codes and not excluded_regions and eligibility.excluded_residence_countries:
        ex_codes, ex_regs = _split_countries_and_regions(eligibility.excluded_residence_countries)
        excluded_codes = ex_codes or []
        excluded_regions = ex_regs or []

    phys_code = _infer_physical_country_code(eligibility, location)
    phys_name = eligibility.physical_location_country or (country_name_for_code(phys_code) if phys_code else None)

    payroll_codes, payroll_regs = _split_countries_and_regions(eligibility.payroll_requirements)
    payroll_codes = payroll_codes or []
    payroll_regs = payroll_regs or []

    work_auth_codes, _ = _split_countries_and_regions(eligibility.work_authorization_required)
    work_auth_codes = work_auth_codes or []
    citizenship_codes, _ = _split_countries_and_regions(eligibility.citizenship_requirements)
    citizenship_codes = citizenship_codes or []

    hybrid_confirmed = eligibility.hybrid_attendance_confirmed
    if hybrid_confirmed is None:
        hybrid_confirmed = any(f.dimension == "hybrid_attendance" for f in (eligibility.facts or []))

    foreign_physical = bool(phys_code and phys_code != cc)
    in_allowed_code = cc in allowed_codes
    in_allowed_region = any(is_country_in_region(cc, reg) for reg in allowed_regions)
    has_residence_scope = bool(
        eligibility.residence_restriction_confirmed or allowed_codes or allowed_regions
    )
    has_foreign_payroll = bool(
        (payroll_codes or payroll_regs)
        and cc not in payroll_codes
        and not any(is_country_in_region(cc, reg) for reg in payroll_regs)
    )

    def _make_result(status: EligibilityStatus, reason: str | None) -> ApplicantEligibilityAssessment:
        eff_codes = allowed_codes if not (is_ng_board and status == "eligible" and cc not in allowed_codes) else []
        eff_regs = (
            [r for r in allowed_regions if is_country_in_region(cc, r)]
            if (is_ng_board and status == "eligible")
            else allowed_regions
        )
        summary = _build_summary_label(
            work_arrangement=work_arrangement,
            status=status,
            applicant_country_name=country_name,
            applicant_country_code=cc,
            global_remote_explicit=eligibility.global_remote_explicit,
            allowed_codes=eff_codes,
            allowed_regions=eff_regs,
            excluded_codes=excluded_codes,
            excluded_regions=excluded_regions,
            location=location,
            physical_country_name=phys_name,
        )
        return ApplicantEligibilityAssessment(
            applicant_country_code=cc,
            applicant_country_name=country_name,
            status=status,
            reason=reason,
            work_arrangement=work_arrangement,
            summary_label=summary,
        )

    # 1. Explicit country exclusion
    if cc in excluded_codes:
        return _make_result("restricted", f"Role explicitly excludes applicants residing in {country_name}.")

    # 2. Explicit regional exclusion
    matching_excl_reg = next((r for r in excluded_regions if is_country_in_region(cc, r)), None)
    if matching_excl_reg:
        return _make_result("restricted", f"Role explicitly excludes applicants in {matching_excl_reg}.")

    # 2b. Active Nigerian job boards default to Nigeria-eligible unless explicitly excluded above
    if is_ng_board:
        return _make_result("eligible", _NG_BOARD_ELIGIBLE_REASON)

    # 3. Explicit allowed residence scope does not include applicant's country or region
    if has_residence_scope and not in_allowed_code and not in_allowed_region:
        scope_names = list(eligibility.allowed_residence_countries or [])
        if not scope_names:
            scope_names = [country_name_for_code(c) or c for c in allowed_codes] + allowed_regions
        return _make_result("restricted", f"Applicant residence restricted to {', '.join(scope_names)}.")

    # 4. Relocation required to another country
    if eligibility.relocation_required and foreign_physical:
        return _make_result("restricted", f"Relocation to {phys_name} is required.")

    # 5. Onsite role in another country (unless explicitly permitted for applicant's country)
    if work_arrangement == "onsite" and foreign_physical and not in_allowed_code:
        return _make_result(
            "restricted",
            f"On-site role in {phys_name} requires physical attendance outside {country_name}.",
        )

    # 6. Confirmed hybrid attendance in another country
    if work_arrangement == "hybrid" and foreign_physical and hybrid_confirmed and not in_allowed_code:
        return _make_result(
            "restricted",
            f"Hybrid role requires in-office attendance in {phys_name}.",
        )

    # 7. Incompatible local payroll requirement
    if has_foreign_payroll:
        req_labels = eligibility.payroll_requirements or [country_name_for_code(c) or c for c in payroll_codes]
        return _make_result("restricted", f"Employment restricted to local {', '.join(req_labels)} payroll.")

    # 8. Explicit country residence permission (unless blocked by single-country citizenship/payroll)
    if in_allowed_code:
        return _make_result("eligible", f"Explicitly permits applicants in {country_name}.")

    # 9. Local onsite or hybrid role located in applicant's own country
    if work_arrangement in ("onsite", "hybrid") and phys_code == cc:
        if citizenship_codes and cc not in citizenship_codes:
            return _make_result("unknown", "Citizenship requirement disclosed for local role.")
        return _make_result(
            "eligible",
            f"{work_arrangement.capitalize()} role located in {phys_name or country_name}.",
        )

    # 10. Explicit pan-regional remote permission (Africa / Sub-Saharan Africa / EU / EEA only)
    # Never assume uniform regional eligibility from bare region tags or non-remote hubs.
    if in_allowed_region:
        matching_uniform_regions = [
            r for r in allowed_regions if r in UNIFORM_CAPABLE_REGIONS and is_country_in_region(cc, r)
        ]
        conflicting_narrow_country = bool(
            (allowed_codes and not in_allowed_code and not eligibility.pan_regional_remote_confirmed)
            or (work_auth_codes and cc not in work_auth_codes and eligibility.visa_sponsorship_status == "not_available")
        )
        if (
            matching_uniform_regions
            and eligibility.pan_regional_remote_confirmed is True
            and work_arrangement == "remote"
            and not conflicting_narrow_country
            and not (foreign_physical and not eligibility.pan_regional_remote_confirmed)
        ):
            reg_label = ", ".join(matching_uniform_regions)
            return _make_result(
                "eligible",
                f"Explicitly permits remote applicants across {reg_label} (confirm country-specific contract terms).",
            )
        # Region matches (e.g., EMEA, Europe, LATAM, APAC, or bare EU/Africa tag without pan-regional remote confirmation)
        matched_reg_labels = [r for r in allowed_regions if is_country_in_region(cc, r)]
        return _make_result(
            "unknown",
            f"Scoped to {', '.join(matched_reg_labels)}; country-level eligibility for {country_name} is unconfirmed.",
        )

    # 11. Explicit worldwide remote
    if eligibility.global_remote_explicit:
        return _make_result("eligible", "Explicitly open worldwide / work from anywhere.")

    # 12. Work authorization / sponsorship / citizenship / clearance disclosures
    if eligibility.work_authorization_required and eligibility.visa_sponsorship_status == "not_available":
        return _make_result(
            "unknown",
            f"Discloses {', '.join(eligibility.work_authorization_required)} work authorization / no sponsorship without confirmed residence or physical attendance restriction.",
        )

    if eligibility.work_authorization_required:
        return _make_result(
            "unknown",
            f"Discloses {', '.join(eligibility.work_authorization_required)} work authorization without confirmed residence or physical attendance restriction.",
        )

    if eligibility.visa_sponsorship_status == "not_available":
        return _make_result("unknown", "Visa sponsorship unavailable; geographic residence eligibility undisclosed.")

    if eligibility.citizenship_requirements or eligibility.security_clearance_required:
        return _make_result("unknown", "Citizenship or security clearance requirement disclosed without residence ban.")

    if work_arrangement == "hybrid" and foreign_physical:
        return _make_result("unknown", f"Hybrid role in {phys_name}; physical attendance frequency undisclosed.")

    return _make_result("unknown", None)


def apply_applicant_country_assessment(
    listing: JobListing,
    applicant_country: str | None,
) -> JobListing:
    """
    Return a shallow copy of ``listing`` with ``eligibility.applicant_assessment``
    populated for ``applicant_country`` without mutating cached objects.
    """
    if not applicant_country:
        return listing
    assessment = evaluate_eligibility_for_country(
        listing.eligibility,
        applicant_country,
        work_model=listing.work_model,
        location=listing.location,
        provider=listing.provider or listing.ats_source,
    )
    if listing.eligibility is None:
        updated_elig = JobEligibility(
            classification="unknown",
            applicant_assessment=assessment,
        )
    else:
        updated_elig = listing.eligibility.model_copy(update={"applicant_assessment": assessment})
    return listing.model_copy(update={"eligibility": updated_elig})


def _determine_classification(
    *,
    global_remote_explicit: bool | None,
    allowed_codes: list[str] | None,
    allowed_regions: list[str] | None,
    work_model: str | None,
    physical_country: str | None,
    work_auth: list[str] | None,
    citizenship: list[str] | None,
    clearance: str | None,
    visa_status: VisaSponsorshipStatus | None,
) -> EligibilityClassification:
    work_arrangement = _normalize_work_arrangement(work_model)
    if global_remote_explicit and not allowed_codes and not allowed_regions:
        return "worldwide"
    if allowed_codes:
        return "country_restricted"
    if allowed_regions:
        return "region_restricted"
    if work_arrangement in ("onsite", "hybrid") and physical_country:
        return "onsite_or_hybrid_local"
    if work_auth or citizenship or clearance or visa_status == "not_available":
        return "work_auth_disclosed"
    return "unknown"


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
    evidence_url: str | None = None,
    verified_at: datetime | None = None,
) -> JobEligibility | None:
    """
    Extract conservative geographic and employment eligibility facts without
    assuming a fixed applicant country, then populate backward-compatible fields.
    """
    has_structured_fields = bool(
        raw_fields
        and (
            raw_fields.get("applicantLocationRequirements")
            or raw_fields.get("country")
            or raw_fields.get("jobRequisitionLocation")
            or raw_fields.get("jobLocation")
            or raw_fields.get("address")
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
        first_loc = re.split(r"[;|]", location)[0].strip()
        resolved_phys = _extract_country_from_location_segment(first_loc)
        if resolved_phys:
            physical_country = resolved_phys
            _add_fact(facts, "physical_location", physical_country, location, method, "location")

    req_countries, req_global, req_snips = _extract_applicant_location_reqs(raw_fields)
    allowed_residence: list[str] | None = req_countries if req_countries else None
    excluded_residence: list[str] | None = None
    residence_confirmed: bool | None = True if req_countries else None
    global_remote_explicit: bool | None = None
    pan_regional_remote_confirmed: bool | None = None

    # Check Lever-style commitment remote scope tags (e.g. "Remote - Latam", "Remote - US")
    cats = (raw_fields or {}).get("categories") if isinstance(raw_fields, dict) else None
    commitment_val = cats.get("commitment") if isinstance(cats, dict) else None
    if isinstance(commitment_val, str) and commitment_val.strip():
        comm_m = re.match(
            rf"^\s*remote\s*[-–/(:]\s*(?P<geo>{_GEO_SCOPE})\s*\)?\s*$",
            commitment_val.strip(),
            re.IGNORECASE,
        )
        if comm_m:
            for geo_hit in re.finditer(_GEO_TOKEN, comm_m.group("geo"), re.IGNORECASE):
                norm_comm_geo = normalize_country_name(geo_hit.group(0))
                if norm_comm_geo and norm_comm_geo != "Worldwide":
                    allowed_residence = _append_unique(allowed_residence, norm_comm_geo)
                    residence_confirmed = True
                    _add_fact(
                        facts,
                        "allowed_residence",
                        norm_comm_geo,
                        commitment_val.strip(),
                        method,
                        "categories.commitment",
                    )

    # Multi-hub hybrid/onsite location strings and structured arrays
    norm_wm = _normalize_work_arrangement(work_model)
    if norm_wm in ("hybrid", "onsite") and not allowed_residence:
        hub_countries, hub_field = _collect_multihub_countries(location, raw_fields)
        if len(hub_countries) >= 2:
            for c_name in hub_countries:
                allowed_residence = _append_unique(allowed_residence, c_name)
                residence_confirmed = True
                _add_fact(facts, "allowed_residence", c_name, location or ", ".join(hub_countries), method, hub_field)

    explicit_role_global_exec = bool(
        description
        and description_is_authentic
        and method != ExtractionMethod.SNIPPET
        and _EXPLICIT_ROLE_GLOBAL_EXEC_RE.search(description)
    )

    if location and not allowed_residence and not explicit_role_global_exec:
        loc_clean = re.sub(r"[\(\[\)\]]", " ", location)
        has_remote_loc_marker = bool(re.search(r"\b(?:remote|home[- ]?based)\b", loc_clean, re.IGNORECASE))
        if has_remote_loc_marker:
            found_loc_geos: list[str] = []
            for geo_hit in re.finditer(_GEO_TOKEN, loc_clean, re.IGNORECASE):
                norm_geo = normalize_country_name(geo_hit.group(0))
                if norm_geo and norm_geo != "Worldwide" and norm_geo not in found_loc_geos:
                    found_loc_geos.append(norm_geo)
            # Also resolve exact delimited segments not explicitly in _GEO_TOKEN (e.g. Slovakia (Remote))
            if ";" in location or "|" in location:
                for seg in re.split(r"[;|]", location):
                    seg_geo = _extract_remote_entry_geo(seg)
                    if seg_geo and seg_geo not in found_loc_geos:
                        found_loc_geos.append(seg_geo)
            for norm_geo in found_loc_geos:
                allowed_residence = _append_unique(allowed_residence, norm_geo)
                residence_confirmed = True
                if normalize_region_name(norm_geo) in UNIFORM_CAPABLE_REGIONS:
                    pan_regional_remote_confirmed = True
                _add_fact(facts, "allowed_residence", norm_geo, location, method, "location")
        elif work_model == "remote":
            # Bare compound multi-region location on explicit remote role (e.g. "NAMER and LatAm")
            region_tokens = [
                tok.strip()
                for tok in re.split(r"\s*(?:,|;|/|&|\band\b|\bor\b)\s*", loc_clean, flags=re.IGNORECASE)
                if tok.strip()
            ]
            if len(region_tokens) >= 2:
                resolved_regs = [normalize_region_name(tok) for tok in region_tokens]
                if all(r and r != "Worldwide" for r in resolved_regs):
                    for reg_name in resolved_regs:
                        if reg_name:
                            allowed_residence = _append_unique(allowed_residence, reg_name)
                            residence_confirmed = True
                            _add_fact(facts, "allowed_residence", reg_name, location, method, "location")

    for c, snip in zip(req_countries, req_snips):
        _add_fact(
            facts,
            "allowed_residence",
            c,
            snip,
            ExtractionMethod.JSON_LD,
            "applicantLocationRequirements",
        )
    if req_global and not allowed_residence:
        global_remote_explicit = True
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
    cleaned_desc: str | None = None
    scoped_matches: list[re.Match[str]] = []

    if description and description_is_authentic and method != ExtractionMethod.SNIPPET:
        cleaned_desc = _strip_eeo_sentences(description)
        text_method = method

        # 1. Extract explicit scoped residence & restriction facts BEFORE checking global worldwide claims
        scoped_matches = list(_WORK_ANYWHERE_SCOPED_RE.finditer(cleaned_desc))
        for sm in scoped_matches:
            scope_text = sm.group("scope")
            for geo_hit in re.finditer(_GEO_TOKEN, scope_text, re.IGNORECASE):
                norm_geo = normalize_country_name(geo_hit.group(0))
                if norm_geo and norm_geo != "Worldwide":
                    allowed_residence = _append_unique(allowed_residence, norm_geo)
                    residence_confirmed = True
                    _add_fact(facts, "allowed_residence", norm_geo, sm.group(0), text_method, "description")

        for pat in _RESIDENCE_PATTERNS:
            for m in pat.finditer(cleaned_desc):
                for geo_hit in re.finditer(_GEO_TOKEN, m.group("geo"), re.IGNORECASE):
                    norm_geo = normalize_country_name(geo_hit.group(0))
                    if norm_geo and norm_geo != "Worldwide":
                        allowed_residence = _append_unique(allowed_residence, norm_geo)
                        residence_confirmed = True
                        _add_fact(facts, "allowed_residence", norm_geo, m.group(0), text_method, "description")

        # Multi-country explicit "Location: City, Country or City, Country" lines in description
        for loc_m in _LOCATION_HEADER_LINE_RE.finditer(cleaned_desc):
            line_val = loc_m.group("line")
            line_geos: list[str] = []
            for geo_hit in re.finditer(_GEO_TOKEN, line_val, re.IGNORECASE):
                norm_geo = normalize_country_name(geo_hit.group(0))
                if norm_geo and norm_geo != "Worldwide" and norm_geo not in line_geos:
                    line_geos.append(norm_geo)
            if len(line_geos) >= 2:
                for norm_geo in line_geos:
                    allowed_residence = _append_unique(allowed_residence, norm_geo)
                    residence_confirmed = True
                    _add_fact(facts, "allowed_residence", norm_geo, loc_m.group(0), text_method, "description")

        if _PAN_REGIONAL_REMOTE_RE.search(cleaned_desc) and work_model == "remote":
            pan_regional_remote_confirmed = True

        for m in _EXCLUDED_RESIDENCE_RE.finditer(cleaned_desc):
            for geo_hit in re.finditer(_GEO_TOKEN, m.group("geo"), re.IGNORECASE):
                norm_geo = normalize_country_name(geo_hit.group(0))
                if norm_geo and norm_geo != "Worldwide":
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
        else:
            for m_ctr in _CONTRACTOR_RE.finditer(cleaned_desc):
                if not _is_privacy_or_legal_disclaimer(cleaned_desc, m_ctr.start()):
                    arrangement = "contractor"
                    _add_fact(facts, "employment_arrangement", "contractor", m_ctr.group(0), text_method, "description")
                    break
        if not arrangement:
            if m_emp := _EMPLOYEE_PAYROLL_RE.search(cleaned_desc):
                arrangement = "employee"
                _add_fact(facts, "employment_arrangement", "employee", m_emp.group(0), text_method, "description")

        if m_tz := _TIMEZONE_RE.search(cleaned_desc):
            timezone_req = m_tz.group(0).strip()
            _add_fact(facts, "timezone", timezone_req, m_tz.group(0), text_method, "description")

        if work_model == "hybrid":
            if m_hyb := _HYBRID_ATTENDANCE_RE.search(cleaned_desc):
                hybrid_attendance_confirmed = True
                _add_fact(facts, "hybrid_attendance", "required", m_hyb.group(0), text_method, "description")

    # Structured multi-country remote lists (Ashby secondaryLocations) after prose residence patterns
    if work_model == "remote" and not allowed_residence and not explicit_role_global_exec:
        sec_geos, sec_field = _collect_remote_structured_geos(location, raw_fields)
        for geo_name in sec_geos:
            allowed_residence = _append_unique(allowed_residence, geo_name)
            residence_confirmed = True
            if normalize_region_name(geo_name) in UNIFORM_CAPABLE_REGIONS:
                pan_regional_remote_confirmed = True
            _add_fact(facts, "allowed_residence", geo_name, location or ", ".join(sec_geos), method, sec_field)

    # 2. Only consider explicit global_remote if NO country/region residence, payroll, or physical city/hybrid lock exists
    if cleaned_desc is not None:
        phys_without_remote_marker = bool(
            physical_country
            and not re.search(r"\b(?:remote|global|worldwide|anywhere)\b", location or "", re.IGNORECASE)
        )
        if (
            norm_wm not in ("onsite", "hybrid")
            and (not phys_without_remote_marker or (norm_wm == "remote" and explicit_role_global_exec))
            and not _GLOBAL_NEGATIVE_RE.search(cleaned_desc)
            and not residence_confirmed
            and not allowed_residence
            and not payroll_reqs
            and not global_remote_explicit
        ):
            for m_glob in _GLOBAL_REMOTE_RE.finditer(cleaned_desc):
                if any(sm.start() <= m_glob.start() < sm.end() for sm in scoped_matches):
                    continue
                if _is_perks_or_culture_context(cleaned_desc, m_glob.start()):
                    continue
                is_role_exec = explicit_role_global_exec and m_glob.group(0).lower().startswith("can be executed")
                if _is_product_marketing_context(cleaned_desc, m_glob.start()) and not is_role_exec:
                    continue
                tail = cleaned_desc[m_glob.end():m_glob.end() + 55]
                if re.match(
                    rf"\s*(?:(?:in|within|across)\s+(?:the\s+)?(?:{_GEO_TOKEN})\b|between\s+|on\s+(?:the\s+)?(?:east|west)\s+coast\b)",
                    tail,
                    re.IGNORECASE,
                ):
                    continue
                global_remote_explicit = True
                _add_fact(facts, "global_remote", "Worldwide", m_glob.group(0), method, "description")
                break

    # Treat non-country regional structured address values (e.g. "European Union") as regional residence
    # evidence on remote roles when no residence constraint was already captured, never as physical_country.
    if work_model == "remote" and not allowed_residence and not explicit_role_global_exec:
        reg_val, reg_snip, reg_field = _extract_structured_region(raw_fields)
        if reg_val and reg_snip:
            allowed_residence = _append_unique(allowed_residence, reg_val)
            residence_confirmed = True
            global_remote_explicit = None
            _add_fact(facts, "allowed_residence", reg_val, reg_snip, method, reg_field)

    # Also treat non-country regional location labels (e.g. "EMEA", "Africa", "Remote, AMER") on remote roles conservatively
    if work_model == "remote" and not allowed_residence and not explicit_role_global_exec and location:
        stripped_loc = re.sub(r"\b(?:remote|home[- ]?based)\b", "", location, flags=re.IGNORECASE).strip(" ,.;:-–/()")
        loc_reg = normalize_region_name(location) or normalize_region_name(stripped_loc)
        if loc_reg and loc_reg != "Worldwide":
            allowed_residence = _append_unique(allowed_residence, loc_reg)
            residence_confirmed = True
            global_remote_explicit = None
            _add_fact(facts, "allowed_residence", loc_reg, location, method, "location")

    # If a location string explicitly says "Worldwide" / "Global" / "Anywhere" with remote work and no restrictions, capture it
    if (
        work_model == "remote"
        and not allowed_residence
        and not residence_confirmed
        and not global_remote_explicit
        and not payroll_reqs
        and location
    ):
        first_loc_seg = re.split(r"[;|]", location)[0].strip()
        stripped_loc = re.sub(r"\b(?:remote|home[- ]?based)\b", "", location, flags=re.IGNORECASE).strip(" ,.;:-–/()")
        stripped_first = re.sub(r"\b(?:remote|home[- ]?based)\b", "", first_loc_seg, flags=re.IGNORECASE).strip(" ,.;:-–/()")
        if (
            normalize_region_name(location) == "Worldwide"
            or normalize_region_name(stripped_loc) == "Worldwide"
            or normalize_region_name(first_loc_seg) == "Worldwide"
            or normalize_region_name(stripped_first) == "Worldwide"
        ):
            global_remote_explicit = True
            _add_fact(facts, "global_remote", "Worldwide", location, method, "location")

    allowed_codes, allowed_regions = _split_countries_and_regions(allowed_residence)
    excluded_codes, excluded_regions = _split_countries_and_regions(excluded_residence)
    physical_country_code = normalize_country_code(physical_country) if physical_country else None

    classification = _determine_classification(
        global_remote_explicit=global_remote_explicit,
        allowed_codes=allowed_codes,
        allowed_regions=allowed_regions,
        work_model=work_model,
        physical_country=physical_country,
        work_auth=work_auth,
        citizenship=citizenship,
        clearance=clearance,
        visa_status=visa_status,
    )

    evidence_excerpt: str | None = None
    source_name: str | None = None
    if facts:
        primary_fact = next(
            (
                f for f in facts
                if f.dimension in (
                    "allowed_residence",
                    "excluded_residence",
                    "global_remote",
                    "payroll_requirement",
                    "hybrid_attendance",
                    "relocation_required",
                )
            ),
            facts[0],
        )
        evidence_excerpt = primary_fact.raw_snippet
        source_name = primary_fact.provider_field_name or primary_fact.method.value
    elif work_model in ("in_person", "onsite") and physical_country:
        source_name = physical_field or "location"

    has_any_signal = any([
        facts,
        physical_country,
        allowed_residence,
        excluded_residence,
        global_remote_explicit,
        citizenship,
        clearance,
        work_auth,
        visa_status,
        payroll_reqs,
        relocation_required is not None,
        relocation_assistance is not None,
        arrangement,
        timezone_req,
        hybrid_attendance_confirmed,
    ])
    if not has_any_signal and not (description and description.strip()):
        return None

    elig = JobEligibility(
        classification=classification,
        physical_location_country=physical_country,
        physical_location_country_code=physical_country_code,
        allowed_residence_countries=allowed_residence,
        allowed_country_codes=allowed_codes,
        excluded_residence_countries=excluded_residence,
        excluded_country_codes=excluded_codes,
        allowed_regions=allowed_regions,
        excluded_regions=excluded_regions,
        residence_restriction_confirmed=residence_confirmed,
        global_remote_explicit=global_remote_explicit,
        pan_regional_remote_confirmed=pan_regional_remote_confirmed,
        hybrid_attendance_confirmed=True if hybrid_attendance_confirmed else None,
        citizenship_requirements=citizenship,
        security_clearance_required=clearance,
        work_authorization_required=work_auth,
        visa_sponsorship_status=visa_status,
        payroll_requirements=payroll_reqs,
        relocation_required=relocation_required,
        relocation_assistance=relocation_assistance,
        employment_arrangement=arrangement,
        timezone_requirements=timezone_req,
        evidence_url=evidence_url,
        evidence_excerpt=evidence_excerpt,
        source=source_name,
        verified_at=verified_at,
        facts=facts,
    )
    elig.objective_scope_label = build_objective_scope_label(
        elig,
        work_model=work_model,
        location=location,
    )

    # Derive backward-compatible Nigeria evaluation via the shared global country evaluator
    ng_assessment = evaluate_eligibility_for_country(
        elig,
        "NG",
        work_model=work_model,
        location=location,
        provider=provider,
    )
    elig.nigeria_eligible = (
        True
        if ng_assessment.status == "eligible"
        else (False if ng_assessment.status == "restricted" else None)
    )
    elig.nigeria_eligibility_reason = ng_assessment.reason
    return elig

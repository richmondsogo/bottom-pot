from __future__ import annotations

import re
from typing import Any, Optional

from src.project_files.models import JobSalary

# Fixed ISO 4217 currency codes
ISO_4217_CURRENCIES: frozenset[str] = frozenset({
    "USD", "GBP", "EUR", "CAD", "AUD", "NGN", "CHF", "JPY", "INR", "NZD",
    "SGD", "ZAR", "KES", "GHS", "BRL", "SEK", "NOK", "DKK", "PLN", "MXN",
    "ILS", "HKD", "AED", "SAR", "KRW", "TRY", "RUB", "TWD", "THB", "IDR",
    "MYR", "PHP", "VND", "CZK", "HUF", "CLP", "COP", "PEN", "ARS", "EGP",
    "JOD", "KWD", "BHD", "OMR", "QAR",
})

# Pay period normalization mapping
_PERIOD_PATTERNS = {
    "year": re.compile(r"(?:/\s*(?:yr|year|a[ñn]o)\b|\b(?:year(?:ly)?|annuall?y?|annual|p\.a\.|per\s+year)\b)", re.IGNORECASE),
    "month": re.compile(r"(?:/\s*(?:mo|month)\b|\b(?:month(?:ly)?|per\s+month)\b)", re.IGNORECASE),
    "week": re.compile(r"(?:/\s*(?:wk|week)\b|\b(?:week(?:ly)?|per\s+week)\b)", re.IGNORECASE),
    "day": re.compile(r"(?:/\s*day\b|\b(?:day|daily|per\s+day)\b)", re.IGNORECASE),
    "hour": re.compile(r"(?:/\s*(?:hr|hour)\b|\b(?:hour(?:ly)?|per\s+hour)\b)", re.IGNORECASE),
}

# Negative guards: phrases that disqualify text from being base salary
_NEGATIVE_PATTERNS = [
    re.compile(r"\b401\(?k\)?\b", re.IGNORECASE),  # 401k retirement
    re.compile(r"\b(?:raised|series\s+[a-z]|funding|valuation)\b", re.IGNORECASE),  # Funding / raised
    re.compile(r"\b\d+[\d,]*\s*(?:employees|people|team\s+members|users|customers)\b", re.IGNORECASE),  # Headcount
    re.compile(r"\b(?:sign-?on|signing|retention|performance|discretionary|annual|target)?\s*bonus\b", re.IGNORECASE),  # Bonus
    re.compile(r"\b(?:equity|stock\s+options?|rsu|rsus|shares)\b", re.IGNORECASE),  # Equity
    re.compile(r"\b(?:quota|target\s+quota|ota|ote)\b", re.IGNORECASE),  # Target/quota
    re.compile(r"\b(?:competitive|market\s+rate|commensurate\s+with\s+experience|d\.?o\.?e\.?)\b", re.IGNORECASE),
    re.compile(r"\b(?:19\d\d|20\d\d)\s*[-–]\s*(?:19\d\d|20\d\d)\b"),  # Year ranges like 2024-2025
    re.compile(r"\b(?:in|since|prior\s+to|before|after)\s+(?:19\d\d|20\d\d)\b", re.IGNORECASE),  # Years
    re.compile(r"\b\d+[\d,]*\s*(?:\+|-|\s*to\s*)\s*\d+[\d,]*\s*years?(?:\s+of)?(?:\s+experience)?\b", re.IGNORECASE),  # Experience
    re.compile(r"\b\d+\s*years?(?:\s+of)?(?:\s+experience)?\b", re.IGNORECASE),
    re.compile(r"\b(?:negotiable|attractive|n/?a|not\s+disclosed|undisclosed|confidential)\b", re.IGNORECASE),
    re.compile(r"\bbudget\b", re.IGNORECASE),
    re.compile(
        r"\b(?:food\s+and\s+meal|meal|lunch|home\s+office|internet|commut(?:er|ing)|wellness|phone|relocation)\s+allowance\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bper\s+working\s+day\b", re.IGNORECASE),
    re.compile(r"\bbenefits?\s+card\b", re.IGNORECASE),
]

_OTHER_DOLLAR_SIGNALS = re.compile(
    r"\b(?:CAD|CA\$|AUD|AU\$|NZD|NZ\$|HKD|HK\$|SGD|SG\$|Canada|Canadian|Australia|Australian|Toronto|Vancouver|Montreal|Ottawa|Calgary|Sydney|Melbourne|Brisbane)\b",
    re.IGNORECASE,
)


def normalize_currency_code(code: str | None) -> str | None:
    """Validate and normalize an ISO currency code."""
    if not code:
        return None
    code_upper = code.strip().upper()
    return code_upper if code_upper in ISO_4217_CURRENCIES else None


def normalize_period(period_raw: str | None) -> str | None:
    """Normalize a pay period to hour, day, week, month, or year. Never default."""
    if not period_raw:
        return None
    period_str = str(period_raw).strip().lower()
    for norm, pattern in _PERIOD_PATTERNS.items():
        if pattern.search(period_str):
            return norm
    return None


def _resolve_currency(
    symbol_or_code: str | None,
    context_text: str = "",
    location_hint: str | None = None,
    bare_n_is_ngn: bool = False,
) -> str | None:
    """Resolve currency string or symbol against ISO 4217 with dollar disambiguation and Nigerian adapter hint."""
    if not symbol_or_code:
        return None
    
    clean = symbol_or_code.strip()
    clean_upper = clean.upper()
    
    # Universal NGN mappings: ₦, NGN, Naira
    if clean_upper in ("NGN", "NAIRA") or clean == "₦":
        return "NGN"
    
    # Bare N maps to NGN only with explicit adapter hint
    if clean_upper == "N":
        if bare_n_is_ngn:
            return "NGN"
        return None

    # Check if explicit ISO code
    if clean_upper in ISO_4217_CURRENCIES:
        return clean_upper
    
    if clean_upper in ("CA$", "CAD"):
        return "CAD"
    if clean_upper in ("AU$", "AUD"):
        return "AUD"
    if clean_upper in ("NZ$", "NZD"):
        return "NZD"

    if clean_upper in ("R$", "BRL"):
        return "BRL"
    if clean == "£":
        return "GBP"
    if clean == "€":
        return "EUR"
    if clean == "₹":
        return "INR"
    if clean in ("¥", "円"):
        return None  # Rule: ¥ stays None
    
    if clean == "$":
        # Disambiguate dollar: $ maps to USD only if no CAD/AUD/other dollar signal is present, otherwise None
        combined_context = f"{context_text} {location_hint or ''}"
        if _OTHER_DOLLAR_SIGNALS.search(combined_context):
            return None
        return "USD"
    
    return None


def _parse_numeric(val: Any, allow_m: bool = False) -> Optional[int]:
    """Parse integer value handling 'k'/'K' and conditional 'm'/'M' suffixes, commas, and floats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(round(val))
    
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s:
        return None

    # Normalize European thousands-dot separator (e.g. "45.000", "1.250.000"), preserving decimals like "52.50" or "1.5m"
    suffix = s[-1] if s[-1].lower() in ("k", "m") else ""
    num_body = s[:-1] if suffix else s
    if re.match(r"^\d{1,3}(?:\.\d{3})+$", num_body):
        s = num_body.replace(".", "") + suffix
    
    # Check for 'k' / 'K' suffix
    if s.lower().endswith("k"):
        try:
            num = float(s[:-1])
            return int(round(num * 1000))
        except ValueError:
            return None

    # Check for 'm' / 'M' suffix (only allowed when explicitly permitted)
    if s.lower().endswith("m"):
        if not allow_m:
            return None
        try:
            num = float(s[:-1])
            return int(round(num * 1_000_000))
        except ValueError:
            return None
    
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def _select_range_currency(
    candidates: list[str | None],
    context_text: str,
    location_hint: str | None,
    bare_n_is_ngn: bool,
) -> tuple[str | None, bool]:
    """
    Resolve the most specific unambiguous currency from prefix/mid/suffix tokens.

    Prefers explicit ISO codes / qualified dollar symbols (e.g. CAD, USD, CA$)
    over a bare ambiguous '$' symbol. Returns (currency, has_conflict).
    """
    non_empty = [c.strip() for c in candidates if c and c.strip()]
    explicit_non_bare = [c for c in non_empty if c != "$"]
    resolved_explicit: list[str] = []
    for raw_tok in explicit_non_bare:
        res = _resolve_currency(
            raw_tok,
            context_text=context_text,
            location_hint=location_hint,
            bare_n_is_ngn=bare_n_is_ngn,
        )
        if res and res not in resolved_explicit:
            resolved_explicit.append(res)

    if len(resolved_explicit) > 1:
        return None, True
    if len(resolved_explicit) == 1:
        return resolved_explicit[0], False

    if non_empty:
        return (
            _resolve_currency(
                non_empty[0],
                context_text=context_text,
                location_hint=location_hint,
                bare_n_is_ngn=bare_n_is_ngn,
            ),
            False,
        )
    return None, False


def _create_jobsalary(
    minimum: Optional[int],
    maximum: Optional[int],
    currency: Optional[str] = None,
    period: Optional[str] = None,
    raw_text: Optional[str] = None,
    source: Optional[str] = None,
) -> Optional[JobSalary]:
    """Safely construct a JobSalary, validating non-negativity and min <= max."""
    if minimum is None and maximum is None:
        return None
    if minimum is not None and minimum < 0:
        return None
    if maximum is not None and maximum < 0:
        return None
    if minimum is not None and maximum is not None and minimum > maximum:
        return None

    try:
        return JobSalary(
            minimum=minimum,
            maximum=maximum,
            currency=currency,
            period=period,
            raw_text=raw_text,
            source=source,
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# Structured Compensation Extraction (Tier 1 & Tier 2)
# ──────────────────────────────────────────────────────────────────────────


class _DisputedSalary:
    """Sentinel indicating structured compensation is explicitly ambiguous or multi-tier disagreeing."""
    pass


_SALARY_DISPUTED = _DisputedSalary()


def _parse_structured_salary_internal(
    data: dict[str, Any],
    provider: str = "",
    location_hint: str | None = None,
) -> Optional[JobSalary] | _DisputedSalary:
    """Internal extractor returning JobSalary, None, or _SALARY_DISPUTED sentinel."""
    if not isinstance(data, dict):
        return None

    prov = provider.lower() if provider else ""

    # 1. SmartRecruiters: data["compensation"]
    # { "min": 135000, "max": 175000, "currency": "GBP", "period": "YEARLY" }
    comp = data.get("compensation")
    if isinstance(comp, dict) and not comp.get("compensationTiers"):
        min_val = _parse_numeric(comp.get("min") or comp.get("minimum"))
        max_val = _parse_numeric(comp.get("max") or comp.get("maximum"))
        curr = normalize_currency_code(comp.get("currency")) or _resolve_currency(comp.get("currency"), location_hint=location_hint)
        period = normalize_period(comp.get("period"))
        if min_val is not None or max_val is not None:
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(comp),
                source=f"{prov or 'smartrecruiters'}_structured",
            )

    # 2. Recruitee: data["salary"]
    # { "min": "40", "max": "48", "period": "hour", "currency": "USD" }
    sal = data.get("salary")
    if isinstance(sal, dict):
        min_val = _parse_numeric(sal.get("min") or sal.get("minimum"))
        max_val = _parse_numeric(sal.get("max") or sal.get("maximum"))
        curr = normalize_currency_code(sal.get("currency")) or _resolve_currency(sal.get("currency"), location_hint=location_hint)
        period = normalize_period(sal.get("period"))
        if min_val is not None or max_val is not None:
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(sal),
                source=f"{prov or 'recruitee'}_structured",
            )

    # 3. Lever: data["salaryRange"], falling back to salaryDescriptionPlain / salaryDescription
    # { "min": 80000, "max": 100000, "currency": "USD", "interval": "per year-indexed" }
    sal_range = data.get("salaryRange")
    if isinstance(sal_range, dict):
        min_val = _parse_numeric(sal_range.get("min") or sal_range.get("minimum"))
        max_val = _parse_numeric(sal_range.get("max") or sal_range.get("maximum"))
        curr = normalize_currency_code(sal_range.get("currency")) or _resolve_currency(sal_range.get("currency"), location_hint=location_hint)
        period = normalize_period(sal_range.get("interval") or sal_range.get("period"))
        if (min_val is not None and min_val > 0) or (max_val is not None and max_val > 0):
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(sal_range),
                source=f"{prov or 'lever'}_structured",
            )

    if prov == "lever":
        sal_desc = data.get("salaryDescriptionPlain") or data.get("salaryDescription")
        if isinstance(sal_desc, str) and sal_desc.strip():
            clean_sal_desc = re.sub(r"<[^>]+>", " ", sal_desc) if "<" in sal_desc else sal_desc
            parsed_sal_desc = parse_text_salary(
                clean_sal_desc,
                location_hint=location_hint,
                source="lever_salary_description",
            )
            if parsed_sal_desc is not None:
                return parsed_sal_desc

    # 3b. Workable: data["salary_from"] / data["salary_to"] / data["salary_currency_iso_code"] / data["salary_frequency"]
    if any(k in data for k in ("salary_from", "salary_to", "salary_currency_iso_code")):
        min_val = _parse_numeric(data.get("salary_from"))
        max_val = _parse_numeric(data.get("salary_to"))
        if min_val is not None and min_val <= 0:
            min_val = None
        if max_val is not None and max_val <= 0:
            max_val = None
        if min_val is not None or max_val is not None:
            raw_curr = data.get("salary_currency_iso_code")
            curr = normalize_currency_code(raw_curr) or _resolve_currency(raw_curr, location_hint=location_hint)
            period = normalize_period(data.get("salary_frequency"))
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(
                    {
                        k: data.get(k)
                        for k in ("salary_from", "salary_to", "salary_currency_iso_code", "salary_frequency")
                        if data.get(k) is not None
                    }
                ),
                source=f"{prov or 'workable'}_structured",
            )

    # 4. Greenhouse: data["pay_input_ranges"]
    # [ { "min_cents": 16420000, "max_cents": 22999000, "currency_type": "USD", "title": "Base Salary" } ]
    pay_ranges = data.get("pay_input_ranges")
    if isinstance(pay_ranges, list) and pay_ranges:
        valid_ranges = []
        for r in pay_ranges:
            if not isinstance(r, dict):
                continue
            title = (r.get("title") or "").strip()
            # Exclude non-base ranges by title only (e.g. bonus, commission, equity, ote, quota, incentive)
            if re.search(r"\b(bonus|commission|equity|ote|quota|incentive)\b", title, re.IGNORECASE):
                continue
            min_cents = r.get("min_cents")
            max_cents = r.get("max_cents")
            if min_cents is not None or max_cents is not None:
                min_val = int(round(min_cents / 100)) if min_cents is not None else None
                max_val = int(round(max_cents / 100)) if max_cents is not None else None
            else:
                min_val = _parse_numeric(r.get("min") or r.get("minimum"))
                max_val = _parse_numeric(r.get("max") or r.get("maximum"))
            if (min_val is not None and min_val <= 0) and (max_val is not None and max_val <= 0):
                continue
            raw_curr = r.get("currency_type") or r.get("currency")
            curr = normalize_currency_code(raw_curr) or _resolve_currency(raw_curr, location_hint=location_hint)
            # Period: from payload/title first; if None, check blurb only if blurb states exactly one unambiguous period
            period = normalize_period(r.get("period") or r.get("interval") or title)
            if not period:
                blurb = r.get("blurb") or ""
                clean_blurb = re.sub(r"<[^>]+>", " ", blurb)
                matches = set()
                for p_match in re.finditer(
                    r"\b(per\s+(?:year|annual|annum|month|hr|hour|week)|annually|hourly|monthly|weekly|/yr|/year|/hr|/hour|/mo|/month)\b",
                    clean_blurb,
                    re.IGNORECASE,
                ):
                    norm = normalize_period(p_match.group(0))
                    if norm:
                        matches.add(norm)
                if len(matches) == 1:
                    period = matches.pop()
            if min_val is not None or max_val is not None:
                valid_ranges.append((min_val, max_val, curr, period, r))

        if not valid_ranges:
            return None

        first_tuple = valid_ranges[0][:4]
        if all(vr[:4] == first_tuple for vr in valid_ranges):
            min_val, max_val, curr, period, _ = valid_ranges[0]
            # Clean raw_text: remove HTML tags from blurbs in pay_ranges representation
            cleaned_ranges = []
            for r in pay_ranges:
                if isinstance(r, dict):
                    clean_r = dict(r)
                    if "blurb" in clean_r and isinstance(clean_r["blurb"], str):
                        clean_r["blurb"] = re.sub(r"<[^>]+>", " ", clean_r["blurb"]).strip()
                    cleaned_ranges.append(clean_r)
                else:
                    cleaned_ranges.append(r)
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(cleaned_ranges),
                source="greenhouse_structured",
            )
        else:
            return _SALARY_DISPUTED

    # 5. Ashby: data["compensation"] or data["compensationTierSummary"]
    ashby_comp = data.get("compensation")
    if isinstance(ashby_comp, dict):
        tiers = ashby_comp.get("compensationTiers")
        if isinstance(tiers, list) and tiers:
            salary_components = []
            for t in tiers:
                if not isinstance(t, dict):
                    continue
                for c in t.get("components", []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("compensationType") == "Salary":
                        min_v = _parse_numeric(c.get("minValue") or c.get("min"))
                        max_v = _parse_numeric(c.get("maxValue") or c.get("max"))
                        if (min_v is not None and min_v <= 0) and (max_v is not None and max_v <= 0):
                            continue
                        if min_v is not None or max_v is not None:
                            curr = normalize_currency_code(c.get("currencyCode") or c.get("currency")) or _resolve_currency(c.get("currencyCode") or c.get("currency"), location_hint=location_hint)
                            interval = normalize_period(c.get("interval"))
                            salary_components.append((min_v, max_v, curr, interval, c))
            if salary_components:
                first_tuple = salary_components[0][:4]
                if all(sc[:4] == first_tuple for sc in salary_components):
                    min_v, max_v, curr, interval, _ = salary_components[0]
                    return _create_jobsalary(
                        minimum=min_v,
                        maximum=max_v,
                        currency=curr,
                        period=interval,
                        raw_text=str(ashby_comp),
                        source="ashby_structured",
                    )
                else:
                    return _SALARY_DISPUTED

        target = ashby_comp.get("targetSalary") or ashby_comp.get("targetSalaryRange")
        if isinstance(target, dict):
            min_val = _parse_numeric(target.get("min") or target.get("minimum") or target.get("minValue"))
            max_val = _parse_numeric(target.get("max") or target.get("maximum") or target.get("maxValue"))
            curr = normalize_currency_code(target.get("currency") or target.get("currencyCode")) or _resolve_currency(target.get("currency"), location_hint=location_hint)
            period = normalize_period(target.get("period") or target.get("interval"))
            if min_val is not None or max_val is not None:
                return _create_jobsalary(
                    minimum=min_val,
                    maximum=max_val,
                    currency=curr,
                    period=period,
                    raw_text=str(ashby_comp),
                    source="ashby_structured",
                )

        comp_tier = ashby_comp.get("compensationTierSummary")
        if isinstance(comp_tier, str):
            if "multiple ranges" in comp_tier.lower():
                return _SALARY_DISPUTED
            res = parse_text_salary(comp_tier, location_hint=location_hint, source="ashby_structured")
            if res:
                return res

    elif isinstance(data.get("compensationTierSummary"), str):
        comp_tier = data["compensationTierSummary"]
        if "multiple ranges" in comp_tier.lower():
            return _SALARY_DISPUTED
        res = parse_text_salary(comp_tier, location_hint=location_hint, source="ashby_structured")
        if res:
            return res

    # 6. JSON-LD schema.org baseSalary
    base_sal = data.get("baseSalary")
    if not base_sal and isinstance(data.get("json_ld"), dict):
        base_sal = data["json_ld"].get("baseSalary")
    if isinstance(base_sal, dict):
        val_obj = base_sal.get("value") if isinstance(base_sal.get("value"), dict) else base_sal
        min_val = _parse_numeric(val_obj.get("minValue") or val_obj.get("value"))
        max_val = _parse_numeric(val_obj.get("maxValue") or val_obj.get("value"))
        # Reject placeholder or zero values (ADR 0001)
        if (min_val is not None and min_val <= 0) and (max_val is not None and max_val <= 0):
            return None
        # Currency from the structured field only (no fallback to location)
        raw_curr = base_sal.get("currency") or val_obj.get("currency")
        curr = normalize_currency_code(raw_curr) if raw_curr else None
        period = normalize_period(val_obj.get("unitText"))
        if (min_val is not None and min_val > 0) or (max_val is not None and max_val > 0):
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(base_sal),
                source="json_ld",
            )

    return None


def parse_structured_salary(
    data: dict[str, Any],
    provider: str = "",
    location_hint: str | None = None,
) -> Optional[JobSalary]:
    """Extract salary from ATS-specific structured payload fields."""
    res = _parse_structured_salary_internal(data, provider=provider, location_hint=location_hint)
    if isinstance(res, _DisputedSalary):
        return None
    return res


# ──────────────────────────────────────────────────────────────────────────
# Deterministic Text Salary Extraction (Tier 3)
# ──────────────────────────────────────────────────────────────────────────

# Core salary patterns
_CURR_SYMBOLS = (
    r"CA\$|AU\$|NZ\$|HK\$|SG\$|R\$|"
    r"USD|GBP|EUR|CAD|AUD|BRL|NGN|Naira|INR|JOD|CHF|JPY|NZD|HKD|SGD|ZAR|KES|GHS|SEK|NOK|DKK|PLN|MXN|ILS|AED|SAR|"
    r"[£€$₦₹]|N(?=\s*\d)"
)

_RANGE_REGEX = re.compile(
    rf"""
    (?P<curr_prefix>{_CURR_SYMBOLS})?\s*
    (?P<min>\d[\d,]*(?:\.\d+)*(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?P<curr_min_suffix>{_CURR_SYMBOLS})?\s*
    (?:\b(?:to|and)\b|[-–—]|\.\.\.)\s*
    (?P<curr_mid>{_CURR_SYMBOLS})?\s*
    (?P<max>\d[\d,]*(?:\.\d+)*(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?P<curr_suffix>{_CURR_SYMBOLS})?\s*
    (?P<period_str>per\s+(?:year|month|week|day|hour)|annually|yearly|annual|monthly|hourly|daily|weekly|/\s*(?:yr|year|a[ñn]o|month|mo|wk|week|day|hr|hour))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_SINGLE_REGEX = re.compile(
    rf"""
    (?P<curr_prefix>{_CURR_SYMBOLS})?\s*
    (?P<val>\d[\d,]*(?:\.\d+)*(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?P<curr_suffix>{_CURR_SYMBOLS})?\s*
    (?P<period_str>per\s+(?:year|month|week|day|hour)|annually|yearly|annual|monthly|hourly|daily|weekly|/\s*(?:yr|year|a[ñn]o|month|mo|wk|week|day|hr|hour))?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_text_salary(
    text: str,
    location_hint: str | None = None,
    source: str = "text",
    bare_n_is_ngn: bool = False,
) -> Optional[JobSalary]:
    """Parse salary from text expression. Strictly validates bounds, currencies, and periods."""
    if not text or not text.strip():
        return None

    raw_stripped = text.strip()

    # Rule: Check negative guards first
    for neg_pat in _NEGATIVE_PATTERNS:
        if neg_pat.search(raw_stripped):
            return None

    is_labelled = bool(
        re.search(r"\b(?:salary|compensation|pay|remuneration|wage|stipend)\b", raw_stripped, re.IGNORECASE)
        or any(s in source.lower() for s in ("salary", "compensation", "pay", "remuneration", "structured", "label"))
    )

    # Find all potential range matches
    range_matches: list[tuple[int, int, Optional[str], Optional[str], str]] = []
    
    for match in _RANGE_REGEX.finditer(raw_stripped):
        m_dict = match.groupdict()
        min_str = m_dict.get("min")
        max_str = m_dict.get("max")
        if not min_str or not max_str:
            continue

        # Suffix 'm' is only allowed directly after currency symbol in labelled context
        allow_min_m = is_labelled and bool(m_dict.get("curr_prefix"))
        allow_max_m = is_labelled and bool(m_dict.get("curr_prefix") or m_dict.get("curr_mid"))

        min_val = _parse_numeric(min_str, allow_m=allow_min_m)
        max_val = _parse_numeric(max_str, allow_m=allow_max_m)
        if min_val is None or max_val is None:
            continue

        # If min was written without 'k'/'m' but max has it (e.g. "80 - 100k" or "1.5 - 2.5m"), scale min up
        if max_str.lower().endswith("k") and not min_str.lower().endswith("k") and min_val < 1000:
            min_val *= 1000
        elif max_str.lower().endswith("m") and not min_str.lower().endswith("m") and min_val < 1000:
            min_val *= 1_000_000

        # Validate basic reasonableness: min <= max and non-negative
        if min_val < 0 or max_val < 0 or min_val > max_val:
            return None

        # Determine currency: explicit ISO/qualified codes take priority over bare '$'
        curr, curr_conflict = _select_range_currency(
            [
                m_dict.get("curr_prefix"),
                m_dict.get("curr_min_suffix"),
                m_dict.get("curr_mid"),
                m_dict.get("curr_suffix"),
            ],
            context_text=raw_stripped,
            location_hint=location_hint,
            bare_n_is_ngn=bare_n_is_ngn,
        )
        if curr_conflict:
            return None

        # Determine period
        period = normalize_period(m_dict.get("period_str"))
        range_matches.append((min_val, max_val, curr, period, match.group(0).strip()))

    # Rule: Multiple differing ranges produce no normalized salary, preserving raw text
    if len(range_matches) > 1:
        first_min, first_max, first_curr = range_matches[0][0], range_matches[0][1], range_matches[0][2]
        for rm in range_matches[1:]:
            if rm[0] != first_min or rm[1] != first_max or (
                first_curr and rm[2] and rm[2] != first_curr
            ):
                # Ambiguous/conflicting: return None
                return None

    if range_matches:
        min_v, max_v, c, p, raw_sub = range_matches[0]
        if not c:
            for rm in range_matches[1:]:
                if rm[2]:
                    c = rm[2]
                    break
        return _create_jobsalary(
            minimum=min_v,
            maximum=max_v,
            currency=c,
            period=p,
            raw_text=raw_stripped,
            source=source,
        )

    # If no range found, try single value (guarding against blank lower-bound range prefixes like "$ USD - $154,500")
    single_matches: list[tuple[int, int, Optional[str], Optional[str], str]] = []
    for match in _SINGLE_REGEX.finditer(raw_stripped):
        prefix_before = raw_stripped[:match.start()]
        if re.search(
            rf"(?:{_CURR_SYMBOLS})(?:\s+(?:{_CURR_SYMBOLS}))?\s*(?:[-–—]|to|\.\.\.)\s*$",
            prefix_before,
            re.IGNORECASE,
        ):
            return None

        m_dict = match.groupdict()
        val_str = m_dict.get("val")
        curr_raw = m_dict.get("curr_prefix") or m_dict.get("curr_suffix")
        period_str = m_dict.get("period_str")
        period = normalize_period(period_str)
        curr, curr_conflict = _select_range_currency(
            [m_dict.get("curr_prefix"), m_dict.get("curr_suffix")],
            context_text=raw_stripped,
            location_hint=location_hint,
            bare_n_is_ngn=bare_n_is_ngn,
        )
        if curr_conflict:
            return None

        # Single values require at least a resolved currency or a resolved period
        if curr is None and period is None:
            continue

        allow_val_m = is_labelled and bool(m_dict.get("curr_prefix"))
        val = _parse_numeric(val_str, allow_m=allow_val_m)
        if val is None or val <= 0:
            continue

        single_matches.append((val, val, curr, period, match.group(0).strip(), prefix_before))

    if len(single_matches) == 1:
        val, _, c, p, raw_sub, prefix_before = single_matches[0]
        is_upper_only = bool(
            re.search(
                r"\b(?:up\s+to|maximum(?:\s+of)?|max(?:\s+of)?|capped\s+at)\s*[*_]*$",
                prefix_before,
                re.IGNORECASE,
            )
        )
        return _create_jobsalary(
            minimum=None if is_upper_only else val,
            maximum=val,
            currency=c,
            period=p,
            raw_text=raw_stripped,
            source=source,
        )

    # Support explicit two-tier scalar rates on labelled Pay/Salary lines (e.g. "$22.75/hour undergrad; $25/hour grad")
    if len(single_matches) == 2 and is_labelled and ";" in raw_stripped:
        v1, _, c1, p1, _, _ = single_matches[0]
        v2, _, c2, p2, _, _ = single_matches[1]
        if c1 and c1 == c2 and p1 and p1 == p2 and 0 < v1 <= v2 and v2 <= v1 * 3:
            return _create_jobsalary(
                minimum=v1,
                maximum=v2,
                currency=c1,
                period=p1,
                raw_text=raw_stripped,
                source=source,
            )

    return None


# ──────────────────────────────────────────────────────────────────────────
# Main Extraction Facade
# ──────────────────────────────────────────────────────────────────────────


def extract_salary(
    provider: str,
    raw_fields: dict[str, Any],
    description: str | None = None,
    location_hint: str | None = None,
    bare_n_is_ngn: bool = False,
) -> Optional[JobSalary]:
    """Unified progressive salary extractor:
    1. Structured ATS provider fields
    2. JSON-LD schema baseSalary
    3. Clearly labelled text in description/fields
    """
    # 1. Try structured ATS fields
    struct_sal = _parse_structured_salary_internal(raw_fields, provider=provider, location_hint=location_hint)
    if isinstance(struct_sal, _DisputedSalary):
        return None
    if struct_sal:
        return struct_sal

    # 2. Try labelled fields like "salary" or "compensation" in raw_fields
    for k in ("salary", "compensation", "pay", "remuneration"):
        val = raw_fields.get(k)
        if isinstance(val, str) and val.strip():
            text_sal = parse_text_salary(val, location_hint=location_hint, source=f"{provider}_{k}", bare_n_is_ngn=bare_n_is_ngn)
            if text_sal:
                return text_sal

    # 3. Look for explicit salary labels in description (e.g. "Salary: $80,000 - $100,000" or "Gross salary. 1160 EUR/month")
    if description:
        clean_desc = re.sub(r"\[([^\]]*)\]\([^)\s]*\)", r"\1", description)
        label_regex = re.compile(
            rf"(?:^|\b)(?:(?:the\s+)?(?:annual\s+base\s+pay|base\s+pay|pay)\s+for\s+this\s+(?:position|role|job)|annual\s+(?:base\s+)?salary|starting\s+base\s+salary|base\s+salary(?:\s+range)?|salary(?:\s+compensation)?|compensation|pay\s*range|base\s*pay|pay(?=[*_\s]*:))[*_]*(?:\.(?=[*_]*\s)\s*|\s*(?:(?:[^\n\r:.]*?(?::|\bis\b))|(?:[^\n\r:.]{{0,80}}?(?=[*_]*\s*(?:{_CURR_SYMBOLS})))))\s*[*_\s]*(?P<cand>(?:[^\n\r<.]|\.(?=\d))+)",
            re.IGNORECASE,
        )
        candidates: list[tuple[str, str | None]] = []
        parsed_salaries: list[JobSalary] = []

        for label_match in label_regex.finditer(clean_desc):
            cand_text = re.sub(r"\[[^\]]*\]\([^\s)]*$", "", label_match.group("cand")).strip(" \t*_")
            if not cand_text:
                continue
            line_start = clean_desc.rfind("\n", 0, label_match.start()) + 1
            label_context = clean_desc[line_start:label_match.start("cand")]
            if m_upper := re.search(
                r"\b(up\s+to|maximum(?:\s+of)?|max(?:\s+of)?|capped\s+at)\s*[*_]*$",
                label_context,
                re.IGNORECASE,
            ):
                cand_text = f"{m_upper.group(1)} {cand_text}"
            hinted_period = normalize_period(label_context)
            candidates.append((cand_text, hinted_period))

            # Inspect immediate continuation lines within the same non-empty paragraph
            # (e.g. "Base Pay Range for:\nVA applicants is ...\nCO applicants is ...")
            tail = clean_desc[label_match.end():]
            next_newline = tail.find("\n")
            if next_newline != -1:
                after_line = tail[next_newline + 1:]
                for cont_line in after_line.splitlines():
                    stripped_cont = cont_line.strip()
                    if not stripped_cont or stripped_cont.startswith("#"):
                        break
                    if label_regex.match(stripped_cont):
                        break
                    if re.search(r"\b(?:bonus|equity|401k|sign[-\s]?on)\b", stripped_cont, re.IGNORECASE) and not re.search(
                        r"\b(?:base|salary|pay)\b", stripped_cont, re.IGNORECASE
                    ):
                        break
                    if _RANGE_REGEX.search(stripped_cont):
                        candidates.append((stripped_cont, hinted_period))

        saw_conflicting_candidate = False
        for cand_text, hinted_period in candidates:
            range_hits = list(_RANGE_REGEX.finditer(cand_text))
            text_sal = parse_text_salary(
                cand_text,
                location_hint=location_hint,
                source=f"{provider}_description_label",
                bare_n_is_ngn=bare_n_is_ngn,
            )
            if text_sal is None and len(range_hits) > 1:
                saw_conflicting_candidate = True
                break
            if text_sal is not None:
                if text_sal.period is None and hinted_period:
                    text_sal = text_sal.model_copy(update={"period": hinted_period})
                parsed_salaries.append(text_sal)

        if not saw_conflicting_candidate and parsed_salaries:
            first = parsed_salaries[0]
            for other in parsed_salaries[1:]:
                if (
                    other.minimum != first.minimum
                    or other.maximum != first.maximum
                    or other.currency != first.currency
                ):
                    return None
            return first

        # 4. Standalone explicit bullet/rate lines when no label matched (e.g. "- $30/hr")
        if not candidates:
            standalone_rate_re = re.compile(
                rf"^(?:[-*•]\s+)?(?P<rate>(?:{_CURR_SYMBOLS})\s*\d[\d,]*(?:\.\d+)?(?:\s*[kKmM](?![a-zA-Z]))?(?:\s*(?:-|–|—|\bto\b)\s*(?:{_CURR_SYMBOLS})?\s*\d[\d,]*(?:\.\d+)?(?:\s*[kKmM](?![a-zA-Z]))?)?\s*(?:/\s*(?:hr|hour|yr|year|mo|month|wk|week|day)|per\s+(?:hour|year|month|week|day))(?:\s*\([^)]*\))?)$",
                re.IGNORECASE,
            )
            standalone_hits: list[JobSalary] = []
            for raw_line in clean_desc.splitlines():
                line_s = raw_line.strip()
                m_rate = standalone_rate_re.match(line_s)
                if not m_rate:
                    continue
                rate_sal = parse_text_salary(
                    m_rate.group("rate"),
                    location_hint=location_hint,
                    source=f"{provider}_description_rate_line",
                    bare_n_is_ngn=bare_n_is_ngn,
                )
                if rate_sal is not None and rate_sal.currency and rate_sal.period:
                    standalone_hits.append(rate_sal)
            if len(standalone_hits) == 1:
                return standalone_hits[0]
            if len(standalone_hits) > 1:
                first_hit = standalone_hits[0]
                if all(
                    h.minimum == first_hit.minimum and h.maximum == first_hit.maximum and h.currency == first_hit.currency
                    for h in standalone_hits[1:]
                ):
                    return first_hit

        return None

    return None

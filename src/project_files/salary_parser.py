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
})

# Pay period normalization mapping
_PERIOD_PATTERNS = {
    "year": re.compile(r"\b(?:year(?:ly)?|annuall?y?|annual|p\.a\.|per\s+year|/\s*yr|/\s*year)\b", re.IGNORECASE),
    "month": re.compile(r"\b(?:month(?:ly)?|per\s+month|/\s*mo|/\s*month)\b", re.IGNORECASE),
    "week": re.compile(r"\b(?:week(?:ly)?|per\s+week|/\s*wk|/\s*week)\b", re.IGNORECASE),
    "day": re.compile(r"\b(?:day|daily|per\s+day|/\s*day)\b", re.IGNORECASE),
    "hour": re.compile(r"\b(?:hour(?:ly)?|per\s+hour|/\s*hr|/\s*hour)\b", re.IGNORECASE),
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

    if clean == "£":
        return "GBP"
    if clean == "€":
        return "EUR"
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


def parse_structured_salary(
    data: dict[str, Any],
    provider: str,
    location_hint: str | None = None,
) -> Optional[JobSalary]:
    """Extract salary from ATS-specific structured payload fields."""
    if not isinstance(data, dict):
        return None

    prov = provider.lower()

    # 1. SmartRecruiters: data["compensation"]
    # { "min": 135000, "max": 175000, "currency": "GBP", "period": "YEARLY" }
    comp = data.get("compensation")
    if isinstance(comp, dict):
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
                source=f"{prov}_structured",
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
                source=f"{prov}_structured",
            )

    # 3. Lever: data["salaryRange"]
    # { "min": 80000, "max": 100000, "currency": "USD", "interval": "per year-indexed" }
    sal_range = data.get("salaryRange")
    if isinstance(sal_range, dict):
        min_val = _parse_numeric(sal_range.get("min") or sal_range.get("minimum"))
        max_val = _parse_numeric(sal_range.get("max") or sal_range.get("maximum"))
        curr = normalize_currency_code(sal_range.get("currency")) or _resolve_currency(sal_range.get("currency"), location_hint=location_hint)
        period = normalize_period(sal_range.get("interval") or sal_range.get("period"))
        if min_val is not None or max_val is not None:
            return _create_jobsalary(
                minimum=min_val,
                maximum=max_val,
                currency=curr,
                period=period,
                raw_text=str(sal_range),
                source=f"{prov}_structured",
            )

    # 4. Greenhouse: data["pay_input_ranges"] or metadata
    # [ { "min_cents": 10000000, "max_cents": 14000000, "currency": "USD" } ]
    pay_ranges = data.get("pay_input_ranges")
    if isinstance(pay_ranges, list) and pay_ranges:
        first = pay_ranges[0]
        if isinstance(first, dict):
            # Check unit: cents vs standard
            min_cents = first.get("min_cents")
            max_cents = first.get("max_cents")
            if min_cents is not None or max_cents is not None:
                min_val = int(round(min_cents / 100)) if min_cents is not None else None
                max_val = int(round(max_cents / 100)) if max_cents is not None else None
            else:
                min_val = _parse_numeric(first.get("min") or first.get("minimum"))
                max_val = _parse_numeric(first.get("max") or first.get("maximum"))
            curr = normalize_currency_code(first.get("currency")) or _resolve_currency(first.get("currency"), location_hint=location_hint)
            period = normalize_period(first.get("period") or first.get("interval"))
            if min_val is not None or max_val is not None:
                return _create_jobsalary(
                    minimum=min_val,
                    maximum=max_val,
                    currency=curr,
                    period=period,
                    raw_text=str(pay_ranges),
                    source="greenhouse_structured",
                )

    # 5. Ashby: data["compensation"] or data["compensationTierSummary"]
    ashby_comp = data.get("compensation")
    if isinstance(ashby_comp, dict):
        comp_tier = ashby_comp.get("compensationTierSummary")
        if isinstance(comp_tier, str):
            res = parse_text_salary(comp_tier, location_hint=location_hint, source="ashby_structured")
            if res:
                return res
        target = ashby_comp.get("targetSalary") or ashby_comp.get("targetSalaryRange")
        if isinstance(target, dict):
            min_val = _parse_numeric(target.get("min") or target.get("minimum"))
            max_val = _parse_numeric(target.get("max") or target.get("maximum"))
            curr = normalize_currency_code(target.get("currency")) or _resolve_currency(target.get("currency"), location_hint=location_hint)
            period = normalize_period(target.get("period"))
            if min_val is not None or max_val is not None:
                return _create_jobsalary(
                    minimum=min_val,
                    maximum=max_val,
                    currency=curr,
                    period=period,
                    raw_text=str(ashby_comp),
                    source="ashby_structured",
                )
    elif isinstance(data.get("compensationTierSummary"), str):
        res = parse_text_salary(data["compensationTierSummary"], location_hint=location_hint, source="ashby_structured")
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


# ──────────────────────────────────────────────────────────────────────────
# Deterministic Text Salary Extraction (Tier 3)
# ──────────────────────────────────────────────────────────────────────────

# Core salary patterns
_CURR_SYMBOLS = r"CA\$|AU\$|NZ\$|HK\$|SG\$|USD|GBP|EUR|CAD|AUD|NGN|Naira|[£€$₦]|N(?=\s*\d)"

_RANGE_REGEX = re.compile(
    rf"""
    (?P<curr_prefix>{_CURR_SYMBOLS})?\s*
    (?P<min>\d[\d,]*(?:\.\d+)?(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?:[-–—]|to|\.\.\.)\s*
    (?P<curr_mid>{_CURR_SYMBOLS})?\s*
    (?P<max>\d[\d,]*(?:\.\d+)?(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?P<curr_suffix>{_CURR_SYMBOLS})?\s*
    (?P<period_str>per\s+(?:year|month|week|day|hour)|annually|yearly|annual|monthly|hourly|daily|weekly|/\s*(?:yr|year|mo|month|wk|week|day|hr|hour))?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_SINGLE_REGEX = re.compile(
    rf"""
    (?P<curr_prefix>{_CURR_SYMBOLS})?\s*
    (?P<val>\d[\d,]*(?:\.\d+)?(?:\s*[kKmM](?![a-zA-Z]))?)\s*
    (?P<curr_suffix>{_CURR_SYMBOLS})?\s*
    (?P<period_str>per\s+(?:year|month|week|day|hour)|annually|yearly|annual|monthly|hourly|daily|weekly|/\s*(?:yr|year|mo|month|wk|week|day|hr|hour))?
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

        # Determine currency
        curr_raw = m_dict.get("curr_prefix") or m_dict.get("curr_mid") or m_dict.get("curr_suffix")
        curr = _resolve_currency(curr_raw, context_text=raw_stripped, location_hint=location_hint, bare_n_is_ngn=bare_n_is_ngn)

        # Determine period
        period = normalize_period(m_dict.get("period_str"))
        range_matches.append((min_val, max_val, curr, period, match.group(0).strip()))

    # Rule: Multiple differing ranges produce no normalized salary, preserving raw text
    if len(range_matches) > 1:
        # Check if they are actually different
        first_min, first_max = range_matches[0][0], range_matches[0][1]
        for rm in range_matches[1:]:
            if rm[0] != first_min or rm[1] != first_max:
                # Ambiguous/conflicting: return None
                return None

    if len(range_matches) == 1:
        min_v, max_v, c, p, raw_sub = range_matches[0]
        return _create_jobsalary(
            minimum=min_v,
            maximum=max_v,
            currency=c,
            period=p,
            raw_text=raw_stripped,
            source=source,
        )

    # If no range found, try single value
    single_matches: list[tuple[int, int, Optional[str], Optional[str], str]] = []
    for match in _SINGLE_REGEX.finditer(raw_stripped):
        m_dict = match.groupdict()
        val_str = m_dict.get("val")
        curr_raw = m_dict.get("curr_prefix") or m_dict.get("curr_suffix")
        period_str = m_dict.get("period_str")
        period = normalize_period(period_str)
        curr = _resolve_currency(curr_raw, context_text=raw_stripped, location_hint=location_hint, bare_n_is_ngn=bare_n_is_ngn)

        # Single values require at least a resolved currency or a resolved period
        if curr is None and period is None:
            continue

        allow_val_m = is_labelled and bool(m_dict.get("curr_prefix"))
        val = _parse_numeric(val_str, allow_m=allow_val_m)
        if val is None or val < 0:
            continue

        single_matches.append((val, val, curr, period, match.group(0).strip()))

    if len(single_matches) == 1:
        val, _, c, p, raw_sub = single_matches[0]
        return _create_jobsalary(
            minimum=val,
            maximum=val,
            currency=c,
            period=p,
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
    struct_sal = parse_structured_salary(raw_fields, provider=provider, location_hint=location_hint)
    if struct_sal:
        return struct_sal

    # 2. Try labelled fields like "salary" or "compensation" in raw_fields
    for k in ("salary", "compensation", "pay", "remuneration"):
        val = raw_fields.get(k)
        if isinstance(val, str) and val.strip():
            text_sal = parse_text_salary(val, location_hint=location_hint, source=f"{provider}_{k}", bare_n_is_ngn=bare_n_is_ngn)
            if text_sal:
                return text_sal

    # 3. Look for explicit salary labels in description (e.g. "Salary: $80,000 - $100,000")
    if description:
        # Search for labelled salary lines
        label_match = re.search(
            r"(?:salary(?:\s+compensation)?|compensation|pay\s*range|base\s*pay)(?:[^\n\r:.]*?(?::|\bis\b))\s*([^\n\r<.]+)",
            description,
            re.IGNORECASE,
        )
        if label_match:
            cand_text = label_match.group(1).strip()
            text_sal = parse_text_salary(cand_text, location_hint=location_hint, source=f"{provider}_description_label", bare_n_is_ngn=bare_n_is_ngn)
            if text_sal:
                return text_sal

    return None

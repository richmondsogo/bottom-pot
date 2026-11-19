"""
ISO 3166-1 alpha-2 country taxonomy, aliases, and conservative regional mappings.

Strictly distinguishes sovereign countries (ISO-2 codes) from multi-country
geographic regions so applicant eligibility can be evaluated uniformly for any
selected country without equating remote work or broad region labels with
worldwide eligibility.
"""

from __future__ import annotations

import re

# Complete ISO 3166-1 alpha-2 catalog (UN-recognized + major territories used in ATS feeds)
ISO2_TO_COUNTRY: dict[str, str] = {
    "AF": "Afghanistan",
    "AL": "Albania",
    "DZ": "Algeria",
    "AD": "Andorra",
    "AO": "Angola",
    "AG": "Antigua and Barbuda",
    "AR": "Argentina",
    "AM": "Armenia",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaijan",
    "BS": "Bahamas",
    "BH": "Bahrain",
    "BD": "Bangladesh",
    "BB": "Barbados",
    "BY": "Belarus",
    "BE": "Belgium",
    "BZ": "Belize",
    "BJ": "Benin",
    "BT": "Bhutan",
    "BO": "Bolivia",
    "BA": "Bosnia and Herzegovina",
    "BW": "Botswana",
    "BR": "Brazil",
    "BN": "Brunei",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "CV": "Cabo Verde",
    "KH": "Cambodia",
    "CM": "Cameroon",
    "CA": "Canada",
    "CF": "Central African Republic",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "KM": "Comoros",
    "CG": "Congo",
    "CD": "DR Congo",
    "CR": "Costa Rica",
    "CI": "Côte d'Ivoire",
    "HR": "Croatia",
    "CU": "Cuba",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DK": "Denmark",
    "DJ": "Djibouti",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "EC": "Ecuador",
    "EG": "Egypt",
    "SV": "El Salvador",
    "GQ": "Equatorial Guinea",
    "ER": "Eritrea",
    "EE": "Estonia",
    "SZ": "Eswatini",
    "ET": "Ethiopia",
    "FJ": "Fiji",
    "FI": "Finland",
    "FR": "France",
    "GA": "Gabon",
    "GM": "Gambia",
    "GE": "Georgia",
    "DE": "Germany",
    "GH": "Ghana",
    "GR": "Greece",
    "GD": "Grenada",
    "GT": "Guatemala",
    "GN": "Guinea",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HT": "Haiti",
    "HN": "Honduras",
    "HK": "Hong Kong",
    "HU": "Hungary",
    "IS": "Iceland",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Iran",
    "IQ": "Iraq",
    "IE": "Ireland",
    "IL": "Israel",
    "IT": "Italy",
    "JM": "Jamaica",
    "JP": "Japan",
    "JO": "Jordan",
    "KZ": "Kazakhstan",
    "KE": "Kenya",
    "KI": "Kiribati",
    "KW": "Kuwait",
    "KG": "Kyrgyzstan",
    "LA": "Laos",
    "LV": "Latvia",
    "LB": "Lebanon",
    "LS": "Lesotho",
    "LR": "Liberia",
    "LY": "Libya",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MG": "Madagascar",
    "MW": "Malawi",
    "MY": "Malaysia",
    "MV": "Maldives",
    "ML": "Mali",
    "MT": "Malta",
    "MH": "Marshall Islands",
    "MR": "Mauritania",
    "MU": "Mauritius",
    "MX": "Mexico",
    "FM": "Micronesia",
    "MD": "Moldova",
    "MC": "Monaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MA": "Morocco",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "NI": "Nicaragua",
    "NE": "Niger",
    "NG": "Nigeria",
    "MK": "North Macedonia",
    "NO": "Norway",
    "OM": "Oman",
    "PK": "Pakistan",
    "PW": "Palau",
    "PS": "Palestine",
    "PA": "Panama",
    "PG": "Papua New Guinea",
    "PY": "Paraguay",
    "PE": "Peru",
    "PH": "Philippines",
    "PL": "Poland",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "RW": "Rwanda",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "VC": "Saint Vincent and the Grenadines",
    "WS": "Samoa",
    "SM": "San Marino",
    "ST": "São Tomé and Príncipe",
    "SA": "Saudi Arabia",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leone",
    "SG": "Singapore",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "SB": "Solomon Islands",
    "SO": "Somalia",
    "ZA": "South Africa",
    "KR": "South Korea",
    "SS": "South Sudan",
    "ES": "Spain",
    "LK": "Sri Lanka",
    "SD": "Sudan",
    "SR": "Suriname",
    "SE": "Sweden",
    "CH": "Switzerland",
    "SY": "Syria",
    "TW": "Taiwan",
    "TJ": "Tajikistan",
    "TZ": "Tanzania",
    "TH": "Thailand",
    "TL": "Timor-Leste",
    "TG": "Togo",
    "TO": "Tonga",
    "TT": "Trinidad and Tobago",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TM": "Turkmenistan",
    "TV": "Tuvalu",
    "UG": "Uganda",
    "UA": "Ukraine",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VU": "Vanuatu",
    "VA": "Vatican City",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "YE": "Yemen",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    name.lower(): code for code, name in ISO2_TO_COUNTRY.items()
}

# Common abbreviations, endonyms, and alternate spellings -> ISO 3166-1 alpha-2 code
_EXTRA_COUNTRY_ALIASES_TO_ISO2: dict[str, str] = {
    "uk": "GB",
    "u.k": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "us": "US",
    "u.s": "US",
    "u.s.": "US",
    "usa": "US",
    "u.s.a": "US",
    "u.s.a.": "US",
    "united states of america": "US",
    "america": "US",
    "deutschland": "DE",
    "españa": "ES",
    "espana": "ES",
    "espagne": "ES",
    "tunisie": "TN",
    "italia": "IT",
    "holland": "NL",
    "the netherlands": "NL",
    "brasil": "BR",
    "méxico": "MX",
    "perú": "PE",
    "panamá": "PA",
    "polska": "PL",
    "sverige": "SE",
    "schweiz": "CH",
    "suisse": "CH",
    "österreich": "AT",
    "osterreich": "AT",
    "belgië": "BE",
    "belgique": "BE",
    "danmark": "DK",
    "norge": "NO",
    "suomi": "FI",
    "czechia": "CZ",
    "slovak republic": "SK",
    "republic of ireland": "IE",
    "uae": "AE",
    "u.a.e": "AE",
    "u.a.e.": "AE",
    "korea": "KR",
    "republic of korea": "KR",
    "viet nam": "VN",
    "ivory coast": "CI",
    "cote d'ivoire": "CI",
    "cote divoire": "CI",
    "democratic republic of the congo": "CD",
    "republic of the congo": "CG",
    "türkiye": "TR",
    "turkiye": "TR",
    "cape verde": "CV",
    "russian federation": "RU",
    "sao tome and principe": "ST",
}

COUNTRY_ALIASES: dict[str, str] = {
    **{k: ISO2_TO_COUNTRY[v] for k, v in COUNTRY_NAME_TO_ISO2.items()},
    **{k: ISO2_TO_COUNTRY[v] for k, v in _EXTRA_COUNTRY_ALIASES_TO_ISO2.items()},
}

CANONICAL_REGIONS: frozenset[str] = frozenset({
    "Worldwide",
    "Africa",
    "Sub-Saharan Africa",
    "EU",
    "EEA",
    "Europe",
    "EMEA",
    "LATAM",
    "APAC",
    "North America",
    "Americas",
    "MENA",
})

REGION_ALIASES: dict[str, str] = {
    "worldwide": "Worldwide",
    "global": "Worldwide",
    "anywhere": "Worldwide",
    "africa": "Africa",
    "african": "Africa",
    "sub-saharan africa": "Sub-Saharan Africa",
    "sub saharan africa": "Sub-Saharan Africa",
    "ssa": "Sub-Saharan Africa",
    "eu": "EU",
    "european union": "EU",
    "eea": "EEA",
    "european economic area": "EEA",
    "europe": "Europe",
    "emea": "EMEA",
    "latam": "LATAM",
    "latin america": "LATAM",
    "apac": "APAC",
    "asia pacific": "APAC",
    "asia-pacific": "APAC",
    "north america": "North America",
    "americas": "Americas",
    "mena": "MENA",
    "middle east and north africa": "MENA",
}

# Pan-regional sets for conservative membership checks
_AFRICA_CODES: frozenset[str] = frozenset({
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD",
    "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE",
    "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG",
    "RW", "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG",
    "ZM", "ZW",
})
_NORTH_AFRICA_CODES: frozenset[str] = frozenset({"DZ", "EG", "LY", "MA", "TN"})
_EU_CODES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE",
})
_EEA_CODES: frozenset[str] = _EU_CODES | frozenset({"IS", "LI", "NO"})
_EUROPE_CODES: frozenset[str] = _EEA_CODES | frozenset({
    "AL", "AD", "AM", "AZ", "BA", "BY", "CH", "GB", "GE", "MC", "MD", "ME", "MK",
    "RS", "RU", "SM", "TR", "UA", "VA",
})
_MENA_CODES: frozenset[str] = _NORTH_AFRICA_CODES | frozenset({
    "AE", "BH", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY", "YE",
})
_NORTH_AMERICA_CODES: frozenset[str] = frozenset({"CA", "MX", "US"})
_LATAM_CODES: frozenset[str] = frozenset({
    "AR", "BO", "BR", "BZ", "CL", "CO", "CR", "CU", "DO", "EC", "GT", "HN", "HT",
    "MX", "NI", "PA", "PE", "PR", "PY", "SV", "UY", "VE",
})
_APAC_CODES: frozenset[str] = frozenset({
    "AU", "BD", "BN", "CN", "FJ", "HK", "ID", "IN", "JP", "KH", "KR", "LA", "LK",
    "MM", "MY", "NP", "NZ", "PG", "PH", "PK", "SG", "TH", "TW", "VN",
})

REGION_MEMBERS: dict[str, frozenset[str]] = {
    "Africa": _AFRICA_CODES,
    "Sub-Saharan Africa": _AFRICA_CODES - _NORTH_AFRICA_CODES,
    "EU": _EU_CODES,
    "EEA": _EEA_CODES,
    "Europe": _EUROPE_CODES,
    "MENA": _MENA_CODES,
    "EMEA": _EUROPE_CODES | _MENA_CODES | _AFRICA_CODES,
    "North America": _NORTH_AMERICA_CODES,
    "LATAM": _LATAM_CODES,
    "Americas": _NORTH_AMERICA_CODES | _LATAM_CODES,
    "APAC": _APAC_CODES,
}

# Regions that may carry pan-regional remote permission ONLY when remote eligibility
# across the region is explicitly stated with no contradictory restriction.
# Broad business zones like EMEA, Europe, APAC, LATAM, MENA, Americas, North America
# are treated as ambiguous ("unknown") for member countries because they rarely
# guarantee uniform legal employment eligibility across all constituent countries.
UNIFORM_CAPABLE_REGIONS: frozenset[str] = frozenset({
    "Africa",
    "Sub-Saharan Africa",
    "EU",
    "EEA",
})


def _clean_token(raw: str | None) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    return re.sub(r"\s+", " ", raw).strip(" ,.;:-")


def normalize_country_code(raw: str | None) -> str | None:
    """Resolve an ISO-2 code or country name/alias to uppercase ISO 3166-1 alpha-2 code."""
    cleaned = _clean_token(raw)
    if not cleaned:
        return None
    upper = cleaned.upper()
    if upper == "UK":
        return "GB"
    if upper in ISO2_TO_COUNTRY:
        return upper
    low = cleaned.lower()
    if low in REGION_ALIASES:
        return None
    if low in COUNTRY_NAME_TO_ISO2:
        return COUNTRY_NAME_TO_ISO2[low]
    if low in _EXTRA_COUNTRY_ALIASES_TO_ISO2:
        return _EXTRA_COUNTRY_ALIASES_TO_ISO2[low]
    return None


def normalize_region_name(raw: str | None) -> str | None:
    """Resolve a geographic macro-region alias to its canonical region label."""
    cleaned = _clean_token(raw)
    if not cleaned:
        return None
    return REGION_ALIASES.get(cleaned.lower())


def country_name_for_code(code: str | None) -> str | None:
    """Return canonical display name for an ISO 3166-1 alpha-2 code."""
    if not code or not isinstance(code, str):
        return None
    norm = code.strip().upper()
    if norm == "UK":
        norm = "GB"
    return ISO2_TO_COUNTRY.get(norm)


def normalize_geo_label(raw: str | None) -> str | None:
    """
    Normalize a country or macro-region string into its canonical display label.

    Preserves unrecognized non-empty strings verbatim for legacy fallback compatibility
    while mapping recognized ISO-2 codes, country aliases, and regions deterministically.
    """
    cleaned = _clean_token(raw)
    if not cleaned:
        return None
    region = normalize_region_name(cleaned)
    if region:
        return region
    code = normalize_country_code(cleaned)
    if code:
        return ISO2_TO_COUNTRY[code]
    return cleaned


def is_country_in_region(country_code: str, region: str) -> bool:
    """Return True when the normalized ISO-2 country belongs to the canonical region."""
    code = normalize_country_code(country_code)
    reg = normalize_region_name(region) or region
    if not code:
        return False
    if reg == "Worldwide":
        return True
    members = REGION_MEMBERS.get(reg)
    return bool(members and code in members)

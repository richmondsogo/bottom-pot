from __future__ import annotations

import pytest

from src.project_files.models import JobSalary
from src.project_files.salary_parser import (
    extract_salary,
    parse_structured_salary,
    parse_text_salary,
)


@pytest.mark.parametrize(
    "text, expected_min, expected_max, expected_currency, expected_period",
    [
        # 1. Standard range with period
        ("$80,000–$100,000 per year", 80_000, 100_000, "USD", "year"),
        # 2. ISO code with k suffixes and annually
        ("USD 80k - 100k annually", 80_000, 100_000, "USD", "year"),
        # 3. GBP single salary with annually
        ("£45,000 annually", 45_000, 45_000, "GBP", "year"),
        # 4. EUR monthly
        ("€4,000 monthly", 4_000, 4_000, "EUR", "month"),
        # 5. Bare ₦ per month (Rule 22b: ₦ maps to NGN universally)
        ("₦500,000 per month", 500_000, 500_000, "NGN", "month"),
        # 6. Hourly rate
        ("$35/hour", 35, 35, "USD", "hour"),
        # 7. Explicit NGN code with monthly
        ("50,000 NGN monthly", 50_000, 50_000, "NGN", "month"),
        # 8. Unmarked period (period remains None, never defaulted)
        ("Salary: 80k-100k USD", 80_000, 100_000, "USD", None),
        # 9. Unmarked currency and period (both stay None, never defaulted)
        ("80k-100k", 80_000, 100_000, None, None),
    ],
)
def test_table_driven_positive_salary_cases(
    text: str,
    expected_min: int,
    expected_max: int,
    expected_currency: str | None,
    expected_period: str | None,
):
    res = parse_text_salary(text)
    assert res is not None
    assert res.minimum == expected_min
    assert res.maximum == expected_max
    assert res.currency == expected_currency
    assert res.period == expected_period
    assert res.raw_text == text


@pytest.mark.parametrize(
    "text, location_hint, expected_currency",
    [
        ("$100k - $120k / yr", None, "USD"),
        ("$100k - $120k / yr", "Toronto, Canada", None),
        ("CA$ 100k - 120k per year", None, "CAD"),
        ("AU$ 90k - 110k per year", None, "AUD"),
        ("¥5,000,000 annually", None, None),  # Rule: ¥ stays None
    ],
)
def test_dollar_currency_disambiguation_and_symbol_rules(
    text: str,
    location_hint: str | None,
    expected_currency: str | None,
):
    res = parse_text_salary(text, location_hint=location_hint)
    assert res is not None
    assert res.currency == expected_currency


@pytest.mark.parametrize(
    "negative_text",
    [
        "Competitive salary",
        "market rate",
        "Salary is commensurate with experience",
        "DOE",
        "We offer a 401k match and full benefits",
        "401k",
        "$50M raised in Series B funding",
        "raised $1.2M",
        "$2M budget",
        "N/A",
        "2024",
        "We are a company with 10,000 employees globally",
        "Receive a $5,000 sign-on bonus upon starting",
        "Founded in 2024 with strong leadership",
        "Over 2024-2025 we expanded operations",
        "5-7 years experience required",
        "$120,000 - $80,000 per year",  # Contradictory bounds (min > max)
        "Salary ranges: $80,000 - $100,000 and $120,000 - $140,000 per year",  # Multiple differing ranges
    ],
)
def test_table_driven_negative_salary_cases(negative_text: str):
    res = parse_text_salary(negative_text)
    assert res is None, f"Expected None for negative input: {negative_text}, got {res}"


def test_structured_smartrecruiters_compensation_live_fixture():
    # Live verified payload from tests/fixtures/real/smartrecruiters/744000155937924.json
    payload = {
        "compensation": {
            "min": 135000,
            "max": 175000,
            "currency": "GBP",
            "period": "YEARLY",
        }
    }
    salary = parse_structured_salary(payload, provider="smartrecruiters")
    assert salary is not None
    assert salary.minimum == 135000
    assert salary.maximum == 175000
    assert salary.currency == "GBP"
    assert salary.period == "year"


def test_structured_recruitee_salary_live_fixture():
    # Live verified payload from tests/fixtures/real/recruitee/offer_2774909.json
    payload = {
        "salary": {
            "min": "40",
            "max": "48",
            "currency": "USD",
            "period": "hour",
        }
    }
    salary = parse_structured_salary(payload, provider="recruitee")
    assert salary is not None
    assert salary.minimum == 40
    assert salary.maximum == 48
    assert salary.currency == "USD"
    assert salary.period == "hour"


def test_structured_greenhouse_cents_documentation_derived():
    # documentation-derived, not live-verified
    payload = {
        "pay_input_ranges": [
            {
                "min_cents": 12000000,
                "max_cents": 15000000,
                "currency": "USD",
                "period": "year",
            }
        ]
    }
    salary = parse_structured_salary(payload, provider="greenhouse")
    assert salary is not None
    assert salary.minimum == 120000
    assert salary.maximum == 150000
    assert salary.currency == "USD"
    assert salary.period == "year"


def test_structured_lever_salary_range_documentation_derived():
    # documentation-derived, not live-verified
    payload = {
        "salaryRange": {
            "min": 90000,
            "max": 115000,
            "currency": "USD",
            "interval": "per year-indexed",
        }
    }
    salary = parse_structured_salary(payload, provider="lever")
    assert salary is not None
    assert salary.minimum == 90000
    assert salary.maximum == 115000
    assert salary.currency == "USD"
    assert salary.period == "year"


def test_structured_ashby_compensation_tier_documentation_derived():
    # documentation-derived, not live-verified
    payload = {
        "compensationTierSummary": "$140,000 - $160,000 per year"
    }
    salary = parse_structured_salary(payload, provider="ashby")
    assert salary is not None
    assert salary.minimum == 140000
    assert salary.maximum == 160000
    assert salary.currency == "USD"
    assert salary.period == "year"


def test_extract_salary_facade_precedence():
    # Structured field takes precedence over description text
    raw_fields = {
        "compensation": {
            "min": 100000,
            "max": 120000,
            "currency": "USD",
            "period": "year",
        }
    }
    desc = "Salary: $50,000 - $60,000 per year"
    res = extract_salary(provider="smartrecruiters", raw_fields=raw_fields, description=desc)
    assert res is not None
    assert res.minimum == 100000
    assert res.maximum == 120000


def test_nigerian_adapter_hint_and_currency_resolution():
    # 1. N 150,000 - N 250,000 monthly with bare_n_is_ngn=True
    res_hint = parse_text_salary("N 150,000 - N 250,000 monthly", bare_n_is_ngn=True)
    assert res_hint is not None
    assert res_hint.minimum == 150_000
    assert res_hint.maximum == 250_000
    assert res_hint.currency == "NGN"
    assert res_hint.period == "month"

    # 2. N 150,000 - N 250,000 monthly without hint -> currency is None
    res_no_hint = parse_text_salary("N 150,000 - N 250,000 monthly", bare_n_is_ngn=False)
    assert res_no_hint is not None
    assert res_no_hint.currency is None
    assert res_no_hint.period == "month"

    # 3. ₦500,000 per month -> maps to NGN universally
    res_naira_sym = parse_text_salary("₦500,000 per month")
    assert res_naira_sym is not None
    assert res_naira_sym.currency == "NGN"
    assert res_naira_sym.minimum == 500_000

    # 4. 50,000 NGN monthly
    res_ngn_code = parse_text_salary("50,000 NGN monthly")
    assert res_ngn_code is not None
    assert res_ngn_code.currency == "NGN"

    # 5. Bare N150k with and without hint
    res_n150k_hint = parse_text_salary("N150k", bare_n_is_ngn=True)
    assert res_n150k_hint is not None
    assert res_n150k_hint.minimum == 150_000
    assert res_n150k_hint.maximum == 150_000
    assert res_n150k_hint.currency == "NGN"
    assert res_n150k_hint.period is None

    res_n150k_no_hint = parse_text_salary("N150k", bare_n_is_ngn=False)
    assert res_n150k_no_hint is None

    # 6. Unparseable phrases and non-salaries produce None
    assert parse_text_salary("N/A", bare_n_is_ngn=True) is None
    assert parse_text_salary("Negotiable", bare_n_is_ngn=True) is None
    assert parse_text_salary("Salary: Negotiable", bare_n_is_ngn=True) is None
    assert parse_text_salary("attractive salary", bare_n_is_ngn=True) is None


def test_m_suffix_strict_salary_rules():
    # Suffix 'm' allowed ONLY in labelled salary context directly after currency symbol
    res_ngn_m = parse_text_salary("Salary: ₦1.5M - ₦2.5M", bare_n_is_ngn=True)
    assert res_ngn_m is not None
    assert res_ngn_m.minimum == 1_500_000
    assert res_ngn_m.maximum == 2_500_000
    assert res_ngn_m.currency == "NGN"

    res_usd_m = parse_text_salary("Salary: $1.2M per year")
    assert res_usd_m is not None
    assert res_usd_m.minimum == 1_200_000
    assert res_usd_m.maximum == 1_200_000
    assert res_usd_m.currency == "USD"
    assert res_usd_m.period == "year"

    # Negatives: raised, funding, budget must never parse as salary
    assert parse_text_salary("$50M raised in Series B funding") is None
    assert parse_text_salary("$2M budget") is None
    assert parse_text_salary("The company raised $1.2M") is None


def test_jsonld_base_salary_structured_extraction():
    # MonetaryAmount with QuantitativeValue
    raw_monetary = {
        "json_ld": {
            "baseSalary": {
                "@type": "MonetaryAmount",
                "currency": "USD",
                "value": {
                    "@type": "QuantitativeValue",
                    "minValue": 120000,
                    "maxValue": 150000,
                    "unitText": "YEAR",
                },
            }
        }
    }
    sal = extract_salary(provider="generic", raw_fields=raw_monetary)
    assert sal is not None
    assert sal.minimum == 120000
    assert sal.maximum == 150000
    assert sal.currency == "USD"
    assert sal.period == "year"
    assert sal.source == "json_ld"

    # Rejection of zero or placeholder values
    raw_zero = {
        "json_ld": {
            "baseSalary": {
                "currency": "USD",
                "value": {"minValue": 0, "maxValue": 0, "unitText": "YEAR"},
            }
        }
    }
    assert extract_salary(provider="generic", raw_fields=raw_zero) is None


def test_snippet_containing_salary_and_work_model_text_yields_none():
    from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting

    raw = RawJobPosting(
        provider="generic",
        source_url="https://example.com/job/1",
        raw_title="Senior Developer",
        raw_company="Acme Corp",
        raw_description="Salary: $120,000 - $140,000 per year. Fully remote work available.",
        description_is_authentic=False,  # Listing card / snippet only
        raw_fields={"snippet": "Salary: $120,000 - $140,000 per year. Fully remote work available."},
    )
    canonical = JobExtractionService.extract(raw)
    assert canonical.salary is None
    assert canonical.work_model is None


def test_pay_period_normalization_slash_and_word_variants():
    # Slash variants
    sal_month = parse_text_salary("$5,900 - $10,500/month")
    assert sal_month is not None
    assert sal_month.period == "month"

    sal_mo = parse_text_salary("$5,900 - $10,500/mo")
    assert sal_mo is not None
    assert sal_mo.period == "month"

    sal_yr = parse_text_salary("$120,000 - $140,000/yr")
    assert sal_yr is not None
    assert sal_yr.period == "year"

    sal_year = parse_text_salary("$120,000 - $140,000/year")
    assert sal_year is not None
    assert sal_year.period == "year"

    sal_hr = parse_text_salary("$45 - $65/hr")
    assert sal_hr is not None
    assert sal_hr.period == "hour"

    # Prose variant
    sal_per_month = parse_text_salary("$5,900 - $10,500 per month")
    assert sal_per_month is not None
    assert sal_per_month.period == "month"

    # No period: must strictly remain None (Rule 2)
    sal_no_period = parse_text_salary("$120,000 - $140,000")
    assert sal_no_period is not None
    assert sal_no_period.period is None



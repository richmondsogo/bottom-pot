from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.project_files.countries import (
    ISO2_TO_COUNTRY,
    is_country_in_region,
    normalize_country_code,
    normalize_geo_label,
    normalize_region_name,
)
from src.project_files.models import ExtractionMethod, JobEligibility, JobListing


REPRESENTATIVE_COUNTRIES = [
    "NG", "GH", "KE", "ZA", "EG",
    "GB", "DE", "US", "CA",
    "IN", "SG", "AU",
]


class TestCountryTaxonomy:
    def test_representative_and_global_iso2_resolution(self):
        assert normalize_country_code("NG") == "NG"
        assert normalize_country_code("Nigeria") == "NG"
        assert normalize_country_code("UK") == "GB"
        assert normalize_country_code("Great Britain") == "GB"
        assert normalize_country_code("United States of America") == "US"
        assert normalize_country_code("Deutschland") == "DE"
        assert normalize_country_code("Ghana") == "GH"
        assert normalize_country_code("Kenya") == "KE"
        assert normalize_country_code("South Africa") == "ZA"
        assert normalize_country_code("Egypt") == "EG"
        assert normalize_country_code("India") == "IN"
        assert normalize_country_code("Singapore") == "SG"
        assert normalize_country_code("Australia") == "AU"
        # Macro-regions must never return an ISO country code
        assert normalize_country_code("EU") is None
        assert normalize_country_code("EMEA") is None
        assert normalize_country_code("Africa") is None
        assert normalize_country_code("Worldwide") is None
        assert len(ISO2_TO_COUNTRY) >= 190

    def test_region_normalization_and_membership(self):
        assert normalize_region_name("European Union") == "EU"
        assert normalize_region_name("Latin America") == "LATAM"
        assert normalize_region_name("Sub-Saharan Africa") == "Sub-Saharan Africa"
        assert normalize_geo_label("UK") == "United Kingdom"
        assert normalize_geo_label("european union") == "EU"

        assert is_country_in_region("NG", "Africa") is True
        assert is_country_in_region("EG", "Africa") is True
        assert is_country_in_region("EG", "Sub-Saharan Africa") is False
        assert is_country_in_region("NG", "Sub-Saharan Africa") is True
        assert is_country_in_region("DE", "EU") is True
        assert is_country_in_region("GB", "EU") is False
        assert is_country_in_region("GB", "Europe") is True
        assert is_country_in_region("NG", "EMEA") is True
        assert is_country_in_region("US", "EMEA") is False
        assert is_country_in_region("SG", "APAC") is True
        assert is_country_in_region("AU", "APAC") is True


class TestGlobalEligibilityEvaluation:
    def test_explicit_worldwide_remote_eligible_across_all_representative_countries(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        verified_ts = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
        elig = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Remote - Worldwide",
            description="We are a distributed engineering team. Work from anywhere in the world — open to candidates worldwide.",
            evidence_url="https://jobs.ashbyhq.com/example/123",
            verified_at=verified_ts,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.global_remote_explicit is True
        assert elig.classification == "worldwide"
        assert elig.evidence_url == "https://jobs.ashbyhq.com/example/123"
        assert elig.verified_at == verified_ts

        for code in REPRESENTATIVE_COUNTRIES:
            res = evaluate_eligibility_for_country(elig, code, work_model="remote", location="Remote - Worldwide")
            assert res.status == "eligible", f"Expected {code} eligible on worldwide role"
            assert res.summary_label == "Remote · Worldwide"

    def test_generic_remote_without_geo_disclosure_stays_unknown_never_worldwide(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="lever",
            work_model="remote",
            location="Remote",
            description="Build backend APIs for our distributed platform team.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.global_remote_explicit is not True
        assert elig.classification == "unknown"

        for code in REPRESENTATIVE_COUNTRIES:
            res = evaluate_eligibility_for_country(elig, code, work_model="remote", location="Remote")
            assert res.status == "unknown", f"Expected {code} unknown when geo undisclosed"
            assert res.summary_label == "Remote · Eligibility unverified"
            assert "worldwide" not in (res.summary_label or "").lower()

    def test_us_only_remote_never_labeled_worldwide_and_restricts_non_us(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="Remote (US only)",
            description="This remote role is open to candidates residing in the United States only.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.allowed_country_codes == ["US"]
        assert elig.global_remote_explicit is not True
        assert elig.classification == "country_restricted"

        us_res = evaluate_eligibility_for_country(elig, "US", work_model="remote", location="Remote (US only)")
        assert us_res.status == "eligible"
        assert us_res.summary_label == "Remote · US only"

        for code in [c for c in REPRESENTATIVE_COUNTRIES if c != "US"]:
            res = evaluate_eligibility_for_country(elig, code, work_model="remote", location="Remote (US only)")
            assert res.status == "restricted", f"Expected {code} restricted on US-only role"
            assert res.summary_label == "Remote · US only"

    def test_germany_and_eu_remote_allows_eu_and_restricts_uk_us_nigeria(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="recruitee",
            work_model="remote",
            location="Remote (Germany and EU)",
            description="You can work remotely from anywhere in Germany or the European Union.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert "DE" in (elig.allowed_country_codes or [])
        assert "EU" in (elig.allowed_regions or [])

        de_res = evaluate_eligibility_for_country(elig, "DE", work_model="remote", location="Remote (Germany and EU)")
        assert de_res.status == "eligible"
        assert de_res.summary_label == "Remote · Germany and EU"

        fr_res = evaluate_eligibility_for_country(elig, "FR", work_model="remote", location="Remote (Germany and EU)")
        assert fr_res.status == "eligible"

        for non_eu in ("NG", "GB", "US", "CA", "IN", "SG", "AU", "EG"):
            res = evaluate_eligibility_for_country(elig, non_eu, work_model="remote", location="Remote (Germany and EU)")
            assert res.status == "restricted", f"Expected {non_eu} restricted on Germany & EU role"

    def test_explicit_africa_wide_remote_permits_african_countries_and_restricts_non_african(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Remote - Africa",
            description="Open to remote applicants across Africa. Join our distributed engineering hub.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert "Africa" in (elig.allowed_regions or [])

        for af_code in ("NG", "GH", "KE", "ZA", "EG"):
            res = evaluate_eligibility_for_country(elig, af_code, work_model="remote", location="Remote - Africa")
            assert res.status == "eligible", f"Expected {af_code} eligible on explicit Africa-wide remote role"

        for non_af in ("GB", "DE", "US", "CA", "IN", "SG", "AU"):
            res = evaluate_eligibility_for_country(elig, non_af, work_model="remote", location="Remote - Africa")
            assert res.status == "restricted", f"Expected {non_af} restricted on Africa-wide role"

    def test_bare_regional_tag_without_pan_regional_acceptance_does_not_assume_uniform_eligibility(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Bare regional location tag (e.g. "Africa" or "European Union" with no continent-wide phrasing)
        elig_eu = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="European Union",
            raw_fields={"address": {"postalAddress": {"addressCountry": "European Union"}}},
            description="Join our European engineering team.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig_eu is not None
        # Outside EU -> restricted; inside EU -> unknown (not assumed uniform without explicit pan-EU remote grant)
        assert evaluate_eligibility_for_country(elig_eu, "NG", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig_eu, "US", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig_eu, "DE", work_model="remote").status == "unknown"

    def test_contradictory_marketing_worldwide_overridden_by_explicit_residency_lock(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Mirrors Step 53 finalsite counterexample
        desc = (
            "Our platform supports more than 7,000 schools worldwide and enables teams to work together.\n"
            "LOCATION: 100% Remote - Anywhere within the US.\n"
            "RESIDENCY REQUIREMENT: These opportunities are limited to permanent residents of the United States."
        )
        elig = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="100% Remote - Anywhere within the US",
            description=desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.global_remote_explicit is not True
        assert elig.allowed_country_codes == ["US"]
        assert evaluate_eligibility_for_country(elig, "US", work_model="remote").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "NG", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig, "DE", work_model="remote").status == "restricted"

    def test_emea_region_keeps_member_countries_unknown_and_outside_restricted(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="teamtailor",
            work_model="remote",
            location="EMEA",
            description="Remote in EMEA. Join our distributed team.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        for member in ("NG", "DE", "GB", "EG"):
            assert evaluate_eligibility_for_country(elig, member, work_model="remote").status == "unknown"
        for non_member in ("US", "CA", "IN", "SG", "AU"):
            assert evaluate_eligibility_for_country(elig, non_member, work_model="remote").status == "restricted"

    def test_onsite_and_hybrid_local_roles_eligible_locally_and_restricted_abroad(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        lagos_onsite = extract_eligibility(
            provider="pinpointhq",
            work_model="in_person",
            location="Lagos, Nigeria",
            description="Onsite software support engineer in Lagos.",
            description_is_authentic=True,
        )
        assert lagos_onsite is not None
        assert lagos_onsite.physical_location_country_code == "NG"
        ng_onsite = evaluate_eligibility_for_country(lagos_onsite, "NG", work_model="in_person", location="Lagos, Nigeria")
        assert ng_onsite.status == "eligible"
        assert ng_onsite.work_arrangement == "onsite"
        assert ng_onsite.summary_label == "Onsite · Lagos, Nigeria"
        assert evaluate_eligibility_for_country(lagos_onsite, "KE", work_model="in_person", location="Lagos, Nigeria").status == "restricted"
        assert evaluate_eligibility_for_country(lagos_onsite, "US", work_model="in_person", location="Lagos, Nigeria").status == "restricted"

        berlin_onsite = extract_eligibility(
            provider="personio",
            work_model="in_person",
            location="Berlin, Germany",
            description="Work onsite at our Berlin headquarters.",
            description_is_authentic=True,
        )
        assert berlin_onsite is not None
        de_onsite = evaluate_eligibility_for_country(berlin_onsite, "DE", work_model="in_person", location="Berlin, Germany")
        assert de_onsite.status == "eligible"
        assert de_onsite.summary_label == "Onsite · Berlin, Germany"
        assert evaluate_eligibility_for_country(berlin_onsite, "NG", work_model="in_person", location="Berlin, Germany").status == "restricted"

        cairo_hybrid = extract_eligibility(
            provider="pinpointhq",
            work_model="hybrid",
            location="Cairo, Egypt",
            description="Hybrid role: expected to be in our Cairo office 3 days a week.",
            description_is_authentic=True,
        )
        assert cairo_hybrid is not None
        assert cairo_hybrid.hybrid_attendance_confirmed is True
        assert evaluate_eligibility_for_country(cairo_hybrid, "EG", work_model="hybrid", location="Cairo, Egypt").status == "eligible"
        assert evaluate_eligibility_for_country(cairo_hybrid, "NG", work_model="hybrid", location="Cairo, Egypt").status == "restricted"

    def test_dual_african_hub_sunking_style_extracted_without_false_ghana_or_us_eligibility(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="pinpointhq",
            work_model="hybrid",
            location="Africa",
            description="Job Location: Nairobi, Kenya or Lagos, Nigeria\nHybrid collaboration with regional teams.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert set(elig.allowed_country_codes or []) == {"KE", "NG"}
        assert evaluate_eligibility_for_country(elig, "NG", work_model="hybrid", location="Africa").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "KE", work_model="hybrid", location="Africa").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "GH", work_model="hybrid", location="Africa").status == "restricted"
        assert evaluate_eligibility_for_country(elig, "EG", work_model="hybrid", location="Africa").status == "restricted"
        assert evaluate_eligibility_for_country(elig, "US", work_model="hybrid", location="Africa").status == "restricted"

    def test_excluded_country_overrides_worldwide_for_that_country_only(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Worldwide",
            description="Work from anywhere globally. Note: unable to hire candidates in the United States or Canada.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert set(elig.excluded_country_codes or []) == {"US", "CA"}
        assert evaluate_eligibility_for_country(elig, "US", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig, "CA", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig, "NG", work_model="remote").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "DE", work_model="remote").status == "eligible"

    def test_employer_hq_physical_country_on_remote_job_is_not_mistaken_for_restriction(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        elig = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            raw_fields={"country": {"descriptor": "United States"}},
            description="Remote Product Engineer building developer tooling.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert elig.physical_location_country_code == "US"
        assert elig.allowed_country_codes is None
        assert evaluate_eligibility_for_country(elig, "NG", work_model="remote").status == "unknown"
        assert evaluate_eligibility_for_country(elig, "US", work_model="remote").status == "unknown"

    def test_backward_compatible_evaluation_for_legacy_job_eligibility_records(self):
        from src.project_files.eligibility_extractor import evaluate_eligibility_for_country

        legacy_elig = JobEligibility(
            allowed_residence_countries=["Spain", "European Union"],
            residence_restriction_confirmed=True,
            physical_location_country="Spain",
            nigeria_eligible=False,
            nigeria_eligibility_reason="Confirmed hybrid office attendance in Spain.",
        )
        es_res = evaluate_eligibility_for_country(legacy_elig, "ES", work_model="hybrid", location="Madrid, Spain")
        assert es_res.status == "eligible"
        ng_res = evaluate_eligibility_for_country(legacy_elig, "NG", work_model="hybrid", location="Madrid, Spain")
        assert ng_res.status == "restricted"

    def test_apply_applicant_country_assessment_projects_without_mutating_source_listing(self):
        from src.project_files.eligibility_extractor import apply_applicant_country_assessment

        base_listing = JobListing(
            id="ashby:demo:1",
            provider="ashby",
            data_source="api",
            title="Backend Engineer",
            company="DemoCo",
            location="Remote (US only)",
            work_model="remote",
            apply_url="https://jobs.ashbyhq.com/demo/1",
            source_url="https://jobs.ashbyhq.com/demo/1",
            scraped_at=datetime.now(timezone.utc),
            query_used="backend",
            ats_source="ashby",
            eligibility=JobEligibility(
                classification="country_restricted",
                allowed_residence_countries=["United States"],
                allowed_country_codes=["US"],
                residence_restriction_confirmed=True,
            ),
        )
        projected_us = apply_applicant_country_assessment(base_listing, "US")
        projected_ng = apply_applicant_country_assessment(base_listing, "NG")

        assert base_listing.eligibility is not None
        assert base_listing.eligibility.applicant_assessment is None
        assert projected_us.eligibility is not None
        assert projected_us.eligibility.applicant_assessment is not None
        assert projected_us.eligibility.applicant_assessment.status == "eligible"
        assert projected_ng.eligibility is not None
        assert projected_ng.eligibility.applicant_assessment is not None
        assert projected_ng.eligibility.applicant_assessment.status == "restricted"

    def test_amer_namer_regions_override_generic_worldwide_footer_boilerplate(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Supabase-style posting: Remote, AMER location + generic footer marketing copy
        desc = (
            "We are hiring a Customer Solution Architect (AMER).\n"
            "WHAT WE OFFER\n"
            "- Fully Remote We hire globally. We believe you can do your best work from anywhere."
        )
        elig_amer = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Remote, AMER",
            description=desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig_amer is not None
        assert elig_amer.classification == "region_restricted"
        assert elig_amer.global_remote_explicit is not True
        assert elig_amer.allowed_regions == ["Americas"]
        assert evaluate_eligibility_for_country(elig_amer, "NG", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig_amer, "DE", work_model="remote").status == "restricted"
        # Americas is non-uniform, so member country remains unknown without US/CA-only lock
        assert evaluate_eligibility_for_country(elig_amer, "US", work_model="remote").status == "unknown"

        # ClickHouse-style compound bare regional remote location
        elig_namer = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="NAMER and LatAm",
            description="Cloud Software Engineer role on distributed infrastructure team.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig_namer is not None
        assert elig_namer.allowed_regions == ["North America", "LATAM"]
        assert evaluate_eligibility_for_country(elig_namer, "NG", work_model="remote").status == "restricted"
        assert evaluate_eligibility_for_country(elig_namer, "US", work_model="remote").status == "unknown"

    def test_step54_manual_audit_edge_cases_residency_countries_mission_and_multihub(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # 1. Mission/beneficiary "anywhere in the world" must not override country-list restriction
        elig_gd = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="Remote",
            description=(
                "You must be based in one of the countries on this list and overlap EAT and US ET.\n"
                "Our Rapid Response team delivers cash to disaster-affected communities within 5 days of a crisis—anywhere in the world."
            ),
            description_is_authentic=True,
        )
        assert elig_gd is not None
        assert elig_gd.global_remote_explicit is not True
        assert evaluate_eligibility_for_country(elig_gd, "NG", work_model="remote").status == "unknown"

        # 2. Sourcegraph-style "require successful candidates to be located in the United States"
        elig_sg = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="Remote",
            description=(
                "While we hire almost anywhere in the world, we do require successful candidates to be located in the United States."
            ),
            description_is_authentic=True,
        )
        assert elig_sg is not None
        assert elig_sg.allowed_country_codes == ["US"]
        assert evaluate_eligibility_for_country(elig_sg, "US", work_model="remote").status == "eligible"
        assert evaluate_eligibility_for_country(elig_sg, "NG", work_model="remote").status == "restricted"

        # 3. Wikimedia-style US States + Countries list with asterisk footnotes
        elig_wm = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="Remote",
            description=(
                "*Please note that we are currently able to hire in the following:\n"
                "**US States**: California, New York\n\n"
                "**Countries:** Brazil, Canada, Germany, Ghana, India, Kenya*, South Africa, Singapore*, United Kingdom."
            ),
            description_is_authentic=True,
        )
        assert elig_wm is not None
        for code in ("US", "GH", "KE", "ZA", "DE", "GB", "CA", "IN", "SG"):
            assert evaluate_eligibility_for_country(elig_wm, code, work_model="remote").status == "eligible"
        assert evaluate_eligibility_for_country(elig_wm, "NG", work_model="remote").status == "restricted"

        # 4. Miaplaza-style "**Location**: 100% remote (EMEA)"
        elig_mp = extract_eligibility(
            provider="recruitee",
            work_model="remote",
            location="Berlin, Germany",
            description="**Location**: 100% remote (EMEA)\nLead DevOps infrastructure.",
            description_is_authentic=True,
        )
        assert elig_mp is not None
        assert elig_mp.allowed_regions == ["EMEA"]
        assert evaluate_eligibility_for_country(elig_mp, "DE", work_model="remote").status == "unknown"
        assert evaluate_eligibility_for_country(elig_mp, "US", work_model="remote").status == "restricted"

        # 5. Paystack-style multi-hub hybrid locations
        elig_ps = extract_eligibility(
            provider="teamtailor",
            work_model="hybrid",
            location="Lagos, Nigeria; Nairobi, Kenya; Cape Town, South Africa",
            description="Work in hybrid collaboration with engineering hubs across Africa.",
            description_is_authentic=True,
        )
        assert elig_ps is not None
        for hub in ("NG", "KE", "ZA"):
            assert evaluate_eligibility_for_country(elig_ps, hub, work_model="hybrid", location="Lagos, Nigeria; Nairobi, Kenya; Cape Town, South Africa").status == "eligible"
        assert evaluate_eligibility_for_country(elig_ps, "GH", work_model="hybrid").status == "restricted"


class TestStep55EligibilityFixes:
    def test_teamtailor_truncated_multihub_location_uses_all_locations(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Paystack RSS with >80 char compact display truncated to "(+2 more)" while all_locations keeps full hubs
        truncated = "Accra, Ghana; Cape Town, South Africa; Dubai, UAE (+2 more)"
        all_locs = [
            "Accra, Ghana",
            "Cape Town, South Africa",
            "Dubai, UAE",
            "Lagos, Nigeria",
            "Nairobi, Kenya",
        ]
        elig = extract_eligibility(
            provider="teamtailor",
            work_model="hybrid",
            location=truncated,
            raw_location=", ".join(all_locs),
            raw_fields={"all_locations": all_locs},
            description="Senior DevOps Engineer working from our regional offices.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert set(elig.allowed_country_codes or []) >= {"GH", "ZA", "AE", "NG", "KE"}
        for hub in ("NG", "KE", "ZA", "GH"):
            assert evaluate_eligibility_for_country(elig, hub, work_model="hybrid", location=truncated).status == "eligible"
        assert evaluate_eligibility_for_country(elig, "US", work_model="hybrid", location=truncated).status == "restricted"

    def test_workable_pipe_separated_and_structured_locations_extract_all_hubs(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # FairMoney Senior Software Engineer-Lending ("İstanbul, Turkey | Lagos, Nigeria")
        elig = extract_eligibility(
            provider="workable",
            work_model="hybrid",
            location="İstanbul, Turkey | Lagos, Nigeria",
            raw_fields={
                "location": {"city": "İstanbul", "country": "Turkey", "countryCode": "TR"},
                "locations": [
                    {"city": "İstanbul", "country": "Turkey", "countryCode": "TR"},
                    {"city": "Lagos", "country": "Nigeria", "countryCode": "NG"},
                ],
            },
            description="Build lending services with our Istanbul and Lagos engineering teams.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert set(elig.allowed_country_codes or []) >= {"TR", "NG"}
        assert evaluate_eligibility_for_country(elig, "NG", work_model="hybrid").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "TR", work_model="hybrid").status == "eligible"
        assert evaluate_eligibility_for_country(elig, "US", work_model="hybrid").status == "restricted"

    def test_ashby_multicountry_remote_secondary_locations_never_left_unknown(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Kraken-style remote job listing explicit countries in primary location + secondaryLocations
        elig = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="United Kingdom; South Africa; Canada; Brazil",
            raw_fields={
                "location": "United Kingdom",
                "workplaceType": "Remote",
                "secondaryLocations": [
                    {"location": "South Africa"},
                    {"location": "Canada"},
                    {"location": "Brazil"},
                ],
            },
            description="Collaborate across distributed teams globally.",
            description_is_authentic=True,
        )
        assert elig is not None
        assert elig.classification == "country_restricted"
        assert elig.global_remote_explicit is not True
        assert set(elig.allowed_country_codes or []) == {"GB", "ZA", "CA", "BR"}
        for ok_cc in ("GB", "ZA", "CA"):
            assert evaluate_eligibility_for_country(elig, ok_cc, work_model="remote").status == "eligible"
        for blocked_cc in ("NG", "US", "DE"):
            assert evaluate_eligibility_for_country(elig, blocked_cc, work_model="remote").status == "restricted"

        # Single bare HQ country on remote role without secondaryLocations must remain conservative unknown
        elig_single = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="United States",
            raw_fields={"location": "United States", "workplaceType": "Remote", "secondaryLocations": []},
            description="Remote engineer building backend infrastructure.",
            description_is_authentic=True,
        )
        assert elig_single is not None
        assert elig_single.allowed_country_codes is None
        assert evaluate_eligibility_for_country(elig_single, "NG", work_model="remote").status == "unknown"

    def test_what_we_offer_plaintext_heading_and_physical_city_not_overridden_by_global_perks(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Supabase non-tech SF role: physical San Francisco location + plain-text "WHAT WE OFFER" footer
        elig_sf = extract_eligibility(
            provider="ashby",
            work_model=None,
            location="San Francisco, CA, US",
            description=(
                "Lead developer events in San Francisco.\n\n"
                "WHAT WE OFFER\n\n"
                "- Fully Remote\n"
                "  We hire globally. We believe you can do your best work from anywhere."
            ),
            description_is_authentic=True,
        )
        assert elig_sf is not None
        assert elig_sf.global_remote_explicit is not True
        assert elig_sf.classification != "worldwide"
        assert evaluate_eligibility_for_country(elig_sf, "NG", location="San Francisco, CA, US").status != "eligible"

        # LiveKit-style hybrid San Francisco role mentioning "Work anywhere in the world"
        elig_hyb = extract_eligibility(
            provider="ashby",
            work_model="hybrid",
            location="San Francisco, CA (Hybrid)",
            description=(
                "Join us in San Francisco!\n"
                "- Work anywhere in the world with flexible hybrid support."
            ),
            description_is_authentic=True,
        )
        assert elig_hyb is not None
        assert elig_hyb.global_remote_explicit is not True
        assert elig_hyb.classification == "onsite_or_hybrid_local"
        assert evaluate_eligibility_for_country(elig_hyb, "NG", work_model="hybrid", location="San Francisco, CA (Hybrid)").status == "unknown"

        # Genuine Supabase Remote, Global role must remain worldwide
        elig_global = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Remote, Global",
            description=(
                "Build AI infrastructure.\n\n"
                "WHAT WE OFFER\n\n"
                "- Fully Remote\n  We hire globally."
            ),
            description_is_authentic=True,
        )
        assert elig_global is not None
        assert elig_global.global_remote_explicit is True
        assert elig_global.classification == "worldwide"
        assert evaluate_eligibility_for_country(elig_global, "NG", work_model="remote", location="Remote, Global").status == "eligible"


class TestStep56EligibilityFixes:
    def test_elevenlabs_global_execution_vs_country_region_and_between_bounds(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # 1. Explicit global execution despite optional country/city hub secondaryLocations
        elig_global = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="United Kingdom",
            raw_fields={
                "location": "United Kingdom",
                "workplaceType": "Remote",
                "secondaryLocations": [
                    {"location": "United States"},
                    {"location": "Poland"},
                    {"location": "Bulgaria"},
                ],
            },
            description=(
                "## Location\n\n"
                "This role is remote and can be executed globally. "
                "If you prefer, you can work from our offices in London, New York, San Francisco, and Warsaw."
            ),
            description_is_authentic=True,
        )
        assert elig_global is not None
        assert elig_global.classification == "worldwide"
        assert elig_global.global_remote_explicit is True
        assert elig_global.allowed_country_codes is None
        for code in ("NG", "DE", "US", "IN", "CA", "GH", "EG", "AU"):
            assert evaluate_eligibility_for_country(elig_global, code, work_model="remote").status == "eligible"

        # 2. Country-scoped "can be executed from anywhere in the United States" -> country_restricted US
        elig_us = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="United States",
            raw_fields={
                "location": "United States",
                "workplaceType": "Remote",
                "secondaryLocations": [{"location": "New York"}, {"location": "San Francisco"}],
            },
            description="This role is remote-first, so it can be executed from anywhere in the United States.",
            description_is_authentic=True,
        )
        assert elig_us is not None
        assert elig_us.classification == "country_restricted"
        assert elig_us.allowed_country_codes == ["US"]
        assert evaluate_eligibility_for_country(elig_us, "US", work_model="remote").status == "eligible"
        assert evaluate_eligibility_for_country(elig_us, "NG", work_model="remote").status == "restricted"

        # 3. Regional "can be executed from anywhere in Europe" -> region_restricted Europe (never worldwide)
        elig_eu = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="United Kingdom",
            raw_fields={
                "location": "United Kingdom",
                "workplaceType": "Remote",
                "secondaryLocations": [{"location": "Germany"}, {"location": "Poland"}],
            },
            description="This role is remote-first, so it can be executed from anywhere in Europe, with the ability to overlap CET hours.",
            description_is_authentic=True,
        )
        assert elig_eu is not None
        assert elig_eu.classification == "region_restricted"
        assert elig_eu.allowed_regions == ["Europe"]
        assert evaluate_eligibility_for_country(elig_eu, "NG", work_model="remote").status == "restricted"

        # 4. Coast-to-continent "anywhere between the US East Coast and India" stays conservative unknown (never worldwide)
        elig_between = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Remote",
            description="This role is remote-first, so it can be executed from anywhere between the US East Coast and India.",
            description_is_authentic=True,
        )
        assert elig_between is not None
        assert elig_between.global_remote_explicit is not True
        assert elig_between.classification == "unknown"
        assert evaluate_eligibility_for_country(elig_between, "NG", work_model="remote").status == "unknown"

    def test_circle_anywhere_first_segment_worldwide_vs_aptos_remote_global_us_eu(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Circle Lead Engineer, Member Growth: primary location is "Anywhere", secondary has AMER/EMEA tz regions
        elig_circle = extract_eligibility(
            provider="ashby",
            work_model="remote",
            location="Anywhere; Europe, Middle East, Africa (EMEA); North America, South America (AMER)",
            raw_fields={
                "location": "Anywhere",
                "workplaceType": "Remote",
                "secondaryLocations": [
                    {"location": "Europe, Middle East, Africa (EMEA)"},
                    {"location": "North America, South America (AMER)"},
                ],
            },
            description="We are a distributed team collaborating asynchronously across time zones.",
            description_is_authentic=True,
        )
        assert elig_circle is not None
        assert elig_circle.global_remote_explicit is True
        assert elig_circle.classification == "worldwide"
        assert evaluate_eligibility_for_country(elig_circle, "NG", work_model="remote").status == "eligible"

        # Aptos "Remote Global (US, EU)" must remain country/region-restricted, NOT worldwide
        elig_aptos = extract_eligibility(
            provider="greenhouse",
            work_model="remote",
            location="Remote Global (US, EU)",
            description="Build global infrastructure.",
            description_is_authentic=True,
        )
        assert elig_aptos is not None
        assert elig_aptos.global_remote_explicit is not True
        assert elig_aptos.allowed_country_codes == ["US"]
        assert elig_aptos.allowed_regions == ["EU"]
        assert evaluate_eligibility_for_country(elig_aptos, "NG", work_model="remote").status == "restricted"

    def test_major_city_and_hybrid_prefix_resolution(self):
        from src.project_files.eligibility_extractor import (
            evaluate_eligibility_for_country,
            extract_eligibility,
        )

        # Affirm London hybrid early-career role (bare city "London")
        elig_london = extract_eligibility(
            provider="greenhouse",
            work_model="hybrid",
            location="London",
            description="After one year in our hybrid London program, collaborate with UK engineering peers.",
            description_is_authentic=True,
        )
        assert elig_london is not None
        assert elig_london.physical_location_country_code == "GB"
        assert elig_london.classification == "onsite_or_hybrid_local"
        assert evaluate_eligibility_for_country(elig_london, "GB", work_model="hybrid", location="London").status == "eligible"
        assert evaluate_eligibility_for_country(elig_london, "NG", work_model="hybrid", location="London").status == "unknown"

        # Coinbase "Hybrid - Singapore" role (mode-prefixed country string)
        elig_sg = extract_eligibility(
            provider="greenhouse",
            work_model="hybrid",
            location="Hybrid - Singapore",
            description="Software Engineer Intern working 3 days a week in our Singapore office.",
            description_is_authentic=True,
        )
        assert elig_sg is not None
        assert elig_sg.physical_location_country_code == "SG"
        assert elig_sg.hybrid_attendance_confirmed is True
        assert evaluate_eligibility_for_country(elig_sg, "SG", work_model="hybrid", location="Hybrid - Singapore").status == "eligible"
        assert evaluate_eligibility_for_country(elig_sg, "NG", work_model="hybrid", location="Hybrid - Singapore").status == "restricted"


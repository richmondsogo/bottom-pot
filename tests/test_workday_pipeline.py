"""Workday quality pipeline and geographic/application eligibility tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.project_files.ats_url_parser import (
    WorkdayUrlParts,
    build_workday_cxs_url,
    parse_ats_url,
    parse_workday_url,
)
from src.project_files.confidence_policy import (
    BASE_CONFIDENCE_TABLE,
    CORE_FIELD_WEIGHTS,
    EvidenceType,
    compute_field_confidence,
)
from src.project_files.models import (
    CanonicalJob,
    CanonicalJobField,
    EligibilityFact,
    EligibilityFactDimension,
    ExtractionMethod,
    JobEligibility,
    JobListing,
)


class TestEligibilityModelsAndConfidencePolicy:
    def test_canonical_fields_and_controlled_fact_dimension(self):
        assert CanonicalJobField.ELIGIBILITY == "eligibility"
        assert CanonicalJobField.RAW_LOCATION == "raw_location"

        fact = EligibilityFact(
            dimension="work_authorization",
            value="United States",
            raw_snippet="Must be legally authorized to work in the United States",
            method=ExtractionMethod.ATS_API,
            provider_field_name="jobDescription",
        )
        assert fact.dimension == "work_authorization"
        assert EligibilityFactDimension is not None

        with pytest.raises(ValidationError):
            EligibilityFact(
                dimension="invented_free_form_dimension",  # type: ignore[arg-type]
                value="x",
                raw_snippet="x",
                method=ExtractionMethod.ATS_API,
            )

    def test_job_eligibility_defaults_preserve_undisclosed_uncertainty(self):
        elig = JobEligibility()
        assert elig.physical_location_country is None
        assert elig.allowed_residence_countries is None
        assert elig.excluded_residence_countries is None
        assert elig.residence_restriction_confirmed is None
        assert elig.global_remote_explicit is None
        assert elig.citizenship_requirements is None
        assert elig.security_clearance_required is None
        assert elig.work_authorization_required is None
        assert elig.visa_sponsorship_status is None
        assert elig.payroll_requirements is None
        assert elig.relocation_required is None
        assert elig.relocation_assistance is None
        assert elig.employment_arrangement is None
        assert elig.timezone_requirements is None
        assert elig.nigeria_eligible is None
        assert elig.nigeria_eligibility_reason is None
        assert elig.facts == []

    def test_canonical_job_and_listing_accept_eligibility_and_raw_location(self):
        elig = JobEligibility(
            physical_location_country="Spain",
            nigeria_eligible=False,
            nigeria_eligibility_reason="On-site physical attendance in Spain",
            payroll_requirements=["Spanish payroll"],
        )
        canonical = CanonicalJob(
            id="workday:dxc:DXCJobs__role_1",
            source="workday",
            source_url="https://dxc.wd1.myworkdayjobs.com/DXCJobs/job/role_1",
            application_url="https://dxc.wd1.myworkdayjobs.com/DXCJobs/job/role_1",
            title="Full Stack Developer",
            company="DXC Technology",
            raw_location="ESP - MD - LAS ROZAS",
            location="ESP - MD - LAS ROZAS, Spain",
            eligibility=elig,
        )
        listing = JobListing(
            id="workday:dxc:DXCJobs__role_1",
            provider="workday",
            data_source="api",
            title="Full Stack Developer",
            company="DXC Technology",
            apply_url="https://dxc.wd1.myworkdayjobs.com/DXCJobs/job/role_1",
            source_url="https://dxc.wd1.myworkdayjobs.com/DXCJobs/job/role_1",
            scraped_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            query_used="full-stack",
            ats_source="workday",
            raw_location="ESP - MD - LAS ROZAS",
            location="ESP - MD - LAS ROZAS, Spain",
            eligibility=elig,
        )
        assert canonical.raw_location == "ESP - MD - LAS ROZAS"
        assert canonical.eligibility is not None
        assert canonical.eligibility.payroll_requirements == ["Spanish payroll"]
        assert listing.raw_location == "ESP - MD - LAS ROZAS"
        assert listing.eligibility is not None
        assert listing.eligibility.nigeria_eligible is False

    def test_confidence_policy_registers_new_fields_without_altering_core_weights(self):
        assert CORE_FIELD_WEIGHTS == {
            CanonicalJobField.TITLE: 0.20,
            CanonicalJobField.COMPANY: 0.20,
            CanonicalJobField.LOCATION: 0.20,
            CanonicalJobField.APPLY_URL: 0.20,
            CanonicalJobField.DESCRIPTION: 0.20,
        }
        assert (CanonicalJobField.RAW_LOCATION, EvidenceType.STRUCTURED_FREE_TEXT) in BASE_CONFIDENCE_TABLE
        assert (CanonicalJobField.ELIGIBILITY, EvidenceType.TYPED_ENUM) in BASE_CONFIDENCE_TABLE
        assert (CanonicalJobField.ELIGIBILITY, EvidenceType.EXPLICIT_LABEL) in BASE_CONFIDENCE_TABLE
        elig_score, _ = compute_field_confidence(
            CanonicalJobField.ELIGIBILITY,
            EvidenceType.TYPED_ENUM,
        )
        raw_loc_score, _ = compute_field_confidence(
            CanonicalJobField.RAW_LOCATION,
            EvidenceType.STRUCTURED_FREE_TEXT,
        )
        assert elig_score == pytest.approx(0.90)
        assert raw_loc_score == pytest.approx(0.90)


class TestWorkdayUrlParsingAndNormalization:
    @pytest.mark.parametrize(
        "url,expected_tenant,expected_site,expected_slug",
        [
            (
                "https://ag.wd3.myworkdayjobs.com/Airbus/job/Albacete/Machine-Learning-Engineer--MLOps---AI-Integration-_JR10454310/apply?source=laand_me&utm_source=laand_me&utm_medium=job_board",
                "ag",
                "Airbus",
                "Machine-Learning-Engineer--MLOps---AI-Integration-_JR10454310",
            ),
            (
                "https://autodesk.wd1.myworkdayjobs.com/Ext/job/Senior-Full-Stack-Developer_26WD101575/apply",
                "autodesk",
                "Ext",
                "Senior-Full-Stack-Developer_26WD101575",
            ),
            (
                "https://bah.wd1.myworkdayjobs.com/BAH_Jobs/job/Artificial-Intelligence-and-Machine-Learning-Engineer--Senior_R0249973/apply",
                "bah",
                "BAH_Jobs",
                "Artificial-Intelligence-and-Machine-Learning-Engineer--Senior_R0249973",
            ),
            (
                "https://bcbsnc.wd5.myworkdayjobs.com/BCBSNC/job/Principal-Product-Developer--Population-Health-Strategy_RQ0019731/apply",
                "bcbsnc",
                "BCBSNC",
                "Principal-Product-Developer--Population-Health-Strategy_RQ0019731",
            ),
            (
                "https://crowdstrike.wd5.myworkdayjobs.com/en-GB/crowdstrikecareers/job/Sr-Backend-Engineer_R29136/apply",
                "crowdstrike",
                "crowdstrikecareers",
                "Sr-Backend-Engineer_R29136",
            ),
            (
                "https://dow.wd1.myworkdayjobs.com/de-DE/ExternalCareers/job/Solution-Specialist---Senior-Full-Stack-Developer_R2068437-1/apply",
                "dow",
                "ExternalCareers",
                "Solution-Specialist---Senior-Full-Stack-Developer_R2068437-1",
            ),
            (
                "https://fis.wd5.myworkdayjobs.com/searchjobs/job/Artificial-Intelligence---Machine-Learning-Engineer-Lead--4-to-7-Years_JR0310029-1/apply",
                "fis",
                "searchjobs",
                "Artificial-Intelligence---Machine-Learning-Engineer-Lead--4-to-7-Years_JR0310029-1",
            ),
            (
                "https://google.wd501.myworkdayjobs.com/gocjobs/job/Full-Stack-Developer-Specialist---Tools---Automation_JR4511-2/apply",
                "google",
                "gocjobs",
                "Full-Stack-Developer-Specialist---Tools---Automation_JR4511-2",
            ),
            (
                "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CA-Pleasanton/Machine-Learning-Engineer---Payroll_JR-0108977/apply?ref=jobbys.vercel.app&utm_source=jobbys.vercel.app",
                "workday",
                "Workday",
                "Machine-Learning-Engineer---Payroll_JR-0108977",
            ),
            (
                "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CO-Boulder/Sr-Machine-Learning-Engineer_JR-0110287/apply?utm_source=aihiringboard.com&utm_medium=referral&utm_campaign=job_board",
                "workday",
                "Workday",
                "Sr-Machine-Learning-Engineer_JR-0110287",
            ),
        ],
    )
    def test_observed_apply_suffix_failures_parse_cleanly(self, url, expected_tenant, expected_site, expected_slug):
        from src.project_files.url_normalizer import url_carries_job_identifier

        wd = parse_workday_url(url)
        assert isinstance(wd, WorkdayUrlParts)
        assert wd.tenant == expected_tenant
        assert wd.site_id == expected_site
        assert wd.job_slug == expected_slug
        assert wd.had_apply_suffix is True
        assert wd.cxs_url == (
            f"https://{wd.netloc}/wday/cxs/{wd.tenant_raw}/{expected_site}/job/{expected_slug}"
        )

        parsed = parse_ats_url(url)
        assert parsed is not None
        assert parsed.ats == "workday"
        assert parsed.company_slug == expected_tenant
        assert parsed.job_id == f"{expected_site.lower()}__{expected_slug}"
        assert parsed.job_id != "apply"
        assert url_carries_job_identifier(url, "workday") is True

    @pytest.mark.parametrize(
        "url,expected_locale,expected_site,expected_slug",
        [
            (
                "https://bilh.wd1.myworkdayjobs.com/en-us/external/job/ai-data-scientist_jr103599",
                "en-us",
                "external",
                "ai-data-scientist_jr103599",
            ),
            (
                "https://dow.wd1.myworkdayjobs.com/zh-CN/ExternalCareers/job/Machine-Learning-Engineer_R2067093-1",
                "zh-CN",
                "ExternalCareers",
                "Machine-Learning-Engineer_R2067093-1",
            ),
            (
                "https://fis.wd5.myworkdayjobs.com/fr-CA/SearchJobs/job/IND-BNGL-FL2-3-TWR-3/Java-Full-Stack-Developer---2---5-Years-_JR0310308",
                "fr-CA",
                "SearchJobs",
                "Java-Full-Stack-Developer---2---5-Years-_JR0310308",
            ),
            (
                "https://pluxee.wd3.myworkdayjobs.com/es/Pluxee_Career_Site/job/Software-Developer---Full-Stack_R5957-1",
                "es",
                "Pluxee_Career_Site",
                "Software-Developer---Full-Stack_R5957-1",
            ),
            (
                "https://okgov.wd1.myworkdayjobs.com/en-US/okgovjobs/job/Oklahoma-County/Senior-Application-Developer_JR66448?hiringCompany=7a8d2de4e0861000cc58d49ed7390000",
                "en-US",
                "okgovjobs",
                "Senior-Application-Developer_JR66448",
            ),
            (
                "https://nvidia.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Senior-Architect_JR198",
                "en-US",
                "NVIDIAExternalCareerSite",
                "Senior-Architect_JR198",
            ),
            (
                "https://paypal.wd1.myworkdayjobs.com/en-US/jobs/job/Machine-Learning-Engineer-Intern---Summer-2027_R0138581",
                "en-US",
                "jobs",
                "Machine-Learning-Engineer-Intern---Summer-2027_R0138581",
            ),
            (
                "https://travelhrportal.wd1.myworkdayjobs.com/en-US/Jobs/job/Machine-Learning-Engineer-I_J-85419",
                "en-US",
                "Jobs",
                "Machine-Learning-Engineer-I_J-85419",
            ),
        ],
    )
    def test_observed_locale_host_and_query_variants(self, url, expected_locale, expected_site, expected_slug):
        wd = parse_workday_url(url)
        assert wd is not None
        assert wd.locale == expected_locale
        assert wd.site_id == expected_site
        assert wd.job_slug == expected_slug
        assert build_workday_cxs_url(url) == wd.cxs_url

    def test_shared_tenant_sites_do_not_collide_while_apply_variants_match(self):
        sei = parse_ats_url(
            "https://cmu.wd115.myworkdayjobs.com/SEI/job/Pittsburgh-PA/Enabling-Mission-Capability-at-Scale-Intern---Summer-2027_2025300"
        )
        cmu = parse_ats_url(
            "https://cmu.wd115.myworkdayjobs.com/cmu/job/Pittsburgh-PA/Enabling-Mission-Capability-at-Scale-Intern---Summer-2027_2025300"
        )
        assert sei is not None and cmu is not None
        assert sei.job_id != cmu.job_id

        direct = parse_ats_url(
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/Machine-Learning-Engineer---Payroll_JR-0108977"
        )
        with_apply = parse_ats_url(
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CA-Pleasanton/Machine-Learning-Engineer---Payroll_JR-0108977/apply?ref=jobbys.vercel.app"
        )
        assert direct is not None and with_apply is not None
        assert direct.job_id == with_apply.job_id

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday",
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday/jobs",
            "https://workday.wd5.myworkdayjobs.com/Workday/job/",
            "https://workday.wd5.myworkdayjobs.com/Workday/job/apply",
            "https://workday.wd5.myworkdayjobs.com/en-US/extra/Workday/job/Role_123",
            "https://example.com/en-US/Workday/job/Role_123",
        ],
    )
    def test_non_job_or_unsupported_workday_urls_return_none(self, bad_url):
        assert parse_workday_url(bad_url) is None
        assert parse_ats_url(bad_url) is None
        assert build_workday_cxs_url(bad_url) is None

    def test_okgov_hiring_company_query_param_is_preserved_during_normalization(self):
        from src.project_files.url_normalizer import normalize_job_url

        url = "https://okgov.wd1.myworkdayjobs.com/en-US/okgovjobs/job/Oklahoma-County/Senior-Application-Developer_JR66448?hiringCompany=7a8d2de4e0861000cc58d49ed7390000&utm_source=serp"
        norm = normalize_job_url(url, "workday")
        assert "hiringCompany=7a8d2de4e0861000cc58d49ed7390000" in norm
        assert "utm_source" not in norm


class TestEligibilityExtractorScenarios:
    def test_scenario_1_explicit_worldwide_or_work_from_anywhere(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        desc = (
            "We are a distributed engineering team.\n"
            "Location: Work from anywhere — open to candidates worldwide."
        )
        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            description=desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.global_remote_explicit is True
        assert elig.nigeria_eligible is True
        assert any(f.dimension == "global_remote" for f in elig.facts)

    def test_scenario_1b_company_marketing_worldwide_does_not_claim_global_remote(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        desc = (
            "Guidewire's Generative AI team builds cloud solutions for P&C insurers worldwide "
            "and helps shape the future of the industry worldwide."
        )
        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            raw_location="United States - Remote",
            description=desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.global_remote_explicit is None
        assert elig.nigeria_eligible is None
        assert not any(f.dimension == "global_remote" for f in elig.facts)

    def test_scenario_2_remote_without_geo_disclosure_remains_unknown(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="Fully remote engineering role building distributed backend APIs.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.allowed_residence_countries is None
        assert elig.residence_restriction_confirmed is None
        assert elig.global_remote_explicit is None
        assert elig.nigeria_eligible is None

    def test_scenario_3_jsonld_restricted_region_excluding_nigeria(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            raw_workplace_type="TELECOMMUTE",
            description="Consultant en Technologie - Développement de solutions SaaS.",
            raw_fields={
                "applicantLocationRequirements": {"@type": "Country", "name": "Tunisia"},
                "jobLocationType": "TELECOMMUTE",
            },
            description_is_authentic=True,
            method=ExtractionMethod.JSON_LD,
        )
        assert elig is not None
        assert elig.allowed_residence_countries == ["Tunisia"]
        assert elig.residence_restriction_confirmed is True
        assert elig.nigeria_eligible is False

    def test_scenario_4_jsonld_restricted_region_including_nigeria(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            raw_workplace_type="TELECOMMUTE",
            description="Remote Platform Engineer.",
            raw_fields={
                "applicantLocationRequirements": {"@type": "Country", "name": "Nigeria"},
                "jobLocationType": "TELECOMMUTE",
            },
            description_is_authentic=True,
            method=ExtractionMethod.JSON_LD,
        )
        assert elig is not None
        assert elig.allowed_residence_countries == ["Nigeria"]
        assert elig.residence_restriction_confirmed is True
        assert elig.nigeria_eligible is True

    def test_scenario_5_explicit_residence_restriction_in_text(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        desc = "This is a remote position, however candidates must reside in the United States."
        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            description=desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.residence_restriction_confirmed is True
        assert elig.allowed_residence_countries == ["United States"]
        assert elig.nigeria_eligible is False

    def test_scenario_6_citizenship_and_clearance_kept_separate_from_residence_and_eeo_ignored(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        blueorigin_desc = (
            "Applicants for employment at Blue Origin must be a U.S. citizen or national, "
            "U.S. permanent resident, or lawfully admitted refugee.\n"
            "Ability to obtain a TS/SCI clearance is required.\n"
            "Relocation assistance is available."
        )
        elig = extract_eligibility(
            provider="workday",
            work_model=None,
            description=blueorigin_desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.citizenship_requirements == ["United States"]
        assert elig.security_clearance_required is not None
        assert "TS/SCI" in elig.security_clearance_required
        assert elig.allowed_residence_countries is None
        assert elig.relocation_assistance is True
        assert elig.relocation_required is None
        assert elig.nigeria_eligible is None

        # Negative guard: EEO boilerplate mentioning citizenship status must NOT trigger citizenship_requirements
        gm_eeo = (
            "All employment decisions are made on a non-discriminatory basis without regard to "
            "sex, race, color, national origin, citizenship status, religion, age, or disability."
        )
        elig_gm = extract_eligibility(
            provider="workday",
            work_model=None,
            description=gm_eeo,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig_gm is not None
        assert elig_gm.citizenship_requirements is None

    def test_scenario_7_office_country_or_multi_hub_list_not_treated_as_residence_ban(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        gsk_desc = (
            "If you are based in Cambridge, MA; Waltham, MA; Rockville, MD; or San Francisco, CA, "
            "the annual base salary for new hires in this position ranges $136,125 to $226,875.\n"
            "Our hubs include London, Berlin, and San Francisco."
        )
        elig = extract_eligibility(
            provider="workday",
            work_model=None,
            raw_fields={"country": {"descriptor": "United States of America"}},
            description=gsk_desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.physical_location_country == "United States"
        assert elig.allowed_residence_countries is None
        assert elig.residence_restriction_confirmed is None
        assert elig.nigeria_eligible is None

    def test_scenario_8_decision_2_domestic_work_auth_and_sponsorship_alone_yield_unknown(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        # Pure sponsorship unavailable -> None
        sponsorship_only = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="***Visa sponsorship is not available for this role.***",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert sponsorship_only is not None
        assert sponsorship_only.visa_sponsorship_status == "not_available"
        assert sponsorship_only.nigeria_eligible is None

        # Decision 2: Domestic work authorization + no sponsorship ALONE (no onsite/residence/payroll restriction)
        # must remain nigeria_eligible=None while extracting both as separate facts!
        cmu_desc = "Eligibility to work in the United States without visa sponsorship."
        work_auth_only = extract_eligibility(
            provider="workday",
            work_model=None,
            description=cmu_desc,
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert work_auth_only is not None
        assert work_auth_only.work_authorization_required == ["United States"]
        assert work_auth_only.visa_sponsorship_status == "not_available"
        assert work_auth_only.nigeria_eligible is None
        dims = {f.dimension for f in work_auth_only.facts}
        assert {"work_authorization", "visa_sponsorship"}.issubset(dims)

    def test_payroll_requirement_is_tracked_distinctly_and_blocks_incompatible_payroll(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="Candidates must be hired on US W-2 payroll in supported states.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.payroll_requirements == ["United States"]
        assert elig.nigeria_eligible is False

    def test_scenario_9_contractor_or_eor_does_not_override_explicit_residence_or_onsite(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        # Explicit global contractor -> True
        global_contractor = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="Engaged globally as an independent contractor (B2B) working from anywhere.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert global_contractor is not None
        assert global_contractor.employment_arrangement == "contractor"
        assert global_contractor.nigeria_eligible is True

        # Decision 2 safeguard: EOR / contractor mention must NOT override explicit residence restriction
        contractor_with_us_residence = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="Hired via Deel EOR or contractor arrangement, however candidates must reside in the United States.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert contractor_with_us_residence is not None
        assert contractor_with_us_residence.employment_arrangement == "eor"
        assert contractor_with_us_residence.allowed_residence_countries == ["United States"]
        assert contractor_with_us_residence.nigeria_eligible is False

    def test_hybrid_attendance_safeguard_requires_foreign_attendance_obligation(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        # Explicit 3-day in-office obligation in foreign country (GM real phrasing) -> False
        gm_hybrid = extract_eligibility(
            provider="workday",
            work_model="hybrid",
            raw_fields={"country": {"descriptor": "United States of America"}},
            description="Hybrid: This internship is categorized as on-site. The selected intern is expected to report to the office 3 days a week.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert gm_hybrid is not None
        assert gm_hybrid.nigeria_eligible is False
        assert any(f.dimension == "hybrid_attendance" for f in gm_hybrid.facts)

        # CIBC real phrasing / unconfirmed proportion -> must NOT invent nigeria_eligible=False
        cibc_hybrid = extract_eligibility(
            provider="workday",
            work_model="hybrid",
            raw_fields={"country": {"descriptor": "Canada"}},
            description="Details on your work arrangement (proportion of on-site and remote work) will be discussed at the time of your interview.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert cibc_hybrid is not None
        assert cibc_hybrid.physical_location_country == "Canada"
        assert cibc_hybrid.nigeria_eligible is None

    def test_snippet_only_posting_does_not_infer_eligibility_from_prose(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model=None,
            description="Work from anywhere! Must reside in United States!",
            description_is_authentic=False,
            method=ExtractionMethod.SNIPPET,
        )
        assert elig is None

    def test_timezone_constraint_extracted_without_blocking_nigeria(self):
        from src.project_files.eligibility_extractor import extract_eligibility

        elig = extract_eligibility(
            provider="workday",
            work_model="remote",
            description="Must have at least 4 hours overlap with EST business hours.",
            description_is_authentic=True,
            method=ExtractionMethod.ATS_API,
        )
        assert elig is not None
        assert elig.timezone_requirements is not None
        assert "EST" in elig.timezone_requirements
        assert elig.nigeria_eligible is None


class TestWorkdayExtractionServiceAndFieldMapping:
    @pytest.mark.parametrize(
        "raw_type,expected_model",
        [
            ("Télétravail partiel", "hybrid"),
            ("Télétravail", "remote"),
            ("Home / Remote", "remote"),
            ("Partially Remote", "hybrid"),
            ("Flexible", None),
        ],
    )
    def test_workday_bilingual_work_model_enums(self, raw_type, expected_model):
        from src.project_files.work_model import resolve_work_model

        res = resolve_work_model(workplace_type=raw_type)
        assert res.value == expected_model
        if expected_model is not None:
            assert res.source == "api_enum"

    def test_decision_1_facility_code_appends_country_and_preserves_raw_location(self):
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
        from src.project_files.models import ValidationStatus

        raw = RawJobPosting(
            provider="workday",
            source_url="https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/Role_51590806",
            provider_job_id="dxcjobs__Role_51590806",
            company_slug="dxctechnology",
            raw_title="Forward Deployed Engineer",
            raw_company="DXC Technology",
            raw_location="ESP - MD - LAS ROZAS",
            raw_description="<p>Build cloud AI systems.</p>",
            raw_fields={"country": {"descriptor": "Spain"}},
            scraped_at=datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc),
        )
        canonical = JobExtractionService.extract(raw)
        assert canonical.raw_location == "ESP - MD - LAS ROZAS"
        assert canonical.location == "ESP - MD - LAS ROZAS, Spain"
        assert canonical.eligibility is not None
        assert canonical.eligibility.physical_location_country == "Spain"
        assert any(
            e.field == CanonicalJobField.RAW_LOCATION
            and e.raw_value == "ESP - MD - LAS ROZAS"
            and e.validation_status == ValidationStatus.ACCEPTED
            for e in canonical.field_evidence
        )

    @pytest.mark.parametrize(
        "raw_loc,country_desc,expected_loc",
        [
            ("Canada, BC, Vancouver, Canada", "Canada", "Canada, BC, Vancouver"),
            ("Pune, India, India", "India", "Pune, India"),
            ("India - Hyderabad, India", "India", "India - Hyderabad"),
            ("IND BNGL FL2-3 TWR 3", "India", "IND BNGL FL2-3 TWR 3, India"),
            ("US FL JAX 347", "United States of America", "US FL JAX 347, United States"),
            ("Pittsburgh, PA", "United States of America", "Pittsburgh, PA"),
            ("Montréal, QC", "Canada", "Montréal, QC"),
        ],
    )
    def test_location_dedup_and_facility_code_rules(self, raw_loc, country_desc, expected_loc):
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting

        raw = RawJobPosting(
            provider="workday",
            source_url="https://acme.wd5.myworkdayjobs.com/Careers/job/Role_1",
            raw_title="Software Engineer",
            raw_company="Acme",
            raw_location=raw_loc,
            raw_description="<p>Engineering role.</p>",
            raw_fields={"country": {"descriptor": country_desc}},
        )
        canonical = JobExtractionService.extract(raw)
        assert canonical.raw_location == raw_loc
        assert canonical.location == expected_loc

    def test_workday_bold_english_and_spanish_requirements_extracted(self):
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting

        raw_es = RawJobPosting(
            provider="workday",
            source_url="https://dxc.wd1.myworkdayjobs.com/DXCJobs/job/Role_1",
            raw_title="Ingeniero AI",
            raw_company="DXC",
            raw_description=(
                "<p><strong>Descripción del puesto:</strong></p><p>Trabajar en cloud.</p>"
                "<p><strong>Requisitos:</strong></p><ul><li>Python</li><li>Kubernetes</li></ul>"
                "<p><strong>Beneficios:</strong></p><ul><li>Seguro médico</li></ul>"
            ),
        )
        canonical_es = JobExtractionService.extract(raw_es)
        assert canonical_es.requirements is not None
        assert "Python" in canonical_es.requirements
        assert "Kubernetes" in canonical_es.requirements
        assert "Seguro" not in canonical_es.requirements

        raw_en = RawJobPosting(
            provider="workday",
            source_url="https://amd.wd1.myworkdayjobs.com/Careers/job/Role_2",
            raw_title="Staff ML Engineer",
            raw_company="AMD",
            raw_description=(
                "<p><strong>Basic Qualifications:</strong></p>"
                "<ul><li>5+ years PyTorch</li><li>Distributed training</li></ul>"
                "<p><strong>Compensation:</strong></p><p>$180,000 - $220,000</p>"
            ),
        )
        canonical_en = JobExtractionService.extract(raw_en)
        assert canonical_en.requirements is not None
        assert "5+ years PyTorch" in canonical_en.requirements
        assert "$180,000" not in canonical_en.requirements

    def test_workday_date_semantics_reject_future_start_date_and_coarse_relative_buckets(self):
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
        from src.project_files.models import ValidationStatus

        scraped = datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc)

        # Future startDate (> scraped_at + 1d) must be rejected
        raw_future = RawJobPosting(
            provider="workday",
            source_url="https://acme.wd5.myworkdayjobs.com/Careers/job/Role_1",
            raw_title="Software Engineer",
            raw_company="Acme",
            raw_date="2026-12-01",
            raw_fields={"date_field_name": "startDate", "postedOn": "Posted Today"},
            scraped_at=scraped,
        )
        canonical_future = JobExtractionService.extract(raw_future)
        assert canonical_future.posted_at is None
        assert any(
            e.field == CanonicalJobField.POSTED_AT and e.validation_status == ValidationStatus.REJECTED
            for e in canonical_future.field_evidence
        )

        # Coarse "Posted 30+ Days Ago" must NEVER fabricate a timestamp
        raw_coarse = RawJobPosting(
            provider="workday",
            source_url="https://acme.wd5.myworkdayjobs.com/Careers/job/Role_2",
            raw_title="Software Engineer",
            raw_company="Acme",
            raw_date="Posted 30+ Days Ago",
            scraped_at=scraped,
        )
        canonical_coarse = JobExtractionService.extract(raw_coarse)
        assert canonical_coarse.posted_at is None
        assert any(
            e.field == CanonicalJobField.POSTED_AT
            and e.validation_status == ValidationStatus.REJECTED
            and e.raw_value == "Posted 30+ Days Ago"
            for e in canonical_coarse.field_evidence
        )


class TestWorkdayClientAndIntegration:
    """Scenario 10 & 11: Single authoritative WorkdayClient, JSON-LD fallback, adapter, deduplicator, allowlist."""

    def test_workday_client_registered_in_ats_clients(self):
        from src.project_files.ats_api_client import ATS_CLIENTS, WorkdayClient

        assert "workday" in ATS_CLIENTS
        assert isinstance(ATS_CLIENTS["workday"], WorkdayClient)

    @pytest.mark.anyio
    async def test_cxs_200_and_enricher_delegation_single_authoritative_path(self, monkeypatch, tmp_path):
        from pathlib import Path
        import httpx
        from src.project_files.ats_api_client import ATS_CLIENTS
        from src.project_files.ats_page_enricher import enrich_ats_page_result
        from src.project_files.ats_url_parser import parse_ats_url
        from src.project_files.cache_store import cache_store
        from src.project_files.extraction_outcome import ExtractionOutcome

        monkeypatch.setattr(cache_store, "db_path", str(tmp_path / "cache.sqlite"))
        cache_store._ensure_db()

        cxs_bytes = Path("tests/fixtures/real/workday/cxs_4dcb1862.json").read_bytes()
        url = (
            "https://dxctechnology.wd1.myworkdayjobs.com/en-US/DXCJobs/job/"
            "ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806/apply?source=Serp"
        )
        canonical_url = (
            "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/"
            "ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"
        )
        calls: list[str] = []

        def handler(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            if "/wday/cxs/" in str(req.url):
                return httpx.Response(200, content=cxs_bytes, headers={"Content-Type": "application/json; charset=utf-8"})
            return httpx.Response(500)

        parsed = parse_ats_url(url)
        assert parsed is not None
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            listing, res = await ATS_CLIENTS["workday"].fetch_result(parsed, client, query_used="agentic ai")

        assert res.outcome == ExtractionOutcome.SUCCESS
        assert listing is not None
        assert listing.data_source == "api"
        assert listing.raw_location == "ESP - MD - LAS ROZAS"
        assert listing.location == "ESP - MD - LAS ROZAS, Spain"
        assert listing.apply_url == url
        assert listing.requirements is not None
        assert "Kubernetes" in listing.requirements
        assert listing.eligibility is not None
        assert listing.eligibility.physical_location_country == "Spain"
        assert len(calls) == 1
        assert "/wday/cxs/dxctechnology/DXCJobs/job/" in calls[0]

        # Enricher must delegate cleanly without invoking duplicate HTTP logic
        calls.clear()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            enriched, res2 = await enrich_ats_page_result(
                url=canonical_url,
                provider="workday",
                search_title="DXC Role",
                snippet="",
                query_used="agentic ai",
                client=client,
            )
        assert res2.outcome == ExtractionOutcome.SUCCESS
        assert enriched is not None
        assert enriched.location == "ESP - MD - LAS ROZAS, Spain"
        assert len(calls) == 1

    @pytest.mark.anyio
    @pytest.mark.parametrize("failure_mode", ["403", "404", "timeout", "waf"])
    async def test_scenario_10_jsonld_fallback_against_real_html_fixtures(self, failure_mode: str):
        import re
        from pathlib import Path
        import httpx
        from bs4 import BeautifulSoup
        from src.project_files.ats_api_client import ATS_CLIENTS
        from src.project_files.ats_url_parser import parse_ats_url
        from src.project_files.extraction_outcome import ExtractionOutcome

        dxc_html = Path("tests/fixtures/real/workday/4dcb1862.html").read_bytes()
        dxc_url = (
            "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/"
            "ESP---MD---LAS-ROZAS/Forward-Deployed-Engineer---Cloud---Agentic-AI_51590806"
        )
        deloitte_html = Path("tests/fixtures/real/workday/760bc3cc.html").read_bytes()
        deloitte_url = (
            "https://fina.wd103.myworkdayjobs.com/en-US/DeloitteRecrute/job/"
            "Tunis-Deloitte-Conseil/Consultant-e--Expriment-e--en-Technologie---Dveloppement-de-solutions-SaaS_R-9299"
        )

        def make_transport(html_bytes: bytes):
            def handler(req: httpx.Request) -> httpx.Response:
                if "/wday/cxs/" in str(req.url):
                    if failure_mode == "403":
                        return httpx.Response(403)
                    if failure_mode == "404":
                        return httpx.Response(404)
                    if failure_mode == "timeout":
                        raise httpx.ReadTimeout("CXS timed out", request=req)
                    if failure_mode == "waf":
                        return httpx.Response(
                            200,
                            text="<html><title>Just a moment...</title><body>Checking your browser before accessing</body></html>",
                            headers={"cf-mitigated": "challenge"},
                        )
                return httpx.Response(200, content=html_bytes, headers={"Content-Type": "text/html"})

            return httpx.MockTransport(handler)

        def _word_completeness(source_html: bytes, extracted_md: str) -> float:
            import json as _json

            soup = BeautifulSoup(source_html.decode("utf-8", errors="replace"), "lxml")
            desc_html = ""
            for s in soup.find_all("script", type="application/ld+json"):
                doc = _json.loads(s.string or "{}")
                if isinstance(doc, dict) and doc.get("@type") == "JobPosting":
                    desc_html = doc.get("description", "")
                    break
            src_words = re.findall(r"\w+", BeautifulSoup(desc_html, "lxml").get_text(" ", strip=True).lower())
            out_words = set(re.findall(r"\w+", extracted_md.lower()))
            assert len(src_words) > 0
            covered = sum(1 for w in src_words if w in out_words)
            return covered / len(src_words)

        parsed_dxc = parse_ats_url(dxc_url)
        assert parsed_dxc is not None
        async with httpx.AsyncClient(transport=make_transport(dxc_html)) as client:
            dxc_job, dxc_res = await ATS_CLIENTS["workday"].fetch_result(parsed_dxc, client)

        assert dxc_res.outcome == ExtractionOutcome.SUCCESS
        assert dxc_job is not None
        assert dxc_job.data_source == "scrape"
        assert dxc_job.title == "Forward Deployed Engineer — Cloud & Agentic AI"
        assert dxc_job.employment_type == "full_time"
        assert dxc_job.description is not None
        assert "&amp;" not in dxc_job.description
        assert _word_completeness(dxc_html, dxc_job.description) >= 0.85
        assert dxc_job.eligibility is not None
        assert dxc_job.eligibility.physical_location_country == "Spain"

        parsed_deloitte = parse_ats_url(deloitte_url)
        assert parsed_deloitte is not None
        async with httpx.AsyncClient(transport=make_transport(deloitte_html)) as client:
            tn_job, tn_res = await ATS_CLIENTS["workday"].fetch_result(parsed_deloitte, client)

        assert tn_res.outcome == ExtractionOutcome.SUCCESS
        assert tn_job is not None
        assert tn_job.data_source == "scrape"
        assert "Expérimenté(e)" in tn_job.title
        assert tn_job.work_model == "remote"
        assert tn_job.description is not None
        assert _word_completeness(deloitte_html, tn_job.description) >= 0.85
        assert tn_job.eligibility is not None
        assert "Tunisia" in tn_job.eligibility.allowed_residence_countries
        assert tn_job.eligibility.nigeria_eligible is False

    @pytest.mark.anyio
    async def test_workday_expired_posting_available_false_returns_not_found(self):
        from pathlib import Path
        import httpx
        from src.project_files.ats_api_client import ATS_CLIENTS
        from src.project_files.ats_url_parser import parse_ats_url
        from src.project_files.extraction_outcome import ExtractionOutcome

        expired_html = Path("tests/fixtures/real/workday/d5f8651a.html").read_bytes()
        url = (
            "https://pwc.wd3.myworkdayjobs.com/en-US/Global_Experienced_Careers/job/"
            "Mumbai/Senior-Associate-Backend_12345"
        )

        def handler(req: httpx.Request) -> httpx.Response:
            if "/wday/cxs/" in str(req.url):
                return httpx.Response(404)
            return httpx.Response(200, content=expired_html, headers={"Content-Type": "text/html"})

        parsed = parse_ats_url(url)
        assert parsed is not None
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            job, res = await ATS_CLIENTS["workday"].fetch_result(parsed, client)

        assert job is None
        assert res.outcome == ExtractionOutcome.NOT_FOUND

    @pytest.mark.anyio
    async def test_workday_total_failure_degrades_to_snippet_without_eligibility(self):
        import httpx
        from src.project_files.ats_api_client import ATS_CLIENTS
        from src.project_files.ats_url_parser import parse_ats_url
        from src.project_files.extraction_outcome import ExtractionOutcome

        url = "https://acme.wd5.myworkdayjobs.com/Careers/job/Remote/Engineer_REQ1"

        def handler(req: httpx.Request) -> httpx.Response:
            if "/wday/cxs/" in str(req.url):
                return httpx.Response(403)
            return httpx.Response(503)

        parsed = parse_ats_url(url)
        assert parsed is not None
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            job, res = await ATS_CLIENTS["workday"].fetch_result(
                parsed, client, fallback_snippet="Remote Engineer - Global"
            )

        assert res.outcome == ExtractionOutcome.RETRYABLE_ERROR
        assert job is not None
        assert job.data_source == "snippet"
        assert job.degraded_from == "api"
        assert job.eligibility is None

    def test_scenario_11_adapter_allowlist_and_deduplicator(self):
        from src.api.allowlist import ADMIN_JOB_FIELDS, USER_JOB_FIELDS, serialize_event_for_user
        from src.project_files.canonical_job_adapter import CanonicalJobAdapter
        from src.project_files.deduplicator import GlobalDeduplicator, is_material_improvement, merge_listings
        from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
        from src.project_files.models import ExtractionMethod, JobListing, ResultsBatch

        assert "eligibility" in USER_JOB_FIELDS
        assert "raw_location" in ADMIN_JOB_FIELDS
        assert "eligibility" not in ADMIN_JOB_FIELDS
        assert "raw_location" not in USER_JOB_FIELDS

        raw = RawJobPosting(
            provider="workday",
            source_url="https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806",
            provider_job_id="dxcjobs__Role_51590806",
            company_slug="dxctechnology",
            raw_title="Forward Deployed Engineer",
            raw_company="DXC Technology",
            raw_location="ESP - MD - LAS ROZAS",
            raw_description="<p>Hybrid role requiring 3 days per week in the Madrid office. Spanish work permit required.</p>",
            raw_fields={"country": {"descriptor": "Spain"}},
        )
        canonical = JobExtractionService.extract(raw)
        # Verify JSON_LD evidence maps to scrape in CanonicalJobAdapter
        canonical_jsonld = canonical.model_copy(
            update={
                "field_evidence": [
                    ev.model_copy(update={"method": ExtractionMethod.JSON_LD})
                    for ev in canonical.field_evidence
                ]
            }
        )
        listing_jsonld = CanonicalJobAdapter.to_listing(canonical_jsonld)
        assert listing_jsonld.data_source == "scrape"
        assert listing_jsonld.raw_location == "ESP - MD - LAS ROZAS"
        assert listing_jsonld.eligibility is not None
        assert listing_jsonld.eligibility.nigeria_eligible is False

        roundtrip = CanonicalJobAdapter.from_listing(listing_jsonld)
        assert roundtrip.raw_location == "ESP - MD - LAS ROZAS"
        assert roundtrip.eligibility is not None
        assert roundtrip.eligibility.nigeria_eligible is False

        import json as _json

        payload_raw = serialize_event_for_user(
            "results", ResultsBatch(batch=[listing_jsonld], total_so_far=1)
        )
        assert payload_raw is not None
        payload = _json.loads(payload_raw)
        first_job = payload["batch"][0]
        assert "eligibility" in first_job
        assert first_job["eligibility"]["nigeria_eligible"] is False
        assert "raw_location" not in first_job

        # Deduplicator: /apply + locale variants collapse and upgrade eligibility/raw_location
        snippet_job = JobListing(
            id="workday:dxctechnology:1",
            title="Forward Deployed Engineer",
            company="DXC Technology",
            company_slug="dxctechnology",
            provider_job_id="dxcjobs__Role_51590806",
            location="Madrid",
            url="https://dxctechnology.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806/apply?source=LinkedIn",
            apply_url="https://dxctechnology.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806/apply?source=LinkedIn",
            source_url="https://dxctechnology.wd1.myworkdayjobs.com/en-US/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806/apply?source=LinkedIn",
            provider="workday",
            data_source="snippet",
            scraped_at=datetime.now(timezone.utc),
            query_used="engineer",
            ats_source="workday",
        )
        cxs_job = listing_jsonld.model_copy(
            update={
                "data_source": "api",
                "url": "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806?ref=board",
                "apply_url": "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806?ref=board",
                "source_url": "https://dxctechnology.wd1.myworkdayjobs.com/DXCJobs/job/ESP---MD---LAS-ROZAS/Role_51590806?ref=board",
            }
        )
        assert is_material_improvement(snippet_job, cxs_job) is True
        merged = merge_listings(snippet_job, cxs_job)
        assert merged.raw_location == "ESP - MD - LAS ROZAS"
        assert merged.eligibility is not None and merged.eligibility.nigeria_eligible is False

        dedup = GlobalDeduplicator()
        deduped = dedup.deduplicate([snippet_job, cxs_job])
        assert len(deduped) == 1
        assert deduped[0].eligibility is not None
        assert deduped[0].eligibility.nigeria_eligible is False

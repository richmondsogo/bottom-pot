"""
Tests for work model resolution ladder, provenance, and LinkedIn recruiter tags (Phase 2).
"""

from src.project_files.work_model import (
    resolve_work_model,
    strip_li_tags,
)


class TestApiEnum:
    def test_explicit_api_enums(self):
        r = resolve_work_model(workplace_type="Remote")
        assert r.value == "remote"
        assert r.source == "api_enum"
        assert r.evidence == "Remote"

        r = resolve_work_model(workplace_type="hybrid")
        assert r.value == "hybrid"
        assert r.source == "api_enum"

        r = resolve_work_model(workplace_type="onsite")
        assert r.value == "in_person"
        assert r.source == "api_enum"

        r = resolve_work_model(workplace_type="Office-based")
        assert r.value == "in_person"

    def test_flexible_is_not_enum_evidence(self):
        # Flexible must not map to hybrid in api_enum
        r = resolve_work_model(workplace_type="Flexible")
        assert r.value is None

    def test_boolean_flags_are_not_evidence(self):
        # is_remote is ignored entirely
        assert resolve_work_model(is_remote=True).value is None
        assert resolve_work_model(is_remote=False).value is None
        assert resolve_work_model(workplace_type=True).value is None
        assert resolve_work_model(workplace_type=False).value is None


class TestJsonLd:
    def test_telecommute(self):
        r = resolve_work_model(jsonld_location_type="TELECOMMUTE")
        assert r.value == "remote"
        assert r.source == "jsonld"
        assert r.evidence == "jobLocationType=TELECOMMUTE"

    def test_other_jsonld(self):
        r = resolve_work_model(jsonld_location_type="PHYSICAL")
        assert r.value is None


class TestLiTag:
    def test_li_remote(self):
        r = resolve_work_model(trusted_description="We are hiring for this role ...#LI-Remote")
        assert r.value == "remote"
        assert r.source == "li_tag"
        assert r.evidence == "#LI-Remote"

    def test_other_li_tags_ignored(self):
        r = resolve_work_model(trusted_description="Internal posting code #LI-JD1 and #LI-DNI")
        assert r.value is None

    def test_conflicting_li_tags_yield_none(self):
        r = resolve_work_model(trusted_description="#LI-Remote #LI-Hybrid in description")
        assert r.value is None

    def test_api_enum_disagrees_with_li_tag_keeps_api_enum(self, caplog):
        # api_enum "Hybrid" + "#LI-Remote" -> hybrid with a logged disagreement
        r = resolve_work_model(workplace_type="Hybrid", trusted_description="Come join us #LI-Remote")
        assert r.value == "hybrid"
        assert r.source == "api_enum"
        assert r.evidence == "Hybrid"

    def test_jsonld_disagrees_with_li_tag_keeps_jsonld(self):
        r = resolve_work_model(jsonld_location_type="TELECOMMUTE", trusted_description="Join us #LI-Hybrid")
        assert r.value == "remote"
        assert r.source == "jsonld"

    def test_entity_encoded_li_tag(self):
        # entity-encoded "&lt;p&gt;...#LI-Hybrid&lt;/p&gt;" -> hybrid
        r = resolve_work_model(trusted_description="&lt;p&gt;Great role...#LI-Hybrid&lt;/p&gt;")
        assert r.value == "hybrid"
        assert r.source == "li_tag"
        assert r.evidence == "#LI-Hybrid"

    def test_li_onsite_weak_fallback(self):
        # Treat #LI-Onsite as weak: don't return in_person from it unless nothing else is available
        # AND it is the only signal; evidence must say "li_tag_onsite".
        r = resolve_work_model(trusted_description="Role details: #LI-Onsite")
        assert r.value == "in_person"
        assert r.source == "li_tag"
        assert r.evidence == "li_tag_onsite"

    def test_li_onsite_overridden_by_location(self):
        # When location has remote signal, weak onsite is not applied
        r = resolve_work_model(location="Remote", trusted_description="Details: #LI-Onsite")
        assert r.value == "remote"
        assert r.source == "location"

    def test_li_tag_disagreement_with_description_scan_yields_none(self):
        # If the tag disagrees with a single description-scan result -> None
        r = resolve_work_model(
            trusted_description="Role details #LI-Remote",
            description="You will work 3 days in the office each week",
            description_ok=True,
        )
        assert r.value is None

    def test_strip_li_tags(self):
        text = "<p>Join our team #LI-Remote today! Code #LI-JD1 applies.</p>"
        cleaned = strip_li_tags(text)
        assert "#LI-Remote" not in cleaned
        assert "#LI-JD1" not in cleaned
        assert "Join our team today! Code applies." in cleaned


class TestLocation:
    def test_location_remote(self):
        r = resolve_work_model(location="Remote - United States")
        assert r.value == "remote"
        assert r.source == "location"

    def test_location_hybrid(self):
        r = resolve_work_model(location="Hybrid - London, UK")
        assert r.value == "hybrid"
        assert r.source == "location"

    def test_physical_location_without_signal_is_none(self):
        # Unknown beats wrong: location "Atlanta, GA" + no signal -> None
        r = resolve_work_model(location="Atlanta, GA")
        assert r.value is None
        assert r.source is None


class TestTitle:
    def test_title_parentheses(self):
        r = resolve_work_model(title="Senior Engineer (Remote)")
        assert r.value == "remote"
        assert r.source == "title"
        assert "(Remote)" in r.evidence

    def test_title_delimiters(self):
        r = resolve_work_model(title="Frontend Engineer - Hybrid")
        assert r.value == "hybrid"
        assert r.source == "title"

        r = resolve_work_model(title="Platform Engineer [On-site]")
        assert r.value == "in_person"
        assert r.source == "title"

    def test_title_false_positive_prevention(self):
        # "Hybrid Cloud Architect" must NOT trigger hybrid
        r = resolve_work_model(title="Hybrid Cloud Architect")
        assert r.value is None


class TestDescriptionScan:
    def test_description_ok_must_be_true(self):
        # Without description_ok=True, description is ignored
        r = resolve_work_model(description="Fully remote position", description_ok=False)
        assert r.value is None

    def test_hybrid_quantum_and_fully_remote(self):
        # "hybrid quantum-classical solutions ... fully remote position" -> remote
        text = "Our team researches hybrid quantum-classical solutions for optimization. This is a fully remote position."
        r = resolve_work_model(description=text, description_ok=True)
        assert r.value == "remote"
        assert r.source == "description"

    def test_flexible_spending_accounts(self):
        r = resolve_work_model(description="We offer generous flexible spending accounts.", description_ok=True)
        assert r.value is None

    def test_distributed_systems_engineer(self):
        r = resolve_work_model(description="Looking for a distributed systems engineer.", description_ok=True)
        assert r.value is None

    def test_negation_remote(self):
        # "This is not a remote position" -> not remote
        r = resolve_work_model(description="Please note that this is not a remote position.", description_ok=True)
        assert r.value is None

    def test_negation_hybrid(self):
        # "not hybrid" -> not hybrid
        r = resolve_work_model(description="This role is strictly not hybrid.", description_ok=True)
        assert r.value is None

    def test_hybrid_days_in_office(self):
        # "3 days in the office" -> hybrid
        r = resolve_work_model(description="Employees work 3 days in the office each week.", description_ok=True)
        assert r.value == "hybrid"
        assert r.source == "description"

    def test_conflicting_description_signals_yield_none(self):
        text = "This is a fully remote position with 3 days in the office required."
        r = resolve_work_model(description=text, description_ok=True)
        assert r.value is None

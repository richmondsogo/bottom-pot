"""Cross-language verification of shared eligibility test vectors."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
from src.extraction.eligibility_extractor import (
    evaluate_eligibility_for_country,
    extract_eligibility,
)
from src.extraction.eligibility_labels import build_objective_scope_label
from src.core.models import JobEligibility

VECTORS_PATH = Path(__file__).resolve().parent / "vectors" / "eligibility.json"
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]

client = TestClient(app)


def test_eligibility_vectors_extraction_and_labels():
    assert len(VECTORS) >= 12
    for vec in VECTORS:
        vid = vec["id"]
        ext_in = vec.get("extraction_input")
        if ext_in:
            extracted = extract_eligibility(
                provider=ext_in["provider"],
                work_model=ext_in.get("work_model"),
                location=ext_in.get("location"),
                raw_location=ext_in.get("raw_location"),
                description=ext_in.get("description"),
                raw_fields=ext_in.get("raw_fields"),
                description_is_authentic=True,
            )
            assert extracted is not None, f"{vid}: extract_eligibility returned None"
            if "expected_classification" in ext_in:
                assert extracted.classification == ext_in["expected_classification"], f"{vid} classification"
            if "expected_global_remote_explicit" in ext_in:
                assert bool(extracted.global_remote_explicit) is ext_in["expected_global_remote_explicit"], (
                    f"{vid} global_remote_explicit"
                )
            if "expected_allowed_country_codes_superset" in ext_in:
                assert set(extracted.allowed_country_codes or []) >= set(
                    ext_in["expected_allowed_country_codes_superset"]
                ), f"{vid} allowed_country_codes superset"
            if "expected_allowed_country_codes_exact" in ext_in:
                assert set(extracted.allowed_country_codes or []) == set(
                    ext_in["expected_allowed_country_codes_exact"]
                ), f"{vid} allowed_country_codes exact"
            if "expected_allowed_regions_exact" in ext_in:
                assert set(extracted.allowed_regions or []) == set(
                    ext_in["expected_allowed_regions_exact"]
                ), f"{vid} allowed_regions exact"

            scope_from_extracted = build_objective_scope_label(
                extracted,
                work_model=ext_in.get("work_model"),
                location=ext_in.get("location"),
            )
            assert extracted.objective_scope_label == scope_from_extracted, f"{vid} extracted objective_scope_label"

        elig = JobEligibility.model_validate(vec["eligibility"])
        scope = build_objective_scope_label(
            elig,
            work_model=vec.get("work_model"),
            location=vec.get("location"),
        )
        assert scope == vec["expected_objective_scope_label"], f"{vid} objective_scope_label"

        for country_code, exp in vec["expected_assessments"].items():
            assessment = evaluate_eligibility_for_country(
                elig,
                country_code,
                work_model=vec.get("work_model"),
                location=vec.get("location"),
            )
            assert assessment.status == exp["status"], f"{vid} [{country_code}] status"
            if "summary_contains" in exp:
                assert exp["summary_contains"] in (assessment.summary_label or ""), (
                    f"{vid} [{country_code}] summary {assessment.summary_label!r}"
                )


def test_eligibility_evaluate_endpoint_matches_vectors():
    sample_vectors = VECTORS
    countries = sorted({cc for vec in sample_vectors for cc in vec["expected_assessments"]})

    for country_code in countries:
        matching_vectors = [vec for vec in sample_vectors if country_code in vec["expected_assessments"]]
        resp = client.post(
            "/api/eligibility/evaluate",
            json={
                "applicant_country": country_code.lower(),
                "jobs": [
                    {
                        "id": vec["id"],
                        "eligibility": vec["eligibility"],
                        "work_model": vec.get("work_model"),
                        "location": vec.get("location"),
                    }
                    for vec in matching_vectors
                ],
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["applicant_country_code"] == country_code
        for vec in matching_vectors:
            got = payload["assessments"][vec["id"]]
            exp = vec["expected_assessments"][country_code]
            assert got["status"] == exp["status"], f"endpoint {vec['id']} [{country_code}]"
            if "summary_contains" in exp:
                assert exp["summary_contains"] in (got.get("summary_label") or ""), (
                    f"endpoint {vec['id']} [{country_code}] summary"
                )


def test_eligibility_evaluate_endpoint_rejects_invalid_country_code():
    resp = client.post(
        "/api/eligibility/evaluate",
        json={"applicant_country": "ZZZ", "jobs": []},
    )
    assert resp.status_code == 422


def test_eligibility_evaluate_endpoint_tolerates_legacy_undisclosed_fields():
    resp = client.post(
        "/api/eligibility/evaluate",
        json={
            "applicant_country": "NG",
            "jobs": [
                {
                    "id": "workday:canonical:legacy",
                    "work_model": "remote",
                    "location": "Remote, Worldwide",
                    "eligibility": {
                        "classification": "worldwide",
                        "global_remote_explicit": True,
                        "visa_sponsorship_status": "undisclosed",
                        "employment_arrangement": "unknown",
                    },
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["assessments"]["workday:canonical:legacy"]["status"] == "eligible"

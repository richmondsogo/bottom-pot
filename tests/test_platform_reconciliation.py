"""
Tests for Platform Inventory Reconciliation and Provider Fan-Out.

Proves:
- Exactly 18 ATS platforms configured in backend ATS_PLATFORMS.
- Exactly 3 active Nigerian platforms in NIGERIAN_SCRAPERS.
- Total 21 authoritative platforms supported across Bottom Pot.
- Default search queries all 18 ATS platforms.
- Individual platform selection correctly filters without unintended exclusions.
- Frontend ALL_PLATFORMS inventory is in exact synchrony with backend inventory.
"""

from pathlib import Path
import re
import pytest

from src.project_files.config import ATS_PLATFORMS
from src.project_files.nigerian_scrapers import NIGERIAN_SCRAPERS
from src.project_files.query_builder import ATS_DOMAINS, build_ats_queries
from src.project_files.models import SearchParams


EXPECTED_18_ATS = {
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "bamboohr",
    "jobvite",
    "smartrecruiters",
    "icims",
    "personio",
    "teamtailor",
    "recruitee",
    "breezy",
    "workday",
    "taleo",
    "jobadder",
    "jazzhr",
    "avature",
    "successfactors",
}

EXPECTED_3_NIGERIAN = {
    "jobberman",
    "myjobmag",
    "hotnigerianjobs",
}


def test_backend_ats_inventory_contains_all_18_platforms():
    actual_slugs = {p.name for p in ATS_PLATFORMS}
    assert actual_slugs == EXPECTED_18_ATS
    assert len(ATS_PLATFORMS) == 18


def test_backend_nigerian_inventory_contains_all_3_sources():
    actual_scrapers = {s.site_name.lower() for s in NIGERIAN_SCRAPERS}
    assert actual_scrapers == EXPECTED_3_NIGERIAN
    assert len(NIGERIAN_SCRAPERS) == 3


def test_default_ats_query_builder_queries_all_18_platforms():
    params = SearchParams(job_title="Software Engineer")
    queries = build_ats_queries(params, platforms=None)
    assert set(queries.keys()) == EXPECTED_18_ATS
    assert len(queries) == 18
    for platform, query in queries.items():
        assert query.startswith(f"site:{ATS_DOMAINS[platform]}")
        assert '"Software Engineer"' in query


def test_custom_platform_selection_filters_cleanly():
    params = SearchParams(job_title="Backend Developer")
    selected = ["greenhouse", "lever", "ashby"]
    queries = build_ats_queries(params, platforms=selected)
    assert set(queries.keys()) == set(selected)
    assert len(queries) == 3


def test_excluding_one_platform_does_not_exclude_unrelated_platforms():
    params = SearchParams(job_title="Data Scientist")
    all_21 = list(EXPECTED_18_ATS | EXPECTED_3_NIGERIAN)
    # User deselects only smartrecruiters
    selected = [p for p in all_21 if p != "smartrecruiters"]
    queries = build_ats_queries(params, platforms=selected)

    # 17 ATS platforms should be queried (all except smartrecruiters)
    expected_queried = EXPECTED_18_ATS - {"smartrecruiters"}
    assert set(queries.keys()) == expected_queried
    assert len(queries) == 17
    assert "smartrecruiters" not in queries
    assert "icims" in queries
    assert "jobadder" in queries
    assert "jazzhr" in queries
    assert "avature" in queries
    assert "successfactors" in queries


def test_frontend_constants_synchrony_with_backend_inventory():
    constants_path = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "lib"
        / "constants.ts"
    )
    content = constants_path.read_text(encoding="utf-8")

    # Extract all { id: '...' } in ALL_PLATFORMS
    platform_ids = set(re.findall(r"id:\s*'([^']+)'", content))

    expected_all_21 = EXPECTED_18_ATS | EXPECTED_3_NIGERIAN
    assert platform_ids == expected_all_21, (
        f"Frontend platform list does not match backend. "
        f"Missing: {expected_all_21 - platform_ids}, Extra: {platform_ids - expected_all_21}"
    )
    assert len(platform_ids) == 21

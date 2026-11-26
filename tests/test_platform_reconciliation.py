"""
Tests for Platform Inventory Reconciliation and Provider Fan-Out.

Proves:
- Exactly 10 ATS platforms configured in backend ATS_PLATFORMS (9 monitorable + workday; 8 near-zero legacy Serper-only platforms retired in Step 58).
- Exactly 3 active Nigerian platforms in NIGERIAN_SCRAPERS.
- Total 13 authoritative platforms supported across Bottom Pot.
- Default search queries all 10 ATS platforms.
- Individual platform selection correctly filters without unintended exclusions.
- Frontend ALL_PLATFORMS inventory is in exact synchrony with backend inventory.
"""

import re
from pathlib import Path

from src.core.models import SearchParams
from src.core.settings import ATS_PLATFORMS
from src.discovery.nigerian_scrapers import NIGERIAN_SCRAPERS
from src.discovery.query_builder import ATS_DOMAINS, build_ats_queries

EXPECTED_10_ATS = {
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
    "personio",
    "teamtailor",
    "recruitee",
    "workday",
    "pinpointhq",
}

RETIRED_LEGACY_ATS = {
    "bamboohr",
    "jobvite",
    "icims",
    "taleo",
    "jobadder",
    "jazzhr",
    "avature",
    "successfactors",
    "breezy",
}

EXPECTED_3_NIGERIAN = {
    "jobberman",
    "myjobmag",
    "hotnigerianjobs",
}


def test_backend_ats_inventory_contains_all_10_platforms():
    actual_slugs = {p.name for p in ATS_PLATFORMS}
    assert actual_slugs == EXPECTED_10_ATS
    assert len(ATS_PLATFORMS) == 10
    assert not (actual_slugs & RETIRED_LEGACY_ATS)
    assert "pinpointhq" in actual_slugs


def test_backend_nigerian_inventory_contains_all_3_sources():
    actual_scrapers = {s.site_name.lower() for s in NIGERIAN_SCRAPERS}
    assert actual_scrapers == EXPECTED_3_NIGERIAN
    assert len(NIGERIAN_SCRAPERS) == 3


def test_default_ats_query_builder_queries_all_10_platforms():
    params = SearchParams(job_title="Software Engineer")
    queries = build_ats_queries(params, platforms=None)
    assert set(queries.keys()) == EXPECTED_10_ATS
    assert len(queries) == 10
    assert not (set(queries.keys()) & RETIRED_LEGACY_ATS)
    for platform, query in queries.items():
        assert query.startswith(f"site:{ATS_DOMAINS[platform]}")
        assert '"software engineer"' in query


def test_custom_platform_selection_filters_cleanly():
    params = SearchParams(job_title="Backend Developer")
    selected = ["greenhouse", "lever", "ashby"]
    queries = build_ats_queries(params, platforms=selected)
    assert set(queries.keys()) == set(selected)
    assert len(queries) == 3


def test_excluding_one_platform_does_not_exclude_unrelated_platforms():
    params = SearchParams(job_title="Data Scientist")
    all_13 = list(EXPECTED_10_ATS | EXPECTED_3_NIGERIAN)
    # User deselects only smartrecruiters
    selected = [p for p in all_13 if p != "smartrecruiters"]
    queries = build_ats_queries(params, platforms=selected)

    # 9 ATS platforms should be queried (all except smartrecruiters)
    expected_queried = EXPECTED_10_ATS - {"smartrecruiters"}
    assert set(queries.keys()) == expected_queried
    assert len(queries) == 9
    assert "smartrecruiters" not in queries
    assert "personio" in queries
    assert "teamtailor" in queries
    assert "recruitee" in queries
    assert "workday" in queries
    assert "pinpointhq" in queries


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

    expected_all_13 = EXPECTED_10_ATS | EXPECTED_3_NIGERIAN
    assert platform_ids == expected_all_13, (
        f"Frontend platform list does not match backend. "
        f"Missing: {expected_all_13 - platform_ids}, Extra: {platform_ids - expected_all_13}"
    )
    assert len(platform_ids) == 13
    assert not (platform_ids & RETIRED_LEGACY_ATS)

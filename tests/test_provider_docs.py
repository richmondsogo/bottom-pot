"""Verify per-provider docs under docs/providers/ stay synchronized with BOARD_ADAPTERS and conformance specs."""

from __future__ import annotations

from pathlib import Path

from src.providers.board_adapters import BOARD_ADAPTERS
from src.providers.contract import PROVIDER_RECONCILIATION_POLICIES
from tests.conformance.fixtures import PROVIDER_SPECS

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDERS_DOC_DIR = REPO_ROOT / "docs" / "providers"

REQUIRED_SECTIONS = (
    "## Endpoints & Transport",
    "## Snapshot Completeness Rules",
    "## Identity Key & Fingerprinting",
    "## Missing-Job Closure Rule",
    "## Known Limits & Caps",
    "## Fixture Provenance",
)


def test_every_monitored_provider_has_complete_contract_documentation():
    assert set(BOARD_ADAPTERS.keys()) == set(PROVIDER_SPECS.keys())
    inventory_text = (PROVIDERS_DOC_DIR / "inventory.md").read_text(encoding="utf-8")
    docs_readme_text = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    for provider, spec in sorted(PROVIDER_SPECS.items()):
        doc_path = PROVIDERS_DOC_DIR / f"{provider}.md"
        assert doc_path.is_file(), f"Missing provider doc: {doc_path}"
        content = doc_path.read_text(encoding="utf-8")

        for heading in REQUIRED_SECTIONS:
            assert heading in content, f"{doc_path.name} missing section '{heading}'"

        expected_threshold = PROVIDER_RECONCILIATION_POLICIES[provider].missing_confirmation_threshold
        assert spec.expected_missing_threshold == expected_threshold
        assert f"missing_confirmation_threshold={expected_threshold}" in content
        assert spec.primary_host in content or "{slug}" in content
        assert f"providers/{provider}.md" in docs_readme_text or f"{provider}.md" in inventory_text

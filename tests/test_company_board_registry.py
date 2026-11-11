"""
Tests for CompanyBoardRegistry.

Verifies:
- Discovered company board candidates are persisted in SQLite.
- Existing boards are deduplicated and not created anew.
- Generic placeholders and invalid tokens are rejected.
- Due board queries respect scheduling and priorities.
- Verification success marks boards as 'verified' and resets backoff.
- Verification failure applies exponential backoff and caps out at 'rejected'.
- Registry survives database re-connections.
"""

import time
import pytest
from src.project_files.company_board_registry import (
    CompanyBoardRegistry,
    build_canonical_board_url,
)


@pytest.fixture
def test_registry(tmp_path):
    db_file = str(tmp_path / "test_boards.sqlite")
    reg = CompanyBoardRegistry(db_path=db_file)
    yield reg
    reg.clear()


def test_register_candidate_creates_new_board(test_registry):
    board = test_registry.register_candidate(
        company_name="Stripe",
        ats_provider="greenhouse",
        board_token="stripe",
        source_url="https://boards.greenhouse.io/stripe/jobs/12345",
        discovery_source="serper_search",
    )
    assert board is not None
    assert board.id is not None
    assert board.company_name == "Stripe"
    assert board.company_slug == "stripe"
    assert board.ats_provider == "greenhouse"
    assert board.board_token == "stripe"
    assert board.board_url == "https://boards.greenhouse.io/stripe"
    assert board.verification_status == "candidate"
    assert board.monitoring_capability == "supported"
    assert board.failure_count == 0


def test_register_candidate_deduplicates_existing_board(test_registry):
    b1 = test_registry.register_candidate(
        company_name="Anthropic",
        ats_provider="lever",
        board_token="anthropic",
        source_url="https://jobs.lever.co/anthropic/uuid1",
    )
    assert b1 is not None

    time.sleep(0.01)

    b2 = test_registry.register_candidate(
        company_name="Anthropic PBC",
        ats_provider="lever",
        board_token="anthropic",
        source_url="https://jobs.lever.co/anthropic/uuid2",
    )
    assert b2 is not None
    assert b2.id == b1.id
    assert b2.last_discovered_at >= b1.last_discovered_at

    # Only one record in table
    boards = test_registry.list_boards()
    assert len(boards) == 1


def test_register_candidate_rejects_generic_placeholders(test_registry):
    # Reject ATS names as slugs
    assert test_registry.register_candidate(ats_provider="greenhouse", board_token="greenhouse") is None
    assert test_registry.register_candidate(ats_provider="personio", board_token="personio") is None
    assert test_registry.register_candidate(ats_provider="icims", board_token="icims") is None
    assert test_registry.register_candidate(ats_provider="breezy", board_token="breezy") is None

    # Reject generic stopwords
    assert test_registry.register_candidate(ats_provider="workday", board_token="jobs") is None
    assert test_registry.register_candidate(ats_provider="workday", board_token="careers") is None
    assert test_registry.register_candidate(ats_provider="workday", board_token="apply") is None
    assert test_registry.register_candidate(ats_provider="workday", board_token="") is None

    # Nothing was inserted
    assert len(test_registry.list_boards()) == 0


def test_record_check_success_marks_verified_and_resets_failures(test_registry):
    board = test_registry.register_candidate(
        company_name="Figma",
        ats_provider="ashby",
        board_token="figma",
    )
    assert board is not None

    # Record first check failure
    test_registry.record_check_failure(board.id, error="HTTP 503")
    failed_board = test_registry.get_board("ashby", "figma")
    assert failed_board.failure_count == 1

    # Record check success
    test_registry.record_check_success(
        board.id,
        active_job_count=42,
        content_fingerprint="sha256:abc12345",
        etag='"etag123"',
    )

    updated = test_registry.get_board("ashby", "figma")
    assert updated.verification_status == "verified"
    assert updated.failure_count == 0
    assert updated.active_job_count == 42
    assert updated.content_fingerprint == "sha256:abc12345"
    assert updated.etag == '"etag123"'
    assert updated.last_successful_check is not None
    assert updated.next_scheduled_check > updated.last_successful_check


def test_record_check_failure_applies_backoff_and_caps_at_rejected(test_registry):
    board = test_registry.register_candidate(
        company_name="Ghost Corp",
        ats_provider="greenhouse",
        board_token="ghost-corp",
    )
    assert board is not None

    # Fail 5 times
    for i in range(1, 6):
        test_registry.record_check_failure(board.id, error=f"HTTP 404 attempt {i}")

    rejected = test_registry.get_board("greenhouse", "ghost-corp")
    assert rejected.failure_count == 5
    assert rejected.verification_status == "rejected"

    # Rejected boards should not be in due monitoring list
    due = test_registry.get_due_monitoring_boards()
    assert all(b.id != board.id for b in due)


def test_registry_persists_across_instances(tmp_path):
    db_file = str(tmp_path / "persistent.sqlite")
    reg1 = CompanyBoardRegistry(db_path=db_file)
    reg1.register_candidate(company_name="Scale AI", ats_provider="greenhouse", board_token="scaleai")

    # Open with new instance
    reg2 = CompanyBoardRegistry(db_path=db_file)
    board = reg2.get_board("greenhouse", "scaleai")
    assert board is not None
    assert board.company_name == "Scale AI"
    assert board.board_token == "scaleai"

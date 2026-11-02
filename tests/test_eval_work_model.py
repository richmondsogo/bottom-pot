"""
Tests for scripts/eval_work_model.py:
- Evaluates through JobExtractionService (production path).
- Pre-set work_model on input is ignored.
- Fails loudly on extraction failures (no fallback to pre-classified values).
- Computes per-class and per-provider metrics (precision, recall, FP rate, unknown rate).
- Partitions rows by presence of stored description.
"""

from __future__ import annotations

import csv
from pathlib import Path
import pytest

from scripts.eval_work_model import evaluate_records, EvalMetrics


def test_preset_work_model_on_input_is_ignored(tmp_path: Path):
    """A row with pre-set work_model='remote' but location='Austin, TX' must be resolved by JobExtractionService."""
    records = [
        {
            "url": "https://boards.greenhouse.io/acme/jobs/1",
            "provider": "greenhouse",
            "title": "Software Engineer",
            "company": "Acme",
            "location": "Austin, TX",
            "work_model": "remote",  # Deliberate poisoned pre-set value
            "label_work_model": "in_person",
            "description": None,
        }
    ]

    report = evaluate_records(records)
    # The extraction service must resolve from location/title, NOT trust the pre-set work_model
    # Location "Austin, TX" yields in_person or None (unknown), never remote
    assert report["all"].total_evaluated == 1
    # Check that predicted value was not "remote"
    assert report["predictions"][0]["predicted"] != "remote"


def test_eval_fails_loudly_if_extraction_service_fails(monkeypatch):
    """Fails loudly if JobExtractionService cannot process a record, never silently falls back."""
    from src.project_files.job_extraction_service import JobExtractionService

    def broken_extract(raw):
        raise RuntimeError("Extraction service internal crash")

    monkeypatch.setattr(JobExtractionService, "extract", broken_extract)

    records = [
        {
            "url": "https://boards.greenhouse.io/acme/jobs/1",
            "provider": "greenhouse",
            "title": "Software Engineer",
            "company": "Acme",
            "location": "Remote",
            "work_model": "remote",
            "label_work_model": "remote",
        }
    ]

    with pytest.raises(RuntimeError, match="Extraction service internal crash"):
        evaluate_records(records)


def test_eval_metrics_computation():
    """Verify precision, recall, false-positive rate, and unknown rate formulas."""
    records = [
        # TP for remote
        {"url": "u1", "provider": "greenhouse", "title": "Eng (Remote)", "location": "Remote", "label_work_model": "remote"},
        # FN for remote (predicted in_person or None, label remote)
        {"url": "u2", "provider": "greenhouse", "title": "Eng", "location": "Dallas, TX", "label_work_model": "remote"},
        # TN for remote (label in_person, predicted in_person)
        {"url": "u3", "provider": "greenhouse", "title": "Eng", "location": "Austin, TX", "label_work_model": "in_person"},
    ]

    report = evaluate_records(records)
    remote_metrics = report["all"].per_class["remote"]
    assert remote_metrics.tp == 1
    assert remote_metrics.fn == 1
    assert remote_metrics.fp == 0
    assert remote_metrics.tn == 1
    assert remote_metrics.precision == 1.0  # 1 / (1 + 0)
    assert remote_metrics.recall == 0.5     # 1 / (1 + 1)
    assert remote_metrics.fp_rate == 0.0    # 0 / (0 + 1)

    cm = report["all"].confusion_matrix
    assert cm[("remote", "remote")] == 1
    assert cm[("remote", "unknown")] == 1
    assert cm[("in_person", "unknown")] == 1


def test_eval_partitions_by_stored_description():
    """Rows with stored descriptions are reported separately from rows without."""
    records = [
        {
            "url": "u1",
            "provider": "greenhouse",
            "title": "Eng",
            "location": "Dallas",
            "description": "This is a 100% remote job across Nigeria and US.",
            "label_work_model": "remote",
        },
        {
            "url": "u2",
            "provider": "greenhouse",
            "title": "Eng",
            "location": "Dallas",
            "description": None,
            "label_work_model": "in_person",
        },
    ]

    report = evaluate_records(records)
    assert report["with_description"].total_evaluated == 1
    assert report["without_description"].total_evaluated == 1
    assert report["all"].total_evaluated == 2

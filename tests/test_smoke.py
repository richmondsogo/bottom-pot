"""Offline regression tests for scripts/smoke.py."""

from __future__ import annotations

from pathlib import Path

from scripts.smoke import run_smoke


def test_offline_smoke_check_passes(tmp_path: Path):
    summary = run_smoke(disposable_dir=tmp_path)
    assert summary["health"]["status"] == "ok"
    assert summary["health"]["monitored_provider_count"] == 9
    assert summary["streamed_jobs"] == 2
    assert summary["eligible_for_ng"] == 1

"""
Audit job results from JSON export to CSV for manual evaluation and golden set creation.

Usage:
    python scripts/audit_jobs.py <results.json> [output_audit.csv]

Reads a downloaded results JSON (e.g. from UI 'Download JSON') and outputs
an audit.csv with blank `label_work_model` ready for manual ground-truth labeling.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any


AUDIT_COLUMNS = [
    "url",
    "provider",
    "data_source",
    "title",
    "company",
    "location",
    "work_model",
    "work_model_source",
    "work_model_evidence",
    "label_work_model",
]


def extract_jobs(data: Any) -> list[dict[str, Any]]:
    """Extract list of job dicts from loaded JSON data."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "jobs", "data", "listings"):
            if key in data and isinstance(data[key], list):
                return [item for item in data[key] if isinstance(item, dict)]
    return []


def job_to_audit_row(job: dict[str, Any]) -> dict[str, str]:
    """Map a job dictionary to audit CSV columns."""
    url = job.get("apply_url") or job.get("source_url") or job.get("url") or ""
    provider = job.get("provider") or job.get("ats_source") or ""
    data_source = job.get("data_source") or ""
    title = job.get("title") or job.get("displayTitle") or ""
    company = job.get("company") or ""
    location = job.get("location") or job.get("displayLocation") or ""
    work_model = job.get("work_model") or ""
    work_model_source = job.get("work_model_source") or ""
    work_model_evidence = job.get("work_model_evidence") or ""

    return {
        "url": str(url),
        "provider": str(provider),
        "data_source": str(data_source),
        "title": str(title),
        "company": str(company),
        "location": str(location),
        "work_model": str(work_model),
        "work_model_source": str(work_model_source),
        "work_model_evidence": str(work_model_evidence),
        "label_work_model": "",
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/audit_jobs.py <results.json> [audit.csv]")
        return 1

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return 1

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("audit.csv")

    try:
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error parsing JSON from {input_path}: {exc}")
        return 1

    jobs = extract_jobs(raw_data)
    if not jobs:
        print(f"No job records found in {input_path}")
        return 1

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job_to_audit_row(job))

    print(f"Wrote {len(jobs)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

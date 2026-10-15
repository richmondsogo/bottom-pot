"""
Summarize job results from JSON export:
- work_model and work_model_source distribution + null %
- description_ok % per provider
- row count, null company %, null location % per provider
- random sample of 15 rows with non-null work_model (title, provider, work_model, source, evidence)

Usage:
    python scripts/summarize_results.py <results.json>
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys
from typing import Any


def extract_jobs(data: Any) -> list[dict[str, Any]]:
    """Extract list of job dicts from loaded JSON data."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "result", "jobs", "batch", "data", "listings"):
            if key in data and isinstance(data[key], list):
                return [item for item in data[key] if isinstance(item, dict)]
    return []


def is_blank_or_unknown(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return not s or s.lower() in ("unknown", "null", "none", "not listed")


def summarize(jobs: list[dict[str, Any]]) -> None:
    total = len(jobs)
    print(f"\n{'='*70}")
    print(f"RESULTS SUMMARY (Total rows: {total})")
    print(f"{'='*70}\n")

    if total == 0:
        print("No job records found.")
        return

    # (a) counts of work_model by value and by work_model_source, and % null
    wm_counts = Counter()
    source_counts = Counter()
    null_wm_count = 0

    for job in jobs:
        wm = job.get("work_model")
        if wm is None or str(wm).strip() == "" or str(wm).lower() in ("null", "none", "unknown"):
            null_wm_count += 1
            wm_counts["(null)"] += 1
        else:
            wm_counts[str(wm)] += 1

        src = job.get("work_model_source")
        if src is None or str(src).strip() == "" or str(src).lower() in ("null", "none"):
            source_counts["(null)"] += 1
        else:
            source_counts[str(src)] += 1

    null_wm_pct = (null_wm_count / total) * 100

    print("--- (a) WORK MODEL DISTRIBUTION ---")
    print(f"Work model null percentage: {null_wm_pct:.1f}% ({null_wm_count}/{total})\n")
    print("By work_model value:")
    for val, count in wm_counts.most_common():
        pct = (count / total) * 100
        print(f"  {val:<18} : {count:>5} ({pct:>5.1f}%)")

    print("\nBy work_model_source:")
    for src, count in source_counts.most_common():
        pct = (count / total) * 100
        print(f"  {src:<18} : {count:>5} ({pct:>5.1f}%)")

    # Group by provider for (b) and (c)
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        prov = str(job.get("provider") or job.get("ats_source") or "unknown").strip().lower()
        by_provider[prov].append(job)

    # (b) percentage of rows with description_ok, per provider
    print(f"\n--- (b) DESCRIPTION QUALITY (description_ok %) PER PROVIDER ---")
    print(f"{'Provider':<20} | {'Total':>7} | {'Desc OK':>8} | {'Desc OK %':>10}")
    print(f"{'-'*20}-+-{'-'*7}-+-{'-'*8}-+-{'-'*10}")
    for prov in sorted(by_provider.keys()):
        prov_jobs = by_provider[prov]
        p_total = len(prov_jobs)
        desc_ok_count = sum(
            1 for j in prov_jobs
            if j.get("description_ok") is True or (j.get("description_ok") is None and bool(j.get("description")))
        )
        p_pct = (desc_ok_count / p_total) * 100 if p_total else 0.0
        print(f"{prov:<20} | {p_total:>7} | {desc_ok_count:>8} | {p_pct:>9.1f}%")

    # (c) per provider: row count, null company %, null location %
    print(f"\n--- (c) DATA COMPLETENESS PER PROVIDER ---")
    print(f"{'Provider':<20} | {'Rows':>7} | {'Null Company %':>15} | {'Null Location %':>15}")
    print(f"{'-'*20}-+-{'-'*7}-+-{'-'*15}-+-{'-'*15}")
    for prov in sorted(by_provider.keys()):
        prov_jobs = by_provider[prov]
        p_total = len(prov_jobs)
        null_co = sum(1 for j in prov_jobs if is_blank_or_unknown(j.get("company")))
        null_loc = sum(1 for j in prov_jobs if is_blank_or_unknown(j.get("location") or j.get("displayLocation")))
        null_co_pct = (null_co / p_total) * 100 if p_total else 0.0
        null_loc_pct = (null_loc / p_total) * 100 if p_total else 0.0
        print(f"{prov:<20} | {p_total:>7} | {null_co_pct:>14.1f}% | {null_loc_pct:>14.1f}%")

    # (d) random sample of 15 rows with non-null work_model
    non_null_wm_jobs = [
        j for j in jobs
        if j.get("work_model") and str(j.get("work_model")).lower() not in ("null", "none", "unknown", "")
    ]

    print(f"\n--- (d) RANDOM SAMPLE OF 15 ROWS WITH NON-NULL WORK MODEL ---")
    sample_size = min(15, len(non_null_wm_jobs))
    if sample_size == 0:
        print("No rows with non-null work_model to sample.")
    else:
        # Use deterministic random sample if needed or seeded random
        rng = random.Random(42)
        sample = rng.sample(non_null_wm_jobs, sample_size)
        for idx, job in enumerate(sample, 1):
            title = str(job.get("title") or job.get("displayTitle") or "").strip()
            provider = str(job.get("provider") or job.get("ats_source") or "").strip()
            wm = str(job.get("work_model") or "").strip()
            src = str(job.get("work_model_source") or "").strip()
            ev = str(job.get("work_model_evidence") or "").strip()
            print(f"[{idx:>2}] {title}")
            print(f"     Provider   : {provider}")
            print(f"     Work Model : {wm}")
            print(f"     Source     : {src}")
            print(f"     Evidence   : \"{ev}\"")
            print()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/summarize_results.py <results.json>")
        return 1

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        return 1

    try:
        raw_text = file_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        print(f"Error reading JSON from {file_path}: {exc}")
        return 1

    jobs = extract_jobs(data)
    summarize(jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

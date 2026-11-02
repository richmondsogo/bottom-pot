"""
Evaluation script for work model resolution against golden labeled dataset.
Always runs records through the production path (JobExtractionService).
Never falls back to pre-classified values.

Usage:
    python scripts/eval_work_model.py [results_json_or_audit_csv] [--labels audit.csv]
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.url_normalizer import normalize_job_url

VALID_CLASSES = ("in_person", "hybrid", "remote")


@dataclass
class ClassMetrics:
    name: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    unknown: int = 0
    total_ground_truth: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return (self.tp / denom) if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return (self.tp / denom) if denom > 0 else 0.0

    @property
    def fp_rate(self) -> float:
        denom = self.fp + self.tn
        return (self.fp / denom) if denom > 0 else 0.0

    @property
    def unknown_rate(self) -> float:
        denom = self.total_ground_truth
        return (self.unknown / denom) if denom > 0 else 0.0


@dataclass
class EvalMetrics:
    subset_name: str
    total_evaluated: int = 0
    per_class: dict[str, ClassMetrics] = field(default_factory=dict)
    per_provider: dict[str, dict[str, ClassMetrics]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.per_class:
            self.per_class = {c: ClassMetrics(name=c) for c in VALID_CLASSES}


def load_records(
    results_path: Optional[Path] = None,
    labels_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """
    Load records and pair with golden labels.
    If results_path is audit.csv itself, load directly from audit.csv.
    If results_path is results.json and labels_path is audit.csv, merge them by URL.
    """
    labels_file = labels_path or (REPO_ROOT / "audit.csv")

    # If results_path is an audit CSV file directly
    if results_path and results_path.suffix.lower() == ".csv":
        labels_file = results_path
        results_path = None

    if not labels_file.exists():
        print(f"Error: Labels file '{labels_file}' not found.", file=sys.stderr)
        sys.exit(1)

    with labels_file.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        raw_labels = list(reader)

    # Optional results lookup
    results_map: dict[str, dict[str, Any]] = {}
    if results_path and results_path.exists():
        try:
            with results_path.open("r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            items = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    for k in ("apply_url", "source_url", "url"):
                        u = (item.get(k) or "").strip()
                        if u:
                            results_map[u] = item
                            results_map[normalize_job_url(u)] = item
        except Exception as exc:
            print(f"Warning: Failed to load results from {results_path}: {exc}", file=sys.stderr)

    paired_records: list[dict[str, Any]] = []
    for row in raw_labels:
        url = (row.get("url") or "").strip()
        matched_result = results_map.get(url) or results_map.get(normalize_job_url(url)) if url else None

        desc = None
        if matched_result:
            desc = matched_result.get("description") or matched_result.get("raw_description")

        paired_records.append({
            "url": url,
            "provider": row.get("provider") or (matched_result.get("provider") if matched_result else "") or "unknown",
            "title": (matched_result.get("title") if matched_result else None) or row.get("title") or "",
            "company": (matched_result.get("company") if matched_result else None) or row.get("company") or "",
            "location": (matched_result.get("location") if matched_result else None) or row.get("location") or "",
            "description": desc,
            "raw_workplace_type": matched_result.get("raw_workplace_type") if matched_result else None,
            # Deliberately ignore any pre-set work_model in row or matched_result
            "label_work_model": (row.get("label_work_model") or "").strip(),
        })

    return paired_records


def evaluate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run evaluation across records through the genuine JobExtractionService production path.
    Fails loudly if any row cannot go through JobExtractionService.
    """
    subsets = {
        "with_description": EvalMetrics(subset_name="With Stored Description"),
        "without_description": EvalMetrics(subset_name="Without Stored Description"),
        "all": EvalMetrics(subset_name="All Labelled Records"),
    }

    predictions: list[dict[str, Any]] = []

    for rec in records:
        raw_label = (rec.get("label_work_model") or "").strip().lower()
        if raw_label not in VALID_CLASSES:
            continue

        url = rec.get("url") or ""
        provider = rec.get("provider") or "unknown"
        desc = rec.get("description")
        has_desc = bool(desc and str(desc).strip())

        # Production Path: JobExtractionService MUST resolve the work model.
        # Fails loudly if extraction raises an error.
        raw_posting = RawJobPosting(
            provider=provider,
            source_url=url,
            raw_title=rec.get("title"),
            raw_company=rec.get("company"),
            raw_location=rec.get("location"),
            raw_workplace_type=rec.get("raw_workplace_type"),
            raw_description=desc,
            description_is_authentic=has_desc,
        )

        canonical = JobExtractionService.extract(raw_posting)
        predicted = canonical.work_model
        if predicted not in VALID_CLASSES:
            predicted = None

        predictions.append({
            "url": url,
            "provider": provider,
            "has_description": has_desc,
            "label": raw_label,
            "predicted": predicted,
            "source": canonical.work_model_source,
            "evidence": canonical.work_model_evidence,
        })

        target_subsets = [subsets["all"], subsets["with_description"] if has_desc else subsets["without_description"]]

        for sub in target_subsets:
            sub.total_evaluated += 1

            if provider not in sub.per_provider:
                sub.per_provider[provider] = {c: ClassMetrics(name=c) for c in VALID_CLASSES}

            for c in VALID_CLASSES:
                cm = sub.per_class[c]
                pm = sub.per_provider[provider][c]

                is_positive = (raw_label == c)
                is_predicted_positive = (predicted == c)

                if is_positive:
                    cm.total_ground_truth += 1
                    pm.total_ground_truth += 1
                    if predicted is None:
                        cm.unknown += 1
                        pm.unknown += 1
                        cm.fn += 1
                        pm.fn += 1
                    elif is_predicted_positive:
                        cm.tp += 1
                        pm.tp += 1
                    else:
                        cm.fn += 1
                        pm.fn += 1
                else:
                    # Ground truth is negative for class c
                    if is_predicted_positive:
                        cm.fp += 1
                        pm.fp += 1
                    else:
                        cm.tn += 1
                        pm.tn += 1

    return {
        "all": subsets["all"],
        "with_description": subsets["with_description"],
        "without_description": subsets["without_description"],
        "predictions": predictions,
    }


def print_report(results: dict[str, Any], total_rows_in_file: int) -> None:
    print("=" * 80)
    print("WORK MODEL PRODUCTION EXTRACTION EVALUATION REPORT")
    print("=" * 80)
    print(f"Total Rows in Dataset: {total_rows_in_file}")
    all_metrics: EvalMetrics = results["all"]
    print(f"Valid Labelled Rows Evaluated: {all_metrics.total_evaluated}")
    print("\nNote: The sample size of 7 remote and 15 hybrid rows limits the statistical power of the numbers.\n")

    for subset_key in ("all", "with_description", "without_description"):
        metrics: EvalMetrics = results[subset_key]
        print("-" * 80)
        print(f"SUBSET: {metrics.subset_name.upper()} (Sample Size N = {metrics.total_evaluated})")
        print("-" * 80)
        if metrics.total_evaluated == 0:
            print("  No records in this partition.\n")
            continue

        print(f"{'Class':<12} | {'Precision':<20} | {'Recall':<20} | {'FP Rate':<20} | {'Unknown Rate':<20}")
        print("-" * 80)
        for c in VALID_CLASSES:
            cm = metrics.per_class[c]
            prec_str = f"{cm.precision * 100:5.1f}% ({cm.tp}/{cm.tp + cm.fp})"
            rec_str = f"{cm.recall * 100:5.1f}% ({cm.tp}/{cm.tp + cm.fn})"
            fpr_str = f"{cm.fp_rate * 100:5.1f}% ({cm.fp}/{cm.fp + cm.tn})"
            unk_str = f"{cm.unknown_rate * 100:5.1f}% ({cm.unknown}/{cm.total_ground_truth})"
            print(f"{c:<12} | {prec_str:<20} | {rec_str:<20} | {fpr_str:<20} | {unk_str:<20}")

        # Per-provider breakdown
        if metrics.per_provider:
            print("\n  Per-Provider Breakdown:")
            for prov, p_classes in sorted(metrics.per_provider.items()):
                prov_total = sum(c.total_ground_truth for c in p_classes.values())
                if prov_total == 0:
                    continue
                print(f"\n    Provider: {prov} (N = {prov_total})")
                for c in VALID_CLASSES:
                    cm = p_classes[c]
                    if cm.total_ground_truth > 0 or (cm.tp + cm.fp) > 0:
                        prec_str = f"{cm.precision * 100:5.1f}% ({cm.tp}/{cm.tp + cm.fp})"
                        rec_str = f"{cm.recall * 100:5.1f}% ({cm.tp}/{cm.tp + cm.fn})"
                        print(f"      {c:<10} -> Precision: {prec_str:<16} Recall: {rec_str}")
        print()

    # Mismatches summary
    mismatches = [p for p in results["predictions"] if p["predicted"] != p["label"]]
    print("=" * 80)
    print(f"MISMATCHES & UNKNOWNS ({len(mismatches)} total out of {all_metrics.total_evaluated}):")
    print("=" * 80)
    for idx, m in enumerate(mismatches, 1):
        has_desc_str = "with-desc" if m["has_description"] else "no-desc"
        print(f"[{idx:02d}] Provider: {m['provider']} ({has_desc_str}) | URL: {m['url']}")
        print(f"     Label:     {m['label']}")
        print(f"     Predicted: {m['predicted'] or 'unknown'} (source: {m['source']}, evidence: {m['evidence']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate work model resolution via JobExtractionService.")
    parser.add_argument("results", nargs="?", type=Path, default=None, help="Path to results JSON or audit CSV")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("audit.csv"),
        help="Path to golden labels CSV (default: audit.csv)",
    )
    args = parser.parse_args()

    records = load_records(args.results, args.labels)
    eval_results = evaluate_records(records)
    print_report(eval_results, len(records))


if __name__ == "__main__":
    main()

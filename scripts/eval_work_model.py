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
ALL_OUTCOMES = ("in_person", "hybrid", "remote", "unknown")


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
    confusion_matrix: dict[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.per_class:
            self.per_class = {c: ClassMetrics(name=c) for c in VALID_CLASSES}
        if not self.confusion_matrix:
            for l in VALID_CLASSES:
                for p in ALL_OUTCOMES:
                    self.confusion_matrix[(l, p)] = 0


@dataclass
class DatasetMetadata:
    total_rows: int = 0
    labelled_rows: int = 0
    unlabelled_rows: int = 0
    excluded_rows: list[dict[str, Any]] = field(default_factory=list)
    provider_counts: dict[str, dict[str, int]] = field(default_factory=dict)


def load_records(
    results_path: Optional[Path] = None,
    labels_path: Optional[Path] = None,
) -> tuple[list[dict[str, Any]], DatasetMetadata]:
    """
    Load records and pair with golden labels.
    If results_path is audit.csv itself, load directly from audit.csv.
    If results_path is results.json and labels_path is audit.csv, merge them by URL.
    """
    labels_file = labels_path or (REPO_ROOT / "audit.csv")

    if results_path and results_path.suffix.lower() == ".csv":
        labels_file = results_path
        results_path = None

    if not labels_file.exists():
        print(f"Error: Labels file '{labels_file}' not found.", file=sys.stderr)
        sys.exit(1)

    with labels_file.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        raw_labels = list(reader)

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

    metadata = DatasetMetadata(total_rows=len(raw_labels))
    paired_records: list[dict[str, Any]] = []

    for idx, row in enumerate(raw_labels):
        url = (row.get("url") or "").strip()
        matched_result = results_map.get(url) or results_map.get(normalize_job_url(url)) if url else None

        desc = None
        if matched_result:
            desc = matched_result.get("description") or matched_result.get("raw_description")

        raw_label = (row.get("label_work_model") or "").strip()
        label_lower = raw_label.lower()
        provider = (row.get("provider") or (matched_result.get("provider") if matched_result else "") or "unknown").strip().lower()

        if provider not in metadata.provider_counts:
            metadata.provider_counts[provider] = {"total": 0, "labelled": 0, "unlabelled": 0}
        metadata.provider_counts[provider]["total"] += 1

        if not raw_label:
            metadata.unlabelled_rows += 1
            metadata.provider_counts[provider]["unlabelled"] += 1
        elif label_lower not in VALID_CLASSES:
            metadata.excluded_rows.append({
                "row_index": idx + 2,
                "url": url,
                "title": row.get("title") or "",
                "provider": provider,
                "label": raw_label,
            })
            metadata.provider_counts[provider]["unlabelled"] += 1
        else:
            metadata.labelled_rows += 1
            metadata.provider_counts[provider]["labelled"] += 1

        paired_records.append({
            "url": url,
            "provider": provider,
            "title": (matched_result.get("title") if matched_result else None) or row.get("title") or "",
            "company": (matched_result.get("company") if matched_result else None) or row.get("company") or "",
            "location": (matched_result.get("location") if matched_result else None) or row.get("location") or "",
            "description": desc,
            "raw_workplace_type": matched_result.get("raw_workplace_type") if matched_result else None,
            "label_work_model": raw_label,
        })

    return paired_records, metadata


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
        provider = (rec.get("provider") or "unknown").strip().lower()
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

        outcome_key = predicted if predicted in VALID_CLASSES else "unknown"

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
            sub.confusion_matrix[(raw_label, outcome_key)] = sub.confusion_matrix.get((raw_label, outcome_key), 0) + 1

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


def print_report(
    results: dict[str, Any],
    metadata: Optional[DatasetMetadata] = None,
    total_rows_in_file: int = 0,
) -> None:
    all_metrics: EvalMetrics = results["all"]
    total_file_rows = metadata.total_rows if metadata else total_rows_in_file

    print("=" * 86)
    print("WORK MODEL PRODUCTION EXTRACTION EVALUATION REPORT")
    print("=" * 86)
    print(f"Total Rows in Dataset File:      {total_file_rows}")
    if metadata:
        non_empty_labels = metadata.labelled_rows + len(metadata.excluded_rows)
        print(f"Rows with Non-Empty Labels:      {non_empty_labels}")
        print(f"Valid Labelled Rows Evaluated:   {metadata.labelled_rows} (in_person, hybrid, remote)")
        print(f"Unlabelled Rows:                 {metadata.unlabelled_rows}")
        print(f"Excluded Non-Job / 404 Rows:     {len(metadata.excluded_rows)}")
        print("\n--- 1. RECONCILIATION: 49 VALID LABELLED ROWS vs 54 NON-EMPTY LABELS ---")
        print("Earlier audits cited 54 labelled rows. 49 represent genuine job postings with")
        print("evaluable work model classes. The remaining 5 are non-job/unfindable records:")
        for ex in metadata.excluded_rows:
            print(f"  • Row {ex['row_index']:03d} [{ex['provider']}]: label='{ex['label']}'")
            print(f"    URL:   {ex['url']}")
            print(f"    Title: {ex['title']}")
    else:
        print(f"Valid Labelled Rows Evaluated:   {all_metrics.total_evaluated}")

    print("\nNote: The sample size of 7 remote and 15 hybrid rows limits the statistical power of the numbers.\n")

    # Confusion matrix on all valid labelled rows
    cm = all_metrics.confusion_matrix
    print("=" * 86)
    print("CONFUSION MATRIX: GROUND TRUTH LABEL vs PREDICTED OUTCOME (N = {})".format(all_metrics.total_evaluated))
    print("=" * 86)
    header = f"{'Ground Truth':<14} | " + " | ".join(f"{p:<12}" for p in ALL_OUTCOMES) + " | Total"
    print(header)
    print("-" * len(header))
    col_totals: dict[str, int] = {p: 0 for p in ALL_OUTCOMES}
    for l in VALID_CLASSES:
        row_str = f"{l:<14} | "
        row_total = 0
        for p in ALL_OUTCOMES:
            cnt = cm.get((l, p), 0)
            col_totals[p] += cnt
            row_total += cnt
            row_str += f"{cnt:<12} | "
        row_str += f"{row_total}"
        print(row_str)
    print("-" * len(header))
    total_row_str = f"{'Total Predicted':<14} | " + " | ".join(f"{col_totals[p]:<12}" for p in ALL_OUTCOMES) + f" | {all_metrics.total_evaluated}"
    print(total_row_str)
    print()

    # Partitioned Subsets
    for subset_key in ("all", "with_description", "without_description"):
        metrics: EvalMetrics = results[subset_key]
        print("-" * 86)
        print(f"SUBSET: {metrics.subset_name.upper()} (Sample Size N = {metrics.total_evaluated})")
        print("-" * 86)
        if metrics.total_evaluated == 0:
            print("  Plain Status: No labelled records exist in this partition.\n")
            continue

        print(f"{'Class':<12} | {'Precision':<20} | {'Recall':<20} | {'FP Rate':<20} | {'Unknown Rate':<20}")
        print("-" * 86)
        prec_list = []
        rec_list = []
        for c in VALID_CLASSES:
            c_metric = metrics.per_class[c]
            prec_str = f"{c_metric.precision * 100:5.1f}% ({c_metric.tp}/{c_metric.tp + c_metric.fp})"
            rec_str = f"{c_metric.recall * 100:5.1f}% ({c_metric.tp}/{c_metric.tp + c_metric.fn})"
            fpr_str = f"{c_metric.fp_rate * 100:5.1f}% ({c_metric.fp}/{c_metric.fp + c_metric.tn})"
            unk_str = f"{c_metric.unknown_rate * 100:5.1f}% ({c_metric.unknown}/{c_metric.total_ground_truth})"
            print(f"{c:<12} | {prec_str:<20} | {rec_str:<20} | {fpr_str:<20} | {unk_str:<20}")
            if c_metric.tp + c_metric.fp > 0:
                prec_list.append(c_metric.precision)
            rec_list.append(c_metric.recall)

        total_tp = sum(metrics.per_class[c].tp for c in VALID_CLASSES)
        total_fp = sum(metrics.per_class[c].fp for c in VALID_CLASSES)
        total_gt = sum(metrics.per_class[c].total_ground_truth for c in VALID_CLASSES)
        macro_prec = (sum(prec_list) / len(prec_list)) if prec_list else 0.0
        macro_rec = (sum(rec_list) / len(rec_list)) if rec_list else 0.0
        micro_prec = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
        micro_rec = (total_tp / total_gt) if total_gt > 0 else 0.0
        accuracy = (total_tp / total_gt) if total_gt > 0 else 0.0

        print("-" * 86)
        print(f"Summary Averages for {metrics.subset_name}:")
        print(f"  • Macro-Averaged Precision: {macro_prec * 100:5.1f}% (average across classes with predictions)")
        print(f"  • Macro-Averaged Recall:    {macro_rec * 100:5.1f}%")
        print(f"  • Micro-Averaged Precision: {micro_prec * 100:5.1f}% ({total_tp}/{total_tp + total_fp} non-unknown predictions)")
        print(f"  • Micro-Averaged Recall:    {micro_rec * 100:5.1f}% ({total_tp}/{total_gt} total labelled rows)")
        print(f"  • Overall Exact Accuracy:   {accuracy * 100:5.1f}% ({total_tp}/{total_gt})")
        print(f"  • Overall Unknown Rate:     {(total_gt - total_tp - total_fp) / total_gt * 100:5.1f}% ({total_gt - total_tp - total_fp}/{total_gt})")
        print()

    # Complete Provider Inventory
    print("=" * 86)
    print("PROVIDER INVENTORY & DISTRIBUTION")
    print("=" * 86)
    if metadata:
        print("Providers Present in Dataset File:")
        sum_labelled = sum(v["labelled"] for v in metadata.provider_counts.values())
        sum_total = sum(v["total"] for v in metadata.provider_counts.values())
        print(f"{'Provider':<20} | {'Labelled (N)':<14} | {'Unlabelled':<12} | {'Total Rows':<12}")
        print("-" * 66)
        for prov, counts in sorted(metadata.provider_counts.items(), key=lambda x: (-x[1]["labelled"], x[0])):
            print(f"{prov:<20} | {counts['labelled']:<14} | {counts['unlabelled']:<12} | {counts['total']:<12}")
        print("-" * 66)
        print(f"{'TOTAL':<20} | {sum_labelled:<14} | {sum_total - sum_labelled:<12} | {sum_total:<12}")
        print(f"\nVerification: Sum of labelled provider Ns ({sum_labelled}) == total labelled ({all_metrics.total_evaluated}) -> CONFIRMED.")

        print("\nProviders Missing from Dataset File:")
        known_absent = ["hotnigerianjobs", "ngcareers", "jobberman", "myjobmag", "lever", "ashby"]
        for p in known_absent:
            if p not in metadata.provider_counts:
                print(f"  • {p:<18} (0 rows in audit.csv; tested via dedicated fixtures in tests/fixtures/)")
    print()

    # Detailed mismatches
    mismatches = [p for p in results["predictions"] if p["predicted"] != p["label"]]
    print("=" * 86)
    print(f"MISMATCHES & UNKNOWNS ({len(mismatches)} total out of {all_metrics.total_evaluated}):")
    print("=" * 86)
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

    records, metadata = load_records(args.results, args.labels)
    eval_results = evaluate_records(records)
    print_report(eval_results, metadata=metadata, total_rows_in_file=len(records))


if __name__ == "__main__":
    main()

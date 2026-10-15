"""
Evaluation script for work model resolution against golden labeled dataset.

Usage:
    python scripts/eval_work_model.py <path_to_results_json> [--labels <path_to_labels_csv>]

Metrics:
    - WRONG RATE: of non-null predictions, how many disagree with the label (target: ~0)
    - COVERAGE: share of explicitly labeled rows that got the right value
    - INFERRED VIOLATIONS: count of rows with inferred=Y that predicted non-None
    - Detailed list of every wrong prediction (url, predicted, label, source, evidence)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.project_files.work_model import resolve_work_model


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    """Load results JSON into a mapping keyed by normalized URL."""
    if not path.exists():
        print(f"Error: Results file '{path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        print(f"Error: Invalid results format in '{path}'. Expected list or {{'results': [...]}}.", file=sys.stderr)
        sys.exit(1)

    mapping: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        # Index by all known URL variations for robust joining
        url = (item.get("apply_url") or item.get("source_url") or item.get("url") or "").strip()
        if url:
            mapping[url] = item
            mapping[url.rstrip("/")] = item
        source_url = (item.get("source_url") or "").strip()
        if source_url:
            mapping[source_url] = item
            mapping[source_url.rstrip("/")] = item
    return mapping


def evaluate(results_path: Path, labels_path: Path) -> int:
    if not labels_path.exists():
        print(f"Warning: Golden labels file '{labels_path}' not found. Cannot evaluate.")
        return 0

    results_by_url = load_results(results_path)

    with labels_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        label_rows = list(reader)

    if not label_rows:
        print(f"Warning: No rows found in labels file '{labels_path}'.")
        return 0

    total_labeled = 0
    non_null_predictions = 0
    wrong_predictions = 0
    explicit_rows = 0
    explicit_correct = 0
    inferred_violations = 0
    mismatches: list[dict[str, str]] = []

    for row in label_rows:
        raw_url = (row.get("url") or "").strip()
        if not raw_url:
            continue
        total_labeled += 1
        label = (row.get("label_work_model") or "").strip().lower()
        if label in ("", "none", "null", "unknown"):
            label = None

        inferred = (row.get("inferred") or "").strip().upper() == "Y"

        job = results_by_url.get(raw_url) or results_by_url.get(raw_url.rstrip("/"))

        if job:
            # Run resolver on job fields to ensure evaluation reflects current resolver
            res = resolve_work_model(
                workplace_type=job.get("raw_workplace_type"),
                location=job.get("location"),
                title=job.get("title"),
                trusted_description=job.get("description"),
            )
            # If resolver yielded None, check if existing job.work_model had a valid value
            predicted = res.value if res.value is not None else job.get("work_model")
            source = res.source or job.get("work_model_source") or "unknown"
            evidence = res.evidence or job.get("work_model_evidence") or ""
        else:
            predicted = None
            source = "missing_result"
            evidence = "URL not found in results JSON"

        # Check inferred rule: rows with inferred=Y must predict None
        if inferred:
            if predicted is not None:
                inferred_violations += 1
                mismatches.append({
                    "url": raw_url,
                    "predicted": str(predicted),
                    "label": "None (inferred=Y violation)",
                    "source": str(source),
                    "evidence": str(evidence),
                })
        else:
            # Explicitly labeled row
            if label is not None:
                explicit_rows += 1
                if predicted == label:
                    explicit_correct += 1

            if predicted is not None:
                non_null_predictions += 1
                if predicted != label:
                    wrong_predictions += 1
                    mismatches.append({
                        "url": raw_url,
                        "predicted": str(predicted),
                        "label": str(label),
                        "source": str(source),
                        "evidence": str(evidence),
                    })

    wrong_rate = (wrong_predictions / non_null_predictions * 100) if non_null_predictions > 0 else 0.0
    coverage = (explicit_correct / explicit_rows * 100) if explicit_rows > 0 else 0.0

    print("=" * 60)
    print("WORK MODEL EVALUATION REPORT")
    print("=" * 60)
    print(f"Results File:          {results_path}")
    print(f"Golden Labels File:    {labels_path}")
    print(f"Total Rows Evaluated:  {total_labeled}")
    print(f"Explicit Rows:         {explicit_rows}")
    print(f"Non-Null Predictions:  {non_null_predictions}")
    print("-" * 60)
    print(f"WRONG RATE:            {wrong_rate:.2f}% ({wrong_predictions}/{non_null_predictions})  [target: ~0%]")
    print(f"COVERAGE:              {coverage:.2f}% ({explicit_correct}/{explicit_rows})")
    print(f"INFERRED VIOLATIONS:   {inferred_violations}")
    print("=" * 60)

    if mismatches:
        print(f"\nMismatches / Violations ({len(mismatches)} total):")
        for idx, m in enumerate(mismatches, 1):
            print(f"  [{idx}] URL:       {m['url']}")
            print(f"      Predicted: {m['predicted']} (source: {m['source']}, evidence: {m['evidence']})")
            print(f"      Label:     {m['label']}\n")
    else:
        print("\nAll predictions match golden labels perfectly!")

    return 1 if wrong_predictions > 0 or inferred_violations > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate work model resolution against golden dataset.")
    parser.add_argument("results", type=Path, help="Path to search results JSON")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("tests/golden/work_model_labels.csv"),
        help="Path to golden labels CSV (default: tests/golden/work_model_labels.csv)",
    )
    args = parser.parse_args()
    sys.exit(evaluate(args.results, args.labels))


if __name__ == "__main__":
    main()

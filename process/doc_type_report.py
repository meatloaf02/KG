"""
Document type distribution report.

Two tables:
1. High-level: doc_type counts + percentages
2. SEC-specific: doc_subtype counts for sec_other documents

Usage:
    python3 -m process.doc_type_report
"""

import json
from collections import Counter
from pathlib import Path

from config import INTERIM_DATA_DIR


def generate_report() -> None:
    """Print document type distribution from processed documents."""
    base_dir = Path(INTERIM_DATA_DIR)
    json_files = sorted(base_dir.rglob("*.json"))
    total = len(json_files)

    type_counts: Counter = Counter()
    subtype_counts: Counter = Counter()

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc_type = data.get("doc_type", "unknown")
            doc_sub_type = data.get("doc_sub_type")
            type_counts[doc_type] += 1
            if doc_type == "sec_other" and doc_sub_type:
                subtype_counts[doc_sub_type] += 1
        except Exception:
            type_counts["_error"] += 1

    # Table 1: High-level distribution
    print("=" * 50)
    print("Document Type Distribution")
    print("=" * 50)
    print(f"{'Type':<28s} {'Count':>5s} {'Pct':>7s}")
    print("-" * 50)
    for dtype, count in type_counts.most_common():
        pct = f"{100 * count / total:.1f}%"
        print(f"  {dtype:<26s} {count:5d} {pct:>7s}")
    print("-" * 50)
    print(f"  {'TOTAL':<26s} {total:5d}")

    # Table 2: SEC-other subtypes
    sec_other_total = type_counts.get("sec_other", 0)
    if sec_other_total > 0:
        print(f"\n{'=' * 50}")
        print(f"sec_other Subtypes ({sec_other_total} documents)")
        print("=" * 50)
        print(f"{'Subtype':<32s} {'Count':>5s} {'Pct':>7s}")
        print("-" * 50)
        accounted = 0
        for sub, count in subtype_counts.most_common():
            pct = f"{100 * count / sec_other_total:.1f}%"
            print(f"  {sub:<30s} {count:5d} {pct:>7s}")
            accounted += count
        no_sub = sec_other_total - accounted
        if no_sub > 0:
            pct = f"{100 * no_sub / sec_other_total:.1f}%"
            print(f"  {'(no subtype)':<30s} {no_sub:5d} {pct:>7s}")
        print("-" * 50)
        print(f"  {'TOTAL':<30s} {sec_other_total:5d}")


if __name__ == "__main__":
    generate_report()

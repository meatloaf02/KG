"""
Reclassify processed documents with updated classifier rules.

Iterates data/interim/**/*.json, re-runs DocumentClassifier.classify(),
and updates only classification fields (doc_type, doc_type_confidence,
doc_sub_type). All other fields (text, sentences, dates) are preserved.

Usage:
    python3 -m process.reclassify --dry-run   # Preview changes
    python3 -m process.reclassify              # Apply changes
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from config import INTERIM_DATA_DIR, setup_logging
from process.doc_classifier import DocumentClassifier

logger = setup_logging(__name__)


def reclassify_all(dry_run: bool = True) -> dict:
    """
    Re-run classification on all processed documents.

    Args:
        dry_run: If True, report changes without writing files.

    Returns:
        Summary statistics dict.
    """
    classifier = DocumentClassifier()
    base_dir = Path(INTERIM_DATA_DIR)

    changed = 0
    unchanged = 0
    errors = 0
    changes_detail: list[dict] = []
    new_type_counts: Counter = Counter()
    new_subtype_counts: Counter = Counter()

    json_files = sorted(base_dir.rglob("*.json"))
    total = len(json_files)
    print(f"Scanning {total} processed documents in {base_dir}...")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            result = classifier.classify(
                url=data.get("source_url"),
                title=data.get("title"),
                text=data.get("text", "")[:5000],
                source_type=data.get("source_type"),
            )

            new_type = result.doc_type.value
            new_confidence = result.confidence
            new_sub_type = result.sub_type

            old_type = data.get("doc_type")
            old_sub_type = data.get("doc_sub_type")

            new_type_counts[new_type] += 1
            if new_type == "sec_other" and new_sub_type:
                new_subtype_counts[new_sub_type] += 1

            if (
                new_type != old_type
                or new_confidence != data.get("doc_type_confidence")
                or new_sub_type != old_sub_type
            ):
                changed += 1
                changes_detail.append({
                    "hash": data.get("content_hash", json_path.stem)[:12],
                    "old_type": old_type,
                    "new_type": new_type,
                    "old_sub": old_sub_type,
                    "new_sub": new_sub_type,
                })

                if not dry_run:
                    data["doc_type"] = new_type
                    data["doc_type_confidence"] = new_confidence
                    data["doc_sub_type"] = new_sub_type
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                unchanged += 1

        except Exception as e:
            errors += 1
            logger.error(f"Error processing {json_path}: {e}")

    # Print summary
    mode = "[DRY RUN]" if dry_run else "[APPLIED]"
    print(f"\n{'=' * 60}")
    print(f"Reclassification Summary {mode}")
    print(f"{'=' * 60}")
    print(f"  Total documents:  {total}")
    print(f"  Changed:          {changed}")
    print(f"  Unchanged:        {unchanged}")
    print(f"  Errors:           {errors}")

    if changes_detail:
        # Show type promotions
        promotions = [c for c in changes_detail if c["old_type"] != c["new_type"]]
        subtype_only = [c for c in changes_detail if c["old_type"] == c["new_type"]]

        if promotions:
            print(f"\n  Type promotions ({len(promotions)}):")
            for c in promotions[:20]:
                print(f"    {c['hash']}  {c['old_type']:15s} → {c['new_type']}")
            if len(promotions) > 20:
                print(f"    ... and {len(promotions) - 20} more")

        if subtype_only:
            print(f"\n  Subtype updates ({len(subtype_only)}):")
            sub_summary: Counter = Counter()
            for c in subtype_only:
                sub_summary[c["new_sub"]] += 1
            for sub, count in sub_summary.most_common():
                print(f"    {sub or 'None':30s}  {count}")

    print(f"\n  New doc_type distribution:")
    for dtype, count in new_type_counts.most_common():
        print(f"    {dtype:25s}  {count:4d}  ({100*count/total:.1f}%)")

    if new_subtype_counts:
        print(f"\n  sec_other subtypes:")
        for sub, count in new_subtype_counts.most_common():
            print(f"    {sub:30s}  {count:4d}")

    return {
        "total": total,
        "changed": changed,
        "unchanged": unchanged,
        "errors": errors,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Reclassify processed documents with updated rules",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report changes without writing files (default: off)",
    )
    args = parser.parse_args()
    reclassify_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

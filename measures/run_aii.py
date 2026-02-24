"""
AII computation runner.

Computes the AI Intensity Index for all canonical_v2 documents,
writes results to CSV, and optionally materializes QuarterlySignal
nodes in Memgraph for fast downstream queries.

Usage:
    python3 -m measures.run_aii              # compute + CSV + Memgraph write
    python3 -m measures.run_aii --dry-run    # compute + CSV only (no graph write)
    python3 -m measures.run_aii --stats      # show current QuarterlySignal nodes
    python3 -m measures.run_aii --output /path/to/out.csv
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import PROCESSED_DATA_DIR, setup_logging
from kg.connection import execute_query, get_driver
from kg.loaders import KGLoader
from kg.schema import QuarterlySignalNode
from measures.aii import compute_aii_index, save_aii_csv

logger = setup_logging(__name__)

AII_VERSION = "1.0.0"
AII_CSV_PATH = PROCESSED_DATA_DIR / "aii_quarterly.csv"

STATS_QUERY = """
MATCH (qs:QuarterlySignal)
RETURN qs.period AS period, qs.aii AS aii, qs.aii_delta AS aii_delta,
       qs.doc_count AS doc_count
ORDER BY qs.year, qs.quarter
"""


# =============================================================================
# Output Helpers
# =============================================================================


def print_summary(df: pd.DataFrame) -> None:
    """Print AII quarterly summary table to stdout."""
    print("=" * 70)
    print("AI Intensity Index (AII) — Quarterly Summary")
    print("=" * 70)
    print(f"{'Period':<10} {'Docs':>5} {'AII':>8} {'Delta':>9} {'GenAI':>7}")
    print("-" * 70)
    for _, row in df.iterrows():
        delta = row["aii_delta"]
        delta_str = f"{delta:+.3f}" if pd.notna(delta) else "      —"
        print(
            f"{row['period']:<10} "
            f"{int(row['doc_count']):>5} "
            f"{row['aii']:>8.3f} "
            f"{delta_str:>9} "
            f"{int(row['bucket_generative_ai']):>7}"
        )
    print("=" * 70)
    print(f"Total quarters: {len(df)}, Total docs: {int(df['doc_count'].sum())}")


def _show_stats(driver) -> None:
    """Show current QuarterlySignal nodes in Memgraph."""
    results = execute_query(STATS_QUERY, driver=driver)
    if not results:
        print("No QuarterlySignal nodes found in Memgraph.")
        return
    print(f"{'Period':<10} {'AII':>8} {'Delta':>9} {'Docs':>5}")
    print("-" * 40)
    for r in results:
        delta = r["aii_delta"]
        delta_str = f"{delta:+.3f}" if delta is not None else "      —"
        print(f"{r['period']:<10} {r['aii']:>8.3f} {delta_str:>9} {r['doc_count']:>5}")
    print(f"\nTotal: {len(results)} QuarterlySignal nodes")


# =============================================================================
# Memgraph Write
# =============================================================================


def _load_to_graph(df: pd.DataFrame, driver) -> None:
    """Load AII rows into Memgraph as QuarterlySignal nodes."""
    computed_at = datetime.now(timezone.utc).isoformat()
    loaded = 0
    failed = 0

    with KGLoader(driver=driver) as loader:
        for _, row in df.iterrows():
            delta = row["aii_delta"]
            signal = QuarterlySignalNode(
                period=row["period"],
                year=int(row["year"]),
                quarter=int(row["quarter"]),
                signal_type="aii",
                aii=float(row["aii"]),
                aii_delta=None if pd.isna(delta) else float(delta),
                doc_count=int(row["doc_count"]),
                quarter_raw_score=float(row["quarter_raw_score"]),
                quarter_tokens=float(row["quarter_tokens"]),
                avg_doc_type_weight=float(row["avg_doc_type_weight"]),
                bucket_classic_ai=int(row["bucket_classic_ai"]),
                bucket_generative_ai=int(row["bucket_generative_ai"]),
                bucket_adjacent_automation=int(row["bucket_adjacent_automation"]),
                computed_at=computed_at,
                extractor_version=AII_VERSION,
            )
            result = loader.load_quarterly_signal(signal)
            if result.success:
                loaded += 1
            else:
                failed += 1
                logger.warning(f"Failed to load {row['period']}: {result.error}")

    logger.info(f"Memgraph write: {loaded} loaded, {failed} failed")
    if failed > 0:
        print(f"WARNING: {failed} quarterly signals failed to load", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Entry Point
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="AII Computation Pipeline")
    parser.add_argument(
        "--dry-run", "--no-graph",
        action="store_true",
        help="Compute and write CSV but skip Memgraph write",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current QuarterlySignal nodes in Memgraph",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Override CSV output path",
    )
    args = parser.parse_args()

    driver = get_driver()

    if args.stats:
        _show_stats(driver)
        return

    # 1. Compute AII
    df = compute_aii_index(driver=driver)

    if df.empty:
        print("No data computed. Check canonical_v2 documents in Memgraph.")
        sys.exit(1)

    # 2. Print summary
    print_summary(df)

    # 3. Write CSV
    csv_path = Path(args.output) if args.output else AII_CSV_PATH
    save_aii_csv(df, csv_path)
    print(f"\nCSV: {csv_path}")

    # 4. Write to Memgraph (unless dry-run)
    if not args.dry_run:
        _load_to_graph(df, driver)
        print(f"Loaded {len(df)} QuarterlySignal nodes to Memgraph.")
    else:
        print("[dry-run] Skipping Memgraph write.")


if __name__ == "__main__":
    main()

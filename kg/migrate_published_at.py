"""
Backfill published_at Date field on existing Document nodes.

Converts the string publish_date property to a native Memgraph Date
stored in published_at. This enables .year, .month, .quarter accessors
in Cypher queries.

Usage:
    python -m kg.migrate_published_at              # Dry run (default)
    python -m kg.migrate_published_at --execute    # Apply changes
    python -m kg.migrate_published_at --verify     # Check results
"""

import argparse
import sys

from config import setup_logging
from kg.connection import execute_query

logger = setup_logging(__name__)

BACKFILL_QUERY = """
MATCH (d:Document)
WHERE d.publish_date IS NOT NULL AND d.published_at IS NULL
SET d.published_at = date(d.publish_date)
RETURN count(d) AS updated_count
"""

COUNT_PENDING_QUERY = """
MATCH (d:Document)
WHERE d.publish_date IS NOT NULL AND d.published_at IS NULL
RETURN count(d) AS pending_count
"""

VERIFY_QUERY = """
MATCH (d:Document)
WHERE d.published_at IS NOT NULL
RETURN d.publish_date AS publish_date,
       d.published_at AS published_at,
       d.published_at.year AS year,
       d.published_at.quarter AS quarter
LIMIT 5
"""

STATS_QUERY = """
MATCH (d:Document)
RETURN count(d) AS total,
       count(d.publish_date) AS has_publish_date,
       count(d.published_at) AS has_published_at
"""


def dry_run() -> None:
    """Show how many nodes would be updated without making changes."""
    print("=" * 60)
    print("Migration: published_at backfill (DRY RUN)")
    print("=" * 60)

    results = execute_query(STATS_QUERY)
    if results:
        row = results[0]
        print(f"\n  Total Document nodes:      {row['total']}")
        print(f"  With publish_date (string): {row['has_publish_date']}")
        print(f"  With published_at (Date):   {row['has_published_at']}")

    results = execute_query(COUNT_PENDING_QUERY)
    if results:
        pending = results[0]["pending_count"]
        print(f"\n  Nodes to backfill: {pending}")

    if pending == 0:
        print("\n  Nothing to do — all nodes already have published_at.")
    else:
        print(f"\n  Run with --execute to backfill {pending} nodes.")

    print("=" * 60)


def execute_migration() -> None:
    """Apply the backfill migration."""
    print("=" * 60)
    print("Migration: published_at backfill (EXECUTE)")
    print("=" * 60)

    results = execute_query(BACKFILL_QUERY)
    if results:
        count = results[0]["updated_count"]
        print(f"\n  Updated {count} Document nodes.")
    else:
        print("\n  No results returned.")

    print("\n  Run with --verify to check results.")
    print("=" * 60)


def verify() -> None:
    """Verify the migration results."""
    print("=" * 60)
    print("Migration: published_at verification")
    print("=" * 60)

    results = execute_query(STATS_QUERY)
    if results:
        row = results[0]
        print(f"\n  Total Document nodes:      {row['total']}")
        print(f"  With publish_date (string): {row['has_publish_date']}")
        print(f"  With published_at (Date):   {row['has_published_at']}")

    pending = execute_query(COUNT_PENDING_QUERY)
    if pending:
        remaining = pending[0]["pending_count"]
        print(f"  Still missing published_at:  {remaining}")

    print("\n  Sample rows:")
    samples = execute_query(VERIFY_QUERY)
    for row in samples:
        print(
            f"    {row['publish_date']} -> {row['published_at']} "
            f"(year={row['year']}, Q{row['quarter']})"
        )

    if not samples:
        print("    (no rows with published_at found)")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill published_at Date field on Document nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--execute",
        action="store_true",
        help="Apply the backfill migration",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration results",
    )

    args = parser.parse_args()

    if args.execute:
        execute_migration()
    elif args.verify:
        verify()
    else:
        dry_run()


if __name__ == "__main__":
    main()

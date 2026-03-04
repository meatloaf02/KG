"""
External media crawl CLI entrypoint.

Usage examples:
  python3 -m ingest.run_media --init-db
  python3 -m ingest.run_media --seeds data_manifests/seeds/external_media.csv --dry-run
  python3 -m ingest.run_media --seeds data_manifests/seeds/external_media.csv --limit 500
  python3 -m ingest.run_media --stats
  python3 -m ingest.run_media --report
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from config import INTERIM_DATA_DIR, PROCESSED_DATA_DIR, setup_logging

logger = setup_logging(__name__)

DEFAULT_REPORT_PATH = PROCESSED_DATA_DIR / "crawl_run_report.json"


def init_db() -> None:
    """Create the document_manifest table."""
    from ingest.media.models import create_manifest_table
    create_manifest_table()
    print("document_manifest table created (or already exists).")


def load_seeds_from_csv(path: Path) -> list[str]:
    """Read seed URLs from a CSV file (first column = url)."""
    seeds: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            if url:
                seeds.append(url)
    return seeds


def dry_run(seeds: list[str], limit: int | None) -> None:
    """Print seeds that would be crawled without fetching."""
    display = seeds[:limit] if limit else seeds
    print(f"\n--- DRY RUN MODE --- ({len(seeds)} total seeds)")
    for i, url in enumerate(display, 1):
        print(f"  [{i}] {url}")
    if limit and len(seeds) > limit:
        print(f"  ... and {len(seeds) - limit} more")


def run_crawl(seeds: list[str], limit: int | None, report_path: Path) -> None:
    """Execute the media crawl and write report."""
    from ingest.media.crawler import MediaCrawler

    crawler = MediaCrawler()
    print(f"Starting crawl with {len(seeds)} seed(s), limit={limit or 'none'}")
    stats = crawler.run(seeds=seeds, limit=limit)

    print("\nCrawl complete:")
    print(f"  Fetched total:       {stats.fetched_total}")
    print(f"  Fetched success:     {stats.fetched_success}")
    print(f"  Fetched failed:      {stats.fetched_failed}")
    print(f"  Dropped (paywall):   {stats.dropped_paywalled_total}")
    print(f"  Dropped (date):      {stats.dropped_out_of_window_total}")
    print(f"  Dropped (relevance): {stats.dropped_not_relevant_total}")
    print(f"  Dropped (language):  {stats.dropped_not_english_total}")
    print(f"  Stored:              {stats.stored_docs_total}")

    if stats.stored_docs_by_domain:
        print("\n  By domain:")
        for domain, count in sorted(stats.stored_docs_by_domain.items()):
            print(f"    {domain}: {count}")

    crawler.write_report(report_path)
    print(f"\nReport written to: {report_path}")


def show_stats() -> None:
    """Print counts from the document_manifest table."""
    from ingest.models import get_session
    from ingest.media.models import DocumentManifest
    from sqlalchemy import func

    session = get_session()
    try:
        total = session.query(func.count(DocumentManifest.id)).scalar()
        paywalled = (
            session.query(func.count(DocumentManifest.id))
            .filter(DocumentManifest.is_paywalled.is_(True))
            .scalar()
        )
        by_domain = (
            session.query(DocumentManifest.domain, func.count(DocumentManifest.id))
            .group_by(DocumentManifest.domain)
            .order_by(func.count(DocumentManifest.id).desc())
            .all()
        )
    finally:
        session.close()

    print(f"\ndocument_manifest statistics:")
    print(f"  Total rows:    {total}")
    print(f"  Paywalled:     {paywalled}")
    if by_domain:
        print("\n  By domain:")
        for domain, count in by_domain:
            print(f"    {domain or '(unknown)'}: {count}")


def show_report(report_path: Path) -> None:
    """Print the last crawl run report."""
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        print("Run a crawl first to generate the report.")
        return
    report = json.loads(report_path.read_text())
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Workday KG — External Media Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize DB table
  python3 -m ingest.run_media --init-db

  # Dry-run to preview seeds
  python3 -m ingest.run_media --seeds data_manifests/seeds/external_media.csv --dry-run

  # Smoke test (5 docs)
  python3 -m ingest.run_media --seeds data_manifests/seeds/external_media.csv --limit 5

  # Full crawl
  python3 -m ingest.run_media --seeds data_manifests/seeds/external_media.csv

  # Show manifest table counts
  python3 -m ingest.run_media --stats

  # Print last crawl report
  python3 -m ingest.run_media --report
        """,
    )

    parser.add_argument("--init-db", action="store_true", help="Create document_manifest table")
    parser.add_argument("--seeds", type=str, metavar="CSV", help="Path to seed CSV file")
    parser.add_argument("--limit", type=int, help="Max fetch attempts (for smoke tests)")
    parser.add_argument("--dry-run", action="store_true", help="Print seeds without fetching")
    parser.add_argument("--stats", action="store_true", help="Show manifest table counts")
    parser.add_argument("--report", action="store_true", help="Print crawl_run_report.json")
    parser.add_argument(
        "--report-path",
        type=str,
        default=str(DEFAULT_REPORT_PATH),
        help="Path for crawl report (default: data/processed/crawl_run_report.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    report_path = Path(args.report_path)

    try:
        if args.init_db:
            init_db()
            return

        if args.stats:
            show_stats()
            return

        if args.report:
            show_report(report_path)
            return

        if args.seeds:
            seeds_path = Path(args.seeds)
            if not seeds_path.exists():
                print(f"Seeds file not found: {seeds_path}")
                sys.exit(1)

            seeds = load_seeds_from_csv(seeds_path)
            if not seeds:
                print("No seed URLs found in CSV.")
                sys.exit(1)

            if args.dry_run:
                dry_run(seeds, args.limit)
                return

            run_crawl(seeds, args.limit, report_path)
            return

        parser.print_help()

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Error: {exc}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

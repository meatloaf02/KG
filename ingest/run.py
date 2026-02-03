"""
Ingestion CLI entrypoint.

Provides command-line interface for document ingestion operations:
- Database initialization
- Fetching from seed URLs
- Fetching individual URLs
- Exporting manifests
- Viewing statistics
"""

import argparse
import sys
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)


def init_db(drop_existing: bool = False) -> None:
    """Initialize database tables."""
    from ingest.models import create_tables, drop_tables, get_engine

    if drop_existing:
        logger.warning("Dropping existing tables...")
        drop_tables()

    logger.info("Creating database tables...")
    create_tables()
    print("Database tables created successfully.")


def fetch_seeds(
    seeds_filter: Optional[str] = None,
    source_type: Optional[str] = None,
    priority: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Fetch documents from seed URLs."""
    from ingest.fetcher import get_fetcher
    from ingest.models import FetchStatus
    from ingest.seeds import get_seed_stats, load_all_seeds, load_seeds_by_file

    # Load seeds
    if seeds_filter and seeds_filter not in ("all", "ALL"):
        seeds = load_seeds_by_file(seeds_filter)
    else:
        seeds = load_all_seeds(
            priority_filter=priority,
            source_type_filter=source_type,
        )

    if not seeds:
        print("No seeds found matching the filter.")
        return

    print(f"Found {len(seeds)} seed URLs")

    if dry_run:
        print("\n--- DRY RUN MODE ---")
        for i, seed in enumerate(seeds[:limit] if limit else seeds):
            print(f"  [{i + 1}] {seed.url}")
            print(f"      source: {seed.source_type}, priority: {seed.priority}")
        if limit and len(seeds) > limit:
            print(f"  ... and {len(seeds) - limit} more")
        return

    # Prepare URL list
    url_list = [(seed.url, seed.source_type) for seed in seeds]

    # Fetch documents
    fetcher = get_fetcher()
    results = fetcher.fetch_many(
        urls=url_list,
        skip_if_exists=not force,
        limit=limit,
    )

    # Print summary
    success = sum(1 for r in results if r.status == FetchStatus.SUCCESS)
    skipped = sum(1 for r in results if r.status == FetchStatus.SKIPPED)
    failed = sum(1 for r in results if r.status == FetchStatus.FAILED)
    existed = sum(1 for r in results if r.already_existed)

    print(f"\nFetch Results:")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Already existed: {existed}")


def fetch_url(url: str, source_type: str = "manual", force: bool = False) -> None:
    """Fetch a single URL."""
    from ingest.fetcher import get_fetcher
    from ingest.models import FetchStatus

    print(f"Fetching: {url}")

    fetcher = get_fetcher()
    result = fetcher.fetch(url, source_type=source_type, skip_if_exists=not force)

    print(f"Status: {result.status.value}")

    if result.status == FetchStatus.SUCCESS:
        print(f"Content hash: {result.content_hash}")
        print(f"File path: {result.file_path}")
        print(f"Size: {result.content_size} bytes")
        if result.title:
            print(f"Title: {result.title}")
    elif result.error_message:
        print(f"Error: {result.error_message}")
    elif result.skipped_reason:
        print(f"Skipped: {result.skipped_reason}")


def export_manifest_cmd(output: Optional[str] = None) -> None:
    """Export document manifest to CSV."""
    from pathlib import Path

    from ingest.manifest import export_manifest

    output_path = Path(output) if output else None
    result_path = export_manifest(output_path=output_path)
    print(f"Manifest exported to: {result_path}")


def show_stats() -> None:
    """Show document statistics."""
    from ingest.manifest import format_stats, get_manifest_stats
    from ingest.seeds import get_seed_stats

    # Show seed stats
    seed_stats = get_seed_stats()
    print("\n" + "=" * 50)
    print("Seed URL Statistics")
    print("=" * 50)
    print(f"Total seeds: {seed_stats['total']}")
    print("\nBy file:")
    for name, count in sorted(seed_stats["by_file"].items()):
        print(f"  {name}: {count}")
    print("\nBy priority:")
    for priority, count in sorted(seed_stats["by_priority"].items()):
        print(f"  {priority}: {count}")

    # Show document stats
    try:
        doc_stats = get_manifest_stats()
        print(format_stats(doc_stats))
    except Exception as e:
        print(f"\nCould not retrieve document stats: {e}")
        print("(Database may not be initialized. Run with --init-db first.)")


def show_seed_files() -> None:
    """List available seed files."""
    from ingest.seeds import get_seed_stats, list_seed_files

    seed_files = list_seed_files()

    if not seed_files:
        print("No seed files found in data_manifests/seeds/")
        return

    print("Available seed files:")
    stats = get_seed_stats()

    for name in seed_files:
        count = stats["by_file"].get(name, 0)
        print(f"  {name}: {count} URLs")


def extract_links_cmd(dry_run: bool = False) -> None:
    """Extract links from fetched documents and add to queue."""
    from ingest.extractor import add_links_to_queue, extract_all_links

    print("Extracting links from fetched documents...")
    links = extract_all_links()

    if not links:
        print("No links extracted. Fetch some documents first.")
        return

    # Show summary by source type
    by_type = {}
    for link in links:
        by_type[link.source_type] = by_type.get(link.source_type, 0) + 1

    print(f"\nExtracted {len(links)} links:")
    for source_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {source_type}: {count}")

    if dry_run:
        print("\n--- DRY RUN MODE ---")
        print("Links would be added to ingestion queue.")
        return

    # Add to queue
    stats = add_links_to_queue(links)
    print(f"\nQueue update:")
    print(f"  Added: {stats['added']}")
    print(f"  Already exists: {stats['existing']}")
    print(f"  Duplicates skipped: {stats['skipped']}")


def crawl_cmd(
    limit: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Extract links and fetch discovered documents."""
    from ingest.extractor import add_links_to_queue, extract_all_links
    from ingest.fetcher import get_fetcher
    from ingest.models import FetchStatus, RawDocument, get_session

    # First extract links
    print("Step 1: Extracting links from fetched documents...")
    links = extract_all_links()

    if not links:
        print("No links to crawl. Fetch seed documents first.")
        return

    print(f"Extracted {len(links)} links")

    if not dry_run:
        # Add to queue
        stats = add_links_to_queue(links)
        print(f"Added {stats['added']} new URLs to queue")

    # Now fetch pending documents
    print("\nStep 2: Fetching discovered documents...")

    db_session = get_session()
    try:
        query = db_session.query(RawDocument).filter(
            RawDocument.status == FetchStatus.PENDING
        )
        if limit:
            query = query.limit(limit)

        pending_docs = query.all()
        urls = [(doc.url, doc.source_type or "unknown") for doc in pending_docs]
    finally:
        db_session.close()

    if not urls:
        print("No pending documents to fetch.")
        return

    print(f"Found {len(urls)} pending documents")

    if dry_run:
        print("\n--- DRY RUN MODE ---")
        for i, (url, source_type) in enumerate(urls[:10]):
            print(f"  [{i + 1}] {url}")
        if len(urls) > 10:
            print(f"  ... and {len(urls) - 10} more")
        return

    # Fetch documents
    fetcher = get_fetcher()
    results = fetcher.fetch_many(urls, skip_if_exists=not force, limit=limit)

    # Print summary
    success = sum(1 for r in results if r.status == FetchStatus.SUCCESS)
    skipped = sum(1 for r in results if r.status == FetchStatus.SKIPPED)
    failed = sum(1 for r in results if r.status == FetchStatus.FAILED)

    print(f"\nCrawl Results:")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Workday KG Document Ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database
  python -m ingest.run --init-db

  # List available seed files
  python -m ingest.run --list-seeds

  # Preview what would be fetched
  python -m ingest.run --seeds all --limit 5 --dry-run

  # Fetch from specific seed file
  python -m ingest.run --seeds sec_filings --limit 10

  # Fetch with filters
  python -m ingest.run --seeds all --priority high --limit 20

  # Fetch a single URL
  python -m ingest.run --url https://example.com/doc.html

  # Show statistics
  python -m ingest.run --stats

  # Export manifest
  python -m ingest.run --export-manifest

  # Extract links from fetched documents
  python -m ingest.run --extract

  # Crawl: extract links and fetch discovered documents
  python -m ingest.run --crawl --limit 50
        """,
    )

    # Database options
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create database tables",
    )
    parser.add_argument(
        "--drop-tables",
        action="store_true",
        help="Drop existing tables before creating (use with --init-db)",
    )

    # Seed options
    parser.add_argument(
        "--seeds",
        type=str,
        metavar="NAME",
        help="Fetch from seed file(s). Use 'all' for all seeds or specify a file name",
    )
    parser.add_argument(
        "--list-seeds",
        action="store_true",
        help="List available seed files",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        help="Filter seeds by source type (e.g., sec_filing)",
    )
    parser.add_argument(
        "--priority",
        type=str,
        choices=["high", "medium", "low"],
        help="Filter seeds by priority",
    )

    # Single URL
    parser.add_argument(
        "--url",
        type=str,
        help="Fetch a single URL",
    )

    # Common options
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of documents to fetch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be fetched without actually fetching",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if URL was already fetched successfully",
    )

    # Link extraction and crawling
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract links from fetched documents and add to queue",
    )
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Extract links and fetch discovered documents",
    )

    # Export and stats
    parser.add_argument(
        "--export-manifest",
        action="store_true",
        help="Export document manifest to CSV",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for manifest export",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show document and seed statistics",
    )

    # Verbosity
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # No arguments - show help
    if len(sys.argv) == 1:
        parser.print_help()
        return

    # Set up logging level
    if args.verbose:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Database initialization
        if args.init_db:
            init_db(drop_existing=args.drop_tables)
            return

        # List seeds
        if args.list_seeds:
            show_seed_files()
            return

        # Show stats
        if args.stats:
            show_stats()
            return

        # Export manifest
        if args.export_manifest:
            export_manifest_cmd(output=args.output)
            return

        # Extract links
        if args.extract:
            extract_links_cmd(dry_run=args.dry_run)
            return

        # Crawl (extract + fetch)
        if args.crawl:
            crawl_cmd(limit=args.limit, dry_run=args.dry_run, force=args.force)
            return

        # Fetch from seeds
        if args.seeds:
            fetch_seeds(
                seeds_filter=args.seeds,
                source_type=args.source_type,
                priority=args.priority,
                limit=args.limit,
                dry_run=args.dry_run,
                force=args.force,
            )
            return

        # Fetch single URL
        if args.url:
            fetch_url(args.url, force=args.force)
            return

        # If we get here, no action was specified
        parser.print_help()

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

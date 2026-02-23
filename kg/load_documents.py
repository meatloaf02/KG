"""
Load all ingested documents from PostgreSQL into Memgraph.

Usage:
    python -m kg.load_documents              # Load all documents
    python -m kg.load_documents --limit 10   # Load first 10 documents
    python -m kg.load_documents --dry-run    # Preview without loading
    python -m kg.load_documents --stats      # Show current stats
"""

import argparse
import sys
from datetime import datetime

from tqdm import tqdm

from config import setup_logging
from ingest.models import FetchStatus, RawDocument, get_session
from kg.loaders import KGLoader
from kg.schema import DocumentNode
from process.storage import ProcessedDocumentStorage

logger = setup_logging(__name__)


def get_documents_to_load(limit: int = None) -> list[RawDocument]:
    """
    Get all successfully fetched documents from PostgreSQL.

    Args:
        limit: Maximum number of documents to return

    Returns:
        List of RawDocument objects
    """
    with get_session() as session:
        query = session.query(RawDocument).filter(
            RawDocument.status == FetchStatus.SUCCESS,
            RawDocument.content_hash.isnot(None),
        ).order_by(RawDocument.fetched_at)

        if limit:
            query = query.limit(limit)

        return query.all()


def raw_to_document_node(
    raw: RawDocument,
    processed_storage: ProcessedDocumentStorage | None = None,
) -> DocumentNode:
    """
    Convert a RawDocument (PostgreSQL) to a DocumentNode (Memgraph).

    Uses processed document data when available for accurate dates,
    titles, and doc_types. Never falls back to fetched_at - a null
    date is better than a wrong date.

    Args:
        raw: RawDocument from PostgreSQL
        processed_storage: Optional storage to look up processed document data

    Returns:
        DocumentNode for Memgraph
    """
    # Default values from raw document
    doc_type = "html"
    doc_sub_type = None
    analysis_eligible = False
    analysis_layer = None
    if raw.content_type:
        if "pdf" in raw.content_type.lower():
            doc_type = "pdf"

    title = raw.title or raw.url[:100]
    publish_date = None  # Never use fetched_at - null is better than wrong

    # Try to get better data from processed document
    if processed_storage and raw.content_hash:
        processed = processed_storage.load(raw.content_hash)
        if processed:
            # Use processed document's extracted date (not fetched_at)
            publish_date = processed.publish_date
            # Use processed document's classification
            if processed.doc_type:
                doc_type = processed.doc_type
            if processed.doc_sub_type:
                doc_sub_type = processed.doc_sub_type
            analysis_eligible = getattr(processed, 'analysis_eligible', False)
            analysis_layer = getattr(processed, 'analysis_layer', None)
            # Use processed document's title if available
            if processed.title:
                title = processed.title

    return DocumentNode(
        content_hash=raw.content_hash,
        url_hash=raw.url_hash,
        title=title,
        doc_type=doc_type,
        source_type=raw.source_type or "unknown",
        publish_date=publish_date,
        source_url=raw.url,
        doc_sub_type=doc_sub_type,
        analysis_eligible=analysis_eligible,
        analysis_layer=analysis_layer,
    )


def load_all_documents(
    limit: int = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """
    Load all documents from PostgreSQL into Memgraph.

    Args:
        limit: Maximum number of documents to load
        dry_run: If True, don't actually load
        batch_size: Number of documents per batch

    Returns:
        Statistics dictionary
    """
    print("=" * 60)
    print("Loading Documents into Memgraph")
    print("=" * 60)

    # Get documents from PostgreSQL
    print("\nFetching documents from PostgreSQL...")
    raw_docs = get_documents_to_load(limit=limit)
    total = len(raw_docs)
    print(f"Found {total} documents to load")

    if dry_run:
        print("\n[DRY RUN] Would load the following documents:")
        for i, raw in enumerate(raw_docs[:10]):
            print(f"  {i+1}. {raw.title or raw.url[:60]}... ({raw.source_type})")
        if total > 10:
            print(f"  ... and {total - 10} more")
        return {"total": total, "loaded": 0, "dry_run": True}

    # Convert to DocumentNode objects (using processed document data for dates)
    print("\nConverting to DocumentNode objects...")
    processed_storage = ProcessedDocumentStorage()
    documents = [raw_to_document_node(raw, processed_storage) for raw in raw_docs]

    # Load into Memgraph
    print(f"\nLoading {total} documents into Memgraph...")

    with KGLoader() as loader:
        # Show initial stats
        initial_stats = loader.get_loader_stats()
        print(f"  Initial nodes: {initial_stats['total_nodes']}")
        print(f"  Initial relationships: {initial_stats['total_relationships']}")

        # Load in batches with progress bar
        loaded = 0
        created = 0
        failed = 0
        errors = []

        with tqdm(total=total, desc="Loading documents", unit="doc") as pbar:
            for i in range(0, total, batch_size):
                batch = documents[i:i + batch_size]

                for doc in batch:
                    result = loader.load_document(doc)
                    if result.success:
                        loaded += 1
                        if result.created:
                            created += 1
                    else:
                        failed += 1
                        if result.error and len(errors) < 10:
                            errors.append(f"{doc.content_hash[:8]}: {result.error}")
                    pbar.update(1)

        # Show final stats
        final_stats = loader.get_loader_stats()

        print("\n" + "-" * 60)
        print("Load Complete!")
        print("-" * 60)
        print(f"  Total documents: {total}")
        print(f"  Loaded: {loaded}")
        print(f"  Created (new): {created}")
        print(f"  Updated (existing): {loaded - created}")
        print(f"  Failed: {failed}")

        if errors:
            print(f"\n  First {len(errors)} errors:")
            for err in errors:
                print(f"    - {err}")

        print("\n" + "-" * 60)
        print("Final Knowledge Graph Stats:")
        print("-" * 60)
        print(f"  Total Nodes: {final_stats['total_nodes']}")
        print(f"  Total Relationships: {final_stats['total_relationships']}")

        if final_stats["nodes_by_label"]:
            print("\n  Nodes by Label:")
            for label, count in sorted(final_stats["nodes_by_label"].items()):
                print(f"    {label}: {count}")

        return {
            "total": total,
            "loaded": loaded,
            "created": created,
            "failed": failed,
            "errors": errors,
            "final_stats": final_stats,
        }


def show_stats():
    """Show current Memgraph statistics."""
    print("=" * 60)
    print("Current Knowledge Graph Stats")
    print("=" * 60)

    with KGLoader() as loader:
        stats = loader.get_loader_stats()

        print(f"\n  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Relationships: {stats['total_relationships']}")

        if stats["nodes_by_label"]:
            print("\n  Nodes by Label:")
            for label, count in sorted(stats["nodes_by_label"].items()):
                print(f"    {label}: {count}")

        if stats["relationships_by_type"]:
            print("\n  Relationships by Type:")
            for rel_type, count in sorted(stats["relationships_by_type"].items()):
                print(f"    {rel_type}: {count}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Load documents from PostgreSQL into Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to load",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without loading",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Documents per batch (default: 100)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current Memgraph statistics",
    )

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    result = load_all_documents(
        limit=args.limit,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )

    if result.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

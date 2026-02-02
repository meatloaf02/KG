"""
Document manifest export to CSV.

Exports metadata about fetched documents for reproducibility
and audit purposes.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import MANIFESTS_DIR, setup_logging
from ingest.models import FetchStatus, RawDocument, get_session

logger = setup_logging(__name__)

DEFAULT_MANIFEST_PATH = MANIFESTS_DIR / "documents.csv"

# CSV columns for manifest export
MANIFEST_COLUMNS = [
    "id",
    "url",
    "url_hash",
    "domain",
    "source_type",
    "status",
    "fetched_at",
    "http_status_code",
    "content_hash",
    "content_type",
    "content_size",
    "file_path",
    "title",
    "sec_accession_number",
    "error_message",
]


def export_manifest(
    output_path: Optional[Path] = None,
    status_filter: Optional[FetchStatus] = None,
) -> Path:
    """
    Export document metadata to CSV.

    Args:
        output_path: Path for output file (uses default if None)
        status_filter: Only export documents with this status

    Returns:
        Path to exported CSV file
    """
    if output_path is None:
        output_path = DEFAULT_MANIFEST_PATH

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    db_session = get_session()
    try:
        # Build query
        query = db_session.query(RawDocument)
        if status_filter:
            query = query.filter(RawDocument.status == status_filter)

        # Order by id for consistent output
        query = query.order_by(RawDocument.id)

        # Export to CSV
        count = 0
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()

            for doc in query:
                row = {
                    "id": doc.id,
                    "url": doc.url,
                    "url_hash": doc.url_hash,
                    "domain": doc.domain,
                    "source_type": doc.source_type,
                    "status": doc.status.value if doc.status else None,
                    "fetched_at": (
                        doc.fetched_at.isoformat() if doc.fetched_at else None
                    ),
                    "http_status_code": doc.http_status_code,
                    "content_hash": doc.content_hash,
                    "content_type": doc.content_type,
                    "content_size": doc.content_size,
                    "file_path": doc.file_path,
                    "title": doc.title,
                    "sec_accession_number": doc.sec_accession_number,
                    "error_message": doc.error_message,
                }
                writer.writerow(row)
                count += 1

        logger.info(f"Exported {count} documents to {output_path}")
        return output_path

    finally:
        db_session.close()


def get_manifest_stats() -> dict:
    """
    Get statistics about fetched documents.

    Returns:
        Dictionary with counts and metadata
    """
    from sqlalchemy import func

    db_session = get_session()
    try:
        stats = {
            "total_documents": 0,
            "by_status": {},
            "by_source_type": {},
            "by_domain": {},
            "total_size_bytes": 0,
            "unique_content_hashes": 0,
        }

        # Total count
        stats["total_documents"] = db_session.query(RawDocument).count()

        # By status
        status_counts = (
            db_session.query(RawDocument.status, func.count(RawDocument.id))
            .group_by(RawDocument.status)
            .all()
        )
        stats["by_status"] = {
            status.value if status else "none": count for status, count in status_counts
        }

        # By source type
        source_counts = (
            db_session.query(RawDocument.source_type, func.count(RawDocument.id))
            .filter(RawDocument.source_type.isnot(None))
            .group_by(RawDocument.source_type)
            .all()
        )
        stats["by_source_type"] = {
            source: count for source, count in source_counts
        }

        # By domain
        domain_counts = (
            db_session.query(RawDocument.domain, func.count(RawDocument.id))
            .filter(RawDocument.domain.isnot(None))
            .group_by(RawDocument.domain)
            .all()
        )
        stats["by_domain"] = {domain: count for domain, count in domain_counts}

        # Total size
        size_result = db_session.query(func.sum(RawDocument.content_size)).scalar()
        stats["total_size_bytes"] = size_result or 0

        # Unique content hashes
        unique_hashes = (
            db_session.query(func.count(func.distinct(RawDocument.content_hash)))
            .filter(RawDocument.content_hash.isnot(None))
            .scalar()
        )
        stats["unique_content_hashes"] = unique_hashes or 0

        return stats

    finally:
        db_session.close()


def format_stats(stats: dict) -> str:
    """
    Format statistics as a human-readable string.

    Args:
        stats: Dictionary from get_manifest_stats()

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("=" * 50)
    lines.append("Document Manifest Statistics")
    lines.append("=" * 50)

    lines.append(f"\nTotal documents: {stats['total_documents']}")

    # Format size
    size_mb = stats["total_size_bytes"] / (1024 * 1024)
    lines.append(f"Total size: {size_mb:.2f} MB")
    lines.append(f"Unique content: {stats['unique_content_hashes']} documents")

    # By status
    lines.append("\nBy Status:")
    for status, count in sorted(stats["by_status"].items()):
        lines.append(f"  {status}: {count}")

    # By source type
    if stats["by_source_type"]:
        lines.append("\nBy Source Type:")
        for source, count in sorted(stats["by_source_type"].items()):
            lines.append(f"  {source}: {count}")

    # By domain
    if stats["by_domain"]:
        lines.append("\nBy Domain:")
        for domain, count in sorted(
            stats["by_domain"].items(), key=lambda x: -x[1]
        ):
            lines.append(f"  {domain}: {count}")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)

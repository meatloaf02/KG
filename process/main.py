"""
Document processing pipeline (NOR-67).

Orchestrates the full document processing workflow:
1. Load raw documents from PostgreSQL
2. Extract text (HTML/PDF)
3. Extract publish date
4. Classify document type
5. Split into sentences
6. Save processed artifacts

Usage:
    python -m process.main                    # Process all documents
    python -m process.main --limit 10         # Process first 10
    python -m process.main --dry-run          # Preview without processing
    python -m process.main --stats            # Show processing stats
    python -m process.main --reprocess        # Reprocess existing
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from config import EXTERNAL_HTML_DIR, EXTERNAL_PDF_DIR, setup_logging
from ingest.models import FetchStatus, RawDocument, get_session
from process.date_extractor import DateExtractor
from process.doc_classifier import DocumentClassifier
from process.html_extractor import HTMLExtractor
from process.pdf_extractor import PDFExtractor
from process.sentence_splitter import SentenceSplitter
from process.storage import ProcessedDocument, ProcessedDocumentStorage, create_processed_document

logger = setup_logging(__name__)

PROCESSOR_VERSION = "1.0.0"


class DocumentProcessor:
    """
    Full document processing pipeline.

    Extracts text, metadata, and sentences from raw documents.
    """

    def __init__(
        self,
        storage: Optional[ProcessedDocumentStorage] = None,
        skip_existing: bool = True,
    ):
        """
        Initialize the processor.

        Args:
            storage: Storage for processed documents
            skip_existing: Skip documents already processed
        """
        self.storage = storage or ProcessedDocumentStorage()
        self.skip_existing = skip_existing

        # Initialize extractors
        self.html_extractor = HTMLExtractor()
        self.pdf_extractor = PDFExtractor()
        self.date_extractor = DateExtractor()
        self.doc_classifier = DocumentClassifier()

    def process_document(self, raw_doc: RawDocument) -> Optional[ProcessedDocument]:
        """
        Process a single document.

        Args:
            raw_doc: RawDocument from PostgreSQL

        Returns:
            ProcessedDocument or None on failure
        """
        content_hash = raw_doc.content_hash

        # Skip if already processed
        if self.skip_existing and self.storage.exists(content_hash):
            logger.debug(f"Skipping already processed: {content_hash[:16]}...")
            return self.storage.load(content_hash)

        # Determine file type and path
        file_path = self._get_file_path(raw_doc)
        if not file_path or not file_path.exists():
            logger.warning(f"File not found for {content_hash[:16]}: {raw_doc.file_path}")
            return None

        is_pdf = raw_doc.content_type and "pdf" in raw_doc.content_type.lower()

        # Extract text
        warnings = []
        if is_pdf:
            result = self.pdf_extractor.extract_from_file(file_path)
            text = result.text
            title = result.title
            warnings.extend(result.extraction_warnings)
        else:
            result = self.html_extractor.extract_from_file(file_path)
            text = result.text
            title = result.title or raw_doc.title
            warnings.extend(result.extraction_warnings)

        if not text or len(text) < 50:
            logger.warning(f"No text extracted from {content_hash[:16]}")
            warnings.append("No text extracted")

        # Read raw HTML for date extraction (non-PDF only)
        raw_html = None
        if not is_pdf and file_path and file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_html = f.read()
            except Exception:
                try:
                    with open(file_path, "r", encoding="latin-1") as f:
                        raw_html = f.read()
                except Exception:
                    pass

        # Extract publish date
        date_result = self.date_extractor.extract(
            url=raw_doc.url,
            html=raw_html,
            text=text[:2000] if text else None,
            filename=file_path.name if file_path else None,
        )
        publish_date = date_result.date_str if date_result else None
        date_confidence = date_result.confidence if date_result else 0.0
        date_source = date_result.source if date_result else None

        # Classify document type
        classification = self.doc_classifier.classify(
            url=raw_doc.url,
            title=title,
            text=text[:5000] if text else None,
            source_type=raw_doc.source_type,
        )

        # Split into sentences
        splitter = SentenceSplitter(doc_id=content_hash)
        sentence_result = splitter.split(text) if text else None
        sentences = sentence_result.sentences if sentence_result else []
        warnings.extend(sentence_result.warnings if sentence_result else [])

        # Create processed document
        processed = create_processed_document(
            content_hash=content_hash,
            url_hash=raw_doc.url_hash,
            source_url=raw_doc.url,
            source_type=raw_doc.source_type or "unknown",
            file_path=str(file_path),
            text=text or "",
            title=title,
            classification=classification,
            publish_date=publish_date,
            date_confidence=date_confidence,
            date_source=date_source,
            sentence_count=len(sentences),
            extraction_warnings=warnings[:10],  # Limit warnings
            processor_version=PROCESSOR_VERSION,
        )

        # Save to storage
        self.storage.save(processed, sentences)

        return processed

    def _get_file_path(self, raw_doc: RawDocument) -> Optional[Path]:
        """Get the file path for a raw document."""
        if not raw_doc.file_path:
            return None

        file_path = Path(raw_doc.file_path)

        # If it's a relative path, resolve it
        if not file_path.is_absolute():
            from config import EXTERNAL_DATA_DIR, PROJECT_ROOT

            # The stored path is like "html/xx/hash.html" - relative to external dir
            external_path = EXTERNAL_DATA_DIR / file_path
            if external_path.exists():
                return external_path

            # Try stripping html/ or pdf/ prefix if already included
            path_str = str(file_path)
            if path_str.startswith("html/"):
                clean_path = path_str[5:]  # Remove "html/" prefix
                html_path = EXTERNAL_HTML_DIR / clean_path
                if html_path.exists():
                    return html_path
            elif path_str.startswith("pdf/"):
                clean_path = path_str[4:]  # Remove "pdf/" prefix
                pdf_path = EXTERNAL_PDF_DIR / clean_path
                if pdf_path.exists():
                    return pdf_path

            # Try as-is from project root
            project_path = PROJECT_ROOT / file_path
            if project_path.exists():
                return project_path

        return file_path if file_path.exists() else None


def get_documents_to_process(
    limit: Optional[int] = None,
    source_type_filter: Optional[str] = None,
) -> list[RawDocument]:
    """
    Get documents to process from PostgreSQL.

    Args:
        limit: Maximum number of documents
        source_type_filter: Filter by source type

    Returns:
        List of RawDocument objects
    """
    with get_session() as session:
        query = session.query(RawDocument).filter(
            RawDocument.status == FetchStatus.SUCCESS,
            RawDocument.content_hash.isnot(None),
        )

        if source_type_filter:
            query = query.filter(RawDocument.source_type == source_type_filter)

        query = query.order_by(RawDocument.fetched_at)

        if limit:
            query = query.limit(limit)

        return query.all()


def process_all_documents(
    limit: Optional[int] = None,
    dry_run: bool = False,
    reprocess: bool = False,
    source_type: Optional[str] = None,
) -> dict:
    """
    Process all documents from PostgreSQL.

    Args:
        limit: Maximum documents to process
        dry_run: Preview without processing
        reprocess: Reprocess already-processed documents
        source_type: Filter by source type

    Returns:
        Processing statistics
    """
    print("=" * 60)
    print("Document Processing Pipeline")
    print("=" * 60)

    # Get documents
    print("\nFetching documents from PostgreSQL...")
    raw_docs = get_documents_to_process(limit=limit, source_type_filter=source_type)
    total = len(raw_docs)
    print(f"Found {total} documents to process")

    if dry_run:
        print("\n[DRY RUN] Would process the following documents:")
        for i, doc in enumerate(raw_docs[:10]):
            print(f"  {i+1}. {doc.title or doc.url[:60]}... ({doc.source_type})")
        if total > 10:
            print(f"  ... and {total - 10} more")
        return {"total": total, "processed": 0, "dry_run": True}

    # Initialize processor
    storage = ProcessedDocumentStorage()
    processor = DocumentProcessor(storage=storage, skip_existing=not reprocess)

    # Process documents
    print(f"\nProcessing {total} documents...")

    processed = 0
    skipped = 0
    failed = 0
    errors = []

    with tqdm(total=total, desc="Processing", unit="doc") as pbar:
        for raw_doc in raw_docs:
            try:
                result = processor.process_document(raw_doc)
                if result:
                    if storage.exists(raw_doc.content_hash):
                        processed += 1
                    else:
                        skipped += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{raw_doc.content_hash[:8]}: {str(e)[:50]}")
                logger.error(f"Error processing {raw_doc.content_hash[:16]}: {e}")

            pbar.update(1)

    # Get final stats
    stats = storage.get_stats()

    print("\n" + "-" * 60)
    print("Processing Complete!")
    print("-" * 60)
    print(f"  Total documents: {total}")
    print(f"  Processed: {processed}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Failed: {failed}")

    if errors:
        print(f"\n  First {len(errors)} errors:")
        for err in errors:
            print(f"    - {err}")

    print("\n" + "-" * 60)
    print("Storage Stats:")
    print("-" * 60)
    print(f"  Total processed: {stats['total_documents']}")
    print(f"  Storage size: {stats['total_size_mb']} MB")

    if stats["doc_types"]:
        print("\n  Documents by type:")
        for doc_type, count in sorted(stats["doc_types"].items()):
            print(f"    {doc_type}: {count}")

    return {
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "storage_stats": stats,
    }


def show_stats():
    """Show current processing statistics."""
    print("=" * 60)
    print("Processing Statistics")
    print("=" * 60)

    storage = ProcessedDocumentStorage()
    stats = storage.get_stats()

    print(f"\n  Total processed documents: {stats['total_documents']}")
    print(f"  Storage size: {stats['total_size_mb']} MB")

    if stats["doc_types"]:
        print("\n  Documents by type:")
        for doc_type, count in sorted(stats["doc_types"].items()):
            print(f"    {doc_type}: {count}")

    # Compare with raw documents
    with get_session() as session:
        raw_count = session.query(RawDocument).filter(
            RawDocument.status == FetchStatus.SUCCESS
        ).count()

    print(f"\n  Raw documents (PostgreSQL): {raw_count}")
    print(f"  Processed: {stats['total_documents']}")
    print(f"  Remaining: {raw_count - stats['total_documents']}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Document Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum documents to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without processing",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess already-processed documents",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default=None,
        help="Filter by source type",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show processing statistics",
    )

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    result = process_all_documents(
        limit=args.limit,
        dry_run=args.dry_run,
        reprocess=args.reprocess,
        source_type=args.source_type,
    )

    if result.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

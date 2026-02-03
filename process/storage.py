"""
Processed artifacts storage layout (NOR-101).

Stores processed documents in a structured format:
- data/interim/{hash[:2]}/{hash}.json - Processing results
- data/interim/{hash[:2]}/{hash}.txt - Clean text
- data/interim/{hash[:2]}/{hash}.sentences.jsonl - Sentences

All files are gitignored but provide reproducible processing artifacts.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import INTERIM_DATA_DIR, setup_logging
from process.doc_classifier import ClassificationResult, DocType
from process.sentence_splitter import Sentence, SentenceSegmentationResult

logger = setup_logging(__name__)


@dataclass
class ProcessedDocument:
    """A fully processed document ready for KG loading."""

    # Identifiers
    content_hash: str
    url_hash: str

    # Source info
    source_url: str
    source_type: str
    file_path: str

    # Extracted content
    title: Optional[str]
    text: str
    char_count: int
    word_count: int

    # Classification
    doc_type: str
    doc_type_confidence: float
    doc_sub_type: Optional[str]

    # Date
    publish_date: Optional[str]
    date_confidence: float
    date_source: Optional[str]

    # Sentences
    sentence_count: int

    # Processing metadata
    processed_at: str
    processor_version: str
    extraction_warnings: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessedDocument":
        """Create from dictionary."""
        return cls(**data)


class ProcessedDocumentStorage:
    """
    Storage for processed document artifacts.

    Directory structure:
    data/interim/
    ├── ab/
    │   ├── abc123def456.json        # Full processing result
    │   ├── abc123def456.txt         # Clean text
    │   └── abc123def456.sentences.jsonl  # Sentences (one per line)
    └── cd/
        └── ...
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize storage.

        Args:
            base_dir: Base directory for storage (default: data/interim)
        """
        self.base_dir = Path(base_dir) if base_dir else INTERIM_DATA_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_doc_dir(self, content_hash: str) -> Path:
        """Get directory for a document based on content hash."""
        prefix = content_hash[:2]
        return self.base_dir / prefix

    def _get_paths(self, content_hash: str) -> dict[str, Path]:
        """Get all file paths for a document."""
        doc_dir = self._get_doc_dir(content_hash)
        return {
            "json": doc_dir / f"{content_hash}.json",
            "text": doc_dir / f"{content_hash}.txt",
            "sentences": doc_dir / f"{content_hash}.sentences.jsonl",
        }

    def exists(self, content_hash: str) -> bool:
        """Check if a processed document exists."""
        paths = self._get_paths(content_hash)
        return paths["json"].exists()

    def save(
        self,
        doc: ProcessedDocument,
        sentences: Optional[list[Sentence]] = None,
    ) -> dict[str, Path]:
        """
        Save a processed document and its artifacts.

        Args:
            doc: Processed document
            sentences: Optional list of sentences

        Returns:
            Dict of saved file paths
        """
        paths = self._get_paths(doc.content_hash)
        doc_dir = self._get_doc_dir(doc.content_hash)
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        with open(paths["json"], "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)

        # Save clean text
        with open(paths["text"], "w", encoding="utf-8") as f:
            f.write(doc.text)

        # Save sentences as JSONL
        if sentences:
            with open(paths["sentences"], "w", encoding="utf-8") as f:
                for sent in sentences:
                    f.write(json.dumps(sent.to_dict(), ensure_ascii=False) + "\n")

        logger.debug(f"Saved processed document: {doc.content_hash}")
        return paths

    def load(self, content_hash: str) -> Optional[ProcessedDocument]:
        """
        Load a processed document.

        Args:
            content_hash: Document content hash

        Returns:
            ProcessedDocument or None if not found
        """
        paths = self._get_paths(content_hash)

        if not paths["json"].exists():
            return None

        try:
            with open(paths["json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            return ProcessedDocument.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load {content_hash}: {e}")
            return None

    def load_text(self, content_hash: str) -> Optional[str]:
        """
        Load just the clean text for a document.

        Args:
            content_hash: Document content hash

        Returns:
            Clean text or None
        """
        paths = self._get_paths(content_hash)

        if not paths["text"].exists():
            return None

        try:
            with open(paths["text"], "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load text for {content_hash}: {e}")
            return None

    def load_sentences(self, content_hash: str) -> list[Sentence]:
        """
        Load sentences for a document.

        Args:
            content_hash: Document content hash

        Returns:
            List of Sentence objects
        """
        paths = self._get_paths(content_hash)

        if not paths["sentences"].exists():
            return []

        sentences = []
        try:
            with open(paths["sentences"], "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line.strip())
                    sentences.append(Sentence(**data))
        except Exception as e:
            logger.error(f"Failed to load sentences for {content_hash}: {e}")

        return sentences

    def list_all(self) -> list[str]:
        """
        List all processed document content hashes.

        Returns:
            List of content hashes
        """
        hashes = []
        for prefix_dir in self.base_dir.iterdir():
            if prefix_dir.is_dir() and len(prefix_dir.name) == 2:
                for json_file in prefix_dir.glob("*.json"):
                    hashes.append(json_file.stem)
        return sorted(hashes)

    def get_stats(self) -> dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dict with statistics
        """
        all_hashes = self.list_all()
        total_size = 0
        doc_types = {}

        for content_hash in all_hashes:
            paths = self._get_paths(content_hash)
            for path in paths.values():
                if path.exists():
                    total_size += path.stat().st_size

            doc = self.load(content_hash)
            if doc:
                doc_type = doc.doc_type
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        return {
            "total_documents": len(all_hashes),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "doc_types": doc_types,
        }

    def delete(self, content_hash: str) -> bool:
        """
        Delete all artifacts for a document.

        Args:
            content_hash: Document content hash

        Returns:
            True if deleted, False if not found
        """
        paths = self._get_paths(content_hash)
        deleted = False

        for path in paths.values():
            if path.exists():
                path.unlink()
                deleted = True

        return deleted


def create_processed_document(
    content_hash: str,
    url_hash: str,
    source_url: str,
    source_type: str,
    file_path: str,
    text: str,
    title: Optional[str],
    classification: ClassificationResult,
    publish_date: Optional[str],
    date_confidence: float,
    date_source: Optional[str],
    sentence_count: int,
    extraction_warnings: list[str],
    processor_version: str = "1.0.0",
) -> ProcessedDocument:
    """
    Create a ProcessedDocument from extraction results.

    Args:
        content_hash: Document content hash
        url_hash: URL hash
        source_url: Original URL
        source_type: Source type from ingestion
        file_path: Path to raw file
        text: Extracted clean text
        title: Document title
        classification: Classification result
        publish_date: Extracted publish date
        date_confidence: Date extraction confidence
        date_source: Source of date extraction
        sentence_count: Number of sentences
        extraction_warnings: List of warnings
        processor_version: Processor version string

    Returns:
        ProcessedDocument
    """
    return ProcessedDocument(
        content_hash=content_hash,
        url_hash=url_hash,
        source_url=source_url,
        source_type=source_type,
        file_path=file_path,
        title=title,
        text=text,
        char_count=len(text),
        word_count=len(text.split()),
        doc_type=classification.doc_type.value,
        doc_type_confidence=classification.confidence,
        doc_sub_type=classification.sub_type,
        publish_date=publish_date,
        date_confidence=date_confidence,
        date_source=date_source,
        sentence_count=sentence_count,
        processed_at=datetime.now(timezone.utc).isoformat(),
        processor_version=processor_version,
        extraction_warnings=extraction_warnings,
    )

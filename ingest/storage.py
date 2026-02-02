"""
Content-addressable file storage for document deduplication.

Files are stored using their content hash as the filename,
providing automatic deduplication when the same content
is fetched from different URLs.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from config import EXTERNAL_HTML_DIR, EXTERNAL_PDF_DIR, ensure_directories, setup_logging
from ingest.url_utils import get_content_hash

logger = setup_logging(__name__)

# MIME type to extension mapping
MIME_TO_EXT = {
    "text/html": "html",
    "text/plain": "txt",
    "application/pdf": "pdf",
    "application/xhtml+xml": "html",
}

# Content type to storage directory mapping
ContentKind = Literal["html", "pdf"]


@dataclass
class StorageResult:
    """Result of a storage operation."""

    content_hash: str
    file_path: Path
    relative_path: str
    size: int
    already_existed: bool


class ContentStorage:
    """
    Content-addressable storage for documents.

    Files are stored in a two-level directory structure:
        {base_dir}/{hash[:2]}/{hash}.{ext}

    This prevents filesystem issues with too many files in a single directory.
    """

    def __init__(
        self,
        html_dir: Path = EXTERNAL_HTML_DIR,
        pdf_dir: Path = EXTERNAL_PDF_DIR,
    ):
        """
        Initialize content storage.

        Args:
            html_dir: Directory for HTML files
            pdf_dir: Directory for PDF files
        """
        self.html_dir = html_dir
        self.pdf_dir = pdf_dir
        ensure_directories()

    def _get_base_dir(self, content_kind: ContentKind) -> Path:
        """Get base directory for content type."""
        if content_kind == "html":
            return self.html_dir
        elif content_kind == "pdf":
            return self.pdf_dir
        else:
            raise ValueError(f"Unknown content kind: {content_kind}")

    def _get_extension(self, mime_type: str) -> str:
        """
        Get file extension for MIME type.

        Args:
            mime_type: MIME type string (may include charset)

        Returns:
            File extension without dot
        """
        # Strip charset and parameters
        base_type = mime_type.split(";")[0].strip().lower()
        return MIME_TO_EXT.get(base_type, "bin")

    def _content_kind_from_mime(self, mime_type: str) -> ContentKind:
        """
        Determine content kind from MIME type.

        Args:
            mime_type: MIME type string

        Returns:
            'html' or 'pdf'
        """
        base_type = mime_type.split(";")[0].strip().lower()
        if base_type == "application/pdf":
            return "pdf"
        return "html"

    def _build_path(
        self, content_hash: str, content_kind: ContentKind, extension: str
    ) -> tuple[Path, str]:
        """
        Build full path and relative path for content.

        Args:
            content_hash: SHA-256 hash of content
            content_kind: 'html' or 'pdf'
            extension: File extension

        Returns:
            Tuple of (full_path, relative_path)
        """
        base_dir = self._get_base_dir(content_kind)
        # Two-level directory: first two chars of hash
        subdir = content_hash[:2]
        filename = f"{content_hash}.{extension}"

        full_path = base_dir / subdir / filename
        relative_path = f"{content_kind}/{subdir}/{filename}"

        return full_path, relative_path

    def store(
        self, content: bytes, mime_type: str, content_hash: Optional[str] = None
    ) -> StorageResult:
        """
        Store content in the filesystem.

        Args:
            content: Raw content bytes
            mime_type: MIME type of content
            content_hash: Pre-computed hash (computed if not provided)

        Returns:
            StorageResult with path and metadata
        """
        # Compute hash if not provided
        if content_hash is None:
            content_hash = get_content_hash(content)

        # Determine paths
        extension = self._get_extension(mime_type)
        content_kind = self._content_kind_from_mime(mime_type)
        full_path, relative_path = self._build_path(content_hash, content_kind, extension)

        # Check if already exists
        already_existed = full_path.exists()

        if already_existed:
            logger.debug(f"Content already exists: {relative_path}")
        else:
            # Create directory and write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(content)
            logger.debug(f"Stored content: {relative_path} ({len(content)} bytes)")

        return StorageResult(
            content_hash=content_hash,
            file_path=full_path,
            relative_path=relative_path,
            size=len(content),
            already_existed=already_existed,
        )

    def exists(self, content_hash: str, content_kind: ContentKind) -> bool:
        """
        Check if content exists in storage.

        Args:
            content_hash: SHA-256 hash of content
            content_kind: 'html' or 'pdf'

        Returns:
            True if content exists
        """
        # Check both possible extensions
        extensions = ["html", "txt"] if content_kind == "html" else ["pdf"]

        for ext in extensions:
            full_path, _ = self._build_path(content_hash, content_kind, ext)
            if full_path.exists():
                return True
        return False

    def get_path(
        self, content_hash: str, content_kind: ContentKind
    ) -> Optional[Path]:
        """
        Get path to stored content.

        Args:
            content_hash: SHA-256 hash of content
            content_kind: 'html' or 'pdf'

        Returns:
            Path to content or None if not found
        """
        extensions = ["html", "txt"] if content_kind == "html" else ["pdf"]

        for ext in extensions:
            full_path, _ = self._build_path(content_hash, content_kind, ext)
            if full_path.exists():
                return full_path
        return None

    def read(self, content_hash: str, content_kind: ContentKind) -> Optional[bytes]:
        """
        Read stored content.

        Args:
            content_hash: SHA-256 hash of content
            content_kind: 'html' or 'pdf'

        Returns:
            Content bytes or None if not found
        """
        path = self.get_path(content_hash, content_kind)
        if path:
            return path.read_bytes()
        return None

    def get_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with file counts and total sizes
        """
        stats = {"html": {"count": 0, "size": 0}, "pdf": {"count": 0, "size": 0}}

        for content_kind in ["html", "pdf"]:
            base_dir = self._get_base_dir(content_kind)
            if base_dir.exists():
                for subdir in base_dir.iterdir():
                    if subdir.is_dir():
                        for f in subdir.iterdir():
                            if f.is_file():
                                stats[content_kind]["count"] += 1
                                stats[content_kind]["size"] += f.stat().st_size

        return stats


# Global storage instance
_storage: Optional[ContentStorage] = None


def get_storage() -> ContentStorage:
    """Get or create global storage instance."""
    global _storage
    if _storage is None:
        _storage = ContentStorage()
    return _storage

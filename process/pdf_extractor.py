"""
PDF to text extraction (NOR-97).

Extracts text from PDF documents using pdfplumber.
Handles multi-page documents and captures extraction metadata.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)


@dataclass
class PDFExtractionResult:
    """Result of PDF text extraction."""

    text: str
    title: Optional[str]
    char_count: int
    word_count: int
    page_count: int
    extraction_warnings: list[str]

    @property
    def is_empty(self) -> bool:
        return self.char_count == 0 or self.word_count < 10


class PDFExtractor:
    """
    Extract text from PDF documents.

    Uses pdfplumber for text extraction with fallback handling
    for problematic PDFs.
    """

    def __init__(
        self,
        min_text_length: int = 50,
        min_word_count: int = 10,
    ):
        """
        Initialize the extractor.

        Args:
            min_text_length: Minimum characters for valid extraction
            min_word_count: Minimum words for valid extraction
        """
        self.min_text_length = min_text_length
        self.min_word_count = min_word_count

    def extract(self, pdf_bytes: bytes) -> PDFExtractionResult:
        """
        Extract text from PDF bytes.

        Args:
            pdf_bytes: Raw PDF content as bytes

        Returns:
            PDFExtractionResult with extracted text and metadata
        """
        import io

        try:
            import pdfplumber
        except ImportError:
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=["pdfplumber not installed"],
            )

        warnings = []

        if not pdf_bytes:
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=["Empty PDF input"],
            )

        try:
            pdf_file = io.BytesIO(pdf_bytes)
            with pdfplumber.open(pdf_file) as pdf:
                page_count = len(pdf.pages)
                title = self._extract_title(pdf)

                # Extract text from all pages
                page_texts = []
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            page_texts.append(page_text)
                    except Exception as e:
                        warnings.append(f"Failed to extract page {i + 1}: {e}")

                text = "\n\n".join(page_texts)

        except Exception as e:
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=[f"Failed to parse PDF: {e}"],
            )

        # Normalize text
        text = self._normalize_text(text)

        # Calculate statistics
        char_count = len(text)
        word_count = len(text.split())

        if char_count < self.min_text_length:
            warnings.append(f"Extracted text too short: {char_count} chars")
        if word_count < self.min_word_count:
            warnings.append(f"Extracted text has few words: {word_count}")

        return PDFExtractionResult(
            text=text,
            title=title,
            char_count=char_count,
            word_count=word_count,
            page_count=page_count,
            extraction_warnings=warnings,
        )

    def extract_from_file(self, file_path: Path) -> PDFExtractionResult:
        """
        Extract text from a PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            PDFExtractionResult
        """
        try:
            import pdfplumber
        except ImportError:
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=["pdfplumber not installed"],
            )

        warnings = []

        if not file_path.exists():
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=[f"File not found: {file_path}"],
            )

        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                title = self._extract_title(pdf)

                # Extract text from all pages
                page_texts = []
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            page_texts.append(page_text)
                    except Exception as e:
                        warnings.append(f"Failed to extract page {i + 1}: {e}")

                text = "\n\n".join(page_texts)

        except Exception as e:
            return PDFExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                page_count=0,
                extraction_warnings=[f"Failed to parse PDF: {e}"],
            )

        # Normalize text
        text = self._normalize_text(text)

        # Calculate statistics
        char_count = len(text)
        word_count = len(text.split())

        if char_count < self.min_text_length:
            warnings.append(f"Extracted text too short: {char_count} chars")
        if word_count < self.min_word_count:
            warnings.append(f"Extracted text has few words: {word_count}")

        return PDFExtractionResult(
            text=text,
            title=title,
            char_count=char_count,
            word_count=word_count,
            page_count=page_count,
            extraction_warnings=warnings,
        )

    def _extract_title(self, pdf) -> Optional[str]:
        """Extract document title from PDF metadata."""
        try:
            metadata = pdf.metadata
            if metadata:
                # Try common metadata fields
                for key in ["Title", "title", "/Title"]:
                    if key in metadata and metadata[key]:
                        title = str(metadata[key]).strip()
                        if title and len(title) > 3:
                            return title

            # Try to extract from first page header
            if pdf.pages:
                first_page_text = pdf.pages[0].extract_text() or ""
                lines = first_page_text.split("\n")[:5]
                for line in lines:
                    line = line.strip()
                    # Look for title-like lines (not too short, not too long)
                    if 10 < len(line) < 200 and not line.startswith("Page"):
                        return line

        except Exception:
            pass

        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text."""
        if not text:
            return ""

        # Fix common PDF extraction issues

        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)

        # Fix hyphenated line breaks (word- continuation)
        text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

        # Normalize line breaks
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove page numbers/headers that appear on every page
        # Common patterns: "Page X of Y", "- X -", just a number alone on a line
        text = re.sub(r"^\s*Page\s+\d+\s*(of\s+\d+)?\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*-\s*\d+\s*-\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Remove empty lines at start/end
        text = text.strip()

        return text


def extract_pdf_text(pdf_bytes: bytes) -> PDFExtractionResult:
    """
    Convenience function to extract text from PDF bytes.

    Args:
        pdf_bytes: Raw PDF content

    Returns:
        PDFExtractionResult
    """
    extractor = PDFExtractor()
    return extractor.extract(pdf_bytes)


def extract_pdf_file(file_path: Path) -> PDFExtractionResult:
    """
    Convenience function to extract text from a PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        PDFExtractionResult
    """
    extractor = PDFExtractor()
    return extractor.extract_from_file(file_path)

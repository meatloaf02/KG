"""
HTML to clean text extraction (NOR-96).

Extracts main content from HTML documents, removing boilerplate,
navigation, ads, and other non-content elements.

Uses a combination of:
- BeautifulSoup for parsing
- Heuristics for main content detection
- Text normalization
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Comment, NavigableString

from config import setup_logging

logger = setup_logging(__name__)

# Tags that typically contain navigation/boilerplate
BOILERPLATE_TAGS = {
    "nav", "header", "footer", "aside", "script", "style", "noscript",
    "iframe", "form", "button", "input", "select", "textarea",
    "svg", "canvas", "video", "audio", "map", "object", "embed",
}

# Tags that typically contain main content
CONTENT_TAGS = {"article", "main", "section", "div", "p", "td", "th"}

# Classes/IDs that typically indicate boilerplate
BOILERPLATE_PATTERNS = re.compile(
    r"(nav|menu|sidebar|footer|header|banner|ad|advertisement|social|share|"
    r"comment|related|recommend|popular|trending|subscribe|newsletter|"
    r"cookie|popup|modal|overlay|widget)",
    re.IGNORECASE,
)

# Classes/IDs that typically indicate content
CONTENT_PATTERNS = re.compile(
    r"(content|article|post|entry|text|body|main|story|document|filing)",
    re.IGNORECASE,
)


@dataclass
class HTMLExtractionResult:
    """Result of HTML text extraction."""

    text: str
    title: Optional[str]
    char_count: int
    word_count: int
    paragraph_count: int
    extraction_warnings: list[str]

    @property
    def is_empty(self) -> bool:
        return self.char_count == 0 or self.word_count < 10


class HTMLExtractor:
    """
    Extract clean text from HTML documents.

    Removes boilerplate content (navigation, ads, footers) and
    extracts the main readable content.
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

    def extract(self, html: str) -> HTMLExtractionResult:
        """
        Extract clean text from HTML.

        Args:
            html: Raw HTML string

        Returns:
            HTMLExtractionResult with extracted text and metadata
        """
        warnings = []

        if not html or not html.strip():
            return HTMLExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                paragraph_count=0,
                extraction_warnings=["Empty HTML input"],
            )

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            # Fallback to html.parser if lxml fails
            try:
                soup = BeautifulSoup(html, "html.parser")
                warnings.append(f"Fell back to html.parser: {e}")
            except Exception as e2:
                return HTMLExtractionResult(
                    text="",
                    title=None,
                    char_count=0,
                    word_count=0,
                    paragraph_count=0,
                    extraction_warnings=[f"Failed to parse HTML: {e2}"],
                )

        # Extract title
        title = self._extract_title(soup)

        # Detect SEC filings: iXBRL (post-2020) or SGML wrapper (pre-2020)
        # These use flat div structures with no semantic content containers
        is_sec_filing = bool(soup.find(re.compile(r"^ix:"))) or "<DOCUMENT>" in html[:200]

        # Remove boilerplate elements (also strips iXBRL metadata)
        self._remove_boilerplate(soup)

        # Remove comments
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

        if is_sec_filing:
            # SEC filings use flat div structure — use full body
            body = soup.find("body")
            text = self._extract_text(body if body else soup)
        else:
            # Try to find main content container
            main_content = self._find_main_content(soup)
            if main_content:
                text = self._extract_text(main_content)
            else:
                # Fallback to body or entire document
                body = soup.find("body")
                text = self._extract_text(body if body else soup)
                warnings.append("Could not identify main content container")

        # Normalize text
        text = self._normalize_text(text)

        # Calculate statistics
        char_count = len(text)
        word_count = len(text.split())
        paragraph_count = text.count("\n\n") + 1 if text else 0

        if char_count < self.min_text_length:
            warnings.append(f"Extracted text too short: {char_count} chars")
        if word_count < self.min_word_count:
            warnings.append(f"Extracted text has few words: {word_count}")

        return HTMLExtractionResult(
            text=text,
            title=title,
            char_count=char_count,
            word_count=word_count,
            paragraph_count=paragraph_count,
            extraction_warnings=warnings,
        )

    def extract_from_file(self, file_path: Path) -> HTMLExtractionResult:
        """
        Extract clean text from an HTML file.

        Args:
            file_path: Path to HTML file

        Returns:
            HTMLExtractionResult
        """
        try:
            # Try UTF-8 first, then fallback encodings
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        html = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Last resort: read as bytes and decode with errors ignored
                with open(file_path, "rb") as f:
                    html = f.read().decode("utf-8", errors="ignore")

            return self.extract(html)

        except Exception as e:
            return HTMLExtractionResult(
                text="",
                title=None,
                char_count=0,
                word_count=0,
                paragraph_count=0,
                extraction_warnings=[f"Failed to read file: {e}"],
            )

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract document title."""
        # Try <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            # Clean up common title patterns
            title = re.sub(r"\s*\|.*$", "", title)  # Remove " | Site Name"
            title = re.sub(r"\s*-\s*[^-]+$", "", title)  # Remove " - Site Name"
            if title:
                return title

        # Try meta og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def _strip_ixbrl(self, soup: BeautifulSoup) -> None:
        """Strip XBRL inline tags from iXBRL filings.

        SEC filings post-2020 use inline XBRL (iXBRL) which embeds XBRL
        metadata directly in HTML. This metadata pollutes text extraction.

        Strategy:
        - Decompose tags that contain only metadata (ix:hidden, ix:header, etc.)
        - Unwrap tags that wrap visible text (ix:nonFraction, ix:nonNumeric, etc.)
        """
        # Tags containing only XBRL metadata — remove entirely
        for tag_name in ["ix:hidden", "ix:header", "ix:references", "ix:resources"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Tags wrapping visible content — unwrap (keep text, remove tag)
        for tag_name in [
            "ix:nonfraction", "ix:nonnumeric", "ix:continuation",
            "ix:footnote", "ix:fraction", "ix:numerator", "ix:denominator",
        ]:
            for tag in soup.find_all(tag_name):
                tag.unwrap()

        # Remove any remaining ix: namespace tags not caught above
        for tag in soup.find_all(re.compile(r"^ix:")):
            tag.decompose()

    def _remove_boilerplate(self, soup: BeautifulSoup) -> None:
        """Remove boilerplate elements from soup in place."""
        # Strip iXBRL metadata before boilerplate removal
        self._strip_ixbrl(soup)

        # Remove known boilerplate tags
        for tag_name in BOILERPLATE_TAGS:
            for tag in soup.find_all(tag_name):
                try:
                    tag.decompose()
                except Exception:
                    pass

        # Remove elements with boilerplate class/id
        # Collect tags to remove first to avoid modifying while iterating
        tags_to_remove = []
        for tag in soup.find_all(True):
            try:
                classes = tag.get("class", [])
                if classes:
                    classes = " ".join(classes) if isinstance(classes, list) else str(classes)
                else:
                    classes = ""
                tag_id = tag.get("id", "") or ""

                if BOILERPLATE_PATTERNS.search(classes) or BOILERPLATE_PATTERNS.search(tag_id):
                    tags_to_remove.append(tag)
            except Exception:
                pass

        for tag in tags_to_remove:
            try:
                tag.decompose()
            except Exception:
                pass

    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Find the main content container."""
        # Try semantic tags first
        for tag_name in ["main", "article"]:
            main = soup.find(tag_name)
            if main:
                return main

        # Try content-indicating classes/IDs
        for tag in soup.find_all(True):
            try:
                classes = tag.get("class", [])
                if classes:
                    classes = " ".join(classes) if isinstance(classes, list) else str(classes)
                else:
                    classes = ""
                tag_id = tag.get("id", "") or ""

                if CONTENT_PATTERNS.search(classes) or CONTENT_PATTERNS.search(tag_id):
                    # Verify it has substantial text
                    text = tag.get_text(strip=True)
                    if len(text) > 200:
                        return tag
            except Exception:
                pass

        # Try finding the div with most text content
        best_div = None
        best_text_len = 0

        for div in soup.find_all("div"):
            try:
                text = div.get_text(strip=True)
                text_len = len(text)

                # Penalize if it contains many links (likely navigation)
                link_count = len(div.find_all("a"))
                if link_count > 20:
                    text_len = text_len // 2

                if text_len > best_text_len:
                    best_text_len = text_len
                    best_div = div
            except Exception:
                pass

        if best_div and best_text_len > 500:
            return best_div

        return None

    def _extract_text(self, element) -> str:
        """Extract text from an element, preserving some structure."""
        if element is None:
            return ""

        texts = []

        for child in element.descendants:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    texts.append(text)
            elif child.name in ["p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"]:
                texts.append("\n")

        return " ".join(texts)

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text."""
        # Replace multiple whitespace with single space
        text = re.sub(r"[ \t]+", " ", text)

        # Normalize line breaks
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Remove empty lines at start/end
        text = text.strip()

        return text


def extract_html_text(html: str) -> HTMLExtractionResult:
    """
    Convenience function to extract text from HTML.

    Args:
        html: Raw HTML string

    Returns:
        HTMLExtractionResult
    """
    extractor = HTMLExtractor()
    return extractor.extract(html)


def extract_html_file(file_path: Path) -> HTMLExtractionResult:
    """
    Convenience function to extract text from an HTML file.

    Args:
        file_path: Path to HTML file

    Returns:
        HTMLExtractionResult
    """
    extractor = HTMLExtractor()
    return extractor.extract_from_file(file_path)

"""
Publish date extraction (NOR-99).

Extracts publication dates from document metadata and content.
Supports multiple date formats and sources.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)

# Common date patterns
DATE_PATTERNS = [
    # ISO format: 2024-01-15
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
    # US format: January 15, 2024 or Jan 15, 2024
    (r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", "month_name"),
    (r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b", "month_abbr"),
    # US format: 01/15/2024 or 1/15/24
    (r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", "us_slash"),
    # UK/ISO format: 15 January 2024
    (r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", "uk_format"),
    # SEC filing date patterns
    (r"Filed:\s*(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
    (r"Filing Date:\s*(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
    (r"Date:\s*(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
]

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


@dataclass
class DateExtractionResult:
    """Result of date extraction."""

    date: Optional[datetime]
    date_str: Optional[str]
    source: str  # "metadata", "url", "content", "filename"
    confidence: float  # 0.0 to 1.0
    raw_match: Optional[str]  # The original matched string


class DateExtractor:
    """
    Extract publication dates from documents.

    Tries multiple sources in order of reliability:
    1. URL patterns (SEC accession numbers contain dates)
    2. Metadata (HTML meta tags, PDF metadata)
    3. Content (dates in document text)
    4. Filename patterns
    """

    def extract_from_url(self, url: str) -> Optional[DateExtractionResult]:
        """
        Extract date from URL patterns.

        SEC URLs often contain dates in accession numbers:
        e.g., 0001193125-24-012345 → filed in 2024
        """
        if not url:
            return None

        # SEC accession number pattern: 0001193125-YY-NNNNNN
        sec_match = re.search(r"/(\d{10})-(\d{2})-(\d+)", url)
        if sec_match:
            year_suffix = sec_match.group(2)
            year = 2000 + int(year_suffix) if int(year_suffix) < 50 else 1900 + int(year_suffix)
            # We don't know the exact date, but we know the year
            try:
                date = datetime(year, 1, 1)
                return DateExtractionResult(
                    date=date,
                    date_str=f"{year}-01-01",
                    source="url_accession",
                    confidence=0.6,  # Lower confidence - only year is certain
                    raw_match=sec_match.group(0),
                )
            except ValueError:
                pass

        # Date in URL path: /2024/01/15/ or /20240115/
        path_date = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if path_date:
            try:
                date = datetime(
                    int(path_date.group(1)),
                    int(path_date.group(2)),
                    int(path_date.group(3)),
                )
                return DateExtractionResult(
                    date=date,
                    date_str=date.strftime("%Y-%m-%d"),
                    source="url_path",
                    confidence=0.9,
                    raw_match=path_date.group(0),
                )
            except ValueError:
                pass

        # Compact date: /20240115/
        compact_date = re.search(r"/(\d{4})(\d{2})(\d{2})/", url)
        if compact_date:
            try:
                date = datetime(
                    int(compact_date.group(1)),
                    int(compact_date.group(2)),
                    int(compact_date.group(3)),
                )
                return DateExtractionResult(
                    date=date,
                    date_str=date.strftime("%Y-%m-%d"),
                    source="url_path",
                    confidence=0.85,
                    raw_match=compact_date.group(0),
                )
            except ValueError:
                pass

        return None

    def extract_from_html_meta(self, html: str) -> Optional[DateExtractionResult]:
        """
        Extract date from HTML meta tags.
        """
        if not html:
            return None

        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return None

        # Try common meta date tags
        date_meta_names = [
            "article:published_time",
            "og:published_time",
            "datePublished",
            "date",
            "DC.date",
            "pubdate",
            "publication_date",
        ]

        for name in date_meta_names:
            # Try property attribute
            tag = soup.find("meta", property=name)
            if not tag:
                tag = soup.find("meta", {"name": name})

            if tag and tag.get("content"):
                date_str = tag["content"]
                result = self._parse_date_string(date_str)
                if result:
                    result.source = "html_meta"
                    result.confidence = 0.95
                    return result

        # Try time tag with datetime attribute
        time_tag = soup.find("time", datetime=True)
        if time_tag:
            date_str = time_tag["datetime"]
            result = self._parse_date_string(date_str)
            if result:
                result.source = "html_time_tag"
                result.confidence = 0.9
                return result

        return None

    def extract_from_content(
        self,
        text: str,
        search_first_n_chars: int = 2000,
    ) -> Optional[DateExtractionResult]:
        """
        Extract date from document content.

        Searches the beginning of the document for date patterns.
        """
        if not text:
            return None

        # Only search beginning of document (more likely to have publication date)
        search_text = text[:search_first_n_chars]

        # Try each pattern
        for pattern, format_type in DATE_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                result = self._parse_match(match, format_type)
                if result:
                    result.source = "content"
                    result.confidence = 0.7  # Lower confidence for content extraction
                    return result

        return None

    def extract_from_filename(self, filename: str) -> Optional[DateExtractionResult]:
        """
        Extract date from filename patterns.
        """
        if not filename:
            return None

        # Common filename date patterns
        # YYYY-MM-DD or YYYYMMDD
        patterns = [
            (r"(\d{4})-(\d{2})-(\d{2})", "iso"),
            (r"(\d{4})(\d{2})(\d{2})", "compact"),
            (r"(\d{2})-(\d{2})-(\d{4})", "us"),
        ]

        for pattern, ptype in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    if ptype == "iso" or ptype == "compact":
                        date = datetime(
                            int(match.group(1)),
                            int(match.group(2)),
                            int(match.group(3)),
                        )
                    else:  # us format
                        date = datetime(
                            int(match.group(3)),
                            int(match.group(1)),
                            int(match.group(2)),
                        )

                    # Validate reasonable date range
                    if 2000 <= date.year <= 2030:
                        return DateExtractionResult(
                            date=date,
                            date_str=date.strftime("%Y-%m-%d"),
                            source="filename",
                            confidence=0.75,
                            raw_match=match.group(0),
                        )
                except ValueError:
                    pass

        return None

    def extract(
        self,
        url: Optional[str] = None,
        html: Optional[str] = None,
        text: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Optional[DateExtractionResult]:
        """
        Extract publication date using all available sources.

        Tries sources in order of reliability:
        1. HTML metadata
        2. URL patterns
        3. Content
        4. Filename

        Returns the highest-confidence result.
        """
        results = []

        if html:
            result = self.extract_from_html_meta(html)
            if result:
                results.append(result)

        if url:
            result = self.extract_from_url(url)
            if result:
                results.append(result)

        if text:
            result = self.extract_from_content(text)
            if result:
                results.append(result)

        if filename:
            result = self.extract_from_filename(filename)
            if result:
                results.append(result)

        if not results:
            return None

        # Return highest confidence result
        return max(results, key=lambda r: r.confidence)

    def _parse_date_string(self, date_str: str) -> Optional[DateExtractionResult]:
        """Parse a date string in various formats."""
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try ISO format first
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
            try:
                date = datetime.strptime(date_str[:19], fmt[:len(date_str)])
                return DateExtractionResult(
                    date=date,
                    date_str=date.strftime("%Y-%m-%d"),
                    source="parsed",
                    confidence=0.9,
                    raw_match=date_str,
                )
            except ValueError:
                continue

        # Try other formats
        result = self._parse_match_from_string(date_str)
        if result:
            return result

        return None

    def _parse_match(self, match, format_type: str) -> Optional[DateExtractionResult]:
        """Parse a regex match into a date."""
        try:
            if format_type == "%Y-%m-%d":
                date = datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                )
            elif format_type == "month_name":
                month = MONTH_NAMES.get(match.group(1).lower())
                if month:
                    date = datetime(int(match.group(3)), month, int(match.group(2)))
                else:
                    return None
            elif format_type == "month_abbr":
                month = MONTH_NAMES.get(match.group(1).lower().rstrip("."))
                if month:
                    date = datetime(int(match.group(3)), month, int(match.group(2)))
                else:
                    return None
            elif format_type == "us_slash":
                year = int(match.group(3))
                if year < 100:
                    year = 2000 + year if year < 50 else 1900 + year
                date = datetime(year, int(match.group(1)), int(match.group(2)))
            elif format_type == "uk_format":
                month = MONTH_NAMES.get(match.group(2).lower())
                if month:
                    date = datetime(int(match.group(3)), month, int(match.group(1)))
                else:
                    return None
            else:
                return None

            # Validate reasonable date range
            if not (2000 <= date.year <= 2030):
                return None

            return DateExtractionResult(
                date=date,
                date_str=date.strftime("%Y-%m-%d"),
                source="pattern",
                confidence=0.8,
                raw_match=match.group(0),
            )

        except (ValueError, IndexError):
            return None

    def _parse_match_from_string(self, text: str) -> Optional[DateExtractionResult]:
        """Try to parse a date from a string using all patterns."""
        for pattern, format_type in DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = self._parse_match(match, format_type)
                if result:
                    return result
        return None


def extract_date(
    url: Optional[str] = None,
    html: Optional[str] = None,
    text: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[DateExtractionResult]:
    """
    Convenience function to extract publication date.

    Args:
        url: Document URL
        html: Raw HTML content
        text: Extracted text content
        filename: Document filename

    Returns:
        DateExtractionResult or None
    """
    extractor = DateExtractor()
    return extractor.extract(url=url, html=html, text=text, filename=filename)

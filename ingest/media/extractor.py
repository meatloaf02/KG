"""
Article extraction and paywall detection for external media pages.

Uses trafilatura for clean text extraction and langdetect for language detection.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)

# HTTP status codes that indicate a paywall
PAYWALL_HTTP_STATUSES = {402, 403, 451}

# Title patterns that suggest a paywall
PAYWALL_TITLE_RE = re.compile(r"(?i)subscribe|subscription|sign in|log in")

# Body patterns that suggest a paywall
PAYWALL_BODY_PATTERNS = [
    re.compile(r"(?i)you have reached your limit"),
    re.compile(r"(?i)to continue reading"),
    re.compile(r"(?i)subscribe to continue"),
    re.compile(r"(?i)this content is available to subscribers"),
    re.compile(r"(?i)already a subscriber"),
    re.compile(r"(?i)purchase a subscription"),
]


@dataclass
class ArticleResult:
    """Result of extracting an article from HTML."""

    clean_text: str
    raw_html: str
    title: Optional[str]
    author: Optional[str]
    publish_date: Optional[date]
    publish_date_confidence: str  # "high" | "medium" | "low"
    language: Optional[str]
    is_paywalled: bool
    size_bytes: int


def detect_paywall(http_status: int, html: str) -> bool:
    """
    Detect whether a page is behind a paywall.

    Checks HTTP status code, title text, and body patterns.
    """
    if http_status in PAYWALL_HTTP_STATUSES:
        return True

    # Check title tag for paywall signals
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match and PAYWALL_TITLE_RE.search(title_match.group(1)):
        return True

    # Check body for paywall patterns
    for pattern in PAYWALL_BODY_PATTERNS:
        if pattern.search(html):
            return True

    return False


def extract_article(html: str, url: str) -> ArticleResult:
    """
    Extract clean article text and metadata from HTML.

    Uses trafilatura for extraction and langdetect for language detection.
    Falls back gracefully if libraries are unavailable.
    """
    try:
        import trafilatura
    except ImportError:
        logger.error("trafilatura not installed; run: pip install trafilatura")
        raise

    size_bytes = len(html.encode("utf-8"))

    # Extract clean text
    clean_text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    ) or ""

    # Extract metadata
    metadata = trafilatura.extract_metadata(html, default_url=url)

    title: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[date] = None
    publish_date_confidence = "low"

    if metadata:
        title = metadata.title or None
        author = metadata.author or None

        if metadata.date:
            try:
                from datetime import datetime
                parsed_dt = datetime.strptime(metadata.date[:10], "%Y-%m-%d")
                publish_date = parsed_dt.date()
                publish_date_confidence = "high"
            except (ValueError, TypeError):
                pass

    # Language detection
    language: Optional[str] = None
    if clean_text:
        try:
            from langdetect import detect, LangDetectException
            language = detect(clean_text)
        except Exception:
            pass

    return ArticleResult(
        clean_text=clean_text,
        raw_html=html,
        title=title,
        author=author,
        publish_date=publish_date,
        publish_date_confidence=publish_date_confidence,
        language=language,
        is_paywalled=False,  # caller sets this after detect_paywall()
        size_bytes=size_bytes,
    )

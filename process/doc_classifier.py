"""
Document type classifier (NOR-98).

Rule-based classifier for document types:
- SEC filings (10-K, 10-Q, 8-K, DEF 14A, etc.)
- Earnings call transcripts
- Press releases
- Blog posts
- News/media articles
- Investor presentations
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)


class DocType(str, Enum):
    """Document type categories."""

    # SEC Filings
    SEC_10K = "sec_10k"
    SEC_10Q = "sec_10q"
    SEC_8K = "sec_8k"
    SEC_DEF14A = "sec_def14a"
    SEC_OTHER = "sec_other"

    # Corporate communications
    EARNINGS_CALL = "earnings_call"
    PRESS_RELEASE = "press_release"
    INVESTOR_PRESENTATION = "investor_presentation"

    # Content
    BLOG_POST = "blog_post"
    NEWS_ARTICLE = "news_article"
    PRODUCT_PAGE = "product_page"

    # Other
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of document classification."""

    doc_type: DocType
    confidence: float  # 0.0 to 1.0
    signals: list[str]  # Reasons for classification
    sub_type: Optional[str] = None  # e.g., "annual report" for 10-K


# URL patterns for classification
URL_PATTERNS = {
    # SEC filings
    DocType.SEC_10K: [
        r"/10-K", r"/10K", r"form10k", r"10-k\.htm",
        r"x10k\.htm", r"\d+d10k\.htm",
    ],
    DocType.SEC_10Q: [
        r"/10-Q", r"/10Q", r"form10q", r"10-q\.htm",
        r"x10q\.htm", r"\d+d10q\.htm",
    ],
    DocType.SEC_8K: [
        r"/8-K", r"/8K", r"form8k", r"8-k\.htm",
        r"d\w+d8k\.htm",
    ],
    DocType.SEC_DEF14A: [
        r"def14a", r"proxy", r"DEF\s*14A",
    ],
    DocType.SEC_OTHER: [
        r"sec\.gov/Archives/edgar", r"/edgar/data/",
    ],
    # Corporate
    DocType.PRESS_RELEASE: [
        r"/press-release", r"/news-release", r"/newsroom",
        r"prnewswire\.com", r"businesswire\.com", r"globenewswire\.com",
    ],
    DocType.EARNINGS_CALL: [
        r"earnings.call", r"earnings-call", r"transcript",
        r"seekingalpha\.com/article", r"fool\.com/earnings",
    ],
    DocType.INVESTOR_PRESENTATION: [
        r"/investor", r"investor-relations", r"presentation",
    ],
    # Content
    DocType.BLOG_POST: [
        r"/blog/", r"blog\.workday\.com",
    ],
    DocType.NEWS_ARTICLE: [
        r"reuters\.com", r"wsj\.com", r"bloomberg\.com",
        r"techcrunch\.com", r"zdnet\.com", r"forbes\.com",
    ],
    DocType.PRODUCT_PAGE: [
        r"/products/", r"/solutions/", r"/features/",
    ],
}

# Content patterns for classification
CONTENT_PATTERNS = {
    DocType.SEC_10K: [
        r"FORM\s+10-K",
        r"ANNUAL\s+REPORT",
        r"For the fiscal year ended",
    ],
    DocType.SEC_10Q: [
        r"FORM\s+10-Q",
        r"QUARTERLY\s+REPORT",
        r"For the quarterly period ended",
    ],
    DocType.SEC_8K: [
        r"FORM\s+8-K",
        r"CURRENT\s+REPORT",
    ],
    DocType.SEC_DEF14A: [
        r"SCHEDULE\s+14A",
        r"PROXY\s+STATEMENT",
        r"DEFINITIVE\s+PROXY",
        r"Annual Meeting of Stockholders",
    ],
    DocType.EARNINGS_CALL: [
        r"earnings\s+call",
        r"conference\s+call",
        r"Q[1-4]\s+\d{4}\s+(earnings|results)",
        r"Operator:",
        r"Question-and-Answer Session",
    ],
    DocType.PRESS_RELEASE: [
        r"FOR\s+IMMEDIATE\s+RELEASE",
        r"Media\s+Contact",
        r"Investor\s+Contact",
        r"announces|announced",
        r"###\s*$",  # Common press release ending
    ],
    DocType.BLOG_POST: [
        r"Posted\s+by",
        r"Written\s+by",
        r"Read\s+more",
        r"Share\s+this",
    ],
}


class DocumentClassifier:
    """
    Rule-based document type classifier.

    Uses URL patterns, content patterns, and metadata to classify documents.
    """

    def classify(
        self,
        url: Optional[str] = None,
        title: Optional[str] = None,
        text: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a document.

        Args:
            url: Document URL
            title: Document title
            text: Document text content
            source_type: Pre-assigned source type from ingestion

        Returns:
            ClassificationResult with type and confidence
        """
        signals = []
        scores = {doc_type: 0.0 for doc_type in DocType}

        # Check pre-assigned source type
        if source_type:
            source_result = self._check_source_type(source_type)
            if source_result:
                scores[source_result] += 0.5
                signals.append(f"source_type: {source_type}")

        # Check URL patterns
        if url:
            for doc_type, patterns in URL_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, url, re.IGNORECASE):
                        scores[doc_type] += 0.3
                        signals.append(f"url_pattern: {pattern}")
                        break

        # Check title patterns
        if title:
            title_result = self._check_title(title)
            if title_result:
                scores[title_result[0]] += title_result[1]
                signals.append(f"title: {title_result[2]}")

        # Check content patterns (first 5000 chars)
        # SEC form type declarations appear in the header (~first 500 chars).
        # Matches in the header get a higher score to distinguish a document's
        # own type from references to other filing types deeper in the text.
        if text:
            header_text = text[:500]
            content_text = text[:5000]
            for doc_type, patterns in CONTENT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, header_text, re.IGNORECASE):
                        scores[doc_type] += 0.3
                        signals.append(f"header_pattern: {pattern}")
                    elif re.search(pattern, content_text, re.IGNORECASE):
                        scores[doc_type] += 0.1
                        signals.append(f"content_pattern: {pattern}")

        # Find highest scoring type
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        # Exhibit/index URLs must never be classified as primary filings.
        # Their content references parent filing types (e.g. SOX certs say
        # "Form 10-K") which can outscore sec_other.
        if self._is_exhibit_url(url) and best_type in (
            DocType.SEC_10K, DocType.SEC_10Q,
            DocType.SEC_8K, DocType.SEC_DEF14A,
        ):
            best_type = DocType.SEC_OTHER
            best_score = scores[DocType.SEC_OTHER]
            signals.append("demoted: exhibit URL → sec_other")

        # Promote specific SEC filings over generic sec_other.
        # When sec_other wins (from broad EDGAR URL + source_type) but a
        # specific filing type (8-K, 10-Q, 10-K) also has signal, prefer it.
        # Skip promotion for exhibit/index URLs (handled above).
        if best_type == DocType.SEC_OTHER and not self._is_exhibit_url(url):
            specific_sec_types = [
                DocType.SEC_10K, DocType.SEC_10Q,
                DocType.SEC_8K, DocType.SEC_DEF14A,
            ]
            # Pick the highest-scoring specific type (not just first with signal)
            best_specific = max(specific_sec_types, key=lambda t: scores[t])
            if scores[best_specific] > 0:
                best_type = best_specific
                best_score = max(best_score, scores[best_specific])
                signals.append(f"promoted: {best_specific.value} over sec_other")

        # If no strong signal, default to unknown
        if best_score < 0.2:
            best_type = DocType.UNKNOWN
            best_score = 0.0

        # Determine sub-type
        sub_type = self._get_sub_type(best_type, title, text, url)

        # Normalize confidence
        confidence = min(best_score, 1.0)

        return ClassificationResult(
            doc_type=best_type,
            confidence=round(confidence, 2),
            signals=signals[:5],  # Limit to top 5 signals
            sub_type=sub_type,
        )

    def _check_source_type(self, source_type: str) -> Optional[DocType]:
        """Map source_type to DocType."""
        source_type = source_type.lower()

        mappings = {
            "sec_filing": DocType.SEC_OTHER,
            "sec_10k": DocType.SEC_10K,
            "sec_10q": DocType.SEC_10Q,
            "sec_8k": DocType.SEC_8K,
            "press_release": DocType.PRESS_RELEASE,
            "earnings_call": DocType.EARNINGS_CALL,
            "transcript": DocType.EARNINGS_CALL,
            "blog": DocType.BLOG_POST,
            "news": DocType.NEWS_ARTICLE,
            "investor_relations": DocType.INVESTOR_PRESENTATION,
        }

        for key, doc_type in mappings.items():
            if key in source_type:
                return doc_type

        return None

    def _check_title(self, title: str) -> Optional[tuple[DocType, float, str]]:
        """Check title for classification signals."""
        title_lower = title.lower()

        # SEC filing patterns in title
        if "10-k" in title_lower or "form 10k" in title_lower:
            return (DocType.SEC_10K, 0.4, "10-K in title")
        if "10-q" in title_lower or "form 10q" in title_lower:
            return (DocType.SEC_10Q, 0.4, "10-Q in title")
        if "8-k" in title_lower or "form 8k" in title_lower:
            return (DocType.SEC_8K, 0.4, "8-K in title")
        if "proxy" in title_lower or "def 14a" in title_lower:
            return (DocType.SEC_DEF14A, 0.4, "Proxy in title")

        # Earnings
        if "earnings" in title_lower and ("call" in title_lower or "results" in title_lower):
            return (DocType.EARNINGS_CALL, 0.4, "earnings in title")
        if "quarterly results" in title_lower:
            return (DocType.EARNINGS_CALL, 0.3, "quarterly results")

        # Press release
        if "announces" in title_lower or "announced" in title_lower:
            return (DocType.PRESS_RELEASE, 0.2, "announces in title")

        return None

    def _get_sub_type(
        self,
        doc_type: DocType,
        title: Optional[str],
        text: Optional[str],
        url: Optional[str] = None,
    ) -> Optional[str]:
        """Determine sub-type for certain document types."""
        if doc_type == DocType.SEC_10K:
            if text and "amendment" in text[:1000].lower():
                return "10-K/A (Amendment)"
            return "Annual Report"

        if doc_type == DocType.SEC_10Q:
            if text and "amendment" in text[:1000].lower():
                return "10-Q/A (Amendment)"
            return "Quarterly Report"

        if doc_type == DocType.SEC_8K:
            # Try to identify the 8-K item
            if text:
                items = self._extract_8k_items(text[:3000])
                if items:
                    return f"8-K Items: {', '.join(items)}"
            return "Current Report"

        if doc_type == DocType.EARNINGS_CALL:
            # Try to identify the quarter
            if title:
                quarter_match = re.search(r"Q([1-4])\s*(\d{4})", title, re.IGNORECASE)
                if quarter_match:
                    return f"Q{quarter_match.group(1)} {quarter_match.group(2)} Earnings Call"
            return "Earnings Call Transcript"

        if doc_type == DocType.SEC_DEF14A:
            return "Proxy Statement"

        if doc_type == DocType.SEC_OTHER:
            return self._get_sec_other_subtype(url, text)

        return None

    def _is_exhibit_url(self, url: Optional[str]) -> bool:
        """Check if URL indicates an exhibit or index page (not a primary filing)."""
        if not url:
            return False
        url_lower = url.lower()
        # EDGAR search/browse pages (not filings)
        if "browse-edgar" in url_lower:
            return True
        # Standard exhibit patterns: dex311, xex231, ex101, ex3-1, etc.
        if re.search(r"ex\d[\d-]+", url_lower):
            return True
        # Alternate exhibit 99.x naming: x991, x992 (without 'ex' prefix)
        if re.search(r"x99\d", url_lower):
            return True
        # Explicit "exhibit" in filename (e.g., a8-kaexhibit993.htm)
        if "exhibit" in url_lower:
            return True
        # EDGAR index pages
        if "-index.htm" in url_lower:
            return True
        return False

    def _get_sec_other_subtype(
        self,
        url: Optional[str],
        text: Optional[str],
    ) -> str:
        """Determine sub-type for sec_other documents.

        Uses URL-first logic (highest signal) with content-based fallbacks.
        Returns a controlled vocabulary string.
        """
        url_lower = (url or "").lower()

        # 1. EDGAR index pages
        if "-index.htm" in url_lower:
            return "index_page"

        # 2. Exhibit detection by URL pattern (ex + number, incl. hyphenated)
        exhibit_match = re.search(r"ex(\d[\d-]+)", url_lower)
        if exhibit_match:
            exhibit_num = exhibit_match.group(1)
            # SOX certifications: EX-31.x, EX-32.x
            if exhibit_num.startswith("31") or exhibit_num.startswith("32"):
                return "exhibit_certification"
            # Press releases: EX-99.x
            if exhibit_num.startswith("99"):
                return "exhibit_press_release"
            # Agreements/contracts: EX-10.x
            if exhibit_num.startswith("10"):
                return "exhibit_agreement"
            # Consent of auditors: EX-23.x
            if exhibit_num.startswith("23"):
                return "exhibit_consent"
            # Subsidiaries list: EX-21.x
            if exhibit_num.startswith("21"):
                return "exhibit_subsidiaries"
            # Any other exhibit
            return "exhibit_other"

        # 3. Content-based fallbacks (first 5000 chars)
        if text:
            content = text[:5000].lower()
            # SOX certification language
            if "certif" in content and "sarbanes" in content:
                return "exhibit_certification"
            # Press release language
            if "forward-looking statements" in content:
                return "exhibit_press_release"

        # 4. Default for remaining sec_other
        return "filing_document"

    def _extract_8k_items(self, text: str) -> list[str]:
        """Extract 8-K item numbers from text."""
        items = []

        # Common 8-K items
        item_patterns = [
            (r"Item\s*2\.02", "2.02 (Results of Operations)"),
            (r"Item\s*5\.02", "5.02 (Management Changes)"),
            (r"Item\s*7\.01", "7.01 (Regulation FD)"),
            (r"Item\s*8\.01", "8.01 (Other Events)"),
            (r"Item\s*9\.01", "9.01 (Financial Statements)"),
        ]

        for pattern, label in item_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                items.append(label.split()[0])

        return items


def classify_document(
    url: Optional[str] = None,
    title: Optional[str] = None,
    text: Optional[str] = None,
    source_type: Optional[str] = None,
) -> ClassificationResult:
    """
    Convenience function to classify a document.

    Args:
        url: Document URL
        title: Document title
        text: Document text content
        source_type: Pre-assigned source type

    Returns:
        ClassificationResult
    """
    classifier = DocumentClassifier()
    return classifier.classify(url=url, title=title, text=text, source_type=source_type)

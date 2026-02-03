"""
Link extraction from fetched HTML documents.

Parses index/listing pages to discover links to actual documents
for crawling.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import EXTERNAL_HTML_DIR, setup_logging
from ingest.domains import is_allowed_domain
from ingest.models import FetchStatus, RawDocument, get_session
from ingest.url_utils import extract_domain, get_url_hash, normalize_url

logger = setup_logging(__name__)


@dataclass
class ExtractedLink:
    """A link extracted from a document."""

    url: str
    source_url: str
    source_content_hash: str
    link_text: str
    source_type: str
    depth: int


class LinkExtractor:
    """
    Extract links from fetched HTML documents.

    Supports domain-specific extraction patterns for:
    - SEC EDGAR filing index pages
    - Workday investor relations pages
    - Press release listings
    - Blog post listings
    """

    def __init__(self, max_depth: int = 2):
        """
        Initialize link extractor.

        Args:
            max_depth: Maximum crawl depth (0 = seeds only)
        """
        self.max_depth = max_depth

    def extract_from_file(
        self,
        file_path: Path,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int = 0,
    ) -> list[ExtractedLink]:
        """
        Extract links from a local HTML file.

        Args:
            file_path: Path to HTML file
            source_url: Original URL of the document
            source_content_hash: Content hash of source document
            source_type: Type of source document
            current_depth: Current crawl depth

        Returns:
            List of extracted links
        """
        if current_depth >= self.max_depth:
            return []

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []

        try:
            html = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return []

        return self.extract_from_html(
            html=html,
            source_url=source_url,
            source_content_hash=source_content_hash,
            source_type=source_type,
            current_depth=current_depth,
        )

    def extract_from_html(
        self,
        html: str,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int = 0,
    ) -> list[ExtractedLink]:
        """
        Extract links from HTML content.

        Args:
            html: HTML content
            source_url: Original URL of the document
            source_content_hash: Content hash of source document
            source_type: Type of source document
            current_depth: Current crawl depth

        Returns:
            List of extracted links
        """
        domain = extract_domain(source_url)
        soup = BeautifulSoup(html, "lxml")

        # Use domain-specific extraction
        if "sec.gov" in domain:
            return self._extract_sec_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )
        elif "investor.workday.com" in domain:
            return self._extract_ir_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )
        elif "blog.workday.com" in domain:
            return self._extract_blog_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )
        elif "prnewswire.com" in domain:
            return self._extract_prnewswire_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )
        elif "techcrunch.com" in domain:
            return self._extract_techcrunch_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )
        else:
            return self._extract_generic_links(
                soup, source_url, source_content_hash, source_type, current_depth
            )

    def _extract_sec_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links from SEC EDGAR pages."""
        links = []
        base_url = "https://www.sec.gov"

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Filing index pages (from company search results)
            if "/Archives/edgar/data/" in href and "index" in href.lower():
                full_url = urljoin(base_url, href)
                links.append(
                    ExtractedLink(
                        url=full_url,
                        source_url=source_url,
                        source_content_hash=source_content_hash,
                        link_text=a.get_text(strip=True)[:100],
                        source_type="sec_filing_index",
                        depth=current_depth + 1,
                    )
                )

            # Actual filing documents (HTML files in Archives)
            elif "/Archives/edgar/data/" in href and href.endswith((".htm", ".html")):
                # Skip index files, we want actual documents
                if "index" not in href.lower():
                    full_url = urljoin(base_url, href)
                    links.append(
                        ExtractedLink(
                            url=full_url,
                            source_url=source_url,
                            source_content_hash=source_content_hash,
                            link_text=a.get_text(strip=True)[:100],
                            source_type="sec_filing",
                            depth=current_depth + 1,
                        )
                    )

        logger.debug(f"Extracted {len(links)} SEC links from {source_url}")
        return links

    def _extract_ir_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links from Workday investor relations pages."""
        links = []
        base_url = "https://investor.workday.com"

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            # Skip navigation and empty links
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Build full URL
            if href.startswith("/"):
                full_url = base_url + href
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin(source_url, href)

            # Filter for relevant links
            domain = extract_domain(full_url)
            if not is_allowed_domain(domain):
                continue

            # Look for document links (PDFs, press releases, etc.)
            if any(
                x in href.lower()
                for x in ["/news/", "/press", "/annual", "/sec-filings", ".pdf"]
            ):
                links.append(
                    ExtractedLink(
                        url=full_url,
                        source_url=source_url,
                        source_content_hash=source_content_hash,
                        link_text=text[:100],
                        source_type="investor_relations",
                        depth=current_depth + 1,
                    )
                )

        logger.debug(f"Extracted {len(links)} IR links from {source_url}")
        return links

    def _extract_blog_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links from Workday blog pages."""
        links = []
        base_url = "https://blog.workday.com"

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            if not href or href.startswith("#"):
                continue

            # Build full URL
            if href.startswith("/"):
                full_url = base_url + href
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin(source_url, href)

            # Filter for blog post links (typically have date pattern or /en-us/)
            if "blog.workday.com" in full_url:
                # Look for actual blog posts (usually have more path segments)
                path = urlparse(full_url).path
                segments = [s for s in path.split("/") if s]
                if len(segments) >= 3:  # e.g., /en-us/2024/01/post-title
                    links.append(
                        ExtractedLink(
                            url=full_url,
                            source_url=source_url,
                            source_content_hash=source_content_hash,
                            link_text=text[:100],
                            source_type="blog",
                            depth=current_depth + 1,
                        )
                    )

        logger.debug(f"Extracted {len(links)} blog links from {source_url}")
        return links

    def _extract_prnewswire_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links from PR Newswire search results."""
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            # PR Newswire press release links
            if "/news-releases/" in href and href.startswith("http"):
                links.append(
                    ExtractedLink(
                        url=href,
                        source_url=source_url,
                        source_content_hash=source_content_hash,
                        link_text=text[:100],
                        source_type="press_release",
                        depth=current_depth + 1,
                    )
                )

        logger.debug(f"Extracted {len(links)} PR Newswire links from {source_url}")
        return links

    def _extract_techcrunch_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links from TechCrunch tag pages."""
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            # TechCrunch article links (have date in URL)
            if re.search(r"techcrunch\.com/\d{4}/\d{2}/\d{2}/", href):
                links.append(
                    ExtractedLink(
                        url=href,
                        source_url=source_url,
                        source_content_hash=source_content_hash,
                        link_text=text[:100],
                        source_type="news_media",
                        depth=current_depth + 1,
                    )
                )

        logger.debug(f"Extracted {len(links)} TechCrunch links from {source_url}")
        return links

    def _extract_generic_links(
        self,
        soup: BeautifulSoup,
        source_url: str,
        source_content_hash: str,
        source_type: str,
        current_depth: int,
    ) -> list[ExtractedLink]:
        """Extract links generically (for unknown domains)."""
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Build full URL
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                parsed = urlparse(source_url)
                full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                full_url = urljoin(source_url, href)

            # Only include allowed domains
            domain = extract_domain(full_url)
            if is_allowed_domain(domain):
                links.append(
                    ExtractedLink(
                        url=full_url,
                        source_url=source_url,
                        source_content_hash=source_content_hash,
                        link_text=text[:100],
                        source_type=source_type,
                        depth=current_depth + 1,
                    )
                )

        logger.debug(f"Extracted {len(links)} generic links from {source_url}")
        return links


def extract_all_links(max_depth: int = 2) -> list[ExtractedLink]:
    """
    Extract links from all successfully fetched documents.

    Args:
        max_depth: Maximum crawl depth

    Returns:
        List of all extracted links
    """
    extractor = LinkExtractor(max_depth=max_depth)
    all_links = []

    db_session = get_session()
    try:
        # Get all successfully fetched documents
        docs = (
            db_session.query(RawDocument)
            .filter(RawDocument.status == FetchStatus.SUCCESS)
            .filter(RawDocument.file_path.isnot(None))
            .all()
        )

        for doc in docs:
            file_path = EXTERNAL_HTML_DIR.parent / doc.file_path
            if file_path.exists():
                links = extractor.extract_from_file(
                    file_path=file_path,
                    source_url=doc.url,
                    source_content_hash=doc.content_hash,
                    source_type=doc.source_type or "unknown",
                    current_depth=0,  # Seeds are depth 0
                )
                all_links.extend(links)

        logger.info(f"Extracted {len(all_links)} total links from {len(docs)} documents")

    finally:
        db_session.close()

    return all_links


def add_links_to_queue(links: list[ExtractedLink], dry_run: bool = False) -> dict:
    """
    Add extracted links to the ingestion queue (raw_documents table).

    Args:
        links: List of extracted links
        dry_run: If True, don't actually add to database

    Returns:
        Dictionary with counts of added, skipped, existing links
    """
    from ingest.models import get_document_by_url_hash

    stats = {"added": 0, "skipped": 0, "existing": 0}

    if dry_run:
        # Just count unique URLs
        seen_hashes = set()
        for link in links:
            url_hash = get_url_hash(link.url)
            if url_hash not in seen_hashes:
                seen_hashes.add(url_hash)
                stats["added"] += 1
        return stats

    db_session = get_session()
    try:
        seen_hashes = set()

        for link in links:
            url_hash = get_url_hash(link.url)

            # Skip duplicates in this batch
            if url_hash in seen_hashes:
                stats["skipped"] += 1
                continue
            seen_hashes.add(url_hash)

            # Check if already in database
            existing = get_document_by_url_hash(db_session, url_hash)
            if existing:
                stats["existing"] += 1
                continue

            # Add new document record
            doc = RawDocument(
                url=link.url,
                url_hash=url_hash,
                normalized_url=normalize_url(link.url),
                domain=extract_domain(link.url),
                source_type=link.source_type,
                status=FetchStatus.PENDING,
            )
            db_session.add(doc)
            stats["added"] += 1

        db_session.commit()
        logger.info(
            f"Added {stats['added']} links to queue "
            f"(skipped {stats['skipped']}, existing {stats['existing']})"
        )

    finally:
        db_session.close()

    return stats

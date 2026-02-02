"""
Document fetcher with database tracking and content storage.

Fetches HTML and PDF documents using rate limiting, robots.txt compliance,
and domain allowlist checking. Tracks all fetches in PostgreSQL.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from config import setup_logging
from ingest.domains import get_domain_config, is_allowed_domain
from ingest.models import (
    FetchStatus,
    RawDocument,
    get_document_by_url_hash,
    get_session,
)
from ingest.rate_limiter import ThrottledSession
from ingest.storage import ContentStorage, get_storage
from ingest.url_utils import (
    extract_domain,
    extract_sec_accession_number,
    get_content_hash,
    get_url_hash,
    is_valid_url,
    normalize_url,
)

logger = setup_logging(__name__)


@dataclass
class FetchResult:
    """Result of a document fetch operation."""

    url: str
    url_hash: str
    status: FetchStatus
    content_hash: Optional[str] = None
    file_path: Optional[str] = None
    content_type: Optional[str] = None
    content_size: Optional[int] = None
    http_status_code: Optional[int] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    already_existed: bool = False
    skipped_reason: Optional[str] = None


class DocumentFetcher:
    """
    Fetch documents with rate limiting, storage, and database tracking.

    Features:
    - Rate limiting via ThrottledSession
    - robots.txt compliance
    - Domain allowlist checking
    - Content-addressable storage
    - PostgreSQL metadata tracking
    - Title extraction from HTML
    - SEC accession number extraction
    """

    def __init__(
        self,
        storage: Optional[ContentStorage] = None,
        session: Optional[ThrottledSession] = None,
    ):
        """
        Initialize document fetcher.

        Args:
            storage: ContentStorage instance (uses default if None)
            session: ThrottledSession instance (creates new if None)
        """
        self.storage = storage or get_storage()
        self.session = session or ThrottledSession()

    def _extract_title(self, content: bytes, content_type: str) -> Optional[str]:
        """
        Extract title from HTML content.

        Args:
            content: Raw content bytes
            content_type: MIME type

        Returns:
            Title text or None
        """
        if "html" not in content_type.lower():
            return None

        try:
            soup = BeautifulSoup(content, "lxml")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return title_tag.string.strip()[:500]  # Limit length
        except Exception as e:
            logger.debug(f"Failed to extract title: {e}")

        return None

    def _check_preconditions(
        self, url: str, source_type: str, skip_if_exists: bool
    ) -> Optional[FetchResult]:
        """
        Check preconditions before fetching.

        Returns FetchResult if fetch should be skipped, None if fetch should proceed.
        """
        url_hash = get_url_hash(url)

        # Validate URL
        if not is_valid_url(url):
            return FetchResult(
                url=url,
                url_hash=url_hash,
                status=FetchStatus.FAILED,
                error_message="Invalid URL format",
            )

        # Check domain allowlist
        domain = extract_domain(url)
        if not is_allowed_domain(domain):
            return FetchResult(
                url=url,
                url_hash=url_hash,
                status=FetchStatus.SKIPPED,
                skipped_reason=f"Domain not in allowlist: {domain}",
            )

        # Check if already fetched
        if skip_if_exists:
            db_session = get_session()
            try:
                existing = get_document_by_url_hash(db_session, url_hash)
                if existing and existing.status == FetchStatus.SUCCESS:
                    return FetchResult(
                        url=url,
                        url_hash=url_hash,
                        status=FetchStatus.SUCCESS,
                        content_hash=existing.content_hash,
                        file_path=existing.file_path,
                        already_existed=True,
                        skipped_reason="Already fetched successfully",
                    )
            finally:
                db_session.close()

        return None

    def _create_pending_record(
        self, url: str, url_hash: str, source_type: str
    ) -> RawDocument:
        """Create a pending record in the database."""
        db_session = get_session()
        try:
            # Check if record exists
            doc = get_document_by_url_hash(db_session, url_hash)

            if doc is None:
                doc = RawDocument(
                    url=url,
                    url_hash=url_hash,
                    normalized_url=normalize_url(url),
                    domain=extract_domain(url),
                    source_type=source_type,
                    status=FetchStatus.PENDING,
                    sec_accession_number=extract_sec_accession_number(url),
                )
                db_session.add(doc)
            else:
                doc.status = FetchStatus.PENDING
                doc.error_message = None

            db_session.commit()
            db_session.refresh(doc)
            return doc
        finally:
            db_session.close()

    def _update_record_success(
        self,
        url_hash: str,
        content_hash: str,
        content_type: str,
        content_size: int,
        file_path: str,
        http_status_code: int,
        title: Optional[str],
    ) -> None:
        """Update record after successful fetch."""
        db_session = get_session()
        try:
            doc = get_document_by_url_hash(db_session, url_hash)
            if doc:
                doc.status = FetchStatus.SUCCESS
                doc.fetched_at = datetime.utcnow()
                doc.content_hash = content_hash
                doc.content_type = content_type
                doc.content_size = content_size
                doc.file_path = file_path
                doc.http_status_code = http_status_code
                doc.title = title
                db_session.commit()
        finally:
            db_session.close()

    def _update_record_failed(
        self, url_hash: str, http_status_code: Optional[int], error_message: str
    ) -> None:
        """Update record after failed fetch."""
        db_session = get_session()
        try:
            doc = get_document_by_url_hash(db_session, url_hash)
            if doc:
                doc.status = FetchStatus.FAILED
                doc.fetched_at = datetime.utcnow()
                doc.http_status_code = http_status_code
                doc.error_message = error_message[:1000]  # Limit length
                db_session.commit()
        finally:
            db_session.close()

    def fetch(
        self,
        url: str,
        source_type: str = "unknown",
        skip_if_exists: bool = True,
    ) -> FetchResult:
        """
        Fetch a document and store it.

        Args:
            url: URL to fetch
            source_type: Type of source (e.g., 'sec_filing')
            skip_if_exists: Skip if URL was already fetched successfully

        Returns:
            FetchResult with status and metadata
        """
        url_hash = get_url_hash(url)
        logger.debug(f"Fetching {url} (hash: {url_hash})")

        # Check preconditions
        skip_result = self._check_preconditions(url, source_type, skip_if_exists)
        if skip_result:
            if skip_result.already_existed:
                logger.debug(f"Skipping {url}: already fetched")
            elif skip_result.skipped_reason:
                logger.warning(f"Skipping {url}: {skip_result.skipped_reason}")
            return skip_result

        # Create pending record
        self._create_pending_record(url, url_hash, source_type)

        try:
            # Make the request
            response = self.session.get(url, timeout=30)

            # Get content and metadata
            content = response.content
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            content_hash = get_content_hash(content)

            # Store content
            storage_result = self.storage.store(
                content=content,
                mime_type=content_type,
                content_hash=content_hash,
            )

            # Extract title from HTML
            title = self._extract_title(content, content_type)

            # Update database record
            self._update_record_success(
                url_hash=url_hash,
                content_hash=content_hash,
                content_type=content_type,
                content_size=storage_result.size,
                file_path=storage_result.relative_path,
                http_status_code=response.status_code,
                title=title,
            )

            logger.info(
                f"Fetched {url} -> {storage_result.relative_path} "
                f"({storage_result.size} bytes)"
            )

            return FetchResult(
                url=url,
                url_hash=url_hash,
                status=FetchStatus.SUCCESS,
                content_hash=content_hash,
                file_path=storage_result.relative_path,
                content_type=content_type,
                content_size=storage_result.size,
                http_status_code=response.status_code,
                title=title,
                already_existed=storage_result.already_existed,
            )

        except ValueError as e:
            # robots.txt disallowed
            error_msg = str(e)
            self._update_record_failed(url_hash, None, error_msg)
            logger.warning(f"Blocked by robots.txt: {url}")
            return FetchResult(
                url=url,
                url_hash=url_hash,
                status=FetchStatus.SKIPPED,
                error_message=error_msg,
                skipped_reason="Blocked by robots.txt",
            )

        except Exception as e:
            # Request failed
            error_msg = str(e)
            http_code = getattr(e, "response", None)
            if http_code:
                http_code = getattr(http_code, "status_code", None)

            self._update_record_failed(url_hash, http_code, error_msg)
            logger.error(f"Failed to fetch {url}: {error_msg}")

            return FetchResult(
                url=url,
                url_hash=url_hash,
                status=FetchStatus.FAILED,
                http_status_code=http_code,
                error_message=error_msg,
            )

    def fetch_many(
        self,
        urls: list[tuple[str, str]],
        skip_if_exists: bool = True,
        limit: Optional[int] = None,
    ) -> list[FetchResult]:
        """
        Fetch multiple documents.

        Args:
            urls: List of (url, source_type) tuples
            skip_if_exists: Skip URLs already fetched successfully
            limit: Maximum number of documents to fetch

        Returns:
            List of FetchResult objects
        """
        results = []

        for i, (url, source_type) in enumerate(urls):
            if limit and i >= limit:
                break

            result = self.fetch(url, source_type, skip_if_exists)
            results.append(result)

        # Log summary
        success_count = sum(1 for r in results if r.status == FetchStatus.SUCCESS)
        skip_count = sum(1 for r in results if r.status == FetchStatus.SKIPPED)
        fail_count = sum(1 for r in results if r.status == FetchStatus.FAILED)

        logger.info(
            f"Fetch complete: {success_count} success, {skip_count} skipped, {fail_count} failed"
        )

        return results


# Global fetcher instance
_fetcher: Optional[DocumentFetcher] = None


def get_fetcher() -> DocumentFetcher:
    """Get or create global fetcher instance."""
    global _fetcher
    if _fetcher is None:
        _fetcher = DocumentFetcher()
    return _fetcher

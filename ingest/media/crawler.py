"""
MediaCrawler — one-shot external media crawl orchestration.

Implements the YAML spec workday_external_media_one_shot_2012_2025.yaml:
- BFS from seed URLs
- Per-domain throttling via ThrottledSession
- robots.txt compliance
- Paywall detection and drop
- Article extraction via trafilatura
- Two-stage Workday relevance filter
- Date window enforcement (2012-01-01 – 2025-12-31)
- Language filter (English only)
- Content-hash exact dedup + simhash near-dup clustering
- JSON blob storage in data/interim/{hash[:2]}/{hash}.json
- Upsert to document_manifest (PostgreSQL)
"""

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from config import INTERIM_DATA_DIR, setup_logging
from ingest.domains import get_domain_config, is_allowed_domain
from ingest.media.dedup import NearDupDetector, canonicalize_url, is_article_like
from ingest.media.extractor import ArticleResult, detect_paywall, extract_article
from ingest.media.relevance import has_ai_keyword, is_blocked_path, relevance_check
from ingest.rate_limiter import ThrottledSession
from ingest.url_utils import extract_domain, get_content_hash, get_url_hash

logger = setup_logging(__name__)


@dataclass
class CrawlStats:
    """Running counters for the crawl session."""

    fetched_total: int = 0
    fetched_success: int = 0
    fetched_failed: int = 0
    dropped_paywalled_total: int = 0
    dropped_out_of_window_total: int = 0
    dropped_not_relevant_total: int = 0
    dropped_not_english_total: int = 0
    stored_docs_total: int = 0
    exact_dup_total: int = 0
    near_dup_total: int = 0
    publish_date_found: int = 0
    ai_keyword_hits: int = 0
    stored_docs_by_domain: dict = field(default_factory=dict)


@dataclass
class ProcessResult:
    """Internal result of processing a single URL."""

    stored: bool = False
    outlinks: list = field(default_factory=list)


class MediaCrawler:
    """
    One-shot external media crawler.

    Usage:
        crawler = MediaCrawler()
        stats = crawler.run(seeds=["https://venturebeat.com/?s=workday"], limit=500)
    """

    PARSER_VERSION = "1.0.0"
    DATE_START = date(2012, 1, 1)
    DATE_END = date(2025, 12, 31)
    MAX_PAGES_TOTAL = 20_000
    MAX_PAGES_PER_DOMAIN = 2_500
    MAX_OUTLINKS_PER_PAGE = 15

    def __init__(self, db_session=None) -> None:
        self.session = ThrottledSession()
        self.dedup = NearDupDetector()
        self.stats = CrawlStats()
        self.interim_dir = INTERIM_DATA_DIR
        self._db_session = db_session  # injected; lazy-created if None
        self._seen_content_hashes: set[str] = set()

    def _get_db_session(self):
        if self._db_session is None:
            from ingest.models import get_session
            self._db_session = get_session()
        return self._db_session

    # Skip a domain after this many consecutive fetch failures (e.g. persistent 403/429)
    MAX_CONSECUTIVE_DOMAIN_FAILURES = 5

    def run(self, seeds: list[str], limit: Optional[int] = None) -> CrawlStats:
        """
        Execute the crawl from the given seed URLs.

        Args:
            seeds: Starting URLs.
            limit: Stop after this many total fetch attempts (for smoke tests).

        Returns:
            CrawlStats with final counts.
        """
        queue: deque[str] = deque(seeds)
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = defaultdict(int)
        domain_consecutive_failures: dict[str, int] = defaultdict(int)
        skipped_domains: set[str] = set()

        effective_limit = limit if limit is not None else self.MAX_PAGES_TOTAL

        while queue and self.stats.fetched_total < effective_limit:
            url = queue.popleft()

            canonical = canonicalize_url(url)
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)

            if is_blocked_path(canonical):
                logger.debug(f"Blocked path: {canonical}")
                continue

            domain = extract_domain(canonical)
            if not is_allowed_domain(domain):
                logger.debug(f"Domain not in allowlist: {domain}")
                continue

            if domain in skipped_domains:
                logger.debug(f"Domain skipped (persistent failures): {domain}")
                continue

            if domain_counts[domain] >= self.MAX_PAGES_PER_DOMAIN:
                logger.debug(f"Domain page limit reached: {domain}")
                continue

            failures_before = self.stats.fetched_failed
            result = self._process_url(canonical, domain)
            domain_counts[domain] += 1

            # Track consecutive fetch failures per domain to skip persistently-blocked domains
            if self.stats.fetched_failed > failures_before:
                domain_consecutive_failures[domain] += 1
                if domain_consecutive_failures[domain] >= self.MAX_CONSECUTIVE_DOMAIN_FAILURES:
                    logger.warning(
                        f"Skipping domain after {self.MAX_CONSECUTIVE_DOMAIN_FAILURES} "
                        f"consecutive failures: {domain}"
                    )
                    skipped_domains.add(domain)
            else:
                domain_consecutive_failures[domain] = 0

            if result and result.outlinks:
                for link in result.outlinks[: self.MAX_OUTLINKS_PER_PAGE]:
                    if link not in seen_urls:
                        queue.append(link)

        return self.stats

    def _process_url(self, url: str, domain: str) -> Optional[ProcessResult]:
        """Fetch, filter, extract, and store a single URL."""
        self.stats.fetched_total += 1

        # a. Fetch
        try:
            response = self.session.get(url, timeout=15)
            html = response.text
            http_status = response.status_code
            mime = response.headers.get("Content-Type", "").split(";")[0].strip()
        except Exception as exc:
            logger.warning(f"Fetch failed: {url} — {exc}")
            self.stats.fetched_failed += 1
            return None

        self.stats.fetched_success += 1

        # b. Paywall detection
        if detect_paywall(http_status, html):
            logger.debug(f"Paywalled: {url}")
            self.stats.dropped_paywalled_total += 1
            return None

        # c. Article extraction
        try:
            article = extract_article(html, url)
        except Exception as exc:
            logger.warning(f"Extraction failed: {url} — {exc}")
            self.stats.fetched_failed += 1
            return None

        # d. Relevance filter
        combined_text = " ".join(filter(None, [article.title, article.clean_text]))
        is_relevant, match_type = relevance_check(combined_text)
        if not is_relevant:
            logger.debug(f"Not relevant: {url}")
            self.stats.dropped_not_relevant_total += 1
            return self._extract_outlinks(html, url, domain)

        # e. Date window check
        if article.publish_date is not None:
            if not (self.DATE_START <= article.publish_date <= self.DATE_END):
                logger.debug(f"Out of date window ({article.publish_date}): {url}")
                self.stats.dropped_out_of_window_total += 1
                return self._extract_outlinks(html, url, domain)

        # f. Language check
        if article.language and article.language != "en":
            logger.debug(f"Non-English ({article.language}): {url}")
            self.stats.dropped_not_english_total += 1
            return None

        # g. Content hash + exact dedup
        content_hash = get_content_hash(article.clean_text.encode("utf-8"))
        if content_hash in self._seen_content_hashes:
            logger.debug(f"Exact duplicate: {url}")
            self.stats.exact_dup_total += 1
            return self._extract_outlinks(html, url, domain)
        self._seen_content_hashes.add(content_hash)

        # Near-dup check
        dup_of_hash = self.dedup.check_and_register(content_hash, article.clean_text)
        near_dup_cluster_id = dup_of_hash  # None if new
        if dup_of_hash is not None:
            self.stats.near_dup_total += 1

        # h. Store JSON blob
        self._store_blob(content_hash, article)

        # i. Upsert to document_manifest
        domain_cfg = get_domain_config(domain)
        ai_hit = has_ai_keyword(combined_text)

        from ingest.media.models import DocumentManifest, upsert_manifest

        doc = DocumentManifest(
            content_hash=content_hash,
            url=url,
            canonical_url=canonicalize_url(url),
            url_hash=get_url_hash(url),
            source_type="external_media",
            publisher=domain,
            domain=domain,
            tier=domain_cfg.tier if domain_cfg else "",
            title=article.title,
            author=article.author,
            publish_date=article.publish_date,
            publish_date_confidence=article.publish_date_confidence,
            fetched_at=datetime.utcnow(),
            http_status=http_status,
            mime=mime,
            size_bytes=article.size_bytes,
            language=article.language,
            is_paywalled=False,
            workday_match_type=match_type,
            ai_keyword_hit=ai_hit,
            near_dup_cluster_id=near_dup_cluster_id,
            dup_of_hash=dup_of_hash,
            parser_version=self.PARSER_VERSION,
        )

        try:
            upsert_manifest(self._get_db_session(), doc)
        except Exception as exc:
            logger.warning(f"DB upsert failed for {url}: {exc}")

        # Update stats
        self.stats.stored_docs_total += 1
        self.stats.stored_docs_by_domain[domain] = (
            self.stats.stored_docs_by_domain.get(domain, 0) + 1
        )
        if article.publish_date is not None:
            self.stats.publish_date_found += 1
        if ai_hit:
            self.stats.ai_keyword_hits += 1

        logger.info(f"Stored: {url} [{domain}]")

        return self._extract_outlinks(html, url, domain)

    def _store_blob(self, content_hash: str, article: ArticleResult) -> None:
        """Write clean text + raw HTML to data/interim/{hash[:2]}/{hash}.json."""
        path = self.interim_dir / content_hash[:2] / f"{content_hash}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "content_hash": content_hash,
                    "clean_text": article.clean_text,
                    "raw_html_optional": article.raw_html,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _extract_outlinks(
        self, html: str, base_url: str, domain: str
    ) -> ProcessResult:
        """Extract article-like outlinks from the page that belong to the same domain."""
        from bs4 import BeautifulSoup

        outlinks: list[str] = []
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup.find_all("a", href=True):
                href = tag["href"].strip()
                if not href or href.startswith("#"):
                    continue
                absolute = urljoin(base_url, href)
                if extract_domain(absolute) == domain and is_article_like(absolute):
                    outlinks.append(canonicalize_url(absolute))
        except Exception as exc:
            logger.debug(f"Outlink extraction failed for {base_url}: {exc}")

        return ProcessResult(stored=True, outlinks=outlinks)

    def write_report(self, out_path: Path) -> None:
        """Write crawl_run_report.json to out_path."""
        from ingest.media.reporter import write_report
        write_report(self.stats, out_path)

    @staticmethod
    def seed_from_search(query: str) -> list[str]:
        """
        Stub for SerpAPI-based seed generation.

        A live API key is required; returns empty list and logs a warning.
        """
        logger.warning(
            "seed_from_search: SerpAPI provider not configured. "
            "Set SERPAPI_KEY environment variable to enable search-based seeding."
        )
        return []

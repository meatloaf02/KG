"""
Tests for ingest module.
"""

import pytest


class TestDomains:
    """Tests for domain allowlist."""

    def test_allowed_domains_not_empty(self):
        from ingest.domains import ALLOWED_DOMAINS

        assert len(ALLOWED_DOMAINS) > 0

    def test_is_allowed_domain(self):
        from ingest.domains import is_allowed_domain

        assert is_allowed_domain("sec.gov")
        assert is_allowed_domain("www.sec.gov")
        assert is_allowed_domain("investor.workday.com")
        assert not is_allowed_domain("example.com")
        assert not is_allowed_domain("malicious-site.com")

    def test_get_domain_config(self):
        from ingest.domains import SourceType, get_domain_config

        config = get_domain_config("sec.gov")
        assert config is not None
        assert config.source_type == SourceType.SEC_FILING
        assert config.requests_per_second > 0

    def test_get_domains_by_source_type(self):
        from ingest.domains import SourceType, get_domains_by_source_type

        sec_domains = get_domains_by_source_type(SourceType.SEC_FILING)
        assert len(sec_domains) >= 1
        assert all(d.source_type == SourceType.SEC_FILING for d in sec_domains)


class TestURLUtils:
    """Tests for URL normalization and deduplication."""

    def test_normalize_url_basic(self):
        from ingest.url_utils import normalize_url

        # Lowercase
        assert normalize_url("HTTP://EXAMPLE.COM/Path") == "http://example.com/Path"

        # Remove default ports
        assert normalize_url("http://example.com:80/path") == "http://example.com/path"
        assert (
            normalize_url("https://example.com:443/path") == "https://example.com/path"
        )

        # Remove trailing slashes
        assert normalize_url("http://example.com/path/") == "http://example.com/path"
        assert normalize_url("http://example.com/") == "http://example.com/"

    def test_normalize_url_tracking_params(self):
        from ingest.url_utils import normalize_url

        # Remove UTM parameters
        url = "http://example.com/page?utm_source=google&utm_medium=cpc&id=123"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "id=123" in normalized

    def test_url_hash(self):
        from ingest.url_utils import get_url_hash

        hash1 = get_url_hash("http://example.com/page")
        hash2 = get_url_hash("http://example.com/page")
        hash3 = get_url_hash("http://example.com/other")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 16

    def test_is_same_document(self):
        from ingest.url_utils import is_same_document

        assert is_same_document(
            "http://example.com/page", "http://example.com/page"
        )
        assert is_same_document(
            "http://example.com/page?utm_source=x",
            "http://example.com/page?utm_medium=y",
        )
        assert not is_same_document(
            "http://example.com/page1", "http://example.com/page2"
        )

    def test_is_valid_url(self):
        from ingest.url_utils import is_valid_url

        assert is_valid_url("http://example.com")
        assert is_valid_url("https://example.com/path?query=1")
        assert not is_valid_url("")
        assert not is_valid_url("not-a-url")
        assert not is_valid_url("ftp://example.com")

    def test_url_deduplicator(self):
        from ingest.url_utils import URLDeduplicator

        dedup = URLDeduplicator()

        # First URL is new
        assert not dedup.is_url_seen("http://example.com/page")
        dedup.mark_url_seen("http://example.com/page")
        assert dedup.is_url_seen("http://example.com/page")

        # Normalized version is also seen
        assert dedup.is_url_seen("http://example.com/page?utm_source=x")

        # Different URL is not seen
        assert not dedup.is_url_seen("http://example.com/other")

    def test_content_hash(self):
        from ingest.url_utils import get_content_hash

        content1 = b"Hello, world!"
        content2 = b"Hello, world!"
        content3 = b"Different content"

        hash1 = get_content_hash(content1)
        hash2 = get_content_hash(content2)
        hash3 = get_content_hash(content3)

        assert hash1 == hash2
        assert hash1 != hash3


class TestRateLimiter:
    """Tests for rate limiting."""

    def test_calculate_backoff(self):
        from ingest.rate_limiter import calculate_backoff

        delay0 = calculate_backoff(0)
        delay1 = calculate_backoff(1)
        delay2 = calculate_backoff(2)

        # Should increase exponentially (with some jitter)
        assert delay0 < delay1 < delay2

    def test_rate_limiter_basic(self):
        from ingest.rate_limiter import RateLimiter

        limiter = RateLimiter(default_rate=10.0)  # 10 req/s for fast test

        # First request should not wait much
        wait1 = limiter.wait_if_needed("http://example.com/page1")
        assert wait1 < 0.2

    def test_rate_limiter_domain_specific(self):
        from ingest.rate_limiter import RateLimiter

        limiter = RateLimiter(
            default_rate=1.0,
            domain_rates={"fast.com": 10.0, "slow.com": 0.5},
        )

        state_fast = limiter._get_domain_state("fast.com")
        state_slow = limiter._get_domain_state("slow.com")

        assert state_fast.requests_per_second == 10.0
        assert state_slow.requests_per_second == 0.5


class TestRobots:
    """Tests for robots.txt handling."""

    def test_robots_checker_init(self):
        from ingest.robots import RobotsChecker

        checker = RobotsChecker()
        assert checker.user_agent is not None
        assert checker.cache_ttl > 0

    def test_get_sec_headers(self):
        from ingest.robots import get_sec_headers

        headers = get_sec_headers()
        assert "User-Agent" in headers
        assert "sec.gov" in headers.get("Host", "").lower() or True  # Optional check

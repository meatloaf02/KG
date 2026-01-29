"""
Robots.txt compliance and user-agent handling.

Ensures all crawling respects robots.txt directives and uses
appropriate identification headers.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from config import REQUEST_DELAY_SECONDS, USER_AGENT, setup_logging

logger = setup_logging(__name__)

# Default user agent for the crawler
DEFAULT_USER_AGENT = USER_AGENT

# Contact email for responsible crawling
CONTACT_EMAIL = "academic-research@example.edu"

# Cache expiry for robots.txt (1 hour)
ROBOTS_CACHE_TTL = 3600


@dataclass
class RobotsResult:
    """Result of robots.txt check."""

    allowed: bool
    crawl_delay: Optional[float] = None
    reason: str = ""


@dataclass
class CachedRobots:
    """Cached robots.txt parser with expiry."""

    parser: RobotFileParser
    fetched_at: float
    fetch_success: bool = True


class RobotsChecker:
    """
    Check robots.txt compliance for URLs.

    Caches robots.txt files per domain and respects crawl-delay directives.
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_ttl: int = ROBOTS_CACHE_TTL,
        default_delay: float = REQUEST_DELAY_SECONDS,
    ):
        """
        Initialize robots checker.

        Args:
            user_agent: User agent string to use
            cache_ttl: Cache time-to-live in seconds
            default_delay: Default delay if no crawl-delay specified
        """
        self.user_agent = user_agent
        self.cache_ttl = cache_ttl
        self.default_delay = default_delay
        self._cache: dict[str, CachedRobots] = {}

    def _get_robots_url(self, url: str) -> str:
        """Get robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_cache_key(self, url: str) -> str:
        """Get cache key (domain) for a URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _is_cache_valid(self, cached: CachedRobots) -> bool:
        """Check if cached robots.txt is still valid."""
        return time.time() - cached.fetched_at < self.cache_ttl

    def _fetch_robots(self, url: str) -> RobotFileParser:
        """
        Fetch and parse robots.txt for a URL.

        Args:
            url: Any URL from the target domain

        Returns:
            RobotFileParser instance
        """
        robots_url = self._get_robots_url(url)
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            # Fetch with our user agent
            response = requests.get(
                robots_url,
                headers=self._get_headers(),
                timeout=10,
                allow_redirects=True,
            )

            if response.status_code == 200:
                parser.parse(response.text.splitlines())
                logger.debug(f"Fetched robots.txt from {robots_url}")
            elif response.status_code in (404, 410):
                # No robots.txt means everything is allowed
                logger.debug(f"No robots.txt at {robots_url} (status {response.status_code})")
            else:
                # Treat other errors as disallow-all for safety
                logger.warning(
                    f"Unexpected status {response.status_code} for {robots_url}"
                )

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
            # On network error, allow access but log warning

        return parser

    def _get_cached_parser(self, url: str) -> RobotFileParser:
        """Get cached or fresh robots.txt parser."""
        cache_key = self._get_cache_key(url)

        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if self._is_cache_valid(cached):
                return cached.parser

        # Fetch fresh
        parser = self._fetch_robots(url)
        self._cache[cache_key] = CachedRobots(
            parser=parser,
            fetched_at=time.time(),
        )

        return parser

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with user agent."""
        return {
            "User-Agent": self.user_agent,
            "From": CONTACT_EMAIL,
            "Accept": "text/plain, text/html, */*",
        }

    def can_fetch(self, url: str) -> RobotsResult:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            RobotsResult with allowed status and crawl delay
        """
        try:
            parser = self._get_cached_parser(url)

            # Check if allowed
            allowed = parser.can_fetch(self.user_agent, url)

            # Get crawl delay
            crawl_delay = parser.crawl_delay(self.user_agent)
            if crawl_delay is None:
                crawl_delay = self.default_delay

            if allowed:
                return RobotsResult(
                    allowed=True,
                    crawl_delay=crawl_delay,
                    reason="Allowed by robots.txt",
                )
            else:
                return RobotsResult(
                    allowed=False,
                    crawl_delay=crawl_delay,
                    reason="Disallowed by robots.txt",
                )

        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # On error, allow but with warning
            return RobotsResult(
                allowed=True,
                crawl_delay=self.default_delay,
                reason=f"Error checking robots.txt: {e}",
            )

    def get_crawl_delay(self, url: str) -> float:
        """
        Get crawl delay for a URL's domain.

        Args:
            url: URL to check

        Returns:
            Crawl delay in seconds
        """
        result = self.can_fetch(url)
        return result.crawl_delay or self.default_delay

    def get_headers(self) -> dict[str, str]:
        """Get headers to use for requests."""
        return self._get_headers()

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached robots.txt files."""
        return len(self._cache)


def get_sec_headers() -> dict[str, str]:
    """
    Get headers compliant with SEC EDGAR requirements.

    SEC requires identification in User-Agent header.
    See: https://www.sec.gov/os/webmaster-faq#developers
    """
    return {
        "User-Agent": f"{DEFAULT_USER_AGENT} ({CONTACT_EMAIL})",
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }


def create_compliant_session(
    user_agent: str = DEFAULT_USER_AGENT,
) -> requests.Session:
    """
    Create a requests session with compliant default headers.

    Args:
        user_agent: User agent string to use

    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "From": CONTACT_EMAIL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return session


# Global robots checker instance
_robots_checker: Optional[RobotsChecker] = None


def get_robots_checker() -> RobotsChecker:
    """Get or create global robots checker instance."""
    global _robots_checker
    if _robots_checker is None:
        _robots_checker = RobotsChecker()
    return _robots_checker


def check_robots(url: str) -> RobotsResult:
    """
    Convenience function to check robots.txt compliance.

    Args:
        url: URL to check

    Returns:
        RobotsResult with allowed status
    """
    return get_robots_checker().can_fetch(url)

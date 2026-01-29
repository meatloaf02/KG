"""
Rate limiting and retry logic for polite crawling.

Implements per-domain throttling, exponential backoff,
and concurrency controls.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Callable, Optional, TypeVar
from urllib.parse import urlparse

from config import MAX_RETRIES, REQUEST_DELAY_SECONDS, setup_logging

logger = setup_logging(__name__)

T = TypeVar("T")

# Default rate limits
DEFAULT_REQUESTS_PER_SECOND = 1.0
DEFAULT_MAX_RETRIES = MAX_RETRIES
DEFAULT_DELAY = REQUEST_DELAY_SECONDS

# Backoff settings
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0
JITTER_FACTOR = 0.1  # 10% jitter


@dataclass
class DomainState:
    """Track rate limiting state for a domain."""

    domain: str
    last_request_time: float = 0.0
    request_count: int = 0
    error_count: int = 0
    requests_per_second: float = DEFAULT_REQUESTS_PER_SECOND
    lock: Lock = field(default_factory=Lock)

    @property
    def min_delay(self) -> float:
        """Minimum delay between requests."""
        return 1.0 / self.requests_per_second


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Optional[any] = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_time: float = 0.0


class RateLimiter:
    """
    Per-domain rate limiter with adaptive throttling.

    Features:
    - Per-domain request tracking
    - Configurable rates per domain
    - Automatic slowdown on errors
    - Thread-safe operation
    """

    def __init__(
        self,
        default_rate: float = DEFAULT_REQUESTS_PER_SECOND,
        domain_rates: Optional[dict[str, float]] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            default_rate: Default requests per second
            domain_rates: Optional domain-specific rates
        """
        self.default_rate = default_rate
        self.domain_rates = domain_rates or {}
        self._domains: dict[str, DomainState] = {}
        self._global_lock = Lock()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc.lower()

    def _get_domain_state(self, domain: str) -> DomainState:
        """Get or create domain state."""
        with self._global_lock:
            if domain not in self._domains:
                rate = self.domain_rates.get(domain, self.default_rate)
                self._domains[domain] = DomainState(
                    domain=domain,
                    requests_per_second=rate,
                )
            return self._domains[domain]

    def wait_if_needed(self, url: str) -> float:
        """
        Wait if necessary to respect rate limits.

        Args:
            url: URL about to be requested

        Returns:
            Actual wait time in seconds
        """
        domain = self._get_domain(url)
        state = self._get_domain_state(domain)

        with state.lock:
            now = time.time()
            elapsed = now - state.last_request_time
            min_delay = state.min_delay

            if elapsed < min_delay:
                wait_time = min_delay - elapsed
                # Add jitter to prevent thundering herd
                wait_time += random.uniform(0, wait_time * JITTER_FACTOR)
                logger.debug(f"Rate limiting {domain}: waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            else:
                wait_time = 0.0

            state.last_request_time = time.time()
            state.request_count += 1

            return wait_time

    def record_error(self, url: str) -> None:
        """
        Record an error for adaptive throttling.

        Increases delay after errors to be more polite.

        Args:
            url: URL that caused error
        """
        domain = self._get_domain(url)
        state = self._get_domain_state(domain)

        with state.lock:
            state.error_count += 1
            # Slow down after errors
            if state.error_count >= 3:
                state.requests_per_second = max(
                    0.1,  # Minimum rate
                    state.requests_per_second * 0.5,
                )
                logger.warning(
                    f"Slowing down {domain} to {state.requests_per_second:.2f} req/s "
                    f"after {state.error_count} errors"
                )

    def record_success(self, url: str) -> None:
        """
        Record successful request.

        Gradually restore rate after errors.

        Args:
            url: URL that succeeded
        """
        domain = self._get_domain(url)
        state = self._get_domain_state(domain)

        with state.lock:
            if state.error_count > 0:
                state.error_count = max(0, state.error_count - 1)
                # Gradually restore rate
                original_rate = self.domain_rates.get(domain, self.default_rate)
                if state.requests_per_second < original_rate:
                    state.requests_per_second = min(
                        original_rate,
                        state.requests_per_second * 1.1,
                    )

    def get_stats(self, domain: Optional[str] = None) -> dict:
        """Get rate limiting statistics."""
        if domain:
            state = self._domains.get(domain)
            if state:
                return {
                    "domain": domain,
                    "request_count": state.request_count,
                    "error_count": state.error_count,
                    "current_rate": state.requests_per_second,
                }
            return {}

        return {
            d: {
                "request_count": s.request_count,
                "error_count": s.error_count,
                "current_rate": s.requests_per_second,
            }
            for d, s in self._domains.items()
        }


def calculate_backoff(
    attempt: int,
    initial: float = INITIAL_BACKOFF,
    maximum: float = MAX_BACKOFF,
    multiplier: float = BACKOFF_MULTIPLIER,
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        initial: Initial delay in seconds
        maximum: Maximum delay in seconds
        multiplier: Backoff multiplier

    Returns:
        Delay in seconds with jitter
    """
    delay = min(initial * (multiplier**attempt), maximum)
    # Add jitter: +/- 10%
    jitter = delay * JITTER_FACTOR * (2 * random.random() - 1)
    return delay + jitter


def with_retry(
    func: Callable[[], T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> RetryResult:
    """
    Execute function with retry logic.

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        retryable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Optional callback called before each retry

    Returns:
        RetryResult with success status and result/error
    """
    start_time = time.time()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = func()
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time=time.time() - start_time,
            )

        except retryable_exceptions as e:
            last_error = e

            if attempt < max_retries:
                delay = calculate_backoff(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )

                if on_retry:
                    on_retry(attempt, e)

                time.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries + 1} attempts failed. Last error: {e}"
                )

    return RetryResult(
        success=False,
        error=last_error,
        attempts=max_retries + 1,
        total_time=time.time() - start_time,
    )


class ThrottledSession:
    """
    Wrapper for requests that enforces rate limiting.

    Combines rate limiting, robots.txt compliance, and retry logic.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """
        Initialize throttled session.

        Args:
            rate_limiter: RateLimiter instance (creates new if None)
            max_retries: Maximum retry attempts
        """
        import requests

        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries
        self.session = requests.Session()

        # Import here to avoid circular imports
        from ingest.robots import get_robots_checker

        self.robots_checker = get_robots_checker()

    def get(self, url: str, **kwargs) -> "requests.Response":
        """
        Make GET request with rate limiting and retries.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for requests.get

        Returns:
            Response object

        Raises:
            ValueError: If URL is disallowed by robots.txt
            requests.RequestException: On request failure after retries
        """
        import requests

        # Check robots.txt
        robots_result = self.robots_checker.can_fetch(url)
        if not robots_result.allowed:
            raise ValueError(f"URL disallowed by robots.txt: {url}")

        # Use robots.txt crawl delay if specified
        if robots_result.crawl_delay:
            domain = urlparse(url).netloc.lower()
            self.rate_limiter.domain_rates[domain] = 1.0 / robots_result.crawl_delay

        # Set headers
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"].update(self.robots_checker.get_headers())

        def do_request():
            # Wait for rate limit
            self.rate_limiter.wait_if_needed(url)

            # Make request
            response = self.session.get(url, **kwargs)

            # Handle rate limit responses
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                try:
                    wait = int(retry_after)
                except ValueError:
                    wait = 60
                raise requests.RequestException(
                    f"Rate limited (429). Retry after {wait}s"
                )

            response.raise_for_status()
            return response

        # Execute with retry
        result = with_retry(
            do_request,
            max_retries=self.max_retries,
            retryable_exceptions=(requests.RequestException,),
            on_retry=lambda attempt, e: self.rate_limiter.record_error(url),
        )

        if result.success:
            self.rate_limiter.record_success(url)
            return result.result
        else:
            raise result.error


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Import domain configs
        from ingest.domains import ALLOWED_DOMAINS

        domain_rates = {
            domain: config.requests_per_second
            for domain, config in ALLOWED_DOMAINS.items()
        }
        _rate_limiter = RateLimiter(domain_rates=domain_rates)
    return _rate_limiter

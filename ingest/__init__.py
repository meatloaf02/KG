# Data collection and ingestion module

from ingest.domains import (
    ALLOWED_DOMAINS,
    DomainConfig,
    Priority,
    SourceType,
    get_domain_config,
    get_domains_by_priority,
    get_domains_by_source_type,
    is_allowed_domain,
    list_all_domains,
)
from ingest.rate_limiter import (
    RateLimiter,
    ThrottledSession,
    calculate_backoff,
    get_rate_limiter,
    with_retry,
)
from ingest.robots import (
    RobotsChecker,
    RobotsResult,
    check_robots,
    create_compliant_session,
    get_robots_checker,
    get_sec_headers,
)
from ingest.url_utils import (
    URLDeduplicator,
    convert_to_https,
    extract_domain,
    extract_sec_accession_number,
    get_content_hash,
    get_url_hash,
    is_same_document,
    is_valid_url,
    normalize_url,
)

__all__ = [
    # Domains
    "ALLOWED_DOMAINS",
    "DomainConfig",
    "Priority",
    "SourceType",
    "get_domain_config",
    "get_domains_by_priority",
    "get_domains_by_source_type",
    "is_allowed_domain",
    "list_all_domains",
    # Rate limiting
    "RateLimiter",
    "ThrottledSession",
    "calculate_backoff",
    "get_rate_limiter",
    "with_retry",
    # Robots
    "RobotsChecker",
    "RobotsResult",
    "check_robots",
    "create_compliant_session",
    "get_robots_checker",
    "get_sec_headers",
    # URL utilities
    "URLDeduplicator",
    "convert_to_https",
    "extract_domain",
    "extract_sec_accession_number",
    "get_content_hash",
    "get_url_hash",
    "is_same_document",
    "is_valid_url",
    "normalize_url",
]

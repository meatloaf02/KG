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
from ingest.fetcher import (
    DocumentFetcher,
    FetchResult,
    get_fetcher,
)
from ingest.manifest import (
    export_manifest,
    format_stats,
    get_manifest_stats,
)
from ingest.models import (
    FetchStatus,
    RawDocument,
    create_tables,
    get_engine,
    get_session,
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
from ingest.seeds import (
    SeedURL,
    get_seed_stats,
    list_seed_files,
    load_all_seeds,
    load_seed_file,
    load_seeds_by_file,
)
from ingest.storage import (
    ContentStorage,
    StorageResult,
    get_storage,
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
    # Fetcher
    "DocumentFetcher",
    "FetchResult",
    "get_fetcher",
    # Manifest
    "export_manifest",
    "format_stats",
    "get_manifest_stats",
    # Models
    "FetchStatus",
    "RawDocument",
    "create_tables",
    "get_engine",
    "get_session",
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
    # Seeds
    "SeedURL",
    "get_seed_stats",
    "list_seed_files",
    "load_all_seeds",
    "load_seed_file",
    "load_seeds_by_file",
    # Storage
    "ContentStorage",
    "StorageResult",
    "get_storage",
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

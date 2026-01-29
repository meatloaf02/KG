"""
Domain allowlist and configuration for data ingestion.

Only domains in the allowlist may be crawled. Each domain has associated
metadata including crawl priority, expected content types, and rate limits.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SourceType(Enum):
    """Classification of document sources."""

    SEC_FILING = "sec_filing"
    EARNINGS_TRANSCRIPT = "earnings_transcript"
    PRESS_RELEASE = "press_release"
    BLOG = "blog"
    INVESTOR_RELATIONS = "investor_relations"
    NEWS_MEDIA = "news_media"


class Priority(Enum):
    """Crawl priority levels."""

    HIGH = 1  # SEC filings, earnings calls
    MEDIUM = 2  # Press releases, IR pages
    LOW = 3  # Blog posts, media articles


@dataclass
class DomainConfig:
    """Configuration for an allowed domain."""

    domain: str
    source_type: SourceType
    priority: Priority
    requests_per_second: float = 1.0  # Rate limit
    description: str = ""
    requires_special_handling: bool = False
    notes: Optional[str] = None


# Allowed domains with their configurations
ALLOWED_DOMAINS: dict[str, DomainConfig] = {
    # SEC EDGAR - Primary source for filings
    "sec.gov": DomainConfig(
        domain="sec.gov",
        source_type=SourceType.SEC_FILING,
        priority=Priority.HIGH,
        requests_per_second=0.1,  # SEC requests 10 req/sec max, we're conservative
        description="SEC EDGAR filing system",
        notes="Use SEC-compliant User-Agent header",
    ),
    "www.sec.gov": DomainConfig(
        domain="www.sec.gov",
        source_type=SourceType.SEC_FILING,
        priority=Priority.HIGH,
        requests_per_second=0.1,
        description="SEC EDGAR filing system (www)",
        notes="Use SEC-compliant User-Agent header",
    ),
    # Workday Investor Relations
    "investor.workday.com": DomainConfig(
        domain="investor.workday.com",
        source_type=SourceType.INVESTOR_RELATIONS,
        priority=Priority.HIGH,
        requests_per_second=0.5,
        description="Workday investor relations portal",
    ),
    # Workday Newsroom
    "newsroom.workday.com": DomainConfig(
        domain="newsroom.workday.com",
        source_type=SourceType.PRESS_RELEASE,
        priority=Priority.MEDIUM,
        requests_per_second=0.5,
        description="Workday press releases and news",
    ),
    # Workday Blog
    "blog.workday.com": DomainConfig(
        domain="blog.workday.com",
        source_type=SourceType.BLOG,
        priority=Priority.MEDIUM,
        requests_per_second=0.5,
        description="Workday corporate blog",
    ),
    # Workday main site (for linked content)
    "www.workday.com": DomainConfig(
        domain="www.workday.com",
        source_type=SourceType.INVESTOR_RELATIONS,
        priority=Priority.LOW,
        requests_per_second=0.5,
        description="Workday main website",
    ),
    # Earnings transcript sources (public)
    "seekingalpha.com": DomainConfig(
        domain="seekingalpha.com",
        source_type=SourceType.EARNINGS_TRANSCRIPT,
        priority=Priority.MEDIUM,
        requests_per_second=0.2,
        description="Seeking Alpha - public transcripts only",
        requires_special_handling=True,
        notes="Only use publicly accessible content; check for paywall",
    ),
    "www.fool.com": DomainConfig(
        domain="www.fool.com",
        source_type=SourceType.EARNINGS_TRANSCRIPT,
        priority=Priority.MEDIUM,
        requests_per_second=0.2,
        description="Motley Fool - public transcripts",
        notes="Verify content is not behind paywall",
    ),
    # News and media sources
    "www.reuters.com": DomainConfig(
        domain="www.reuters.com",
        source_type=SourceType.NEWS_MEDIA,
        priority=Priority.LOW,
        requests_per_second=0.2,
        description="Reuters news coverage",
    ),
    "techcrunch.com": DomainConfig(
        domain="techcrunch.com",
        source_type=SourceType.NEWS_MEDIA,
        priority=Priority.LOW,
        requests_per_second=0.2,
        description="TechCrunch technology news",
    ),
    "www.businesswire.com": DomainConfig(
        domain="www.businesswire.com",
        source_type=SourceType.PRESS_RELEASE,
        priority=Priority.MEDIUM,
        requests_per_second=0.3,
        description="Business Wire press release distribution",
    ),
    "www.prnewswire.com": DomainConfig(
        domain="www.prnewswire.com",
        source_type=SourceType.PRESS_RELEASE,
        priority=Priority.MEDIUM,
        requests_per_second=0.3,
        description="PR Newswire press release distribution",
    ),
}


def is_allowed_domain(domain: str) -> bool:
    """Check if a domain is in the allowlist."""
    # Normalize domain (remove www. prefix for matching if needed)
    normalized = domain.lower().strip()
    return normalized in ALLOWED_DOMAINS


def get_domain_config(domain: str) -> Optional[DomainConfig]:
    """Get configuration for an allowed domain."""
    normalized = domain.lower().strip()
    return ALLOWED_DOMAINS.get(normalized)


def get_domains_by_source_type(source_type: SourceType) -> list[DomainConfig]:
    """Get all domains for a given source type."""
    return [cfg for cfg in ALLOWED_DOMAINS.values() if cfg.source_type == source_type]


def get_domains_by_priority(priority: Priority) -> list[DomainConfig]:
    """Get all domains with a given priority."""
    return [cfg for cfg in ALLOWED_DOMAINS.values() if cfg.priority == priority]


def list_all_domains() -> list[str]:
    """Return list of all allowed domain names."""
    return list(ALLOWED_DOMAINS.keys())

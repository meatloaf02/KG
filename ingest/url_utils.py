"""
URL normalization and deduplication utilities.

Provides canonical URL handling to ensure consistent identification
of documents across different URL formats and tracking parameters.
"""

import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    # Google Analytics
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "gclsrc",
    # Facebook
    "fbclid",
    "fb_action_ids",
    "fb_action_types",
    "fb_source",
    "fb_ref",
    # Twitter
    "twclid",
    # Microsoft
    "msclkid",
    # HubSpot
    "hsa_acc",
    "hsa_cam",
    "hsa_grp",
    "hsa_ad",
    "hsa_src",
    "hsa_tgt",
    "hsa_kw",
    "hsa_mt",
    "hsa_net",
    "hsa_ver",
    # Mailchimp
    "mc_cid",
    "mc_eid",
    # Generic tracking
    "ref",
    "source",
    "campaign",
    "_ga",
    "_gl",
    "trk",
    "trkInfo",
}

# SEC EDGAR specific parameters to preserve
SEC_PRESERVE_PARAMS = {
    "action",
    "CIK",
    "type",
    "dateb",
    "owner",
    "count",
    "filenum",
    "State",
    "SIC",
}


def normalize_url(url: str, preserve_fragment: bool = False) -> str:
    """
    Normalize a URL to its canonical form.

    Normalization steps:
    1. Parse URL components
    2. Lowercase scheme and host
    3. Remove default ports (80 for http, 443 for https)
    4. Remove trailing slashes from path (except root)
    5. Sort query parameters
    6. Remove tracking parameters
    7. Remove fragment (optional)

    Args:
        url: URL to normalize
        preserve_fragment: If True, keep the fragment identifier

    Returns:
        Normalized canonical URL
    """
    if not url:
        return ""

    # Parse URL
    parsed = urlparse(url.strip())

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path
    path = parsed.path
    # Remove trailing slash except for root
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # Ensure path starts with /
    if not path:
        path = "/"

    # Process query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Determine which params to preserve based on domain
    is_sec_domain = "sec.gov" in netloc

    # Filter and sort query parameters
    filtered_params = {}
    for key, values in query_params.items():
        # Skip tracking parameters (unless SEC domain with preserved params)
        if key.lower() in TRACKING_PARAMS:
            if not (is_sec_domain and key in SEC_PRESERVE_PARAMS):
                continue

        # Keep the parameter
        filtered_params[key] = values

    # Sort parameters for consistent ordering
    sorted_params = sorted(filtered_params.items())
    query = urlencode(sorted_params, doseq=True)

    # Handle fragment
    fragment = parsed.fragment if preserve_fragment else ""

    # Reconstruct URL
    normalized = urlunparse((scheme, netloc, path, "", query, fragment))

    return normalized


def get_url_hash(url: str) -> str:
    """
    Generate a hash for a normalized URL.

    Uses SHA-256 truncated to 16 characters for reasonable uniqueness
    while keeping file names manageable.

    Args:
        url: URL to hash (will be normalized first)

    Returns:
        16-character hex hash string
    """
    normalized = normalize_url(url)
    full_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return full_hash[:16]


def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL.

    Args:
        url: URL to extract domain from

    Returns:
        Domain string (e.g., 'www.example.com')
    """
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_same_document(url1: str, url2: str) -> bool:
    """
    Check if two URLs point to the same document.

    Compares normalized URLs to handle variations in:
    - Protocol (http vs https)
    - Trailing slashes
    - Query parameter ordering
    - Tracking parameters

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if URLs point to the same document
    """
    return normalize_url(url1) == normalize_url(url2)


def get_content_hash(content: bytes) -> str:
    """
    Generate a hash of document content for deduplication.

    Uses SHA-256 for content-based deduplication.

    Args:
        content: Raw document content

    Returns:
        64-character hex hash string
    """
    return hashlib.sha256(content).hexdigest()


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and well-formed.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        # Scheme must be http or https
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        return True
    except Exception:
        return False


def convert_to_https(url: str) -> str:
    """
    Convert HTTP URL to HTTPS.

    Args:
        url: URL to convert

    Returns:
        URL with https scheme
    """
    parsed = urlparse(url)
    if parsed.scheme == "http":
        return urlunparse(("https",) + parsed[1:])
    return url


def extract_sec_accession_number(url: str) -> str | None:
    """
    Extract SEC accession number from EDGAR URL.

    Args:
        url: SEC EDGAR URL

    Returns:
        Accession number or None if not found
    """
    # Pattern: 0001327811-24-000012 (CIK-YY-NNNNNN)
    pattern = r"(\d{10}-\d{2}-\d{6})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


class URLDeduplicator:
    """
    Track seen URLs and detect duplicates.

    Uses both URL normalization and content hashing for deduplication.
    """

    def __init__(self):
        self._seen_urls: set[str] = set()
        self._seen_content: set[str] = set()

    def is_url_seen(self, url: str) -> bool:
        """Check if URL has been seen before."""
        normalized = normalize_url(url)
        return normalized in self._seen_urls

    def mark_url_seen(self, url: str) -> None:
        """Mark URL as seen."""
        normalized = normalize_url(url)
        self._seen_urls.add(normalized)

    def is_content_seen(self, content: bytes) -> bool:
        """Check if content has been seen before."""
        content_hash = get_content_hash(content)
        return content_hash in self._seen_content

    def mark_content_seen(self, content: bytes) -> str:
        """Mark content as seen and return hash."""
        content_hash = get_content_hash(content)
        self._seen_content.add(content_hash)
        return content_hash

    def add_url(self, url: str, content: bytes | None = None) -> tuple[bool, bool]:
        """
        Add URL and optionally content, returning duplicate status.

        Args:
            url: URL to add
            content: Optional content bytes

        Returns:
            Tuple of (url_is_new, content_is_new)
        """
        url_is_new = not self.is_url_seen(url)
        self.mark_url_seen(url)

        content_is_new = True
        if content is not None:
            content_is_new = not self.is_content_seen(content)
            self.mark_content_seen(content)

        return url_is_new, content_is_new

    @property
    def url_count(self) -> int:
        """Number of unique URLs seen."""
        return len(self._seen_urls)

    @property
    def content_count(self) -> int:
        """Number of unique content hashes seen."""
        return len(self._seen_content)

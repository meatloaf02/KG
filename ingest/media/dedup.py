"""
URL canonicalization and near-duplicate detection for external media articles.

Near-duplicate detection uses simhash with a hamming distance threshold of 4
to cluster syndicated content that appears across multiple outlets.
"""

import re
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import setup_logging

logger = setup_logging(__name__)

# Tracking parameters to drop during URL canonicalization
DROP_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "gclsrc",
    "msclkid",
    "twclid",
}

# Regex to identify article-like URL paths (vs. index/search pages)
# Matches: date-based paths, /news/, /article, /blog/, and long slug segments (3+ hyphens)
ARTICLE_URL_RE = re.compile(
    r"/\d{4}/\d{2}/|/\d{4}-\d{2}-\d{2}/|/news/|/article|/blog/|(?:/[^/]*-[^/]*-[^/]*-[^/]+/?$)"
)

# Pagination paths to follow when crawling search/index pages
PAGINATION_RE = re.compile(r"/page/\d+/?$")

# Hamming distance threshold for near-duplicate clustering
NEAR_DUP_THRESHOLD = 4


def canonicalize_url(url: str) -> str:
    """
    Return a canonical form of the URL.

    Steps:
    - Force HTTPS
    - Lowercase scheme and host
    - Drop tracking query parameters
    - Sort remaining parameters
    - Remove fragment
    """
    if not url:
        return url

    parsed = urlparse(url.strip())
    scheme = "https"
    netloc = parsed.netloc.lower()

    # Strip default ports
    if netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif netloc.endswith(":80"):
        netloc = netloc[:-3]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Filter query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in query_params.items() if k.lower() not in DROP_PARAMS}
    query = urlencode(sorted(filtered.items()), doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def is_article_like(url: str) -> bool:
    """
    Return True if the URL path looks like an article or a pagination page worth following.

    Matches date-based paths, /news/, /blog/, /article, long slug paths (3+ hyphens),
    and pagination pages (/page/N/).
    """
    path = urlparse(url).path
    return bool(ARTICLE_URL_RE.search(path) or PAGINATION_RE.search(path))


class NearDupDetector:
    """
    Simhash-based near-duplicate clustering.

    Uses hamming distance ≤ NEAR_DUP_THRESHOLD to cluster articles whose
    fingerprints are very similar (e.g. syndicated or lightly edited copies).
    """

    def __init__(self) -> None:
        # Maps simhash integer → content_hash of the first seen article
        self._index: dict[int, str] = {}

    def _compute_simhash(self, text: str) -> int:
        """Compute a 64-bit simhash fingerprint for the text."""
        try:
            from simhash import Simhash
            return Simhash(text).value
        except ImportError:
            logger.error("simhash not installed; run: pip install simhash")
            raise

    @staticmethod
    def _hamming_distance(a: int, b: int) -> int:
        """Count differing bits between two integers."""
        return bin(a ^ b).count("1")

    def check_and_register(self, content_hash: str, text: str) -> Optional[str]:
        """
        Check whether text is a near-duplicate of a previously seen article.

        Returns:
            cluster_id (content_hash of the first seen near-dup) if duplicate,
            or None if the article is new.

        Side effect: registers the article if it is new.
        """
        if not text:
            return None

        fingerprint = self._compute_simhash(text)

        # Check against all stored fingerprints
        for stored_fp, cluster_id in self._index.items():
            if self._hamming_distance(fingerprint, stored_fp) <= NEAR_DUP_THRESHOLD:
                logger.debug(
                    f"Near-duplicate detected: {content_hash!r} clusters with {cluster_id!r}"
                )
                return cluster_id

        # New article — register it
        self._index[fingerprint] = content_hash
        return None

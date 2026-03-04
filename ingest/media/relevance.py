"""
Relevance and AI keyword filtering for external media articles.

Implements two-stage Workday relevance check:
  Stage 1 — require at least one strong company reference.
  Stage 2 — if only a bare "Workday" token matched, require a disambiguation signal.
"""

import re
from urllib.parse import urlparse
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)

# Stage 1: strong company references (any match → pass stage 1 unconditionally)
STAGE1_PRIMARY = [
    "WDAY",
    "Workday, Inc.",
    "Workday Inc",          # without comma (common in news articles)
    "Workday Student",
    "Workday HCM",
    "Workday Recruiting",
    "Workday Financial",
    "Workday Adaptive",
    "Workday Peakon",
    "Workday CEO",          # executive reference (news-specific)
    "Workday's",            # possessive form
    "Workday platform",
    "Workday product",
    "Workday customers",
    "Workday partner",
]

# Stage 1: bare token that requires disambiguation
STAGE1_BARE = re.compile(r"\bWorkday\b")

# Stage 2: disambiguation signals for bare "Workday" match
# Covers SEC filing terminology AND news/trade-press language
STAGE2_DISAMBIGUATION = [
    # Stock / financial
    "NASDAQ",
    "WDAY",
    # Product / domain
    "HCM",
    "Human Capital",
    "Financial Management",
    "enterprise software",
    "enterprise cloud",
    "Workday Student",
    "Workday Recruiting",
    # Named executives (Workday-specific names)
    "Bhusri",               # Aneel Bhusri, founder/CEO
    "Eschenbach",           # Carl Eschenbach, co-CEO
    # Business context signals (paired with "Workday" = highly specific)
    "SaaS",
    "ERP",
    "payroll",
    "workforce management",
    "talent management",
    "HR tech",
    "HR software",
    "cloud ERP",
    "earnings call",
    "earnings report",
    "quarterly results",
]

# AI-related keywords
AI_KEYWORDS = [
    "AI",
    "artificial intelligence",
    "machine learning",
    "generative AI",
    "genAI",
    "AI agents",
    "agentic",
]

# URL path patterns to skip (navigation/utility pages, not articles)
BLOCKED_PATH_PATTERNS = [
    re.compile(r"/tag/"),
    re.compile(r"/category/"),
    re.compile(r"/topics/"),
    re.compile(r"/author/"),
    re.compile(r"/newsletter"),
    re.compile(r"/subscribe"),
    re.compile(r"/subscription"),
    re.compile(r"/account"),
    re.compile(r"/login"),
    re.compile(r"/signin"),
    re.compile(r"/privacy"),
    re.compile(r"/terms"),
    re.compile(r"/careers"),
    re.compile(r"/about"),
]


def is_blocked_path(url: str) -> bool:
    """Return True if the URL path matches a blocked navigation pattern."""
    path = urlparse(url).path
    return any(p.search(path) for p in BLOCKED_PATH_PATTERNS)


def relevance_check(text: str) -> tuple[bool, Optional[str]]:
    """
    Check whether article text is relevant to Workday (the company).

    Returns:
        (is_relevant, workday_match_type)
        workday_match_type is "primary" or "disambiguation" when relevant, None otherwise.
    """
    if not text:
        return False, None

    # Stage 1a: strong primary references → always relevant
    for term in STAGE1_PRIMARY:
        if term in text:
            return True, "primary"

    # Stage 1b: bare "Workday" token found
    if STAGE1_BARE.search(text):
        # Stage 2: require at least one disambiguation signal
        for signal in STAGE2_DISAMBIGUATION:
            if signal in text:
                return True, "disambiguation"
        # Bare "Workday" without context — could be "workday" (generic noun)
        logger.debug("Bare 'Workday' found but no disambiguation signal; skipping")
        return False, None

    return False, None


def has_ai_keyword(text: str) -> bool:
    """Return True if the text contains at least one AI-related keyword."""
    if not text:
        return False
    return any(kw in text for kw in AI_KEYWORDS)

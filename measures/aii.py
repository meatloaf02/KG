"""
AI Intensity Index (AII) computation.

Computes a weighted, token-normalized AI language signal per quarter
from canonical_v2 documents. AII differs from ai_density in three ways:
  1. Three weighted term buckets (not MENTIONS graph edges)
  2. Corpus-level aggregation preserving denominator integrity
  3. Doc-type weighting (10-K = 1.5x, 10-Q = 1.2x, 8-K = 1.0x)

Formula:
    Per document:
        raw_score      = Σ(bucket_weight × occurrences_of_bucket_terms)
        token_count    = len(clean_text) / 4
        doc_aii        = (raw_score / token_count) × 1000 × doc_type_weight

    Per quarter (corpus-level):
        quarter_raw    = Σ(raw_score  for all docs in quarter)
        quarter_tokens = Σ(token_count for all docs in quarter)
        quarter_aii    = (quarter_raw / quarter_tokens) × 1000 × avg_doc_type_weight

Usage:
    from measures.aii import compute_aii_index
    df = compute_aii_index()
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

from config import setup_logging
from kg.connection import execute_query, get_driver
from process.storage import ProcessedDocumentStorage

logger = setup_logging(__name__)


# =============================================================================
# Term Buckets and Document Type Weights
# =============================================================================

AII_TERM_BUCKETS: dict[str, dict] = {
    "classic_ai": {
        "weight": 1.0,
        "terms": [
            "artificial intelligence",
            "machine learning",
            "deep learning",
        ],
    },
    "generative_ai": {
        "weight": 2.0,
        "terms": [
            "generative ai",
            "large language model",
            "llm",
            "foundation model",
            "copilot",
        ],
    },
    "adjacent_automation": {
        "weight": 0.75,
        "terms": [
            "ai-powered",
            "intelligent automation",
            "predictive analytics",
        ],
    },
}

DOC_TYPE_WEIGHTS: dict[str, float] = {
    "sec_10k": 1.5,
    "sec_10q": 1.2,
    "sec_8k": 1.0,
}
DOC_TYPE_WEIGHT_DEFAULT = 1.0

AII_MULTIPLIER = 1000
ANALYSIS_LAYER_FILTER = "canonical_v2"


# =============================================================================
# Pattern Compilation
# =============================================================================


def _compile_bucket_patterns(terms: list[str]) -> list[re.Pattern]:
    """
    Compile word-boundary regex patterns for a list of terms.

    Mirrors EntityExtractor._compile_patterns() logic:
    - re.escape for special chars
    - hyphen → [\\s\\-]? (optional separator)
    - space → [\\s\\-] (required separator, allows hyphen)
    - wrapped in \\b...\\b word boundaries
    - case-insensitive
    - sorted longest-first for greedy matching
    """
    compiled = []
    for term in terms:
        escaped = re.escape(term)
        escaped = escaped.replace(r"\-", r"[\s\-]?")
        escaped = escaped.replace(r"\ ", r"[\s\-]")
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        compiled.append((pattern, term))

    # Sort longest-first for greedy matching
    compiled.sort(key=lambda x: len(x[1]), reverse=True)
    return [p for p, _ in compiled]


def _build_all_patterns() -> dict[str, list[re.Pattern]]:
    """Compile patterns for all buckets once."""
    return {
        bucket_name: _compile_bucket_patterns(bucket_data["terms"])
        for bucket_name, bucket_data in AII_TERM_BUCKETS.items()
    }


# =============================================================================
# Term Counting
# =============================================================================


def count_bucket_terms(text: str, patterns: list[re.Pattern]) -> int:
    """
    Count total occurrences of all patterns in text.

    Unlike entity extraction, spans are NOT deduplicated — every match
    is counted for intensity measurement.
    """
    total = 0
    for pattern in patterns:
        total += len(pattern.findall(text))
    return total


# =============================================================================
# Memgraph Query
# =============================================================================

CANONICAL_DOCS_QUERY = """
MATCH (d:Document)
WHERE d.analysis_layer = $layer AND d.published_at IS NOT NULL
RETURN
    d.content_hash AS content_hash,
    d.doc_type     AS doc_type,
    d.published_at.year AS year,
    (d.published_at.month - 1) / 3 + 1 AS quarter
ORDER BY d.published_at
"""


def fetch_canonical_docs(driver=None) -> list[dict]:
    """
    Fetch all canonical_v2 document metadata from Memgraph.

    Returns list of dicts with: content_hash, doc_type, year, quarter
    """
    logger.info(f"Fetching {ANALYSIS_LAYER_FILTER} documents from Memgraph...")
    results = execute_query(
        CANONICAL_DOCS_QUERY,
        {"layer": ANALYSIS_LAYER_FILTER},
        driver=driver,
    )
    logger.info(f"Found {len(results)} {ANALYSIS_LAYER_FILTER} documents")
    return [dict(r) for r in results]


# =============================================================================
# Per-Document AII
# =============================================================================


def compute_doc_aii(
    text: str,
    doc_type: str,
    bucket_patterns: dict[str, list[re.Pattern]],
) -> Optional[dict]:
    """
    Compute AII components for a single document.

    Returns None if token_count == 0 (empty text).
    Returns dict with: raw_score, token_count, doc_type_weight, doc_aii, bucket_counts
    """
    token_count = len(text) / 4
    if token_count == 0:
        return None

    bucket_counts: dict[str, int] = {}
    raw_score = 0.0

    for bucket_name, patterns in bucket_patterns.items():
        weight = AII_TERM_BUCKETS[bucket_name]["weight"]
        count = count_bucket_terms(text, patterns)
        bucket_counts[bucket_name] = count
        raw_score += weight * count

    doc_type_weight = DOC_TYPE_WEIGHTS.get(doc_type, DOC_TYPE_WEIGHT_DEFAULT)
    doc_aii = (raw_score / token_count) * AII_MULTIPLIER * doc_type_weight

    return {
        "raw_score": raw_score,
        "token_count": token_count,
        "doc_type_weight": doc_type_weight,
        "doc_aii": doc_aii,
        "bucket_counts": bucket_counts,
    }


# =============================================================================
# Quarterly Aggregation
# =============================================================================


def compute_aii_index(driver=None) -> pd.DataFrame:
    """
    Compute quarterly AII from canonical_v2 documents.

    Returns pd.DataFrame sorted by (year, quarter) with columns:
        period, year, quarter, doc_count,
        aii, aii_delta,
        quarter_raw_score, quarter_tokens, avg_doc_type_weight,
        bucket_classic_ai, bucket_generative_ai, bucket_adjacent_automation
    """
    # Build compiled patterns once (not per document)
    bucket_patterns = _build_all_patterns()

    # Fetch canonical_v2 manifest from Memgraph
    if driver is None:
        driver = get_driver()
    docs = fetch_canonical_docs(driver=driver)

    if not docs:
        logger.warning("No canonical_v2 documents found in Memgraph")
        return pd.DataFrame()

    # Load text and compute per-document AII
    storage = ProcessedDocumentStorage()

    # quarter_data[(year, quarter)] = list of per-doc component dicts
    quarter_data: dict[tuple, list[dict]] = defaultdict(list)

    skipped_missing = 0
    skipped_empty = 0
    processed = 0

    for doc in docs:
        content_hash = doc["content_hash"]
        doc_type = doc["doc_type"]
        year = doc["year"]
        quarter = doc["quarter"]

        text = storage.load_text(content_hash)
        if text is None:
            logger.warning(f"Text file missing for {content_hash[:12]} ({doc_type})")
            skipped_missing += 1
            continue

        components = compute_doc_aii(text, doc_type, bucket_patterns)
        if components is None:
            logger.warning(f"Empty text for {content_hash[:12]} ({doc_type})")
            skipped_empty += 1
            continue

        quarter_data[(year, quarter)].append(components)
        processed += 1

    logger.info(
        f"Processed {processed} docs; skipped {skipped_missing} missing text, "
        f"{skipped_empty} empty text"
    )

    # Corpus-level aggregation per quarter
    rows = []
    for (year, quarter), doc_components in sorted(quarter_data.items()):
        n = len(doc_components)
        if n == 0:
            continue

        if n == 1:
            logger.warning(f"{year}-Q{quarter}: only 1 document in quarter")

        quarter_raw = sum(d["raw_score"] for d in doc_components)
        quarter_tokens = sum(d["token_count"] for d in doc_components)
        avg_doc_type_weight = sum(d["doc_type_weight"] for d in doc_components) / n

        if quarter_tokens == 0:
            logger.warning(f"{year}-Q{quarter}: zero total tokens, skipping")
            continue

        aii = (quarter_raw / quarter_tokens) * AII_MULTIPLIER * avg_doc_type_weight

        bucket_totals: dict[str, int] = {}
        for bucket_name in AII_TERM_BUCKETS:
            bucket_totals[bucket_name] = sum(
                d["bucket_counts"].get(bucket_name, 0) for d in doc_components
            )

        period = f"{year}-Q{quarter}"
        rows.append({
            "period": period,
            "year": year,
            "quarter": quarter,
            "doc_count": n,
            "aii": round(aii, 6),
            "quarter_raw_score": round(quarter_raw, 4),
            "quarter_tokens": round(quarter_tokens, 1),
            "avg_doc_type_weight": round(avg_doc_type_weight, 4),
            "bucket_classic_ai": bucket_totals["classic_ai"],
            "bucket_generative_ai": bucket_totals["generative_ai"],
            "bucket_adjacent_automation": bucket_totals["adjacent_automation"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Compute aii_delta (QoQ change; first row → NaN)
    df = df.sort_values(["year", "quarter"]).reset_index(drop=True)
    df["aii_delta"] = df["aii"].diff().round(6)

    col_order = [
        "period", "year", "quarter", "doc_count",
        "aii", "aii_delta",
        "quarter_raw_score", "quarter_tokens", "avg_doc_type_weight",
        "bucket_classic_ai", "bucket_generative_ai", "bucket_adjacent_automation",
    ]
    return df[col_order]


# =============================================================================
# Per-Doc-Type Quarterly Aggregation
# =============================================================================


def compute_aii_by_doctype(driver=None) -> pd.DataFrame:
    """
    Compute quarterly AII stratified by document type (long-form).

    Returns one row per (quarter, doc_type) combination.
    Columns match compute_aii_index() minus aii_delta, plus doc_type.
    """
    bucket_patterns = _build_all_patterns()
    if driver is None:
        driver = get_driver()
    docs = fetch_canonical_docs(driver=driver)
    storage = ProcessedDocumentStorage()

    # Group by (year, quarter, doc_type)
    strat_data: dict[tuple, list[dict]] = defaultdict(list)
    for doc in docs:
        content_hash = doc["content_hash"]
        doc_type = doc["doc_type"]
        year, quarter = doc["year"], doc["quarter"]
        text = storage.load_text(content_hash)
        if text is None:
            continue
        components = compute_doc_aii(text, doc_type, bucket_patterns)
        if components is None:
            continue
        strat_data[(year, quarter, doc_type)].append(components)

    rows = []
    for (year, quarter, doc_type), doc_components in sorted(strat_data.items()):
        n = len(doc_components)
        quarter_raw = sum(d["raw_score"] for d in doc_components)
        quarter_tokens = sum(d["token_count"] for d in doc_components)
        avg_weight = sum(d["doc_type_weight"] for d in doc_components) / n
        if quarter_tokens == 0:
            continue
        aii = (quarter_raw / quarter_tokens) * AII_MULTIPLIER * avg_weight
        bucket_totals = {
            b: sum(d["bucket_counts"].get(b, 0) for d in doc_components)
            for b in AII_TERM_BUCKETS
        }
        rows.append({
            "period": f"{year}-Q{quarter}",
            "year": year,
            "quarter": quarter,
            "doc_type": doc_type,
            "doc_count": n,
            "aii": round(aii, 6),
            "quarter_raw_score": round(quarter_raw, 4),
            "quarter_tokens": round(quarter_tokens, 1),
            "avg_doc_type_weight": round(avg_weight, 4),
            "bucket_classic_ai": bucket_totals["classic_ai"],
            "bucket_generative_ai": bucket_totals["generative_ai"],
            "bucket_adjacent_automation": bucket_totals["adjacent_automation"],
        })

    col_order = [
        "period", "year", "quarter", "doc_type", "doc_count",
        "aii", "quarter_raw_score", "quarter_tokens", "avg_doc_type_weight",
        "bucket_classic_ai", "bucket_generative_ai", "bucket_adjacent_automation",
    ]
    df = pd.DataFrame(rows).sort_values(["year", "quarter", "doc_type"]).reset_index(drop=True)
    return df[col_order]


# =============================================================================
# CSV Export
# =============================================================================


def save_aii_csv(df: pd.DataFrame, path: Path) -> None:
    """Write AII quarterly DataFrame to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.6f")
    logger.info(f"Wrote {len(df)} rows to {path}")

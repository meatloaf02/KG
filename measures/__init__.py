# Signal computation and entity extraction module

from measures.extractor import (
    EntityExtractor,
    ExtractionResult,
    extract_entities,
    extract_entities_from_sentences,
)
from measures.lexicons import (
    AI_CAPABILITY_LEXICON,
    EntityMatch,
    PRODUCT_LEXICON,
    RISK_LEXICON,
    get_all_lexicons,
    get_entity_ids_by_type,
)
from measures.quarterly import (
    QuarterlyMetrics,
    QuarterlySignals,
    compute_quarterly_signals,
)

__all__ = [
    # Extractor
    "EntityExtractor",
    "ExtractionResult",
    "extract_entities",
    "extract_entities_from_sentences",
    # Lexicons
    "AI_CAPABILITY_LEXICON",
    "PRODUCT_LEXICON",
    "RISK_LEXICON",
    "EntityMatch",
    "get_all_lexicons",
    "get_entity_ids_by_type",
    # Quarterly Signals
    "QuarterlyMetrics",
    "QuarterlySignals",
    "compute_quarterly_signals",
]

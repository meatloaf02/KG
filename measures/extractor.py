"""
Entity extraction from document text (NOR-107, NOR-108, NOR-109, NOR-136).

Dictionary-based entity matching with normalization.
Extracts capabilities, products, risk topics, and events from sentences.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from config import setup_logging
from measures.lexicons import (
    AI_CAPABILITY_LEXICON,
    EVENT_LEXICON,
    PRODUCT_LEXICON,
    RISK_LEXICON,
    EntityMatch,
)

logger = setup_logging(__name__)


@dataclass
class ExtractionResult:
    """Result of entity extraction from a document."""

    doc_hash: str
    capability_mentions: list[EntityMatch] = field(default_factory=list)
    product_mentions: list[EntityMatch] = field(default_factory=list)
    risk_mentions: list[EntityMatch] = field(default_factory=list)
    event_mentions: list[EntityMatch] = field(default_factory=list)

    @property
    def total_mentions(self) -> int:
        return (
            len(self.capability_mentions)
            + len(self.product_mentions)
            + len(self.risk_mentions)
            + len(self.event_mentions)
        )

    @property
    def unique_capabilities(self) -> set[str]:
        return {m.entity_id for m in self.capability_mentions}

    @property
    def unique_products(self) -> set[str]:
        return {m.entity_id for m in self.product_mentions}

    @property
    def unique_risks(self) -> set[str]:
        return {m.entity_id for m in self.risk_mentions}

    @property
    def unique_events(self) -> set[str]:
        return {m.entity_id for m in self.event_mentions}


class EntityExtractor:
    """
    Extract entities from text using dictionary-based matching.

    Supports capabilities, products, and risk topics with
    case-insensitive matching and word boundary detection.
    """

    def __init__(self):
        """Initialize the extractor with compiled patterns."""
        self.capability_patterns = self._compile_patterns(AI_CAPABILITY_LEXICON)
        self.product_patterns = self._compile_patterns(PRODUCT_LEXICON)
        self.risk_patterns = self._compile_patterns(RISK_LEXICON)
        self.event_patterns = self._compile_patterns(EVENT_LEXICON)

    def _compile_patterns(self, lexicon: dict) -> list[tuple[re.Pattern, tuple]]:
        """
        Compile regex patterns for a lexicon.

        Returns list of (pattern, entity_info) sorted by pattern length
        (longer patterns first for greedy matching).
        """
        patterns = []
        for surface_form, entity_info in lexicon.items():
            # Escape special regex chars and add word boundaries
            escaped = re.escape(surface_form)
            # Allow for hyphen/space variations
            # Important: replace hyphens before spaces to avoid corrupting
            # the [\s\-] character class inserted by the space replacement.
            escaped = escaped.replace(r"\-", r"[\s\-]?")
            escaped = escaped.replace(r"\ ", r"[\s\-]")
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            patterns.append((pattern, surface_form, entity_info))

        # Sort by surface form length (longest first) for greedy matching
        patterns.sort(key=lambda x: len(x[1]), reverse=True)
        return patterns

    def extract_from_text(
        self,
        text: str,
        doc_hash: str,
        extract_capabilities: bool = True,
        extract_products: bool = True,
        extract_risks: bool = True,
        extract_events: bool = True,
    ) -> ExtractionResult:
        """
        Extract all entity mentions from text.

        Args:
            text: Document text
            doc_hash: Document content hash
            extract_capabilities: Extract AI/ML capabilities
            extract_products: Extract Workday products
            extract_risks: Extract risk topics
            extract_events: Extract events

        Returns:
            ExtractionResult with all mentions
        """
        result = ExtractionResult(doc_hash=doc_hash)

        if not text:
            return result

        if extract_capabilities:
            result.capability_mentions = self._extract_entities(
                text, self.capability_patterns, "capability"
            )

        if extract_products:
            result.product_mentions = self._extract_entities(
                text, self.product_patterns, "product"
            )

        if extract_risks:
            result.risk_mentions = self._extract_entities(
                text, self.risk_patterns, "risk"
            )

        if extract_events:
            result.event_mentions = self._extract_entities(
                text, self.event_patterns, "event"
            )

        return result

    def extract_from_sentences(
        self,
        sentences: list[dict],
        doc_hash: str,
        extract_capabilities: bool = True,
        extract_products: bool = True,
        extract_risks: bool = True,
        extract_events: bool = True,
    ) -> ExtractionResult:
        """
        Extract entities from pre-split sentences.

        Args:
            sentences: List of sentence dicts with 'text', 'sentence_id', 'start_char'
            doc_hash: Document content hash
            extract_capabilities: Extract AI/ML capabilities
            extract_products: Extract Workday products
            extract_risks: Extract risk topics
            extract_events: Extract events

        Returns:
            ExtractionResult with mentions including sentence IDs
        """
        result = ExtractionResult(doc_hash=doc_hash)

        if not sentences:
            return result

        for sent in sentences:
            sent_text = sent.get("text", "")
            sent_id = sent.get("sentence_id", "")
            sent_start = sent.get("start_char", 0)

            if extract_capabilities:
                mentions = self._extract_entities(
                    sent_text, self.capability_patterns, "capability",
                    sentence_id=sent_id, offset=sent_start
                )
                result.capability_mentions.extend(mentions)

            if extract_products:
                mentions = self._extract_entities(
                    sent_text, self.product_patterns, "product",
                    sentence_id=sent_id, offset=sent_start
                )
                result.product_mentions.extend(mentions)

            if extract_risks:
                mentions = self._extract_entities(
                    sent_text, self.risk_patterns, "risk",
                    sentence_id=sent_id, offset=sent_start
                )
                result.risk_mentions.extend(mentions)

            if extract_events:
                mentions = self._extract_entities(
                    sent_text, self.event_patterns, "event",
                    sentence_id=sent_id, offset=sent_start
                )
                result.event_mentions.extend(mentions)

        return result

    def _extract_entities(
        self,
        text: str,
        patterns: list[tuple[re.Pattern, str, tuple]],
        entity_type: str,
        sentence_id: Optional[str] = None,
        offset: int = 0,
    ) -> list[EntityMatch]:
        """
        Extract entities of a specific type from text.

        Args:
            text: Text to search
            patterns: Compiled patterns with entity info
            entity_type: Type of entity (capability, product, risk)
            sentence_id: Optional sentence ID for provenance
            offset: Character offset to add to positions

        Returns:
            List of EntityMatch objects
        """
        matches = []
        matched_spans = set()  # Track matched spans to avoid duplicates

        for pattern, surface_form, entity_info in patterns:
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()

                # Skip if this span overlaps with an already matched span
                span_key = (start, end)
                if any(self._spans_overlap(span_key, existing) for existing in matched_spans):
                    continue

                matched_spans.add(span_key)

                entity_id, name, category = entity_info

                matches.append(EntityMatch(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    name=name,
                    normalized_name=name.lower(),
                    category=category,
                    match_text=match.group(),
                    start_char=start + offset,
                    end_char=end + offset,
                    confidence=1.0,
                ))

        return matches

    def _spans_overlap(self, span1: tuple[int, int], span2: tuple[int, int]) -> bool:
        """Check if two spans overlap."""
        return not (span1[1] <= span2[0] or span2[1] <= span1[0])


def extract_entities(
    text: str,
    doc_hash: str,
) -> ExtractionResult:
    """
    Convenience function to extract all entities from text.

    Args:
        text: Document text
        doc_hash: Document content hash

    Returns:
        ExtractionResult
    """
    extractor = EntityExtractor()
    return extractor.extract_from_text(text, doc_hash)


def extract_entities_from_sentences(
    sentences: list[dict],
    doc_hash: str,
) -> ExtractionResult:
    """
    Convenience function to extract entities from sentences.

    Args:
        sentences: List of sentence dicts
        doc_hash: Document content hash

    Returns:
        ExtractionResult
    """
    extractor = EntityExtractor()
    return extractor.extract_from_sentences(sentences, doc_hash)

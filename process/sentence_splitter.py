"""
Sentence segmentation (NOR-100).

Splits text into sentences with stable IDs for evidence tracking.
Uses spaCy for accurate sentence boundary detection.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from config import setup_logging

logger = setup_logging(__name__)

# Global spaCy model cache
_nlp = None


def get_spacy_model():
    """Load spaCy model lazily."""
    global _nlp
    if _nlp is None:
        try:
            import sys
            # Disable spaCy on Python 3.14+ due to pydantic incompatibility
            if sys.version_info >= (3, 14):
                logger.info("Skipping spaCy on Python 3.14+ (pydantic incompatibility)")
                return None

            import spacy
            try:
                _nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("Downloading spaCy model en_core_web_sm...")
                import subprocess
                subprocess.run(["python3", "-m", "spacy", "download", "en_core_web_sm"], check=True)
                _nlp = spacy.load("en_core_web_sm")
        except (ImportError, Exception) as e:
            logger.info(f"spaCy not available ({e}). Using regex fallback.")
            return None
    return _nlp


@dataclass
class Sentence:
    """A single sentence with position information."""

    text: str
    sentence_id: str  # Stable ID based on content hash
    index: int  # Position in document (0-based)
    start_char: int  # Character offset in original text
    end_char: int  # Character offset end
    word_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "sentence_id": self.sentence_id,
            "index": self.index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "word_count": self.word_count,
        }


@dataclass
class SentenceSegmentationResult:
    """Result of sentence segmentation."""

    sentences: list[Sentence]
    total_sentences: int
    total_words: int
    avg_sentence_length: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "sentences": [s.to_dict() for s in self.sentences],
            "total_sentences": self.total_sentences,
            "total_words": self.total_words,
            "avg_sentence_length": self.avg_sentence_length,
            "warnings": self.warnings,
        }


class SentenceSplitter:
    """
    Split text into sentences with stable IDs.

    Uses spaCy for accurate sentence boundary detection with
    fallback to regex-based splitting.
    """

    def __init__(
        self,
        doc_id: Optional[str] = None,
        min_sentence_length: int = 10,
        max_sentence_length: int = 5000,
    ):
        """
        Initialize the splitter.

        Args:
            doc_id: Document ID to include in sentence IDs (for uniqueness)
            min_sentence_length: Minimum characters for a valid sentence
            max_sentence_length: Maximum characters before splitting further
        """
        self.doc_id = doc_id
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length

    def split(self, text: str) -> SentenceSegmentationResult:
        """
        Split text into sentences.

        Args:
            text: Input text to segment

        Returns:
            SentenceSegmentationResult with sentences and metadata
        """
        warnings = []

        if not text or not text.strip():
            return SentenceSegmentationResult(
                sentences=[],
                total_sentences=0,
                total_words=0,
                avg_sentence_length=0.0,
                warnings=["Empty input text"],
            )

        # Preprocess text
        text = self._preprocess(text)

        # Try spaCy first
        nlp = get_spacy_model()
        if nlp:
            sentences = self._split_with_spacy(text, nlp)
        else:
            sentences = self._split_with_regex(text)
            warnings.append("Used regex fallback (spaCy not available)")

        # Filter and validate sentences
        valid_sentences = []
        for i, sent in enumerate(sentences):
            # Skip very short sentences
            if len(sent.text) < self.min_sentence_length:
                continue

            # Split very long sentences
            if len(sent.text) > self.max_sentence_length:
                sub_sents = self._split_long_sentence(sent, len(valid_sentences))
                valid_sentences.extend(sub_sents)
                warnings.append(f"Split long sentence at index {i}")
            else:
                # Update index
                sent.index = len(valid_sentences)
                valid_sentences.append(sent)

        # Regenerate IDs with final indices
        for sent in valid_sentences:
            sent.sentence_id = self._generate_sentence_id(sent.text, sent.index)

        # Calculate statistics
        total_sentences = len(valid_sentences)
        total_words = sum(s.word_count for s in valid_sentences)
        avg_length = total_words / total_sentences if total_sentences > 0 else 0.0

        return SentenceSegmentationResult(
            sentences=valid_sentences,
            total_sentences=total_sentences,
            total_words=total_words,
            avg_sentence_length=round(avg_length, 2),
            warnings=warnings,
        )

    def _preprocess(self, text: str) -> str:
        """Preprocess text before splitting."""
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        # Fix common issues
        # Add space after periods that are missing it
        text = re.sub(r"\.([A-Z])", r". \1", text)

        # Normalize quotes
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")

        return text.strip()

    def _split_with_spacy(self, text: str, nlp) -> list[Sentence]:
        """Split using spaCy's sentence segmentation."""
        # Process in chunks if text is very long
        max_length = 100000
        if len(text) > max_length:
            return self._split_long_text_with_spacy(text, nlp, max_length)

        doc = nlp(text)
        sentences = []

        for i, sent in enumerate(doc.sents):
            sent_text = sent.text.strip()
            if sent_text:
                sentences.append(Sentence(
                    text=sent_text,
                    sentence_id="",  # Will be set later
                    index=i,
                    start_char=sent.start_char,
                    end_char=sent.end_char,
                    word_count=len(sent_text.split()),
                ))

        return sentences

    def _split_long_text_with_spacy(self, text: str, nlp, max_length: int) -> list[Sentence]:
        """Split very long text in chunks."""
        sentences = []
        offset = 0

        while offset < len(text):
            # Find a good break point (paragraph or sentence)
            chunk_end = min(offset + max_length, len(text))
            if chunk_end < len(text):
                # Try to break at paragraph
                para_break = text.rfind("\n\n", offset, chunk_end)
                if para_break > offset:
                    chunk_end = para_break
                else:
                    # Try to break at period
                    period_break = text.rfind(". ", offset, chunk_end)
                    if period_break > offset:
                        chunk_end = period_break + 1

            chunk = text[offset:chunk_end]
            doc = nlp(chunk)

            for sent in doc.sents:
                sent_text = sent.text.strip()
                if sent_text:
                    sentences.append(Sentence(
                        text=sent_text,
                        sentence_id="",
                        index=len(sentences),
                        start_char=offset + sent.start_char,
                        end_char=offset + sent.end_char,
                        word_count=len(sent_text.split()),
                    ))

            offset = chunk_end

        return sentences

    def _split_with_regex(self, text: str) -> list[Sentence]:
        """Fallback regex-based sentence splitting."""
        # Simple sentence boundary pattern
        # Handles: . ! ? followed by space and capital letter
        pattern = r"(?<=[.!?])\s+(?=[A-Z])"

        parts = re.split(pattern, text)
        sentences = []
        offset = 0

        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                start = text.find(part, offset)
                end = start + len(part)
                sentences.append(Sentence(
                    text=part,
                    sentence_id="",
                    index=i,
                    start_char=start,
                    end_char=end,
                    word_count=len(part.split()),
                ))
                offset = end

        return sentences

    def _split_long_sentence(self, sentence: Sentence, start_index: int) -> list[Sentence]:
        """Split a very long sentence into smaller parts."""
        text = sentence.text
        parts = []

        # Try to split at semicolons or colons
        sub_parts = re.split(r"[;:]\s+", text)

        if len(sub_parts) > 1:
            offset = sentence.start_char
            for i, part in enumerate(sub_parts):
                part = part.strip()
                if part:
                    start = text.find(part)
                    parts.append(Sentence(
                        text=part,
                        sentence_id="",
                        index=start_index + i,
                        start_char=offset + start,
                        end_char=offset + start + len(part),
                        word_count=len(part.split()),
                    ))
        else:
            # Can't split further, keep as is
            parts.append(sentence)

        return parts

    def _generate_sentence_id(self, text: str, index: int) -> str:
        """
        Generate a stable sentence ID.

        The ID is based on:
        - Document ID (if provided)
        - Sentence index
        - Content hash (first 8 chars)
        """
        # Create content hash
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:8]

        if self.doc_id:
            return f"{self.doc_id[:16]}-s{index:04d}-{content_hash}"
        else:
            return f"s{index:04d}-{content_hash}"


def split_sentences(
    text: str,
    doc_id: Optional[str] = None,
) -> SentenceSegmentationResult:
    """
    Convenience function to split text into sentences.

    Args:
        text: Input text
        doc_id: Optional document ID for sentence ID generation

    Returns:
        SentenceSegmentationResult
    """
    splitter = SentenceSplitter(doc_id=doc_id)
    return splitter.split(text)

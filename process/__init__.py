# Text extraction and processing module

from process.html_extractor import (
    HTMLExtractor,
    HTMLExtractionResult,
    extract_html_text,
    extract_html_file,
)

from process.pdf_extractor import (
    PDFExtractor,
    PDFExtractionResult,
    extract_pdf_text,
    extract_pdf_file,
)

from process.date_extractor import (
    DateExtractor,
    DateExtractionResult,
    extract_date,
)

from process.sentence_splitter import (
    SentenceSplitter,
    Sentence,
    SentenceSegmentationResult,
    split_sentences,
)

from process.doc_classifier import (
    DocumentClassifier,
    DocType,
    ClassificationResult,
    classify_document,
)

from process.storage import (
    ProcessedDocument,
    ProcessedDocumentStorage,
    create_processed_document,
)

from process.main import (
    DocumentProcessor,
    process_all_documents,
)

__all__ = [
    # HTML extraction
    "HTMLExtractor",
    "HTMLExtractionResult",
    "extract_html_text",
    "extract_html_file",
    # PDF extraction
    "PDFExtractor",
    "PDFExtractionResult",
    "extract_pdf_text",
    "extract_pdf_file",
    # Date extraction
    "DateExtractor",
    "DateExtractionResult",
    "extract_date",
    # Sentence splitting
    "SentenceSplitter",
    "Sentence",
    "SentenceSegmentationResult",
    "split_sentences",
    # Document classification
    "DocumentClassifier",
    "DocType",
    "ClassificationResult",
    "classify_document",
    # Storage
    "ProcessedDocument",
    "ProcessedDocumentStorage",
    "create_processed_document",
    # Main pipeline
    "DocumentProcessor",
    "process_all_documents",
]

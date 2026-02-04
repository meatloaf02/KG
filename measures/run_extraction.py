"""
Entity extraction runner (NOR-107, NOR-108, NOR-109).

Runs entity extraction on all processed documents and loads
the resulting mentions into Memgraph as MENTIONS/DISCLOSES relationships.

Usage:
    python -m measures.run_extraction                  # Extract from all docs
    python -m measures.run_extraction --limit 10      # Limit documents
    python -m measures.run_extraction --dry-run       # Preview without loading
    python -m measures.run_extraction --stats         # Show extraction stats
"""

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from tqdm import tqdm

from config import setup_logging
from kg.loaders import KGLoader
from kg.schema import Evidence
from measures.extractor import EntityExtractor, ExtractionResult
from measures.lexicons import AI_CAPABILITY_LEXICON, PRODUCT_LEXICON, RISK_LEXICON
from process.storage import ProcessedDocumentStorage

logger = setup_logging(__name__)

EXTRACTOR_VERSION = "1.0.0"


@dataclass
class ExtractionStats:
    """Statistics from extraction run."""

    total_docs: int = 0
    processed_docs: int = 0
    skipped_docs: int = 0
    failed_docs: int = 0

    # Entity counts (unique per document)
    capability_mentions: int = 0
    product_mentions: int = 0
    risk_mentions: int = 0

    # Relationship counts (loaded into KG)
    capability_relationships: int = 0
    product_relationships: int = 0
    risk_relationships: int = 0

    # Entity distribution
    capability_counts: dict = field(default_factory=lambda: defaultdict(int))
    product_counts: dict = field(default_factory=lambda: defaultdict(int))
    risk_counts: dict = field(default_factory=lambda: defaultdict(int))

    errors: list = field(default_factory=list)


def ensure_entity_nodes(loader: KGLoader) -> dict:
    """
    Ensure all entity nodes exist in the graph.

    Creates nodes for all entities in the lexicons so that
    MENTIONS relationships can be created.

    Returns:
        Dict with counts of entities created
    """
    stats = {
        "capabilities": 0,
        "products": 0,
        "risks": 0,
    }

    # Get unique entity IDs from lexicons
    capability_entities = {}
    for surface_form, (entity_id, name, category) in AI_CAPABILITY_LEXICON.items():
        if entity_id not in capability_entities:
            capability_entities[entity_id] = {"name": name, "category": category}

    product_entities = {}
    for surface_form, (entity_id, name, category) in PRODUCT_LEXICON.items():
        if entity_id not in product_entities:
            product_entities[entity_id] = {"name": name, "category": category}

    risk_entities = {}
    for surface_form, (entity_id, name, category) in RISK_LEXICON.items():
        if entity_id not in risk_entities:
            risk_entities[entity_id] = {"name": name, "category": category}

    # Load capability nodes (with all required parameters)
    for entity_id, info in capability_entities.items():
        result = loader.load_capability({
            "id": entity_id,
            "name": info["name"],
            "normalized_name": info["name"].lower(),
            "category": info["category"],
            "first_seen": None,
        })
        if result.success:
            stats["capabilities"] += 1

    # Load product nodes (with all required parameters)
    for entity_id, info in product_entities.items():
        result = loader.load_product({
            "id": entity_id,
            "name": info["name"],
            "normalized_name": info["name"].lower(),
            "description": info["category"],  # category is description for products
            "first_seen": None,
        })
        if result.success:
            stats["products"] += 1

    # Load risk topic nodes (with all required parameters)
    for entity_id, info in risk_entities.items():
        result = loader.load_risk_topic({
            "id": entity_id,
            "name": info["name"],
            "normalized_name": info["name"].lower(),
            "category": info["category"],
            "first_seen": None,
        })
        if result.success:
            stats["risks"] += 1

    return stats


def extract_and_load_document(
    doc_hash: str,
    text: str,
    extractor: EntityExtractor,
    loader: KGLoader,
    stats: ExtractionStats,
    dry_run: bool = False,
) -> bool:
    """
    Extract entities from a document and load into KG.

    Args:
        doc_hash: Document content hash
        text: Document text
        extractor: EntityExtractor instance
        loader: KGLoader instance
        stats: ExtractionStats to update
        dry_run: If True, don't load into KG

    Returns:
        True if successful
    """
    try:
        # Run extraction
        result = extractor.extract_from_text(text, doc_hash)

        # Track unique entities mentioned in this document
        doc_capabilities = set()
        doc_products = set()
        doc_risks = set()

        # Process capability mentions
        for mention in result.capability_mentions:
            doc_capabilities.add(mention.entity_id)
            stats.capability_counts[mention.entity_id] += 1

            if not dry_run:
                evidence = Evidence(
                    text=mention.match_text,
                    sentence_id=f"{doc_hash[:16]}-ext",
                    start_char=mention.start_char,
                    end_char=mention.end_char,
                    confidence=mention.confidence,
                    extracted_at=datetime.now(timezone.utc),
                    extractor_version=EXTRACTOR_VERSION,
                )
                load_result = loader.load_mention_capability(
                    doc_hash, mention.entity_id, evidence
                )
                if load_result.success:
                    stats.capability_relationships += 1

        # Process product mentions
        for mention in result.product_mentions:
            doc_products.add(mention.entity_id)
            stats.product_counts[mention.entity_id] += 1

            if not dry_run:
                evidence = Evidence(
                    text=mention.match_text,
                    sentence_id=f"{doc_hash[:16]}-ext",
                    start_char=mention.start_char,
                    end_char=mention.end_char,
                    confidence=mention.confidence,
                    extracted_at=datetime.now(timezone.utc),
                    extractor_version=EXTRACTOR_VERSION,
                )
                load_result = loader.load_mention_product(
                    doc_hash, mention.entity_id, evidence
                )
                if load_result.success:
                    stats.product_relationships += 1

        # Process risk mentions
        for mention in result.risk_mentions:
            doc_risks.add(mention.entity_id)
            stats.risk_counts[mention.entity_id] += 1

            if not dry_run:
                evidence = Evidence(
                    text=mention.match_text,
                    sentence_id=f"{doc_hash[:16]}-ext",
                    start_char=mention.start_char,
                    end_char=mention.end_char,
                    confidence=mention.confidence,
                    extracted_at=datetime.now(timezone.utc),
                    extractor_version=EXTRACTOR_VERSION,
                )
                load_result = loader.load_disclosure(
                    doc_hash, mention.entity_id, evidence
                )
                if load_result.success:
                    stats.risk_relationships += 1

        # Update document-level stats
        stats.capability_mentions += len(doc_capabilities)
        stats.product_mentions += len(doc_products)
        stats.risk_mentions += len(doc_risks)
        stats.processed_docs += 1

        return True

    except Exception as e:
        logger.error(f"Error extracting from {doc_hash[:16]}: {e}")
        stats.errors.append(f"{doc_hash[:8]}: {str(e)[:50]}")
        stats.failed_docs += 1
        return False


def run_extraction(
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> ExtractionStats:
    """
    Run entity extraction on all processed documents.

    Args:
        limit: Maximum documents to process
        dry_run: If True, extract but don't load into KG

    Returns:
        ExtractionStats with results
    """
    print("=" * 60)
    print("Entity Extraction Pipeline")
    print("=" * 60)

    stats = ExtractionStats()

    # Initialize components
    storage = ProcessedDocumentStorage()
    extractor = EntityExtractor()

    # Get all processed documents
    print("\nLoading processed documents...")
    all_hashes = storage.list_all()
    stats.total_docs = len(all_hashes)

    if limit:
        all_hashes = all_hashes[:limit]

    print(f"Found {stats.total_docs} processed documents")
    if limit:
        print(f"Processing first {limit} documents")

    if dry_run:
        print("\n[DRY RUN] Extracting entities but not loading into KG")

    # Initialize KG loader (only if not dry run)
    loader = None
    if not dry_run:
        print("\nConnecting to Memgraph...")
        loader = KGLoader()

        # Ensure entity nodes exist
        print("Ensuring entity nodes exist in KG...")
        node_stats = ensure_entity_nodes(loader)
        print(f"  Capabilities: {node_stats['capabilities']}")
        print(f"  Products: {node_stats['products']}")
        print(f"  Risk Topics: {node_stats['risks']}")

    # Process documents
    print(f"\nExtracting entities from {len(all_hashes)} documents...")

    with tqdm(total=len(all_hashes), desc="Extracting", unit="doc") as pbar:
        for content_hash in all_hashes:
            # Load document text
            text = storage.load_text(content_hash)
            if not text:
                stats.skipped_docs += 1
                pbar.update(1)
                continue

            # Extract and load
            extract_and_load_document(
                content_hash,
                text,
                extractor,
                loader if not dry_run else KGLoader.__new__(KGLoader),  # Dummy for dry run
                stats,
                dry_run=dry_run,
            )
            pbar.update(1)

    # Close loader
    if loader:
        loader.close()

    return stats


def show_stats():
    """Show current extraction statistics from the KG."""
    print("=" * 60)
    print("Extraction Statistics")
    print("=" * 60)

    with KGLoader() as loader:
        kg_stats = loader.get_loader_stats()

        print(f"\nKnowledge Graph Overview:")
        print(f"  Total Nodes: {kg_stats['total_nodes']}")
        print(f"  Total Relationships: {kg_stats['total_relationships']}")

        if kg_stats["nodes_by_label"]:
            print("\n  Nodes by Label:")
            for label, count in sorted(kg_stats["nodes_by_label"].items()):
                print(f"    {label}: {count}")

        if kg_stats["relationships_by_type"]:
            print("\n  Relationships by Type:")
            for rel_type, count in sorted(kg_stats["relationships_by_type"].items()):
                print(f"    {rel_type}: {count}")

    print("\n" + "=" * 60)


def print_stats(stats: ExtractionStats):
    """Print extraction statistics."""
    print("\n" + "-" * 60)
    print("Extraction Complete!")
    print("-" * 60)

    print(f"\n  Documents:")
    print(f"    Total: {stats.total_docs}")
    print(f"    Processed: {stats.processed_docs}")
    print(f"    Skipped (no text): {stats.skipped_docs}")
    print(f"    Failed: {stats.failed_docs}")

    print(f"\n  Entity Mentions (unique per doc):")
    print(f"    Capabilities: {stats.capability_mentions}")
    print(f"    Products: {stats.product_mentions}")
    print(f"    Risks: {stats.risk_mentions}")

    if stats.capability_relationships or stats.product_relationships or stats.risk_relationships:
        print(f"\n  Relationships Loaded:")
        print(f"    MENTIONS (Capability): {stats.capability_relationships}")
        print(f"    MENTIONS (Product): {stats.product_relationships}")
        print(f"    DISCLOSES (Risk): {stats.risk_relationships}")

    # Top entities
    if stats.capability_counts:
        print(f"\n  Top 10 Capabilities:")
        sorted_caps = sorted(stats.capability_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for entity_id, count in sorted_caps:
            print(f"    {entity_id}: {count} mentions")

    if stats.product_counts:
        print(f"\n  Top 10 Products:")
        sorted_prods = sorted(stats.product_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for entity_id, count in sorted_prods:
            print(f"    {entity_id}: {count} mentions")

    if stats.risk_counts:
        print(f"\n  Top 10 Risk Topics:")
        sorted_risks = sorted(stats.risk_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for entity_id, count in sorted_risks:
            print(f"    {entity_id}: {count} mentions")

    if stats.errors:
        print(f"\n  First {len(stats.errors)} errors:")
        for err in stats.errors[:10]:
            print(f"    - {err}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Entity Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum documents to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract entities but don't load into KG",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current extraction statistics",
    )

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    stats = run_extraction(
        limit=args.limit,
        dry_run=args.dry_run,
    )

    print_stats(stats)

    if stats.failed_docs > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

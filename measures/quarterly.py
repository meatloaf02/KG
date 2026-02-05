"""
Quarterly signal aggregation (NOR-110).

Computes quarterly rollups from Knowledge Graph data:
- AI-language intensity (capability mentions per document)
- Product mention frequency
- Risk disclosure density
- Coverage metrics (documents per quarter)

Usage:
    python -m measures.quarterly                     # Compute all signals
    python -m measures.quarterly --output signals.csv  # Export to CSV
    python -m measures.quarterly --stats             # Show summary stats
"""

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import PROCESSED_DATA_DIR, setup_logging
from kg.connection import execute_query, get_driver

logger = setup_logging(__name__)


@dataclass
class QuarterlyMetrics:
    """Metrics for a single quarter."""

    year: int
    quarter: int

    # Document counts
    document_count: int = 0
    sec_filing_count: int = 0
    press_release_count: int = 0
    blog_count: int = 0
    other_count: int = 0

    # Entity mention counts
    capability_mention_count: int = 0
    product_mention_count: int = 0
    risk_mention_count: int = 0

    # Unique entity counts
    unique_capabilities: int = 0
    unique_products: int = 0
    unique_risks: int = 0

    # Entity breakdown
    capability_breakdown: dict = field(default_factory=dict)
    product_breakdown: dict = field(default_factory=dict)
    risk_breakdown: dict = field(default_factory=dict)

    @property
    def period(self) -> str:
        """Get period string like '2023-Q1'."""
        return f"{self.year}-Q{self.quarter}"

    @property
    def ai_intensity(self) -> float:
        """AI-language intensity = capability mentions per document."""
        if self.document_count == 0:
            return 0.0
        return round(self.capability_mention_count / self.document_count, 4)

    @property
    def product_coverage(self) -> float:
        """Product coverage = product mentions per document."""
        if self.document_count == 0:
            return 0.0
        return round(self.product_mention_count / self.document_count, 4)

    @property
    def risk_density(self) -> float:
        """Risk disclosure density = risk mentions per document."""
        if self.document_count == 0:
            return 0.0
        return round(self.risk_mention_count / self.document_count, 4)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "period": self.period,
            "year": self.year,
            "quarter": self.quarter,
            "document_count": self.document_count,
            "sec_filing_count": self.sec_filing_count,
            "press_release_count": self.press_release_count,
            "blog_count": self.blog_count,
            "other_count": self.other_count,
            "capability_mention_count": self.capability_mention_count,
            "product_mention_count": self.product_mention_count,
            "risk_mention_count": self.risk_mention_count,
            "unique_capabilities": self.unique_capabilities,
            "unique_products": self.unique_products,
            "unique_risks": self.unique_risks,
            "ai_intensity": self.ai_intensity,
            "product_coverage": self.product_coverage,
            "risk_density": self.risk_density,
        }


@dataclass
class QuarterlySignals:
    """Complete quarterly signal data."""

    quarters: list[QuarterlyMetrics]
    computed_at: str
    total_documents: int = 0
    total_capabilities: int = 0
    total_products: int = 0
    total_risks: int = 0

    def to_csv(self, output_path: Path) -> Path:
        """Export to CSV file."""
        if not self.quarters:
            raise ValueError("No data to export")

        fieldnames = list(self.quarters[0].to_dict().keys())

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for q in sorted(self.quarters, key=lambda x: (x.year, x.quarter)):
                writer.writerow(q.to_dict())

        return output_path


def parse_quarter_from_date(date_str: Optional[str]) -> Optional[tuple[int, int]]:
    """
    Parse year and quarter from a date string.

    Args:
        date_str: Date string in various formats (YYYY-MM-DD, YYYY/MM/DD, etc.)

    Returns:
        Tuple of (year, quarter) or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Try common date formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y%m%d"]:
            try:
                dt = datetime.strptime(date_str[:10], fmt[:len(date_str[:10])])
                quarter = (dt.month - 1) // 3 + 1
                return (dt.year, quarter)
            except ValueError:
                continue

        # Try to extract just year-month
        if len(date_str) >= 7:
            year = int(date_str[:4])
            month = int(date_str[5:7])
            quarter = (month - 1) // 3 + 1
            return (year, quarter)

    except (ValueError, IndexError):
        pass

    return None


def get_documents_by_quarter(driver=None) -> dict[tuple[int, int], list[dict]]:
    """
    Get all documents grouped by quarter.

    Args:
        driver: Optional Memgraph driver

    Returns:
        Dict mapping (year, quarter) to list of document dicts
    """
    query = """
    MATCH (d:Document)
    WHERE d.publish_date IS NOT NULL
    RETURN d.content_hash AS content_hash,
           d.publish_date AS publish_date,
           d.source_type AS source_type,
           d.title AS title
    ORDER BY d.publish_date
    """

    results = execute_query(query, driver=driver)
    quarters = defaultdict(list)

    for record in results:
        parsed = parse_quarter_from_date(record.get("publish_date"))
        if parsed:
            quarters[parsed].append(record)

    return dict(quarters)


def get_mentions_by_quarter(driver=None) -> dict[tuple[int, int], dict[str, list]]:
    """
    Get all entity mentions grouped by quarter.

    Args:
        driver: Optional Memgraph driver

    Returns:
        Dict mapping (year, quarter) to dict of entity mentions by type
    """
    # Query for capability mentions
    cap_query = """
    MATCH (d:Document)-[r:MENTIONS]->(c:Capability)
    WHERE d.publish_date IS NOT NULL
    RETURN d.publish_date AS publish_date,
           d.content_hash AS doc_hash,
           c.id AS entity_id,
           c.name AS entity_name,
           'capability' AS entity_type
    """

    # Query for product mentions
    prod_query = """
    MATCH (d:Document)-[r:MENTIONS]->(p:Product)
    WHERE d.publish_date IS NOT NULL
    RETURN d.publish_date AS publish_date,
           d.content_hash AS doc_hash,
           p.id AS entity_id,
           p.name AS entity_name,
           'product' AS entity_type
    """

    # Query for risk disclosures
    risk_query = """
    MATCH (d:Document)-[r:DISCLOSES]->(rt:RiskTopic)
    WHERE d.publish_date IS NOT NULL
    RETURN d.publish_date AS publish_date,
           d.content_hash AS doc_hash,
           rt.id AS entity_id,
           rt.name AS entity_name,
           'risk' AS entity_type
    """

    quarters = defaultdict(lambda: {"capabilities": [], "products": [], "risks": []})

    # Execute queries
    for query, entity_key in [
        (cap_query, "capabilities"),
        (prod_query, "products"),
        (risk_query, "risks"),
    ]:
        results = execute_query(query, driver=driver)
        for record in results:
            parsed = parse_quarter_from_date(record.get("publish_date"))
            if parsed:
                quarters[parsed][entity_key].append(record)

    return dict(quarters)


def compute_quarterly_signals(driver=None) -> QuarterlySignals:
    """
    Compute quarterly signal metrics from the Knowledge Graph.

    Args:
        driver: Optional Memgraph driver

    Returns:
        QuarterlySignals with all computed metrics
    """
    logger.info("Computing quarterly signals...")

    driver = driver or get_driver()

    # Get documents by quarter
    docs_by_quarter = get_documents_by_quarter(driver)
    mentions_by_quarter = get_mentions_by_quarter(driver)

    # Get all quarters (union of docs and mentions)
    all_quarters = set(docs_by_quarter.keys()) | set(mentions_by_quarter.keys())

    metrics = []
    total_docs = 0
    all_capabilities = set()
    all_products = set()
    all_risks = set()

    for year, quarter in sorted(all_quarters):
        qm = QuarterlyMetrics(year=year, quarter=quarter)

        # Count documents by type
        docs = docs_by_quarter.get((year, quarter), [])
        qm.document_count = len(docs)
        total_docs += len(docs)

        for doc in docs:
            source_type = doc.get("source_type", "").lower()
            if "sec" in source_type:
                qm.sec_filing_count += 1
            elif "press" in source_type:
                qm.press_release_count += 1
            elif "blog" in source_type:
                qm.blog_count += 1
            else:
                qm.other_count += 1

        # Count entity mentions
        mentions = mentions_by_quarter.get((year, quarter), {"capabilities": [], "products": [], "risks": []})

        # Capability mentions
        cap_entities = set()
        cap_counts = defaultdict(int)
        for m in mentions["capabilities"]:
            cap_entities.add(m["entity_id"])
            cap_counts[m["entity_id"]] += 1
            all_capabilities.add(m["entity_id"])
        qm.capability_mention_count = len(mentions["capabilities"])
        qm.unique_capabilities = len(cap_entities)
        qm.capability_breakdown = dict(cap_counts)

        # Product mentions
        prod_entities = set()
        prod_counts = defaultdict(int)
        for m in mentions["products"]:
            prod_entities.add(m["entity_id"])
            prod_counts[m["entity_id"]] += 1
            all_products.add(m["entity_id"])
        qm.product_mention_count = len(mentions["products"])
        qm.unique_products = len(prod_entities)
        qm.product_breakdown = dict(prod_counts)

        # Risk mentions
        risk_entities = set()
        risk_counts = defaultdict(int)
        for m in mentions["risks"]:
            risk_entities.add(m["entity_id"])
            risk_counts[m["entity_id"]] += 1
            all_risks.add(m["entity_id"])
        qm.risk_mention_count = len(mentions["risks"])
        qm.unique_risks = len(risk_entities)
        qm.risk_breakdown = dict(risk_counts)

        metrics.append(qm)

    return QuarterlySignals(
        quarters=metrics,
        computed_at=datetime.now().isoformat(),
        total_documents=total_docs,
        total_capabilities=len(all_capabilities),
        total_products=len(all_products),
        total_risks=len(all_risks),
    )


def print_signals(signals: QuarterlySignals) -> None:
    """Print quarterly signals summary."""
    print("=" * 80)
    print("Quarterly Signal Aggregation")
    print("=" * 80)

    print(f"\nComputed at: {signals.computed_at}")
    print(f"Total documents with dates: {signals.total_documents}")
    print(f"Total quarters covered: {len(signals.quarters)}")
    print(f"Unique capabilities: {signals.total_capabilities}")
    print(f"Unique products: {signals.total_products}")
    print(f"Unique risk topics: {signals.total_risks}")

    if not signals.quarters:
        print("\nNo quarterly data available.")
        return

    # Print table header
    print("\n" + "-" * 80)
    print(f"{'Period':<10} {'Docs':>6} {'SEC':>5} {'AI Int':>8} {'Prod Cov':>9} {'Risk Den':>9}")
    print("-" * 80)

    # Print each quarter
    for q in sorted(signals.quarters, key=lambda x: (x.year, x.quarter)):
        print(
            f"{q.period:<10} "
            f"{q.document_count:>6} "
            f"{q.sec_filing_count:>5} "
            f"{q.ai_intensity:>8.4f} "
            f"{q.product_coverage:>9.4f} "
            f"{q.risk_density:>9.4f}"
        )

    print("-" * 80)

    # Print signal trends
    if len(signals.quarters) >= 2:
        print("\nSignal Trends (first vs last quarter):")
        first = min(signals.quarters, key=lambda x: (x.year, x.quarter))
        last = max(signals.quarters, key=lambda x: (x.year, x.quarter))

        ai_change = last.ai_intensity - first.ai_intensity
        prod_change = last.product_coverage - first.product_coverage
        risk_change = last.risk_density - first.risk_density

        print(f"  AI Intensity:    {first.ai_intensity:.4f} → {last.ai_intensity:.4f} ({ai_change:+.4f})")
        print(f"  Product Coverage: {first.product_coverage:.4f} → {last.product_coverage:.4f} ({prod_change:+.4f})")
        print(f"  Risk Density:    {first.risk_density:.4f} → {last.risk_density:.4f} ({risk_change:+.4f})")

    # Print top entities by mention count
    print("\n" + "-" * 80)
    print("Top Entities (by total mentions across all quarters):")

    # Aggregate across quarters
    cap_totals = defaultdict(int)
    prod_totals = defaultdict(int)
    risk_totals = defaultdict(int)

    for q in signals.quarters:
        for entity_id, count in q.capability_breakdown.items():
            cap_totals[entity_id] += count
        for entity_id, count in q.product_breakdown.items():
            prod_totals[entity_id] += count
        for entity_id, count in q.risk_breakdown.items():
            risk_totals[entity_id] += count

    print("\n  Capabilities:")
    for entity_id, count in sorted(cap_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {entity_id}: {count}")

    print("\n  Products:")
    for entity_id, count in sorted(prod_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {entity_id}: {count}")

    print("\n  Risk Topics:")
    for entity_id, count in sorted(risk_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {entity_id}: {count}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Quarterly Signal Aggregation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show summary statistics only",
    )

    args = parser.parse_args()

    # Compute signals
    signals = compute_quarterly_signals()

    # Print results
    print_signals(signals)

    # Export if requested
    if args.output:
        output_path = Path(args.output)
        signals.to_csv(output_path)
        print(f"\nExported to: {output_path}")

    # Also export to default location
    default_output = PROCESSED_DATA_DIR / "quarterly_signals.csv"
    default_output.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(default_output)
    print(f"Saved to: {default_output}")


if __name__ == "__main__":
    main()

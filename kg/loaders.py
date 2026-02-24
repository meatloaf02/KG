"""
Idempotent Knowledge Graph loaders for Memgraph.

Provides a KGLoader class with methods to load nodes and relationships
using MERGE operations. All operations are idempotent - re-running
them does not create duplicates.

Supports:
- Document loading by content_hash
- Entity loading (Product, Capability, RiskTopic, Event)
- Relationship creation with full provenance
- Batch operations for efficient bulk loading
- Transaction management

Usage:
    from kg.loaders import KGLoader

    loader = KGLoader()
    loader.load_document(doc_data)
    loader.load_mention(doc_hash, product_id, evidence)
    loader.close()

    # Or as context manager:
    with KGLoader() as loader:
        loader.load_documents_batch(documents)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Union

from config import setup_logging
from kg.connection import execute_query, execute_write, get_driver
from kg.schema import (
    CREATE_ANNOUNCES_CAPABILITY,
    CREATE_ANNOUNCES_EVENT,
    CREATE_CAPABILITY,
    CREATE_COMPANY,
    CREATE_DISCLOSES,
    CREATE_DOCUMENT,
    CREATE_EVENT,
    CREATE_HAS_CAPABILITY,
    CREATE_MENTIONS_CAPABILITY,
    CREATE_MENTIONS_PRODUCT,
    CREATE_OWNS,
    CREATE_PRODUCT,
    CREATE_QUARTERLY_SIGNAL,
    CREATE_RISK_TOPIC,
    CapabilityNode,
    DocumentNode,
    EventNode,
    Evidence,
    ProductNode,
    QuarterlySignalNode,
    RiskTopicNode,
)

logger = setup_logging(__name__)


@dataclass
class LoadResult:
    """Result of a load operation."""

    success: bool
    node_id: Optional[str] = None
    created: bool = False
    error: Optional[str] = None

    @classmethod
    def ok(cls, node_id: str, created: bool = False) -> "LoadResult":
        """Create a successful result."""
        return cls(success=True, node_id=node_id, created=created)

    @classmethod
    def fail(cls, error: str) -> "LoadResult":
        """Create a failed result."""
        return cls(success=False, error=error)


@dataclass
class BatchLoadResult:
    """Result of a batch load operation."""

    total: int
    loaded: int
    created: int
    failed: int
    errors: list[str]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return (self.loaded / self.total * 100) if self.total > 0 else 0.0


class KGLoader:
    """
    Knowledge Graph loader with idempotent MERGE operations.

    All load methods use MERGE to ensure idempotency. Running the same
    load operation multiple times will not create duplicates.

    Supports both individual and batch loading operations.
    """

    def __init__(self, driver=None):
        """
        Initialize the loader.

        Args:
            driver: Optional driver instance (uses global if not provided)
        """
        self._driver = driver
        self._owns_driver = driver is None
        self.extractor_version = "1.0.0"

    @property
    def driver(self):
        """Lazy driver initialization."""
        if self._driver is None:
            self._driver = get_driver()
        return self._driver

    def close(self) -> None:
        """Close the driver if we own it."""
        if self._owns_driver and self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self) -> "KGLoader":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    # =========================================================================
    # Document Loading
    # =========================================================================

    def load_document(
        self,
        doc: Union[DocumentNode, dict],
    ) -> LoadResult:
        """
        Load a document node by content_hash (idempotent).

        Args:
            doc: DocumentNode or dict with document data

        Returns:
            LoadResult with success status and node info
        """
        if isinstance(doc, DocumentNode):
            params = doc.to_dict()
        else:
            params = doc

        if not params.get("content_hash"):
            return LoadResult.fail("content_hash is required")

        try:
            results = execute_query(CREATE_DOCUMENT, params, driver=self.driver)
            if results:
                node = results[0].get("d")
                # Check if it was created or matched
                created = node.get("created_at") == node.get("updated_at", node.get("created_at"))
                return LoadResult.ok(params["content_hash"], created=created)
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load document {params.get('content_hash')}: {e}")
            return LoadResult.fail(str(e))

    def load_documents_batch(
        self,
        documents: list[Union[DocumentNode, dict]],
        batch_size: int = 100,
    ) -> BatchLoadResult:
        """
        Load multiple documents in batches.

        Args:
            documents: List of DocumentNode or dict objects
            batch_size: Number of documents per batch

        Returns:
            BatchLoadResult with statistics
        """
        total = len(documents)
        loaded = 0
        created = 0
        failed = 0
        errors = []

        for i in range(0, total, batch_size):
            batch = documents[i : i + batch_size]
            logger.info(f"Loading documents batch {i // batch_size + 1} ({len(batch)} docs)")

            for doc in batch:
                result = self.load_document(doc)
                if result.success:
                    loaded += 1
                    if result.created:
                        created += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(result.error)

        return BatchLoadResult(
            total=total,
            loaded=loaded,
            created=created,
            failed=failed,
            errors=errors[:10],  # Limit errors to first 10
        )

    # =========================================================================
    # Entity Loading
    # =========================================================================

    def load_company(
        self,
        company_id: str,
        name: str,
        ticker: Optional[str] = None,
    ) -> LoadResult:
        """
        Load a company node (idempotent).

        Args:
            company_id: Unique company identifier
            name: Company name
            ticker: Stock ticker symbol

        Returns:
            LoadResult
        """
        params = {
            "id": company_id,
            "name": name,
            "ticker": ticker,
        }

        try:
            results = execute_query(CREATE_COMPANY, params, driver=self.driver)
            if results:
                return LoadResult.ok(company_id)
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load company {company_id}: {e}")
            return LoadResult.fail(str(e))

    def load_product(
        self,
        product: Union[ProductNode, dict],
    ) -> LoadResult:
        """
        Load a product node (idempotent).

        Args:
            product: ProductNode or dict with product data

        Returns:
            LoadResult
        """
        if isinstance(product, ProductNode):
            params = product.to_dict()
        else:
            params = product

        if not params.get("id"):
            return LoadResult.fail("id is required")

        try:
            results = execute_query(CREATE_PRODUCT, params, driver=self.driver)
            if results:
                return LoadResult.ok(params["id"])
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load product {params.get('id')}: {e}")
            return LoadResult.fail(str(e))

    def load_capability(
        self,
        capability: Union[CapabilityNode, dict],
    ) -> LoadResult:
        """
        Load a capability node (idempotent).

        Args:
            capability: CapabilityNode or dict with capability data

        Returns:
            LoadResult
        """
        if isinstance(capability, CapabilityNode):
            params = capability.to_dict()
        else:
            params = capability

        if not params.get("id"):
            return LoadResult.fail("id is required")

        try:
            results = execute_query(CREATE_CAPABILITY, params, driver=self.driver)
            if results:
                return LoadResult.ok(params["id"])
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load capability {params.get('id')}: {e}")
            return LoadResult.fail(str(e))

    def load_risk_topic(
        self,
        risk: Union[RiskTopicNode, dict],
    ) -> LoadResult:
        """
        Load a risk topic node (idempotent).

        Args:
            risk: RiskTopicNode or dict with risk topic data

        Returns:
            LoadResult
        """
        if isinstance(risk, RiskTopicNode):
            params = risk.to_dict()
        else:
            params = risk

        if not params.get("id"):
            return LoadResult.fail("id is required")

        try:
            results = execute_query(CREATE_RISK_TOPIC, params, driver=self.driver)
            if results:
                return LoadResult.ok(params["id"])
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load risk topic {params.get('id')}: {e}")
            return LoadResult.fail(str(e))

    def load_event(
        self,
        event: Union[EventNode, dict],
    ) -> LoadResult:
        """
        Load an event node (idempotent).

        Args:
            event: EventNode or dict with event data

        Returns:
            LoadResult
        """
        if isinstance(event, EventNode):
            params = event.to_dict()
        else:
            params = event

        if not params.get("id"):
            return LoadResult.fail("id is required")

        try:
            results = execute_query(CREATE_EVENT, params, driver=self.driver)
            if results:
                return LoadResult.ok(params["id"])
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load event {params.get('id')}: {e}")
            return LoadResult.fail(str(e))

    def load_quarterly_signal(
        self,
        signal: Union[QuarterlySignalNode, dict],
    ) -> LoadResult:
        """
        Load or update a QuarterlySignal node (idempotent MERGE on period).

        Args:
            signal: QuarterlySignalNode or dict with signal data.
                    aii_delta may be None for the first available quarter.

        Returns:
            LoadResult with period as node_id.
        """
        if isinstance(signal, QuarterlySignalNode):
            params = signal.to_dict()
        else:
            params = signal

        if not params.get("period"):
            return LoadResult.fail("period is required")

        try:
            results = execute_query(CREATE_QUARTERLY_SIGNAL, params, driver=self.driver)
            if results:
                return LoadResult.ok(params["period"])
            return LoadResult.fail("No result returned")
        except Exception as e:
            logger.error(f"Failed to load QuarterlySignal {params.get('period')}: {e}")
            return LoadResult.fail(str(e))

    # =========================================================================
    # Relationship Loading (with Provenance)
    # =========================================================================

    def _build_evidence_params(
        self,
        evidence: Union[Evidence, dict, None],
    ) -> dict:
        """Build evidence parameters for relationship creation."""
        if evidence is None:
            return {
                "evidence_text": None,
                "sentence_id": None,
                "start_char": None,
                "end_char": None,
                "confidence": 1.0,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "extractor_version": self.extractor_version,
            }
        elif isinstance(evidence, Evidence):
            return evidence.to_dict()
        else:
            return {
                "evidence_text": evidence.get("text") or evidence.get("evidence_text"),
                "sentence_id": evidence.get("sentence_id"),
                "start_char": evidence.get("start_char"),
                "end_char": evidence.get("end_char"),
                "confidence": evidence.get("confidence", 1.0),
                "extracted_at": evidence.get("extracted_at", datetime.now(timezone.utc).isoformat()),
                "extractor_version": evidence.get("extractor_version", self.extractor_version),
            }

    def load_mention_product(
        self,
        doc_hash: str,
        product_id: str,
        evidence: Union[Evidence, dict, None] = None,
    ) -> LoadResult:
        """
        Create a MENTIONS relationship from Document to Product.

        Args:
            doc_hash: Document content_hash
            product_id: Product ID
            evidence: Evidence object or dict with provenance data

        Returns:
            LoadResult
        """
        params = {
            "doc_hash": doc_hash,
            "product_id": product_id,
            **self._build_evidence_params(evidence),
        }

        try:
            results = execute_query(CREATE_MENTIONS_PRODUCT, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{doc_hash}->{product_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create MENTIONS relationship: {e}")
            return LoadResult.fail(str(e))

    def load_mention_capability(
        self,
        doc_hash: str,
        capability_id: str,
        evidence: Union[Evidence, dict, None] = None,
    ) -> LoadResult:
        """
        Create a MENTIONS relationship from Document to Capability.

        Args:
            doc_hash: Document content_hash
            capability_id: Capability ID
            evidence: Evidence object or dict with provenance data

        Returns:
            LoadResult
        """
        params = {
            "doc_hash": doc_hash,
            "capability_id": capability_id,
            **self._build_evidence_params(evidence),
        }

        try:
            results = execute_query(CREATE_MENTIONS_CAPABILITY, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{doc_hash}->{capability_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create MENTIONS relationship: {e}")
            return LoadResult.fail(str(e))

    def load_disclosure(
        self,
        doc_hash: str,
        risk_id: str,
        evidence: Union[Evidence, dict, None] = None,
    ) -> LoadResult:
        """
        Create a DISCLOSES relationship from Document to RiskTopic.

        Args:
            doc_hash: Document content_hash
            risk_id: RiskTopic ID
            evidence: Evidence object or dict with provenance data

        Returns:
            LoadResult
        """
        params = {
            "doc_hash": doc_hash,
            "risk_id": risk_id,
            **self._build_evidence_params(evidence),
        }

        try:
            results = execute_query(CREATE_DISCLOSES, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{doc_hash}->{risk_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create DISCLOSES relationship: {e}")
            return LoadResult.fail(str(e))

    def load_announcement_event(
        self,
        doc_hash: str,
        event_id: str,
        evidence: Union[Evidence, dict, None] = None,
    ) -> LoadResult:
        """
        Create an ANNOUNCES relationship from Document to Event.

        Args:
            doc_hash: Document content_hash
            event_id: Event ID
            evidence: Evidence object or dict with provenance data

        Returns:
            LoadResult
        """
        params = {
            "doc_hash": doc_hash,
            "event_id": event_id,
            **self._build_evidence_params(evidence),
        }

        try:
            results = execute_query(CREATE_ANNOUNCES_EVENT, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{doc_hash}->{event_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create ANNOUNCES relationship: {e}")
            return LoadResult.fail(str(e))

    def load_announcement_capability(
        self,
        doc_hash: str,
        capability_id: str,
        evidence: Union[Evidence, dict, None] = None,
    ) -> LoadResult:
        """
        Create an ANNOUNCES relationship from Document to Capability.

        Args:
            doc_hash: Document content_hash
            capability_id: Capability ID
            evidence: Evidence object or dict with provenance data

        Returns:
            LoadResult
        """
        params = {
            "doc_hash": doc_hash,
            "capability_id": capability_id,
            **self._build_evidence_params(evidence),
        }

        try:
            results = execute_query(CREATE_ANNOUNCES_CAPABILITY, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{doc_hash}->{capability_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create ANNOUNCES relationship: {e}")
            return LoadResult.fail(str(e))

    def load_product_capability(
        self,
        product_id: str,
        capability_id: str,
        first_seen: Optional[str] = None,
    ) -> LoadResult:
        """
        Create a HAS_CAPABILITY relationship from Product to Capability.

        Args:
            product_id: Product ID
            capability_id: Capability ID
            first_seen: Date when capability was first observed

        Returns:
            LoadResult
        """
        params = {
            "product_id": product_id,
            "capability_id": capability_id,
            "first_seen": first_seen,
        }

        try:
            results = execute_query(CREATE_HAS_CAPABILITY, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{product_id}->{capability_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create HAS_CAPABILITY relationship: {e}")
            return LoadResult.fail(str(e))

    def load_ownership(
        self,
        company_id: str,
        product_id: str,
    ) -> LoadResult:
        """
        Create an OWNS relationship from Company to Product.

        Args:
            company_id: Company ID
            product_id: Product ID

        Returns:
            LoadResult
        """
        params = {
            "company_id": company_id,
            "product_id": product_id,
        }

        try:
            results = execute_query(CREATE_OWNS, params, driver=self.driver)
            if results:
                return LoadResult.ok(f"{company_id}->{product_id}")
            return LoadResult.fail("Nodes not found or relationship not created")
        except Exception as e:
            logger.error(f"Failed to create OWNS relationship: {e}")
            return LoadResult.fail(str(e))

    # =========================================================================
    # Bulk Loading Utilities
    # =========================================================================

    def load_document_with_mentions(
        self,
        doc: Union[DocumentNode, dict],
        product_mentions: Optional[list[tuple[str, Union[Evidence, dict, None]]]] = None,
        capability_mentions: Optional[list[tuple[str, Union[Evidence, dict, None]]]] = None,
        risk_disclosures: Optional[list[tuple[str, Union[Evidence, dict, None]]]] = None,
    ) -> dict[str, Any]:
        """
        Load a document and all its relationships in one operation.

        Args:
            doc: Document data
            product_mentions: List of (product_id, evidence) tuples
            capability_mentions: List of (capability_id, evidence) tuples
            risk_disclosures: List of (risk_id, evidence) tuples

        Returns:
            Dict with load statistics
        """
        stats = {
            "document": None,
            "product_mentions": 0,
            "capability_mentions": 0,
            "risk_disclosures": 0,
            "errors": [],
        }

        # Load document first
        doc_result = self.load_document(doc)
        if not doc_result.success:
            stats["errors"].append(f"Document: {doc_result.error}")
            return stats

        stats["document"] = doc_result.node_id
        doc_hash = doc_result.node_id

        # Load product mentions
        if product_mentions:
            for product_id, evidence in product_mentions:
                result = self.load_mention_product(doc_hash, product_id, evidence)
                if result.success:
                    stats["product_mentions"] += 1
                else:
                    stats["errors"].append(f"Product mention {product_id}: {result.error}")

        # Load capability mentions
        if capability_mentions:
            for capability_id, evidence in capability_mentions:
                result = self.load_mention_capability(doc_hash, capability_id, evidence)
                if result.success:
                    stats["capability_mentions"] += 1
                else:
                    stats["errors"].append(f"Capability mention {capability_id}: {result.error}")

        # Load risk disclosures
        if risk_disclosures:
            for risk_id, evidence in risk_disclosures:
                result = self.load_disclosure(doc_hash, risk_id, evidence)
                if result.success:
                    stats["risk_disclosures"] += 1
                else:
                    stats["errors"].append(f"Risk disclosure {risk_id}: {result.error}")

        return stats

    def get_loader_stats(self) -> dict[str, int]:
        """
        Get statistics about the current state of the knowledge graph.

        Returns:
            Dict with node and relationship counts
        """
        from kg.connection import get_database_stats

        return get_database_stats(self.driver)


def main():
    """Demo the KGLoader functionality."""
    print("=" * 60)
    print("KGLoader Demo")
    print("=" * 60)

    with KGLoader() as loader:
        # Show current stats
        print("\nCurrent Knowledge Graph Stats:")
        stats = loader.get_loader_stats()
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Relationships: {stats['total_relationships']}")

        if stats["nodes_by_label"]:
            print("\n  Nodes by Label:")
            for label, count in sorted(stats["nodes_by_label"].items()):
                print(f"    {label}: {count}")

        if stats["relationships_by_type"]:
            print("\n  Relationships by Type:")
            for rel_type, count in sorted(stats["relationships_by_type"].items()):
                print(f"    {rel_type}: {count}")

        # Demo: Load a test document with mentions
        print("\n" + "-" * 60)
        print("Demo: Loading a test document with mentions...")

        doc = DocumentNode(
            content_hash="demo-doc-001",
            url_hash="demo-url-001",
            title="Demo: Workday AI Capabilities Report",
            doc_type="demo",
            source_type="demo",
            publish_date="2024-01-15",
        )

        # Load document with capability mentions (using seed capabilities)
        result = loader.load_document_with_mentions(
            doc=doc,
            capability_mentions=[
                ("ai", Evidence(
                    text="Workday's AI-powered platform",
                    sentence_id="demo-s1",
                    start_char=0,
                    end_char=30,
                    confidence=0.95,
                )),
                ("ml", Evidence(
                    text="machine learning algorithms",
                    sentence_id="demo-s2",
                    start_char=50,
                    end_char=77,
                    confidence=0.90,
                )),
            ],
            product_mentions=[
                ("workday-hcm", Evidence(
                    text="Workday Human Capital Management",
                    sentence_id="demo-s3",
                    start_char=100,
                    end_char=132,
                    confidence=1.0,
                )),
            ],
        )

        print(f"\n  Document loaded: {result['document']}")
        print(f"  Capability mentions: {result['capability_mentions']}")
        print(f"  Product mentions: {result['product_mentions']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")

        # Show updated stats
        print("\n" + "-" * 60)
        print("Updated Knowledge Graph Stats:")
        stats = loader.get_loader_stats()
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Relationships: {stats['total_relationships']}")

        print("\n" + "=" * 60)
        print("Demo complete!")
        print("=" * 60)


if __name__ == "__main__":
    main()

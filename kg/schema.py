"""
Memgraph Knowledge Graph schema definition.

Defines node labels, relationship types, indexes, and constraints
for the Workday AI Knowledge Graph stored in Memgraph.

Node Labels:
- Document: Ingested documents (SEC filings, press releases, etc.)
- Company: Companies mentioned (primarily Workday)
- Product: Workday products (HCM, Financials, etc.)
- Capability: Technology capabilities (AI, ML, analytics, etc.)
- RiskTopic: Risk disclosure topics
- Event: Corporate events (earnings, acquisitions, etc.)

Relationship Types:
- MENTIONS: Document mentions an entity (with evidence)
- DISCLOSES: Document discloses a risk topic
- ANNOUNCES: Document announces an event or capability
- HAS_CAPABILITY: Product has a capability
- OWNS: Company owns a product
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# =============================================================================
# Schema Constants
# =============================================================================

# Node labels
NODE_DOCUMENT = "Document"
NODE_COMPANY = "Company"
NODE_PRODUCT = "Product"
NODE_CAPABILITY = "Capability"
NODE_RISK_TOPIC = "RiskTopic"
NODE_EVENT = "Event"

# Relationship types
REL_MENTIONS = "MENTIONS"
REL_DISCLOSES = "DISCLOSES"
REL_ANNOUNCES = "ANNOUNCES"
REL_HAS_CAPABILITY = "HAS_CAPABILITY"
REL_OWNS = "OWNS"

# Capability categories
CAPABILITY_CATEGORIES = [
    "artificial_intelligence",
    "machine_learning",
    "analytics",
    "automation",
    "cloud",
    "security",
    "integration",
    "mobile",
    "user_experience",
]

# Risk topic categories
RISK_CATEGORIES = [
    "cybersecurity",
    "regulatory",
    "competition",
    "technology",
    "operational",
    "financial",
    "market",
    "talent",
]

# Event types
EVENT_TYPES = [
    "earnings_call",
    "product_launch",
    "acquisition",
    "partnership",
    "leadership_change",
    "conference",
    "regulatory_filing",
]


# =============================================================================
# Cypher Schema Queries
# =============================================================================

# Index creation queries for Memgraph
INDEX_QUERIES = [
    # Document indexes
    "CREATE INDEX ON :Document(content_hash);",
    "CREATE INDEX ON :Document(url_hash);",
    "CREATE INDEX ON :Document(publish_date);",
    "CREATE INDEX ON :Document(doc_type);",
    "CREATE INDEX ON :Document(source_type);",
    # Company indexes
    "CREATE INDEX ON :Company(id);",
    "CREATE INDEX ON :Company(name);",
    # Product indexes
    "CREATE INDEX ON :Product(id);",
    "CREATE INDEX ON :Product(name);",
    "CREATE INDEX ON :Product(normalized_name);",
    # Capability indexes
    "CREATE INDEX ON :Capability(id);",
    "CREATE INDEX ON :Capability(name);",
    "CREATE INDEX ON :Capability(category);",
    # RiskTopic indexes
    "CREATE INDEX ON :RiskTopic(id);",
    "CREATE INDEX ON :RiskTopic(name);",
    "CREATE INDEX ON :RiskTopic(category);",
    # Event indexes
    "CREATE INDEX ON :Event(id);",
    "CREATE INDEX ON :Event(name);",
    "CREATE INDEX ON :Event(event_type);",
    "CREATE INDEX ON :Event(event_date);",
]

# Constraint queries (Memgraph supports unique constraints)
CONSTRAINT_QUERIES = [
    "CREATE CONSTRAINT ON (d:Document) ASSERT d.content_hash IS UNIQUE;",
    "CREATE CONSTRAINT ON (c:Company) ASSERT c.id IS UNIQUE;",
    "CREATE CONSTRAINT ON (p:Product) ASSERT p.id IS UNIQUE;",
    "CREATE CONSTRAINT ON (cap:Capability) ASSERT cap.id IS UNIQUE;",
    "CREATE CONSTRAINT ON (r:RiskTopic) ASSERT r.id IS UNIQUE;",
    "CREATE CONSTRAINT ON (e:Event) ASSERT e.id IS UNIQUE;",
]


# =============================================================================
# Node Creation Templates
# =============================================================================

CREATE_DOCUMENT = """
MERGE (d:Document {content_hash: $content_hash})
ON CREATE SET
    d.url_hash = $url_hash,
    d.title = $title,
    d.doc_type = $doc_type,
    d.source_type = $source_type,
    d.publish_date = $publish_date,
    d.source_url = $source_url,
    d.created_at = timestamp()
ON MATCH SET
    d.updated_at = timestamp()
RETURN d
"""

CREATE_COMPANY = """
MERGE (c:Company {id: $id})
ON CREATE SET
    c.name = $name,
    c.ticker = $ticker,
    c.created_at = timestamp()
RETURN c
"""

CREATE_PRODUCT = """
MERGE (p:Product {id: $id})
ON CREATE SET
    p.name = $name,
    p.normalized_name = $normalized_name,
    p.description = $description,
    p.first_seen = $first_seen,
    p.created_at = timestamp()
ON MATCH SET
    p.updated_at = timestamp()
RETURN p
"""

CREATE_CAPABILITY = """
MERGE (cap:Capability {id: $id})
ON CREATE SET
    cap.name = $name,
    cap.normalized_name = $normalized_name,
    cap.category = $category,
    cap.first_seen = $first_seen,
    cap.created_at = timestamp()
ON MATCH SET
    cap.updated_at = timestamp()
RETURN cap
"""

CREATE_RISK_TOPIC = """
MERGE (r:RiskTopic {id: $id})
ON CREATE SET
    r.name = $name,
    r.normalized_name = $normalized_name,
    r.category = $category,
    r.first_seen = $first_seen,
    r.created_at = timestamp()
ON MATCH SET
    r.updated_at = timestamp()
RETURN r
"""

CREATE_EVENT = """
MERGE (e:Event {id: $id})
ON CREATE SET
    e.name = $name,
    e.event_type = $event_type,
    e.event_date = $event_date,
    e.description = $description,
    e.created_at = timestamp()
ON MATCH SET
    e.updated_at = timestamp()
RETURN e
"""


# =============================================================================
# Relationship Creation Templates (with provenance)
# =============================================================================

CREATE_MENTIONS_PRODUCT = """
MATCH (d:Document {content_hash: $doc_hash})
MATCH (p:Product {id: $product_id})
MERGE (d)-[r:MENTIONS]->(p)
ON CREATE SET
    r.evidence_text = $evidence_text,
    r.sentence_id = $sentence_id,
    r.start_char = $start_char,
    r.end_char = $end_char,
    r.confidence = $confidence,
    r.extracted_at = $extracted_at,
    r.extractor_version = $extractor_version
RETURN r
"""

CREATE_MENTIONS_CAPABILITY = """
MATCH (d:Document {content_hash: $doc_hash})
MATCH (cap:Capability {id: $capability_id})
MERGE (d)-[r:MENTIONS]->(cap)
ON CREATE SET
    r.evidence_text = $evidence_text,
    r.sentence_id = $sentence_id,
    r.start_char = $start_char,
    r.end_char = $end_char,
    r.confidence = $confidence,
    r.extracted_at = $extracted_at,
    r.extractor_version = $extractor_version
RETURN r
"""

CREATE_DISCLOSES = """
MATCH (d:Document {content_hash: $doc_hash})
MATCH (r:RiskTopic {id: $risk_id})
MERGE (d)-[rel:DISCLOSES]->(r)
ON CREATE SET
    rel.evidence_text = $evidence_text,
    rel.sentence_id = $sentence_id,
    rel.start_char = $start_char,
    rel.end_char = $end_char,
    rel.confidence = $confidence,
    rel.extracted_at = $extracted_at,
    rel.extractor_version = $extractor_version
RETURN rel
"""

CREATE_ANNOUNCES_EVENT = """
MATCH (d:Document {content_hash: $doc_hash})
MATCH (e:Event {id: $event_id})
MERGE (d)-[r:ANNOUNCES]->(e)
ON CREATE SET
    r.evidence_text = $evidence_text,
    r.sentence_id = $sentence_id,
    r.start_char = $start_char,
    r.end_char = $end_char,
    r.confidence = $confidence,
    r.extracted_at = $extracted_at,
    r.extractor_version = $extractor_version
RETURN r
"""

CREATE_ANNOUNCES_CAPABILITY = """
MATCH (d:Document {content_hash: $doc_hash})
MATCH (cap:Capability {id: $capability_id})
MERGE (d)-[r:ANNOUNCES]->(cap)
ON CREATE SET
    r.evidence_text = $evidence_text,
    r.sentence_id = $sentence_id,
    r.start_char = $start_char,
    r.end_char = $end_char,
    r.confidence = $confidence,
    r.extracted_at = $extracted_at,
    r.extractor_version = $extractor_version
RETURN r
"""

CREATE_HAS_CAPABILITY = """
MATCH (p:Product {id: $product_id})
MATCH (cap:Capability {id: $capability_id})
MERGE (p)-[r:HAS_CAPABILITY]->(cap)
ON CREATE SET
    r.first_seen = $first_seen,
    r.created_at = timestamp()
RETURN r
"""

CREATE_OWNS = """
MATCH (c:Company {id: $company_id})
MATCH (p:Product {id: $product_id})
MERGE (c)-[r:OWNS]->(p)
ON CREATE SET
    r.created_at = timestamp()
RETURN r
"""


# =============================================================================
# Query Templates
# =============================================================================

# Get document with all relationships
GET_DOCUMENT_GRAPH = """
MATCH (d:Document {content_hash: $content_hash})
OPTIONAL MATCH (d)-[r]->(entity)
RETURN d, collect({rel: type(r), props: properties(r), entity: entity}) as relationships
"""

# Get all mentions of a capability over time
GET_CAPABILITY_TIMELINE = """
MATCH (d:Document)-[r:MENTIONS]->(cap:Capability {name: $capability_name})
RETURN d.publish_date as date, d.title as title, r.evidence_text as evidence
ORDER BY d.publish_date
"""

# Get risk disclosures by category
GET_RISKS_BY_CATEGORY = """
MATCH (d:Document)-[r:DISCLOSES]->(risk:RiskTopic {category: $category})
RETURN d.publish_date as date, risk.name as risk_topic, r.evidence_text as evidence
ORDER BY d.publish_date DESC
"""

# Count mentions by quarter
COUNT_MENTIONS_BY_QUARTER = """
MATCH (d:Document)-[:MENTIONS]->(cap:Capability)
WHERE d.publish_date IS NOT NULL
RETURN
    cap.name as capability,
    d.publish_date.year as year,
    (d.publish_date.month - 1) / 3 + 1 as quarter,
    count(*) as mention_count
ORDER BY year, quarter, capability
"""

# Get product-capability associations
GET_PRODUCT_CAPABILITIES = """
MATCH (p:Product)-[:HAS_CAPABILITY]->(cap:Capability)
RETURN p.name as product, collect(cap.name) as capabilities
ORDER BY p.name
"""


# =============================================================================
# Data Classes for Type Safety
# =============================================================================

@dataclass
class Evidence:
    """Evidence for a relationship between document and entity."""

    text: str
    sentence_id: str
    start_char: int
    end_char: int
    confidence: float = 1.0
    extracted_at: Optional[datetime] = None
    extractor_version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "evidence_text": self.text,
            "sentence_id": self.sentence_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "confidence": self.confidence,
            "extracted_at": (self.extracted_at or datetime.utcnow()).isoformat(),
            "extractor_version": self.extractor_version,
        }


@dataclass
class DocumentNode:
    """Document node data."""

    content_hash: str
    url_hash: str
    title: str
    doc_type: str
    source_type: str
    publish_date: Optional[str] = None
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "content_hash": self.content_hash,
            "url_hash": self.url_hash,
            "title": self.title,
            "doc_type": self.doc_type,
            "source_type": self.source_type,
            "publish_date": self.publish_date,
            "source_url": self.source_url,
        }


@dataclass
class CapabilityNode:
    """Capability node data."""

    id: str
    name: str
    normalized_name: str
    category: str
    first_seen: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "id": self.id,
            "name": self.name,
            "normalized_name": self.normalized_name,
            "category": self.category,
            "first_seen": self.first_seen,
        }


@dataclass
class ProductNode:
    """Product node data."""

    id: str
    name: str
    normalized_name: str
    description: Optional[str] = None
    first_seen: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "id": self.id,
            "name": self.name,
            "normalized_name": self.normalized_name,
            "description": self.description,
            "first_seen": self.first_seen,
        }


@dataclass
class RiskTopicNode:
    """Risk topic node data."""

    id: str
    name: str
    normalized_name: str
    category: str
    first_seen: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "id": self.id,
            "name": self.name,
            "normalized_name": self.normalized_name,
            "category": self.category,
            "first_seen": self.first_seen,
        }


@dataclass
class EventNode:
    """Event node data."""

    id: str
    name: str
    event_type: str
    event_date: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Cypher parameters."""
        return {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type,
            "event_date": self.event_date,
            "description": self.description,
        }


def get_all_schema_queries() -> list[str]:
    """Return all schema creation queries (indexes + constraints)."""
    return CONSTRAINT_QUERIES + INDEX_QUERIES


def get_index_queries() -> list[str]:
    """Return only index creation queries."""
    return INDEX_QUERIES


def get_constraint_queries() -> list[str]:
    """Return only constraint creation queries."""
    return CONSTRAINT_QUERIES

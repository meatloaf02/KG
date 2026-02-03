# Knowledge Graph Schema

This document describes the Memgraph knowledge graph schema for the Workday AI Knowledge Graph project.

## Overview

The knowledge graph stores structured information extracted from Workday's public documents, enabling analysis of AI language evolution, product capabilities, and risk disclosures over time.

```
┌─────────────────┐     ┌─────────────────────────────────────────┐
│   PostgreSQL    │     │              Memgraph                   │
│                 │     │                                         │
│ raw_documents   │────▶│  (:Document)──[:MENTIONS]──▶(:Product)  │
│ (fetch metadata)│     │       │                                 │
│                 │     │       ├──[:MENTIONS]──▶(:Capability)    │
│                 │     │       ├──[:DISCLOSES]─▶(:RiskTopic)     │
│                 │     │       └──[:ANNOUNCES]─▶(:Event)         │
│                 │     │                                         │
│                 │     │  (:Company)──[:OWNS]──▶(:Product)       │
│                 │     │  (:Product)──[:HAS_CAPABILITY]──▶(:Cap) │
└─────────────────┘     └─────────────────────────────────────────┘
```

## Node Labels

### Document

Represents an ingested document (SEC filing, press release, blog post, etc.)

| Property | Type | Description |
|----------|------|-------------|
| `content_hash` | string | SHA-256 hash of content (primary key) |
| `url_hash` | string | Hash of source URL |
| `title` | string | Document title |
| `doc_type` | string | Document type (10-K, 10-Q, 8-K, press_release, blog, etc.) |
| `source_type` | string | Source type (sec_filing, investor_relations, blog, etc.) |
| `publish_date` | date | Publication date |
| `source_url` | string | Original URL |
| `created_at` | timestamp | When node was created |
| `updated_at` | timestamp | When node was last updated |

### Company

Represents a company entity.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (primary key) |
| `name` | string | Full company name |
| `ticker` | string | Stock ticker symbol |
| `cik` | string | SEC CIK number |

### Product

Represents a Workday product.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (primary key) |
| `name` | string | Product name |
| `normalized_name` | string | Lowercase normalized name |
| `description` | string | Product description |
| `first_seen` | date | First mention date |

**Workday Products:**
- Workday HCM (Human Capital Management)
- Workday Financial Management
- Workday Adaptive Planning
- Workday Payroll
- Workday Recruiting
- Workday Learning
- Workday Prism Analytics
- Workday Peakon Employee Voice

### Capability

Represents a technology capability (AI, ML, analytics, etc.)

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (primary key) |
| `name` | string | Capability name |
| `normalized_name` | string | Lowercase normalized name |
| `category` | string | Category (see below) |
| `first_seen` | date | First mention date |

**Categories:**
- `artificial_intelligence` - AI, NLP, chatbots, generative AI, LLMs
- `machine_learning` - ML, deep learning, neural networks
- `analytics` - Predictive analytics, business intelligence
- `automation` - RPA, workflow automation
- `cloud` - Cloud computing, SaaS
- `security` - Cybersecurity, data protection
- `integration` - APIs, integrations
- `mobile` - Mobile apps, responsive design
- `user_experience` - UX, UI improvements

### RiskTopic

Represents a risk disclosure topic.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (primary key) |
| `name` | string | Risk topic name |
| `normalized_name` | string | Lowercase normalized name |
| `category` | string | Category (see below) |
| `first_seen` | date | First mention date |

**Categories:**
- `cybersecurity` - Data breaches, security incidents
- `regulatory` - Compliance, legal risks
- `competition` - Competitive pressures
- `technology` - Technology disruption, AI ethics
- `operational` - Service outages, operational failures
- `financial` - Revenue, profitability risks
- `market` - Market conditions, economic factors
- `talent` - Employee retention, hiring challenges

### Event

Represents a corporate event.

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Unique identifier (primary key) |
| `name` | string | Event name |
| `event_type` | string | Type (see below) |
| `event_date` | date | Event date |
| `description` | string | Event description |

**Event Types:**
- `earnings_call` - Quarterly earnings calls
- `product_launch` - New product announcements
- `acquisition` - M&A activity
- `partnership` - Strategic partnerships
- `leadership_change` - Executive changes
- `conference` - Industry conferences
- `regulatory_filing` - SEC filings

## Relationship Types

### MENTIONS

Document mentions an entity (Product or Capability). Includes provenance.

```cypher
(:Document)-[:MENTIONS]->(:Product)
(:Document)-[:MENTIONS]->(:Capability)
```

| Property | Type | Description |
|----------|------|-------------|
| `evidence_text` | string | Exact text span containing the mention |
| `sentence_id` | string | Stable sentence identifier |
| `start_char` | int | Start character offset |
| `end_char` | int | End character offset |
| `confidence` | float | Extraction confidence (0-1) |
| `extracted_at` | datetime | Extraction timestamp |
| `extractor_version` | string | Extractor version |

### DISCLOSES

Document discloses a risk topic. Includes provenance.

```cypher
(:Document)-[:DISCLOSES]->(:RiskTopic)
```

Properties: Same as MENTIONS

### ANNOUNCES

Document announces an event or new capability. Includes provenance.

```cypher
(:Document)-[:ANNOUNCES]->(:Event)
(:Document)-[:ANNOUNCES]->(:Capability)
```

Properties: Same as MENTIONS

### HAS_CAPABILITY

Product has a capability.

```cypher
(:Product)-[:HAS_CAPABILITY]->(:Capability)
```

| Property | Type | Description |
|----------|------|-------------|
| `first_seen` | date | When capability was first associated |
| `created_at` | timestamp | When relationship was created |

### OWNS

Company owns a product.

```cypher
(:Company)-[:OWNS]->(:Product)
```

| Property | Type | Description |
|----------|------|-------------|
| `created_at` | timestamp | When relationship was created |

## Indexes

The following indexes are created for query performance:

```cypher
// Document
CREATE INDEX ON :Document(content_hash);
CREATE INDEX ON :Document(url_hash);
CREATE INDEX ON :Document(publish_date);
CREATE INDEX ON :Document(doc_type);
CREATE INDEX ON :Document(source_type);

// Company
CREATE INDEX ON :Company(id);
CREATE INDEX ON :Company(name);

// Product
CREATE INDEX ON :Product(id);
CREATE INDEX ON :Product(name);
CREATE INDEX ON :Product(normalized_name);

// Capability
CREATE INDEX ON :Capability(id);
CREATE INDEX ON :Capability(name);
CREATE INDEX ON :Capability(category);

// RiskTopic
CREATE INDEX ON :RiskTopic(id);
CREATE INDEX ON :RiskTopic(name);
CREATE INDEX ON :RiskTopic(category);

// Event
CREATE INDEX ON :Event(id);
CREATE INDEX ON :Event(name);
CREATE INDEX ON :Event(event_type);
CREATE INDEX ON :Event(event_date);
```

## Constraints

Unique constraints ensure data integrity:

```cypher
CREATE CONSTRAINT ON (d:Document) ASSERT d.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (c:Company) ASSERT c.id IS UNIQUE;
CREATE CONSTRAINT ON (p:Product) ASSERT p.id IS UNIQUE;
CREATE CONSTRAINT ON (cap:Capability) ASSERT cap.id IS UNIQUE;
CREATE CONSTRAINT ON (r:RiskTopic) ASSERT r.id IS UNIQUE;
CREATE CONSTRAINT ON (e:Event) ASSERT e.id IS UNIQUE;
```

## Example Queries

### AI Capability Mentions Over Time

```cypher
MATCH (d:Document)-[r:MENTIONS]->(cap:Capability)
WHERE cap.category = 'artificial_intelligence'
RETURN d.publish_date, cap.name, r.evidence_text
ORDER BY d.publish_date;
```

### Quarterly Mention Counts

```cypher
MATCH (d:Document)-[:MENTIONS]->(cap:Capability)
WHERE d.publish_date IS NOT NULL
RETURN
    cap.name as capability,
    d.publish_date.year as year,
    (d.publish_date.month - 1) / 3 + 1 as quarter,
    count(*) as mentions
ORDER BY year, quarter, capability;
```

### Risk Disclosure Trends

```cypher
MATCH (d:Document)-[r:DISCLOSES]->(risk:RiskTopic)
RETURN
    d.publish_date.year as year,
    risk.category,
    count(*) as disclosures
ORDER BY year, risk.category;
```

### Documents Mentioning AI and a Product

```cypher
MATCH (d:Document)-[:MENTIONS]->(cap:Capability {id: 'ai'})
MATCH (d)-[:MENTIONS]->(p:Product {id: 'workday-hcm'})
RETURN d.title, d.publish_date, d.source_type;
```

### Product Capabilities

```cypher
MATCH (p:Product)-[:HAS_CAPABILITY]->(cap:Capability)
RETURN p.name as product, collect(cap.name) as capabilities
ORDER BY p.name;
```

### Evidence Trail for an Entity

```cypher
MATCH (d:Document)-[r:MENTIONS]->(cap:Capability {name: 'Machine Learning'})
RETURN
    d.title,
    d.publish_date,
    r.evidence_text,
    r.confidence
ORDER BY d.publish_date DESC
LIMIT 10;
```

## Schema Files

| File | Description |
|------|-------------|
| `kg/schema.py` | Python module with Cypher queries and data classes |
| `kg/schema.cypher` | Raw Cypher file for manual schema creation |
| `docs/kg_schema.md` | This documentation |

## Usage

### Programmatic (Python)

```python
from kg.schema import (
    get_all_schema_queries,
    CREATE_DOCUMENT,
    CREATE_MENTIONS_CAPABILITY,
    DocumentNode,
    Evidence,
)

# Get all schema creation queries
queries = get_all_schema_queries()

# Create a document node
doc = DocumentNode(
    content_hash="abc123...",
    url_hash="def456...",
    title="Q1 2024 Earnings Call",
    doc_type="earnings_call",
    source_type="investor_relations",
)

# Create evidence for a mention
evidence = Evidence(
    text="We are investing heavily in artificial intelligence...",
    sentence_id="doc1_sent_42",
    start_char=150,
    end_char=210,
    confidence=0.95,
)
```

### Direct Cypher (mgconsole)

```bash
# Load schema
cat kg/schema.cypher | mgconsole

# Or individual queries
mgconsole -c "CREATE INDEX ON :Document(content_hash);"
```

// =============================================================================
// Workday AI Knowledge Graph - Memgraph Schema
// =============================================================================
// This file contains the complete Cypher schema for the knowledge graph.
// Run with: cat kg/schema.cypher | mgconsole
// Or use kg/schema.py for programmatic schema creation.
// =============================================================================

// -----------------------------------------------------------------------------
// CONSTRAINTS (Unique identifiers)
// -----------------------------------------------------------------------------

CREATE CONSTRAINT ON (d:Document) ASSERT d.content_hash IS UNIQUE;
CREATE CONSTRAINT ON (c:Company) ASSERT c.id IS UNIQUE;
CREATE CONSTRAINT ON (p:Product) ASSERT p.id IS UNIQUE;
CREATE CONSTRAINT ON (cap:Capability) ASSERT cap.id IS UNIQUE;
CREATE CONSTRAINT ON (r:RiskTopic) ASSERT r.id IS UNIQUE;
CREATE CONSTRAINT ON (e:Event) ASSERT e.id IS UNIQUE;

// -----------------------------------------------------------------------------
// INDEXES (Query performance)
// -----------------------------------------------------------------------------

// Document indexes
CREATE INDEX ON :Document(content_hash);
CREATE INDEX ON :Document(url_hash);
CREATE INDEX ON :Document(publish_date);
CREATE INDEX ON :Document(doc_type);
CREATE INDEX ON :Document(source_type);

// Company indexes
CREATE INDEX ON :Company(id);
CREATE INDEX ON :Company(name);

// Product indexes
CREATE INDEX ON :Product(id);
CREATE INDEX ON :Product(name);
CREATE INDEX ON :Product(normalized_name);

// Capability indexes
CREATE INDEX ON :Capability(id);
CREATE INDEX ON :Capability(name);
CREATE INDEX ON :Capability(category);

// RiskTopic indexes
CREATE INDEX ON :RiskTopic(id);
CREATE INDEX ON :RiskTopic(name);
CREATE INDEX ON :RiskTopic(category);

// Event indexes
CREATE INDEX ON :Event(id);
CREATE INDEX ON :Event(name);
CREATE INDEX ON :Event(event_type);
CREATE INDEX ON :Event(event_date);

// -----------------------------------------------------------------------------
// SEED DATA: Workday Company
// -----------------------------------------------------------------------------

MERGE (c:Company {id: 'workday'})
ON CREATE SET
    c.name = 'Workday, Inc.',
    c.ticker = 'WDAY',
    c.cik = '0001327811',
    c.created_at = timestamp();

// -----------------------------------------------------------------------------
// SEED DATA: Workday Products
// -----------------------------------------------------------------------------

MERGE (p:Product {id: 'workday-hcm'})
ON CREATE SET
    p.name = 'Workday Human Capital Management',
    p.normalized_name = 'workday hcm',
    p.description = 'Human resources management suite',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-financials'})
ON CREATE SET
    p.name = 'Workday Financial Management',
    p.normalized_name = 'workday financials',
    p.description = 'Financial management and accounting suite',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-planning'})
ON CREATE SET
    p.name = 'Workday Adaptive Planning',
    p.normalized_name = 'workday planning',
    p.description = 'Enterprise planning and budgeting',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-payroll'})
ON CREATE SET
    p.name = 'Workday Payroll',
    p.normalized_name = 'workday payroll',
    p.description = 'Payroll processing solution',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-recruiting'})
ON CREATE SET
    p.name = 'Workday Recruiting',
    p.normalized_name = 'workday recruiting',
    p.description = 'Talent acquisition platform',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-learning'})
ON CREATE SET
    p.name = 'Workday Learning',
    p.normalized_name = 'workday learning',
    p.description = 'Learning management system',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-prism'})
ON CREATE SET
    p.name = 'Workday Prism Analytics',
    p.normalized_name = 'workday prism',
    p.description = 'Analytics and reporting platform',
    p.created_at = timestamp();

MERGE (p:Product {id: 'workday-peakon'})
ON CREATE SET
    p.name = 'Workday Peakon Employee Voice',
    p.normalized_name = 'workday peakon',
    p.description = 'Employee engagement platform',
    p.created_at = timestamp();

// Link products to company
MATCH (c:Company {id: 'workday'})
MATCH (p:Product)
WHERE p.id STARTS WITH 'workday-'
MERGE (c)-[:OWNS]->(p);

// -----------------------------------------------------------------------------
// SEED DATA: AI/ML Capabilities
// -----------------------------------------------------------------------------

MERGE (cap:Capability {id: 'ai'})
ON CREATE SET
    cap.name = 'Artificial Intelligence',
    cap.normalized_name = 'artificial intelligence',
    cap.category = 'artificial_intelligence',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'ml'})
ON CREATE SET
    cap.name = 'Machine Learning',
    cap.normalized_name = 'machine learning',
    cap.category = 'machine_learning',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'nlp'})
ON CREATE SET
    cap.name = 'Natural Language Processing',
    cap.normalized_name = 'natural language processing',
    cap.category = 'artificial_intelligence',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'predictive-analytics'})
ON CREATE SET
    cap.name = 'Predictive Analytics',
    cap.normalized_name = 'predictive analytics',
    cap.category = 'analytics',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'automation'})
ON CREATE SET
    cap.name = 'Automation',
    cap.normalized_name = 'automation',
    cap.category = 'automation',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'chatbot'})
ON CREATE SET
    cap.name = 'Chatbot',
    cap.normalized_name = 'chatbot',
    cap.category = 'artificial_intelligence',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'generative-ai'})
ON CREATE SET
    cap.name = 'Generative AI',
    cap.normalized_name = 'generative ai',
    cap.category = 'artificial_intelligence',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'llm'})
ON CREATE SET
    cap.name = 'Large Language Model',
    cap.normalized_name = 'large language model',
    cap.category = 'artificial_intelligence',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'deep-learning'})
ON CREATE SET
    cap.name = 'Deep Learning',
    cap.normalized_name = 'deep learning',
    cap.category = 'machine_learning',
    cap.created_at = timestamp();

MERGE (cap:Capability {id: 'cloud-computing'})
ON CREATE SET
    cap.name = 'Cloud Computing',
    cap.normalized_name = 'cloud computing',
    cap.category = 'cloud',
    cap.created_at = timestamp();

// -----------------------------------------------------------------------------
// SEED DATA: Risk Topics
// -----------------------------------------------------------------------------

MERGE (r:RiskTopic {id: 'cybersecurity-risk'})
ON CREATE SET
    r.name = 'Cybersecurity Risk',
    r.normalized_name = 'cybersecurity risk',
    r.category = 'cybersecurity',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'data-breach'})
ON CREATE SET
    r.name = 'Data Breach',
    r.normalized_name = 'data breach',
    r.category = 'cybersecurity',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'regulatory-compliance'})
ON CREATE SET
    r.name = 'Regulatory Compliance',
    r.normalized_name = 'regulatory compliance',
    r.category = 'regulatory',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'competition-risk'})
ON CREATE SET
    r.name = 'Competition Risk',
    r.normalized_name = 'competition risk',
    r.category = 'competition',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'technology-disruption'})
ON CREATE SET
    r.name = 'Technology Disruption',
    r.normalized_name = 'technology disruption',
    r.category = 'technology',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'talent-retention'})
ON CREATE SET
    r.name = 'Talent Retention',
    r.normalized_name = 'talent retention',
    r.category = 'talent',
    r.created_at = timestamp();

MERGE (r:RiskTopic {id: 'ai-ethics'})
ON CREATE SET
    r.name = 'AI Ethics and Bias',
    r.normalized_name = 'ai ethics',
    r.category = 'technology',
    r.created_at = timestamp();

// -----------------------------------------------------------------------------
// EXAMPLE QUERIES
// -----------------------------------------------------------------------------

// Get all AI capability mentions over time:
// MATCH (d:Document)-[r:MENTIONS]->(cap:Capability)
// WHERE cap.category = 'artificial_intelligence'
// RETURN d.publish_date, cap.name, r.evidence_text
// ORDER BY d.publish_date;

// Count mentions by quarter:
// MATCH (d:Document)-[:MENTIONS]->(cap:Capability)
// WHERE d.publish_date IS NOT NULL
// RETURN cap.name,
//        d.publish_date.year as year,
//        (d.publish_date.month - 1) / 3 + 1 as quarter,
//        count(*) as mentions
// ORDER BY year, quarter;

// Get risk disclosure trends:
// MATCH (d:Document)-[r:DISCLOSES]->(risk:RiskTopic)
// RETURN d.publish_date.year as year, risk.category, count(*) as disclosures
// ORDER BY year, risk.category;

// Find documents mentioning both AI and a specific product:
// MATCH (d:Document)-[:MENTIONS]->(cap:Capability {id: 'ai'})
// MATCH (d)-[:MENTIONS]->(p:Product {id: 'workday-hcm'})
// RETURN d.title, d.publish_date;

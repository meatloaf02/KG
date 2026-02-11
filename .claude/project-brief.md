# Project Brief: Workday AI Knowledge Graph

## Purpose
Academic, single-company case study modeling Workday, Inc.'s AI language evolution, product capabilities, and risk disclosures from 2015 to present. PostgreSQL + Memgraph backed. Emphasis on reproducibility and traceability.

## Linear Workspace
- **Team**: Northwestern | **Project**: Knowledge Graph | **Prefix**: NOR

---

## Architecture Overview

```
Seeds (CSV) → Ingest (PostgreSQL) → Process (text/dates) → KG (Memgraph) → Measures → Model
```

### Pipeline Stages
1. **Ingest** — Fetch public documents, store content-addressable files
2. **Process** — Extract text, dates, classify doc types, split sentences
3. **KG Load** — Create graph nodes/edges in Memgraph
4. **Measures** — Dictionary-based entity extraction + quarterly signal aggregation
5. **Model** — Predict next-quarter stock return direction (stub)

---

## Data Sources

### Databases

| Database   | Purpose              | Connection                                         |
|------------|----------------------|----------------------------------------------------|
| PostgreSQL | Raw document metadata | `postgresql://localhost:5432/workday_kg` (env: `WORKDAY_KG_DATABASE_URL`) |
| Memgraph   | Knowledge graph       | `bolt://localhost:7688` (env: `WORKDAY_KG_MEMGRAPH_HOST/PORT`) |

Docker Compose exposes Memgraph on host port **7688** (container 7687) and Lab UI on **7445**.

### Seed URL Sources (`data_manifests/seeds/`)

| File                   | Content                        | Priority |
|------------------------|--------------------------------|----------|
| `sec_filings.csv`      | 10-K, 10-Q, 8-K filings       | High     |
| `transcripts.csv`      | Earnings call transcripts      | High     |
| `investor_relations.csv` | IR pages                     | Medium   |
| `press_releases.csv`   | Newsroom content               | Medium   |
| `blog.csv`             | Corporate blog posts           | Low      |
| `media.csv`            | Public news coverage           | Low      |

Allowed domains: sec.gov, investor.workday.com, newsroom.workday.com, blog.workday.com, seekingalpha.com, fool.com, reuters.com, techcrunch.com, venturebeat.com.

### Configuration (`config.yaml`)
- Ingestion window: 2015–2025
- Rate limit: 1 req/s per domain, 3 retries with exponential backoff
- User-Agent: `WorkdayKG-Academic-Research/1.0`
- All config keys overridable via `WORKDAY_KG_` prefixed env vars

---

## Knowledge Graph Schema (Memgraph)

### Entities

#### Document (12 fields)
| Field           | Type      | Notes                                |
|-----------------|-----------|--------------------------------------|
| `content_hash`  | string    | SHA-256, **primary key**, unique     |
| `url_hash`      | string    | Hash of source URL                   |
| `title`         | string    |                                      |
| `doc_type`      | string    | 10-K, 10-Q, 8-K, press_release, blog, earnings_call |
| `source_type`   | string    | sec_filing, investor_relations, blog, media |
| `publish_date`  | string    | ISO date (legacy)                    |
| `published_at`  | Date      | Native Memgraph Date (preferred)     |
| `source_url`    | string    |                                      |
| `created_at`    | timestamp |                                      |
| `updated_at`    | timestamp |                                      |

#### Company (4 fields)
| Field        | Type   | Notes                        |
|--------------|--------|------------------------------|
| `id`         | string | Primary key, unique          |
| `name`       | string | e.g. "Workday, Inc."        |
| `ticker`     | string | e.g. "WDAY"                 |
| `cik`        | string | SEC CIK: "0001327811"       |
| `created_at` | timestamp |                           |

Seed: single Company node for Workday.

#### Product (6 fields)
| Field             | Type      | Notes              |
|-------------------|-----------|---------------------|
| `id`              | string    | Primary key, unique |
| `name`            | string    |                     |
| `normalized_name` | string    | Lowercase           |
| `description`     | string    |                     |
| `first_seen`      | string    | ISO date, optional  |
| `created_at`      | timestamp |                     |
| `updated_at`      | timestamp |                     |

Seed products (8): workday-hcm, workday-financials, workday-planning, workday-payroll, workday-recruiting, workday-learning, workday-prism, workday-peakon.

#### Capability (6 fields)
| Field             | Type      | Notes                          |
|-------------------|-----------|--------------------------------|
| `id`              | string    | Primary key, unique            |
| `name`            | string    |                                |
| `normalized_name` | string    | Lowercase                      |
| `category`        | string    | artificial_intelligence, machine_learning, analytics, automation, cloud, security, integration, mobile, user_experience |
| `first_seen`      | string    | ISO date, optional             |
| `created_at`      | timestamp |                                |
| `updated_at`      | timestamp |                                |

Seed capabilities (10): ai, ml, nlp, predictive-analytics, automation, generative-ai, llm, deep-learning, conversational-ai, computer-vision.

#### RiskTopic (6 fields)
| Field             | Type      | Notes                          |
|-------------------|-----------|--------------------------------|
| `id`              | string    | Primary key, unique            |
| `name`            | string    |                                |
| `normalized_name` | string    | Lowercase                      |
| `category`        | string    | cybersecurity, regulatory, competition, technology, operational, financial, market, talent |
| `first_seen`      | string    | ISO date, optional             |
| `created_at`      | timestamp |                                |
| `updated_at`      | timestamp |                                |

Seed risk topics (5): cybersecurity-risk, data-breach, regulatory-compliance, competition-risk, ai-ethics.

#### Event (6 fields)
| Field        | Type      | Notes                          |
|--------------|-----------|--------------------------------|
| `id`         | string    | Primary key, unique            |
| `name`       | string    |                                |
| `event_type` | string    | earnings_call, product_launch, acquisition, partnership, leadership_change, conference, regulatory_filing |
| `event_date` | string    | ISO date, optional             |
| `description`| string    |                                |
| `created_at` | timestamp |                                |
| `updated_at` | timestamp |                                |

### Relationships

#### MENTIONS (Document → Product | Capability)
| Property            | Type     | Notes                       |
|---------------------|----------|-----------------------------|
| `evidence_text`     | string   | Exact text span             |
| `sentence_id`       | string   | Stable sentence identifier  |
| `start_char`        | int      | Start offset in document    |
| `end_char`          | int      | End offset                  |
| `confidence`        | float    | 0–1                         |
| `extracted_at`      | datetime | ISO format                  |
| `extractor_version` | string   | Algorithm version           |

#### DISCLOSES (Document → RiskTopic)
Same properties as MENTIONS.

#### ANNOUNCES (Document → Event | Capability)
Same properties as MENTIONS.

#### HAS_CAPABILITY (Product → Capability)
| Property     | Type      |
|--------------|-----------|
| `first_seen` | string    |
| `created_at` | timestamp |

#### OWNS (Company → Product)
| Property     | Type      |
|--------------|-----------|
| `created_at` | timestamp |

---

## Measures & Signals

### Entity Extraction (`measures/extractor.py`)
- Dictionary-based matching from lexicons (`measures/lexicons.py`)
- Regex with word boundaries, case-insensitive, greedy longest-match
- Deduplication by span overlap
- Four lexicon categories: AI capabilities (120+ surface forms), products (50+), risks (80+), events (50+)

### Quarterly Aggregation (`measures/quarterly.py`)
Output: `data/processed/quarterly_signals.csv`

**Raw counts per quarter**: document_count, sec_filing_count, press_release_count, blog_count, capability_mention_count, product_mention_count, risk_mention_count, event_mention_count, unique_capabilities/products/risks/events, entity-level breakdowns.

**Derived signals**:
| Signal             | Formula                              |
|--------------------|--------------------------------------|
| `ai_intensity`     | capability_mentions / document_count |
| `product_coverage` | product_mentions / document_count    |
| `risk_density`     | risk_mentions / document_count       |
| `event_density`    | event_mentions / document_count      |

---

## Ingest Layer (PostgreSQL)

### `raw_documents` Table
| Column                | Type          | Notes                    |
|-----------------------|---------------|--------------------------|
| `id`                  | Integer       | PK, auto-increment       |
| `url`                 | String(2048)  |                          |
| `url_hash`            | String(16)    | Unique, indexed          |
| `normalized_url`      | String(2048)  |                          |
| `domain`              | String(255)   | Indexed                  |
| `source_type`         | String(50)    | Indexed                  |
| `fetched_at`          | DateTime      |                          |
| `status`              | Enum          | PENDING, SUCCESS, FAILED, SKIPPED |
| `http_status_code`    | Integer       |                          |
| `error_message`       | Text          |                          |
| `content_hash`        | String(64)    | Indexed                  |
| `content_type`        | String(100)   |                          |
| `content_size`        | Integer       |                          |
| `file_path`           | String(512)   |                          |
| `title`               | Text          |                          |
| `sec_accession_number`| String(25)    | Indexed                  |
| `created_at`          | DateTime      |                          |
| `updated_at`          | DateTime      |                          |

Content stored in `data/external/{html,pdf}/{hash_prefix}/` (content-addressable).

---

## Process Layer

### ProcessedDocument Output
Stored in `data/interim/{hash_prefix}/`:
- `{hash}.json` — full processing result
- `{hash}.txt` — clean text
- `{hash}.sentences.jsonl` — one sentence per line

Key fields: content_hash, title, text, char_count, word_count, doc_type, doc_type_confidence, publish_date, date_confidence, date_source, sentence_count, processor_version.

---

## Predictive Model (Stub — NOR-111)

- **Target**: Next-quarter stock return direction (up/down)
- **Train**: 2015–2019 | **Validation**: 2020–2021 | **Test**: 2022–present
- **Features**: Quarterly signals with lagged features
- **Approach**: Interpretable models (logistic regression, decision trees)
- **Constraint**: Chronological splits, lagged features only (no leakage)

---

## Key Files Reference

| Area       | File                         | Purpose                          |
|------------|------------------------------|----------------------------------|
| Config     | `config.yaml`                | All project configuration        |
| Config     | `config.py`                  | Python config loader + env vars  |
| Config     | `docker-compose.yml`         | Memgraph + PostgreSQL containers |
| Schema     | `kg/schema.cypher`           | Raw Cypher DDL                   |
| Schema     | `kg/schema.py`               | Python schema definitions        |
| Loaders    | `kg/loaders.py`              | Idempotent entity/rel loaders    |
| Loaders    | `kg/load_documents.py`       | Batch document loader            |
| Connection | `kg/connection.py`           | Memgraph driver management       |
| Ingest     | `ingest/models.py`           | SQLAlchemy ORM (raw_documents)   |
| Ingest     | `ingest/seeds.py`            | CSV seed loader                  |
| Ingest     | `ingest/fetcher.py`          | HTTP fetcher + retries           |
| Process    | `process/main.py`            | Processing pipeline orchestrator |
| Process    | `process/storage.py`         | Processed doc storage            |
| Measures   | `measures/lexicons.py`       | Entity surface-form dictionaries |
| Measures   | `measures/extractor.py`      | Dictionary-based extraction      |
| Measures   | `measures/quarterly.py`      | Quarterly signal aggregation     |
| Model      | `model/main.py`              | Predictive model (stub)          |

---

## Commands

```bash
make setup          # Environment setup
make ingest         # Data collection
make build-db       # Create Memgraph schema
make transform      # Process documents
make signals        # Compute quarterly signals
make train          # Train predictive model

# Granular
python3 -m ingest.run --init-db
python3 -m ingest.run --seeds all
python3 -m ingest.run --stats
python3 -m process.main [--limit N] [--dry-run] [--stats]
python3 -m measures.run_extraction [--dry-run] [--stats]
python3 -m measures.quarterly [--output PATH]
```

# Modeling the Evolution of AI Language, Capabilities, and Risk in Workday, Inc. (2015–Present)

## 1. Project Overview
This project implements a **fully reproducible, PostgreSQL-backed knowledge graph (KG)** modeling **Workday, Inc.** as a **single-company case study** in the Information Technology (IT) sector.

The knowledge base focuses on the **evolution of AI-related language, product capabilities, market positioning, and risk disclosures** across **publicly available documents** from **2015 to the present**. From this KG, the project derives **quantitative signals** and evaluates a **leakage-safe baseline predictive model**.

The project is designed as a **term-long academic project** and emphasizes:
- Clear scope boundaries
- Public-only, compliant data collection
- Reproducibility
- Traceability from structured data back to source evidence

---

## Linear Workspace
-	**Team**: Northwestern
-	**Project**: Knowledge Graph
-	**Issue Prefix**: NOR

## Development Workflow
1. Issues start in 'Backlog'
2. Move to 'In Progress' when work begins
3. Move to 'Done' when done

---

## 2. Scope & Definition of Done (DoD)

### In Scope
- **Company:** Workday, Inc. only
- **Time range:** 2015 → present
- **Sources:** Publicly accessible documents only
- **Outputs:** Knowledge graph, derived signals, baseline predictive model

### Out of Scope
- Paywalled or credentialed sources
- Multi-company comparisons
- High-frequency or real-time trading systems
- Proprietary or licensed datasets

---

### Operational Definition of Done

This project is considered **complete** when **all** of the following conditions are met:

#### Knowledge Base
- Models **Workday, Inc.** as a single-company case study
- Captures AI-related language, product/capability evolution, market positioning, and risk disclosures
- Stores structured data in **PostgreSQL** using a documented KG-style schema
- Every extracted entity and relationship includes:
  - Source document reference
  - Evidence span (text excerpt)
  - Timestamp
  - Extraction provenance

#### Data
- All sources are **public-only** and compliant with terms of service
- Raw documents (HTML/PDF/text) are **not committed** to GitHub
- Reproducibility is ensured via:
  - URL seed lists
  - Fetch timestamps
  - Content hashes
  - Deterministic transformation pipelines

#### Signals / Measures
- At least **four quantitative signals**, including:
  - AI-language intensity over time
  - Product or capability mention trends
  - Risk disclosure density
  - One analyst/media-derived proxy signal

#### Modeling
- One **leakage-safe baseline predictive model**
- Time-indexed features with explicit lagging
- Chronological train/validation/test splits
- Interpretable outputs (coefficients or feature importance)

#### Reproducibility
- A fresh clone of the repository can recreate:
  - Database schema
  - Transformed KG tables
  - Signal tables
  - Model training and evaluation
- Execution is driven by scripted commands (e.g., `make`)

#### Output
- One primary **Jupyter notebook** that:
  - Demonstrates KG coverage
  - Visualizes signals
  - Runs example KG queries
  - Presents model results and interpretation

---

## 3. Data Sources (Public-Only Policy)

### Allowed Sources
- SEC filings (10-K, 10-Q, 8-K)
- Earnings call transcripts published publicly
- Investor relations web pages
- Press releases
- Corporate blogs and announcements
- Public news and media articles

### Disallowed Sources
- Paywalled analyst reports or PDFs
- Login-protected or credentialed portals
- APIs with restrictive or incompatible terms of service

All ingestion respects `robots.txt`, rate limits, and site terms of service.

---

## 4. Knowledge Graph Design

### Core Entities
- Company
- Document
- Product
- Technology Capability
- Event
- Risk Topic

### Core Relationships
- `MENTIONS` (Document → Product / Capability)
- `DISCLOSES` (Document → Risk Topic)
- `ANNOUNCES` (Document → Event / Capability)
- `ASSOCIATED_WITH` (Product ↔ Capability)

Each relationship stores:
- Source document ID
- Evidence text span
- Extraction confidence (where applicable)
- Timestamp

---

## 5. Data Pipeline Overview

1. URL seeding and ingestion (public-only)
2. Text extraction from HTML and PDF
3. Document classification and metadata extraction
4. Sentence segmentation
5. Entity and signal extraction
6. Loading into PostgreSQL KG schema
7. Quarterly signal aggregation
8. Feature engineering with time lags
9. Predictive modeling and evaluation

Raw source documents are treated as **ephemeral** and are excluded from version control.

---

## 6. Ground Truth & Validation Strategy

Given project constraints, evaluation focuses on **precision-oriented validation** using a thin gold set.

- Approximately **50 documents** are sampled
- ~**500 sentences** are manually labeled for:
  - AI-related language
  - Risk-related language
  - Product or capability mentions

Evaluation emphasizes:
- Extraction precision
- Qualitative error analysis
- Documented limitations

This approach provides defensible quality assurance without requiring full-scale annotation.

---

## 7. Measures & Signals

Signals are aggregated at a **quarterly** level and include:
- AI-language intensity trends
- Product and capability mention frequency
- Risk disclosure density
- Event frequency and intensity

All signals are time-indexed and derived exclusively from documents available **prior** to the aggregation period.

---

## 8. Predictive Modeling (Leakage-Safe)

- **Target:** Next-quarter stock return direction (up/down)
- **Feature windows:** Lagged historical signals only
- **Splits:** Chronological (no random splits)
  - Train: 2015–2019
  - Validation: 2020–2021
  - Test: 2022–present

Strict safeguards are implemented to prevent:
- Look-ahead bias
- Timestamp leakage
- Use of post-target documents

Models prioritize interpretability over complexity.

---

## 9. Reproducibility

### Included in GitHub
- Ingestion and parsing code
- KG schema and migrations
- Transformation and aggregation logic
- Feature engineering scripts
- Modeling and evaluation scripts

### Excluded from GitHub
- Raw HTML/PDF documents
- Full extracted text corpora
- Large derived tables

### Example Execution
```bash
make setup
make ingest
make build-db
make transform
make signals
make train
```

---

## 10. Demo Notebook

Primary output:
```
notebooks/01_demo.ipynb
```

The notebook demonstrates:
- Knowledge graph coverage
- Signal trends over time
- Example KG queries
- Model performance and interpretation

---

## 11. Risk Register & Compliance

| Risk | Category | Mitigation |
|----|----|----|
| robots.txt violations | Legal | Respect robots.txt and domain allowlists |
| Rate limiting | Technical | Throttling, retries, and backoff |
| Paywalled content ingestion | Legal | Public-only source policy |
| Document availability drift | Reproducibility | Hashes and timestamps recorded |
| Document misclassification | Data Quality | Rule-based fallbacks and audits |
| LLM hallucination | Modeling | Extractive prompts with evidence spans |
| Temporal leakage | Modeling | Lagged features and as-of joins |
| Model overfitting | Scientific | Simple baselines and held-out test set |
| Storage limits | Infrastructure | Exclude raw data from Git |
| Evaluation bias | Scientific | Manual audit set and transparent reporting |

---

## 12. Repository Structure

```text
.
├── ingest/
├── process/
├── kg/
├── measures/
├── model/
├── notebooks/
├── data_manifests/
├── docs/
└── README.md
```

---

## 13. License & Usage

This repository is intended for **academic, non-commercial use only**.


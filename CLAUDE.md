# Workday AI Knowledge Graph - Project Context

## Overview
PostgreSQL-backed knowledge graph modeling Workday, Inc.'s AI language evolution, product capabilities, and risk disclosures from 2015 to present. Academic, single-company case study emphasizing reproducibility and traceability.

## Linear Workspace
- **Team**: Northwestern
- **Project**: Knowledge Graph
- **Issue Prefix**: NOR
- **Workflow**: Backlog → In Progress → Done

## Key Constraints
- **Public data only** - No paywalled/credentialed sources
- **No raw documents in git** - Store URL seeds, hashes, timestamps instead
- **Leakage-safe modeling** - Chronological splits, lagged features only
- **Respect robots.txt** and rate limits

## Allowed Data Sources
- SEC filings (10-K, 10-Q, 8-K)
- Public earnings call transcripts
- Investor relations pages
- Press releases
- Corporate blogs
- Public news/media

## Knowledge Graph Schema

### Entities
- Company, Document, Product, Technology Capability, Event, Risk Topic

### Relationships
- `MENTIONS` (Document → Product/Capability)
- `DISCLOSES` (Document → Risk Topic)
- `ANNOUNCES` (Document → Event/Capability)
- `ASSOCIATED_WITH` (Product ↔ Capability)

Each relationship requires: source doc ID, evidence text span, timestamp, extraction provenance

## Signals (Quarterly)
1. AI-language intensity over time
2. Product/capability mention trends
3. Risk disclosure density
4. Analyst/media-derived proxy signal

## Predictive Model
- **Target**: Next-quarter stock return direction (up/down)
- **Train**: 2015-2019, **Validation**: 2020-2021, **Test**: 2022-present
- Interpretable models preferred

## Repository Structure
```
ingest/      # Data collection
process/     # Text extraction, parsing
kg/          # Schema, migrations
measures/    # Signal computation
model/       # Predictive modeling
notebooks/   # Demo notebook (01_demo.ipynb)
data_manifests/  # URL seeds, hashes
docs/        # Documentation
```

## Commands
```bash
make setup     # Environment setup
make ingest    # Data collection
make build-db  # Create schema
make transform # Process data
make signals   # Compute signals
make train     # Train model
```

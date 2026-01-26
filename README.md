# Workday AI Knowledge Graph

A PostgreSQL-backed knowledge graph modeling the evolution of AI language, capabilities, and risk disclosures in Workday, Inc. (2015–Present).

## Quick Start

```bash
# Setup environment
make setup
source .venv/bin/activate

# Run pipeline
make ingest      # Collect public data
make build-db    # Create schema
make transform   # Process and load data
make signals     # Compute signals
make train       # Train model
```

## Project Structure

```
├── ingest/          # Data collection from public sources
├── process/         # Text extraction and parsing
├── kg/              # Knowledge graph schema and operations
├── measures/        # Signal computation
├── model/           # Predictive modeling
├── notebooks/       # Analysis and demo notebooks
├── data_manifests/  # URL seeds, hashes, timestamps
└── docs/            # Documentation
```

## Documentation

See [workday_ai_knowledge_graph_readme.md](workday_ai_knowledge_graph_readme.md) for full project specification.

## License

Academic, non-commercial use only.

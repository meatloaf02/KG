.PHONY: setup ingest ingest-media init-ingest-db ingest-stats ingest-manifest build-db transform signals aii train clean test lint format hooks help

# Default target
help:
	@echo "Workday AI Knowledge Graph - Available Commands"
	@echo "================================================"
	@echo "make setup      - Set up Python environment and install dependencies"
	@echo "make ingest     - Collect data from public sources"
	@echo "make ingest-media - One-shot external media crawl (see YAML spec)"
	@echo "make build-db   - Create PostgreSQL schema and tables"
	@echo "make transform  - Process raw data and load into KG"
	@echo "make signals    - Compute quarterly signals"
	@echo "make aii        - Compute AI Intensity Index (AII)"
	@echo "make train      - Train predictive model"
	@echo "make test       - Run test suite"
	@echo "make lint       - Check code style with ruff"
	@echo "make format     - Format code with ruff"
	@echo "make hooks      - Install pre-commit hooks"
	@echo "make clean      - Remove generated files"

# Environment setup
setup:
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
	. .venv/bin/activate && pip install -r requirements.txt
	@echo "Environment setup complete. Activate with: source .venv/bin/activate"

# Data ingestion
ingest:
	@echo "Starting data ingestion..."
	python -m ingest.run --seeds all

# External media crawl
ingest-media:  ## One-shot external media crawl (see YAML spec)
	$(VENV)/python3 -m ingest.run_media \
	  --seeds data_manifests/seeds/external_media.csv \
	  --limit $(or $(LIMIT),20000)

# Initialize ingestion database
init-ingest-db:
	@echo "Initializing ingestion database..."
	python -m ingest.run --init-db

# Show ingestion statistics
ingest-stats:
	python -m ingest.run --stats

# Export document manifest
ingest-manifest:
	python -m ingest.run --export-manifest

# Database setup
build-db:
	@echo "Building database schema..."
	python -m kg.schema

# Data transformation
transform:
	@echo "Transforming and loading data..."
	python -m process.main

# Signal computation
signals:
	@echo "Computing signals..."
	python -m measures.main

# AII (AI Intensity Index)
aii:
	@echo "Computing AII..."
	python3 -m measures.run_aii

# Model training
train:
	@echo "Training model..."
	python -m model.main

# Run tests
test:
	pytest tests/ -v

# Lint code
lint:
	ruff check .

# Format code
format:
	ruff format .
	ruff check --fix .

# Install pre-commit hooks
hooks:
	pre-commit install

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned generated files"

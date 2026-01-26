.PHONY: setup ingest build-db transform signals train clean test help

# Default target
help:
	@echo "Workday AI Knowledge Graph - Available Commands"
	@echo "================================================"
	@echo "make setup      - Set up Python environment and install dependencies"
	@echo "make ingest     - Collect data from public sources"
	@echo "make build-db   - Create PostgreSQL schema and tables"
	@echo "make transform  - Process raw data and load into KG"
	@echo "make signals    - Compute quarterly signals"
	@echo "make train      - Train predictive model"
	@echo "make test       - Run test suite"
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
	python -m ingest.main

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

# Model training
train:
	@echo "Training model..."
	python -m model.main

# Run tests
test:
	pytest tests/ -v

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned generated files"

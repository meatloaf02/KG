"""
Project configuration.
"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/workday_kg")

# Data directories (ephemeral, not in git)
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Manifests (tracked in git)
MANIFESTS_DIR = PROJECT_ROOT / "data_manifests"

# Time range
START_YEAR = 2015
END_YEAR = 2025

# Model splits
TRAIN_END = 2019
VALIDATION_END = 2021

# Rate limiting
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3

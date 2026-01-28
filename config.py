"""
Project configuration with YAML loading and environment variable overrides.

Configuration precedence (highest to lowest):
1. Environment variables (prefixed with WORKDAY_KG_)
2. config.yaml
3. Default values
"""

import logging
import os
from pathlib import Path

import yaml

# Project root
PROJECT_ROOT = Path(__file__).parent

# Load YAML configuration
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


def _load_yaml_config() -> dict:
    """Load configuration from YAML file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_config(yaml_path: str, env_var: str, default, cast_type=str):
    """
    Get configuration value with precedence: env > yaml > default.

    Args:
        yaml_path: Dot-separated path in YAML (e.g., 'database.url')
        env_var: Environment variable name
        default: Default value if not found
        cast_type: Type to cast the value to
    """
    # Check environment variable first
    env_value = os.getenv(env_var)
    if env_value is not None:
        if cast_type == bool:
            return env_value.lower() in ("true", "1", "yes")
        return cast_type(env_value)

    # Check YAML config
    config = _load_yaml_config()
    keys = yaml_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return cast_type(value) if value is not None else default


# Database
DATABASE_URL = _get_config(
    "database.url", "WORKDAY_KG_DATABASE_URL", "postgresql://localhost:5432/workday_kg"
)

# Data directories (ephemeral, not in git)
DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
EXTERNAL_HTML_DIR = EXTERNAL_DATA_DIR / "html"
EXTERNAL_PDF_DIR = EXTERNAL_DATA_DIR / "pdf"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Manifests (tracked in git)
MANIFESTS_DIR = PROJECT_ROOT / "data_manifests"

# Time range
START_YEAR = _get_config("ingestion.start_year", "WORKDAY_KG_START_YEAR", 2015, int)
END_YEAR = _get_config("ingestion.end_year", "WORKDAY_KG_END_YEAR", 2025, int)

# Rate limiting
REQUEST_DELAY_SECONDS = _get_config(
    "ingestion.request_delay_seconds", "WORKDAY_KG_REQUEST_DELAY", 1.0, float
)
MAX_RETRIES = _get_config("ingestion.max_retries", "WORKDAY_KG_MAX_RETRIES", 3, int)
USER_AGENT = _get_config(
    "ingestion.user_agent",
    "WORKDAY_KG_USER_AGENT",
    "WorkdayKG-Academic-Research/1.0",
)

# Model splits
TRAIN_END = _get_config("modeling.train_end_year", "WORKDAY_KG_TRAIN_END", 2019, int)
VALIDATION_END = _get_config(
    "modeling.validation_end_year", "WORKDAY_KG_VALIDATION_END", 2021, int
)
RANDOM_SEED = _get_config("modeling.random_seed", "WORKDAY_KG_RANDOM_SEED", 42, int)

# Logging configuration
LOG_LEVEL = _get_config("logging.level", "WORKDAY_KG_LOG_LEVEL", "INFO")
LOG_FORMAT = _get_config(
    "logging.format",
    "WORKDAY_KG_LOG_FORMAT",
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
LOG_DATE_FORMAT = _get_config(
    "logging.date_format", "WORKDAY_KG_LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"
)


def setup_logging(name: str = None) -> logging.Logger:
    """
    Configure and return a logger.

    Args:
        name: Logger name (defaults to root logger)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger


def ensure_directories():
    """Create necessary data directories if they don't exist."""
    for dir_path in [
        DATA_DIR,
        EXTERNAL_DATA_DIR,
        EXTERNAL_HTML_DIR,
        EXTERNAL_PDF_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
        MANIFESTS_DIR,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

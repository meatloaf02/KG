"""
Seed URL loading from CSV manifest files.

Loads URL seeds from data_manifests/seeds/ directory for ingestion.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import MANIFESTS_DIR, setup_logging

logger = setup_logging(__name__)

SEEDS_DIR = MANIFESTS_DIR / "seeds"


@dataclass
class SeedURL:
    """A URL seed with metadata."""

    url: str
    source_type: str
    priority: str
    notes: str = ""
    # Optional fields that vary by seed file
    filing_type: Optional[str] = None
    fiscal_year: Optional[str] = None
    fiscal_quarter: Optional[str] = None
    content_type: Optional[str] = None

    @property
    def priority_rank(self) -> int:
        """Get numeric priority for sorting (lower is higher priority)."""
        priority_map = {"high": 1, "medium": 2, "low": 3}
        return priority_map.get(self.priority.lower(), 4)


def load_seed_file(file_path: Path) -> list[SeedURL]:
    """
    Load seed URLs from a CSV file.

    Args:
        file_path: Path to CSV seed file

    Returns:
        List of SeedURL objects
    """
    seeds = []

    if not file_path.exists():
        logger.warning(f"Seed file not found: {file_path}")
        return seeds

    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Handle empty or whitespace-only URLs
                url = row.get("url", "").strip()
                if not url:
                    continue

                seed = SeedURL(
                    url=url,
                    source_type=row.get("source_type", "").strip(),
                    priority=row.get("priority", "medium").strip(),
                    notes=row.get("notes", "").strip(),
                    filing_type=row.get("filing_type", "").strip() or None,
                    fiscal_year=row.get("fiscal_year", "").strip() or None,
                    fiscal_quarter=row.get("fiscal_quarter", "").strip() or None,
                    content_type=row.get("content_type", "").strip() or None,
                )
                seeds.append(seed)

        logger.info(f"Loaded {len(seeds)} seeds from {file_path.name}")

    except csv.Error as e:
        logger.error(f"Error reading seed file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {e}")

    return seeds


def load_all_seeds(
    priority_filter: Optional[str] = None,
    source_type_filter: Optional[str] = None,
) -> list[SeedURL]:
    """
    Load seeds from all seed files in data_manifests/seeds/.

    Args:
        priority_filter: Filter by priority ('high', 'medium', 'low')
        source_type_filter: Filter by source type (e.g., 'sec_filing')

    Returns:
        List of SeedURL objects sorted by priority
    """
    all_seeds = []

    if not SEEDS_DIR.exists():
        logger.warning(f"Seeds directory not found: {SEEDS_DIR}")
        return all_seeds

    # Load from all CSV files
    for csv_file in sorted(SEEDS_DIR.glob("*.csv")):
        seeds = load_seed_file(csv_file)
        all_seeds.extend(seeds)

    # Apply filters
    if priority_filter:
        priority_filter = priority_filter.lower()
        all_seeds = [s for s in all_seeds if s.priority.lower() == priority_filter]

    if source_type_filter:
        source_type_filter = source_type_filter.lower()
        all_seeds = [s for s in all_seeds if s.source_type.lower() == source_type_filter]

    # Sort by priority
    all_seeds.sort(key=lambda s: s.priority_rank)

    logger.info(
        f"Loaded {len(all_seeds)} total seeds "
        f"(priority={priority_filter or 'all'}, source={source_type_filter or 'all'})"
    )

    return all_seeds


def load_seeds_by_file(filename: str) -> list[SeedURL]:
    """
    Load seeds from a specific seed file by name.

    Args:
        filename: Name of seed file (with or without .csv extension)

    Returns:
        List of SeedURL objects
    """
    if not filename.endswith(".csv"):
        filename = f"{filename}.csv"

    file_path = SEEDS_DIR / filename
    return load_seed_file(file_path)


def list_seed_files() -> list[str]:
    """
    List available seed files.

    Returns:
        List of seed file names (without .csv extension)
    """
    if not SEEDS_DIR.exists():
        return []

    return [f.stem for f in sorted(SEEDS_DIR.glob("*.csv"))]


def get_seed_stats() -> dict:
    """
    Get statistics about available seeds.

    Returns:
        Dictionary with counts by file and source type
    """
    stats = {
        "by_file": {},
        "by_source_type": {},
        "by_priority": {},
        "total": 0,
    }

    for csv_file in sorted(SEEDS_DIR.glob("*.csv")):
        seeds = load_seed_file(csv_file)
        stats["by_file"][csv_file.stem] = len(seeds)
        stats["total"] += len(seeds)

        for seed in seeds:
            source = seed.source_type or "unknown"
            priority = seed.priority.lower()

            stats["by_source_type"][source] = stats["by_source_type"].get(source, 0) + 1
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

    return stats

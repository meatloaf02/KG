"""
AI Density per Document (NOR-XXX).

Computes AI Density = (Capability MENTIONS / Total Tokens) × 10,000
for each canonical_v1 document and exports results to CSV + plots.

- Total Tokens = char_count / 4 (standard approximation)
- AI Mentions  = count of distinct MENTIONS relationships to Capability nodes
- Documents with zero MENTIONS get density = 0

Usage:
    python -m measures.ai_density
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import INTERIM_DATA_DIR, PROCESSED_DATA_DIR, setup_logging
from kg.connection import execute_query, get_driver

logger = setup_logging(__name__)


# ---------------------------------------------------------------------------
# Step 1: Load canonical_v1 docs from interim JSONs
# ---------------------------------------------------------------------------

def load_eligible_docs() -> list[dict]:
    """
    Glob all interim JSONs and return analysis_eligible documents.

    Returns list of dicts with keys:
        content_hash, char_count, doc_type, publish_date, source_url
    """
    docs = []
    json_files = list(INTERIM_DATA_DIR.rglob("*.json"))
    logger.info(f"Scanning {len(json_files)} interim JSON files...")

    for path in json_files:
        try:
            with open(path, encoding="utf-8") as f:
                record = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping {path}: {e}")
            continue

        if not record.get("analysis_eligible", False):
            continue

        char_count = record.get("char_count", 0) or 0
        docs.append({
            "content_hash": record["content_hash"],
            "char_count": char_count,
            "total_tokens": char_count / 4,
            "doc_type": record.get("doc_type", "unknown"),
            "publish_date": record.get("publish_date", ""),
            "source_url": record.get("source_url", ""),
        })

    logger.info(f"Found {len(docs)} analysis-eligible documents")
    return docs


# ---------------------------------------------------------------------------
# Step 2: Query Memgraph for MENTIONS counts per document
# ---------------------------------------------------------------------------

MENTIONS_QUERY = """
MATCH (doc:Document)
WHERE doc.analysis_eligible = true
OPTIONAL MATCH (doc)-[:MENTIONS]->(c:Capability)
RETURN doc.content_hash AS content_hash, count(c) AS ai_mentions
"""


def fetch_mentions(driver=None) -> dict[str, int]:
    """
    Query Memgraph for capability mention counts per document.

    Returns dict mapping content_hash -> ai_mentions count (0 for no mentions).
    """
    logger.info("Querying Memgraph for MENTIONS counts...")
    results = execute_query(MENTIONS_QUERY, driver=driver)
    mentions = {r["content_hash"]: r["ai_mentions"] for r in results}
    logger.info(f"Got mention counts for {len(mentions)} documents from Memgraph")
    return mentions


# ---------------------------------------------------------------------------
# Step 3: Join and compute AI Density
# ---------------------------------------------------------------------------

def compute_ai_density(docs: list[dict], mentions: dict[str, int]) -> list[dict]:
    """
    Join interim JSON records with Memgraph mention counts and compute density.

    Returns list of dicts with keys:
        doc_id, doc_type, publish_date, source_url, ai_density
    Sorted by publish_date ascending.
    """
    rows = []
    missing_from_graph = 0

    for doc in docs:
        h = doc["content_hash"]
        ai_mentions = mentions.get(h, 0)
        if h not in mentions:
            missing_from_graph += 1

        total_tokens = doc["total_tokens"]
        if total_tokens > 0:
            ai_density = round((ai_mentions / total_tokens) * 10_000, 6)
        else:
            ai_density = 0.0

        rows.append({
            "doc_id": h[:12],
            "doc_type": doc["doc_type"],
            "publish_date": doc["publish_date"],
            "source_url": doc["source_url"],
            "ai_density": ai_density,
            # Keep full hash for diagnostics (not written to CSV)
            "_content_hash": h,
            "_ai_mentions": ai_mentions,
        })

    if missing_from_graph:
        logger.warning(
            f"{missing_from_graph} documents found in interim JSONs but not in Memgraph "
            "(treating as 0 mentions)"
        )

    rows.sort(key=lambda r: r["publish_date"])
    return rows


# ---------------------------------------------------------------------------
# Step 4: Write CSV
# ---------------------------------------------------------------------------

CSV_COLUMNS = ["doc_id", "doc_type", "publish_date", "source_url", "ai_density"]


def write_csv(rows: list[dict], output_path: Path) -> None:
    """Write ai_density CSV to output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {len(rows)} rows to {output_path}")


# ---------------------------------------------------------------------------
# Step 5: Plot — 10-K AI Density by Year (bar chart)
# ---------------------------------------------------------------------------

def plot_10k(rows: list[dict], output_path: Path) -> None:
    """Bar chart: one bar per fiscal year for sec_10k documents."""
    subset = [r for r in rows if r["doc_type"] == "sec_10k"]
    if not subset:
        logger.warning("No sec_10k rows found; skipping 10-K plot")
        return

    # Aggregate by year (should be exactly 1 per FY, but average if not)
    by_year: dict[int, list[float]] = defaultdict(list)
    for r in subset:
        year = int(r["publish_date"][:4])
        by_year[year].append(r["ai_density"])

    years = sorted(by_year)
    densities = [sum(by_year[y]) / len(by_year[y]) for y in years]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(years, densities, color="steelblue", width=0.6)

    # Value labels above each bar
    for bar, val in zip(bars, densities):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(densities) * 0.01,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax.set_xlabel("Year")
    ax.set_ylabel("AI Density (mentions / 10k tokens)")
    ax.set_title("Workday 10-K AI Density by Year")
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=45)
    ax.set_ylim(0, max(densities) * 1.15 if densities else 1)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"Saved 10-K plot to {output_path}")


# ---------------------------------------------------------------------------
# Step 6: Plot — 10-Q AI Density by Year (scatter + mean line)
# ---------------------------------------------------------------------------

def plot_10q(rows: list[dict], output_path: Path) -> None:
    """Scatter + mean-per-year line: sec_10q documents."""
    subset = [r for r in rows if r["doc_type"] == "sec_10q"]
    if not subset:
        logger.warning("No sec_10q rows found; skipping 10-Q plot")
        return

    years_all = [int(r["publish_date"][:4]) for r in subset]
    densities_all = [r["ai_density"] for r in subset]

    # Mean per year
    by_year: dict[int, list[float]] = defaultdict(list)
    for y, d in zip(years_all, densities_all):
        by_year[y].append(d)
    years_sorted = sorted(by_year)
    means = [sum(by_year[y]) / len(by_year[y]) for y in years_sorted]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(years_all, densities_all, color="steelblue", alpha=0.6, zorder=3, label="Individual 10-Q")
    ax.plot(years_sorted, means, color="darkorange", linewidth=2, marker="o", label="Annual mean")

    ax.set_xlabel("Year")
    ax.set_ylabel("AI Density (mentions / 10k tokens)")
    ax.set_title("Workday 10-Q AI Density by Year")
    ax.set_xticks(years_sorted)
    ax.set_xticklabels([str(y) for y in years_sorted], rotation=45)
    ax.legend()

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"Saved 10-Q plot to {output_path}")


# ---------------------------------------------------------------------------
# Verification summary
# ---------------------------------------------------------------------------

def print_summary(rows: list[dict]) -> None:
    total = len(rows)
    non_zero = sum(1 for r in rows if r["ai_density"] > 0)
    by_type: dict[str, list] = defaultdict(list)
    for r in rows:
        by_type[r["doc_type"]].append(r["ai_density"])

    print("=" * 60)
    print("AI Density Summary")
    print("=" * 60)
    print(f"Total documents: {total}")
    print(f"Non-zero density: {non_zero}")
    print(f"Zero density:     {total - non_zero}")
    print()
    print(f"{'doc_type':<20} {'count':>6} {'mean_density':>14} {'max_density':>13}")
    print("-" * 60)
    for dt, vals in sorted(by_type.items()):
        mean_d = sum(vals) / len(vals)
        max_d = max(vals)
        print(f"{dt:<20} {len(vals):>6} {mean_d:>14.4f} {max_d:>13.4f}")
    print("=" * 60)

    # Spot-check: 10-K values
    ten_k = [r for r in rows if r["doc_type"] == "sec_10k"]
    print(f"\n10-K non-zero: {sum(1 for r in ten_k if r['ai_density'] > 0)}/{len(ten_k)}")

    # Spot-check: sample 8-Ks
    eight_k = [r for r in rows if r["doc_type"] == "sec_8k"][:5]
    if eight_k:
        zero_8k = sum(1 for r in eight_k if r["ai_density"] == 0)
        print(f"8-K sample (first 5) with density=0: {zero_8k}/5")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    driver = get_driver()

    # 1. Load eligible docs from interim JSONs
    docs = load_eligible_docs()

    # 2. Query Memgraph for MENTIONS counts
    mentions = fetch_mentions(driver=driver)

    # 3. Join and compute AI Density
    rows = compute_ai_density(docs, mentions)

    # 4. Write CSV
    csv_path = PROCESSED_DATA_DIR / "ai_density.csv"
    write_csv(rows, csv_path)

    # 5. Plot 10-K
    plots_dir = PROCESSED_DATA_DIR / "plots"
    plot_10k(rows, plots_dir / "ai_density_10k.png")

    # 6. Plot 10-Q
    plot_10q(rows, plots_dir / "ai_density_10q.png")

    # Verification summary
    print_summary(rows)

    print(f"\nCSV:      {csv_path}")
    print(f"Plots:    {plots_dir}/")


if __name__ == "__main__":
    main()

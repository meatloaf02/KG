"""
Crawl run report writer.

Writes crawl_run_report.json with all metrics specified in the YAML spec's
outputs.crawl_run_report.metrics section.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from config import setup_logging

logger = setup_logging(__name__)

if TYPE_CHECKING:
    from ingest.media.crawler import CrawlStats


def write_report(stats: "CrawlStats", out_path: Path) -> None:
    """
    Write a JSON crawl report to out_path.

    Computes derived rates from raw counts and includes a timestamp.
    """
    fetched_total = stats.fetched_total
    stored_total = stats.stored_docs_total

    dedup_exact_rate = (
        stats.exact_dup_total / fetched_total if fetched_total > 0 else 0.0
    )
    dedup_near_rate = (
        stats.near_dup_total / fetched_total if fetched_total > 0 else 0.0
    )
    publish_date_coverage_rate = (
        stats.publish_date_found / stored_total if stored_total > 0 else 0.0
    )
    workday_relevance_pass_rate = (
        stored_total / stats.fetched_success if stats.fetched_success > 0 else 0.0
    )
    ai_keyword_hit_rate = (
        stats.ai_keyword_hits / stored_total if stored_total > 0 else 0.0
    )

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "fetched_total": fetched_total,
        "fetched_success": stats.fetched_success,
        "fetched_failed": stats.fetched_failed,
        "dropped_paywalled_total": stats.dropped_paywalled_total,
        "dropped_out_of_window_total": stats.dropped_out_of_window_total,
        "dropped_not_relevant_total": stats.dropped_not_relevant_total,
        "dropped_not_english_total": stats.dropped_not_english_total,
        "stored_docs_total": stored_total,
        "stored_docs_by_domain": stats.stored_docs_by_domain,
        "exact_dup_total": stats.exact_dup_total,
        "near_dup_total": stats.near_dup_total,
        "dedup_exact_rate": round(dedup_exact_rate, 4),
        "dedup_near_rate": round(dedup_near_rate, 4),
        "publish_date_coverage_rate": round(publish_date_coverage_rate, 4),
        "workday_relevance_pass_rate": round(workday_relevance_pass_rate, 4),
        "ai_keyword_hit_rate": round(ai_keyword_hit_rate, 4),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    logger.info(f"Crawl report written to {out_path}")

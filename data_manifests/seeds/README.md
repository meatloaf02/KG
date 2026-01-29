# Seed URL Lists

This directory contains CSV files with seed URLs for data collection.

## Files

| File | Description | Source Count |
|------|-------------|--------------|
| `sec_filings.csv` | SEC EDGAR filing index URLs | 4 |
| `investor_relations.csv` | Workday IR pages | 7 |
| `press_releases.csv` | Newsroom and wire service URLs | 5 |
| `blog.csv` | Workday blog category pages | 7 |
| `transcripts.csv` | Earnings call transcript sources | 2 |
| `media.csv` | News and media coverage | 2 |

## CSV Schema

All seed files use a common base schema with optional columns:

### Required Columns
- `url`: Full URL to fetch
- `source_type`: One of: sec_filing, investor_relations, press_release, blog, earnings_transcript, news_media
- `priority`: high, medium, or low

### Optional Columns
- `content_type`: Specific content classification
- `fiscal_year`: For time-bound content
- `fiscal_quarter`: Q1, Q2, Q3, Q4
- `filing_type`: SEC filing type (10-K, 10-Q, 8-K, etc.)
- `category`: Blog or content category
- `notes`: Free-text notes

## Usage

The ingestion pipeline reads these files to:
1. Discover index/listing pages
2. Extract individual document URLs
3. Queue documents for fetching

## Adding New Seeds

1. Verify the domain is in the allowlist (`ingest/domains.py`)
2. Add URL to the appropriate CSV file
3. Set appropriate priority
4. Add notes explaining the source

## Compliance

All URLs must:
- Be publicly accessible (no login required)
- Respect robots.txt directives
- Be from allowed domains only

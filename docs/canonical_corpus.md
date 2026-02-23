# Canonical Analysis Corpus

## Definition

The canonical analysis corpus is the set of documents eligible for
signal computation, entity extraction, and predictive modeling. Each
document represents **one primary narrative filing per SEC filing event**
for Workday, Inc. (CIK 1327811) from fiscal Q4 2012 through Q4 2025.

Only documents with `analysis_eligible = true` in the processed JSON
files are included. Each eligible document is tagged with
`analysis_layer = 'canonical_v1'` to version the corpus definition.

## Inclusion Rules

A document is canonical when ALL of the following hold:

| Condition | Implementation |
|-----------|---------------|
| Correct filing type | `doc_type` is one of the four primary SEC types below |
| Correct sub-type | `doc_sub_type` matches the expected value for its type |
| Sufficient content | `char_count >= 100` (filters XBRL viewer shells) |
| Not an exhibit | `_is_exhibit_url()` returns `False` (filters SOX certs, press release exhibits, articles of incorporation) |
| Not an index page | URL does not contain `-index.htm` or `browse-edgar` |

### Eligible Filing Types

| doc_type | doc_sub_type | Description | Expected cadence |
|----------|-------------|-------------|------------------|
| `sec_10k` | `Annual Report` | Annual report on Form 10-K | 1 per fiscal year (filed ~Q1) |
| `sec_10q` | `Quarterly Report` | Quarterly report on Form 10-Q | 3 per fiscal year (Q2–Q4) |
| `sec_def14a` | `Proxy Statement` | Definitive proxy statement (DEF 14A) | 1 per fiscal year (filed ~Q2) |
| `sec_8k` | `8-K Items: 2.02` / `8.01` | Current reports — earnings results (2.02) or other events (8.01) | Variable |

8-K selection criteria: only items 2.02 (Results of Operations and
Financial Condition) and 8.01 (Other Events) are included. Item 9.01
(Financial Statements and Exhibits) alone is excluded because it
typically accompanies 2.02 without adding narrative content.

## Current Corpus Statistics

**118 documents** across FY2013–FY2026 (partial).

| Type | Count | Sub-types |
|------|-------|-----------|
| sec_10k | 13 | Annual Report (13) |
| sec_10q | 40 | Quarterly Report (40) |
| sec_def14a | 13 | Proxy Statement (13) |
| sec_8k | 52 | 2.02 (24), 2.02+9.01 (12), 8.01 (10), 2.02+8.01 (4), 8.01+9.01 (2) |

Date range: 2012-10-31 to 2025-11-25

### Coverage by Fiscal Year

Workday's fiscal year ends January 31. A fiscal-year row shows all
filings whose `publish_date` falls within that fiscal year.

| Fiscal Year | 10-K | 10-Q | DEF 14A | 8-K | Total |
|-------------|------|------|---------|-----|-------|
| FY2013 (ends Jan 2013) | 1 | 1 | — | — | 2 |
| FY2014 | 1 | 3 | 1 | — | 5 |
| FY2015 | 1 | 3 | 1 | — | 5 |
| FY2016 | 1 | 3 | 1 | — | 5 |
| FY2017 | 1 | 3 | 1 | 4 | 9 |
| FY2018 | 1 | 3 | 1 | 8 | 13 |
| FY2019 | 1 | 3 | 1 | 3 | 8 |
| FY2020 | 1 | 3 | 1 | 5 | 10 |
| FY2021 | 1 | 3 | 1 | 5 | 10 |
| FY2022 | 1 | 3 | 1 | 5 | 10 |
| FY2023 | 1 | 3 | 1 | 5 | 10 |
| FY2024 | 1 | 3 | 2* | 4 | 10 |
| FY2025 | 1 | 3 | 1 | 5 | 10 |
| FY2026 (partial) | — | 3 | — | 8 | 11 |

10-K coverage is complete for FY2013–FY2025 (13 fiscal years).
10-Q coverage is complete for FY2014–FY2026 (3 per year, 1 for FY2013).
DEF 14A coverage is complete for FY2014–FY2025 (1 per year).

\* FY2024 shows 2 DEF 14A because the FY2025 proxy (filed by a
third-party filer) has an accession-derived date of 2024-01-01
(year-only approximation). Accession-based dates default to January 1
of the filing year when the URL contains no more precise date signal.

## Exclusion Rules

The following are explicitly excluded from the canonical corpus:

- **Exhibit documents** — SOX certifications (EX-31, EX-32), press
  release exhibits (EX-99), articles of incorporation (EX-3), consent
  of auditors (EX-23), subsidiary lists (EX-21), and all other exhibits
- **EDGAR index pages** — Filing index pages (`-index.htm`)
- **EDGAR search pages** — Browse/search result pages (`browse-edgar`)
- **Empty/shell documents** — Documents with fewer than 100 characters
  (e.g., XBRL Inline Viewer wrappers)
- **8-K items without narrative content** — Item 9.01 alone (financial
  statement exhibits), Item 5.02 alone (management changes with no
  narrative), and other non-narrative items

## Eligibility Logic

Eligibility is determined by `_is_analysis_eligible()` in
`process/reclassify.py`. Documents that pass are assigned
`analysis_layer = 'canonical_v1'`; all others receive `None`.

```python
def _is_analysis_eligible(doc_type, doc_sub_type, char_count=0):
    if char_count < 100:
        return False
    if doc_type == "sec_10k" and doc_sub_type == "Annual Report":
        return True
    if doc_type == "sec_10q" and doc_sub_type == "Quarterly Report":
        return True
    if doc_type == "sec_def14a" and doc_sub_type == "Proxy Statement":
        return True
    if doc_type == "sec_8k" and doc_sub_type:
        if "2.02" in doc_sub_type or "8.01" in doc_sub_type:
            return True
    return False

# After eligibility check:
analysis_layer = "canonical_v1" if analysis_eligible else None
```

The `analysis_layer` field versions the corpus so that future rule
changes (e.g., adding earnings call transcripts) can coexist as
`canonical_v2` without breaking consumers that depend on `canonical_v1`.

## Pipeline Commands

To regenerate the canonical corpus from raw data:

```bash
python3 -m process.main --reprocess   # Re-extract text and dates
python3 -m process.reclassify          # Re-classify and set analysis_eligible
python3 -m kg.load_documents           # Load into Memgraph
python3 -m measures.quarterly          # Compute quarterly signals
```

Note: `--reprocess` resets `analysis_eligible` to `False` on all
documents, so `reclassify` must always run after reprocessing.

## Date Extraction

Document dates are extracted by `process/date_extractor.py` using a
multi-source strategy. The highest-confidence result wins.

| Source | Confidence | Notes |
|--------|-----------|-------|
| HTML meta tags | 0.95 | `article:published_time`, `og:published_time`, etc. |
| SEC filename (`wday-YYYYMMDD`, `wd-YYYYMMDD`) | 0.85 | Workday-specific; covers both old (`wday-MMDDYYYY`) and new (`wday-YYYYMMDD`) formats |
| URL path date (`/2024/01/15/`) | 0.85–0.90 | Rare in SEC URLs |
| Content patterns | 0.70 | Searches first 2000 characters for date strings |
| Accession number (hyphenated or unhyphenated) | 0.60 | Year-only; defaults to January 1 |

**Known limitations:**
- Accession-derived dates are year-only approximations (month/day
  default to January 1). This can place a document in the wrong
  fiscal quarter.
- iXBRL filings (2021+) use `"January 31 , 2024"` (space before comma)
  which does not match the content date regex. The SEC filename pattern
  handles these cases at higher confidence.

## Modeling Splits

Per CLAUDE.md, the temporal splits for leakage-safe modeling are:

| Split | Period | Use |
|-------|--------|-----|
| Train | 2015–2019 | Model fitting |
| Validation | 2020–2021 | Hyperparameter tuning |
| Test | 2022–present | Final evaluation |

Pre-2015 data (FY2013–FY2014) is available for feature engineering
warm-up but is not part of the formal train set.

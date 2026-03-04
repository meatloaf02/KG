# AII: Formula, Parameters, and Versioned Dataset

---

## Formula

**Per document** (`measures/aii.py:177–210`):
```
token_count    = len(clean_text) / 4
raw_score      = 1.0×count(classic_ai_terms)
               + 2.0×count(generative_ai_terms)
               + 0.75×count(adjacent_automation_terms)
doc_aii        = (raw_score / token_count) × 1000 × doc_type_weight
```

**Per quarter — corpus-level aggregation** (`aii.py:286–294`):
```
quarter_raw    = Σ raw_score      (all docs in quarter)
quarter_tokens = Σ token_count    (all docs in quarter)
AII            = (quarter_raw / quarter_tokens) × 1000 × avg_doc_type_weight
```

The denominator is **summed across the corpus before dividing** — not averaged per-doc then averaged — which preserves denominator integrity when document lengths vary across quarters.

---

## Parameter Choices

**Term buckets** (`aii.py:44–71`):

| Bucket | Weight | Terms |
|---|---|---|
| `classic_ai` | 1.0 | `artificial intelligence`, `machine learning`, `deep learning` |
| `generative_ai` | **2.0** | `generative ai`, `large language model`, `llm`, `foundation model`, `copilot` |
| `adjacent_automation` | **0.75** | `ai-powered`, `intelligent automation`, `predictive analytics` |

**Doc-type weights** (`aii.py:73–78`):

| Type | Weight | Rationale |
|---|---|---|
| `sec_10k` | **1.5** | Annual report — most deliberate AI language |
| `sec_10q` | **1.2** | Quarterly filing — strategic but shorter horizon |
| `sec_8k` | **1.0** | Current report — reactive disclosure, lower signal |
| default | 1.0 | All other doc types |

**Scale multiplier**: `× 1000` — makes values human-readable (range ~0–0.26 rather than 0–0.00026).

**Corpus filter**: `analysis_layer = 'canonical_v2'` — the frozen, leakage-safe SEC filing set.

---

## Justification for Each Decision

**Bucket weights (1.0 / 2.0 / 0.75)**

Sensitivity analysis (`notebook 03`) tested 7 alternative parameterizations. All variants achieve Pearson r ≥ 0.955 against baseline. The 2.0× GenAI weight is a **prior encoding strategic emphasis**, not an empirically optimized value — and sensitivity showed it barely matters for 79% of the dataset because `generative_ai` bucket is zero until 2023-Q2. The 0.75× discount on `adjacent_automation` reflects that those terms (`predictive analytics`, `intelligent automation`) are common in enterprise SaaS contexts independent of AI strategy.

**Corpus-level vs. per-document aggregation**

Averaging per-doc AII then averaging across docs would give equal weight to a 2-page 8-K and a 120-page 10-K. Pooling numerator and denominator before dividing means longer, denser documents contribute proportionally — appropriate for measuring AI language intensity across a heterogeneous corpus.

**Token approximation (`len(text) / 4`)**

A standard approximation (~4 chars/token for English prose). Exact tokenizer counts would require loading a tokenizer per document; the approximation is consistent across all documents and sufficient for a ratio where the multiplier is arbitrary anyway.

**Doc-type stratification**

`doc_flat` variant (r = 0.997) shows removing weights barely changes the signal. Weights are retained because they encode a theoretically grounded prior about deliberateness of disclosure language, not because they materially change the empirical output.

**No temporal smoothing in the production signal**

`smooth_2q` (r = 0.97) and `smooth_4q` (r = 0.91) lag the 2020-Q1 peak by 1–3 quarters. The unsmoothed signal is used for predictive modeling to preserve quarter-level granularity for chronological splits and lagged-feature construction. Smoothing is available analytically from the CSV without recomputing.

---

## Versioned Signal Dataset

**File**: `data/processed/aii_quarterly.csv`
**Version**: `AII_VERSION = "1.0.0"` (`run_aii.py:30`)
**Corpus**: `canonical_v2`, 53 quarters, 2012-Q4 – 2025-Q4

| Column | Description |
|---|---|
| `period` | `YYYY-QN` label |
| `year`, `quarter` | Numeric |
| `doc_count` | Documents in quarter |
| `aii` | Final AII value |
| `aii_delta` | QoQ change (first row = NaN) |
| `quarter_raw_score` | Σ weighted term counts |
| `quarter_tokens` | Σ token estimates |
| `avg_doc_type_weight` | Mean doc-type weight for quarter |
| `bucket_classic_ai` | Raw count of classic AI term matches |
| `bucket_generative_ai` | Raw count of GenAI term matches |
| `bucket_adjacent_automation` | Raw count of adjacent-automation matches |

Signal is also materialized as `QuarterlySignal` nodes in Memgraph with `extractor_version="1.0.0"` and `computed_at` timestamp for provenance tracing (`run_aii.py:97–113`).

The 38 active quarters (AII > 0, from 2014-Q2 onward) are what all analysis notebooks use for correlation and era-stratified tests. The 15 zero-valued pre-signal quarters (E0) are retained in the CSV for completeness but excluded from variance and correlation analysis.

# Ground Truth & Validation Strategy

## Overview

Given project constraints (single researcher, term-long timeline), evaluation focuses on **precision-oriented validation** using a thin gold set rather than comprehensive recall measurement.

## Gold Set Specification

### Document Sample
- **Target**: ~50 documents
- **Selection**: Stratified sample across:
  - Source types (SEC, transcript, press, blog, media)
  - Time periods (early: 2015-2017, middle: 2018-2020, recent: 2021-present)
  - Document lengths (short, medium, long)

### Sentence Sample
- **Target**: ~500 sentences
- **Selection**: From sampled documents, prioritize:
  - Sentences flagged as AI-related by extraction pipeline
  - Sentences flagged as risk-related
  - Sentences with product/capability mentions
  - Random sample of non-flagged sentences (negative examples)

## Labeling Schema

### AI-Related Language
| Label | Definition | Examples |
|-------|------------|----------|
| `AI_EXPLICIT` | Direct mention of AI/ML terminology | "machine learning", "artificial intelligence" |
| `AI_IMPLICIT` | AI-adjacent capability language | "predictive analytics", "intelligent automation" |
| `AI_NONE` | No AI relevance | General business language |

### Risk-Related Language
| Label | Definition | Examples |
|-------|------------|----------|
| `RISK_AI` | AI-specific risk disclosure | "algorithmic bias", "model accuracy" |
| `RISK_TECH` | Technology risk (non-AI specific) | "cybersecurity", "data breach" |
| `RISK_OTHER` | Non-technology risk | "market conditions", "competition" |
| `RISK_NONE` | Not a risk statement | General operations |

### Product/Capability Mentions
| Label | Definition | Examples |
|-------|------------|----------|
| `PRODUCT` | Named Workday product | "Workday HCM", "Workday Financial Management" |
| `CAPABILITY` | AI/technology capability | "Skills Cloud", "machine learning models" |
| `BOTH` | Product with capability | "Workday Adaptive Planning's AI forecasting" |
| `NONE` | No product/capability mention | General statements |

## Labeling Process

### CSV Template
```csv
doc_id,sentence_id,sentence_text,ai_label,risk_label,product_label,notes
DOC001,S001,"Workday uses machine learning...",AI_EXPLICIT,RISK_NONE,CAPABILITY,""
```

### Instructions
1. Read sentence in context (±2 sentences)
2. Apply labels independently (one sentence may have multiple labels)
3. Mark ambiguous cases with notes
4. Flag sentences that need second review

### Quality Control
- 10% of sentences double-labeled for inter-rater consistency
- Disagreements resolved by re-examination
- Document labeling decisions in notes column

## Evaluation Metrics

### Primary Metric: Precision
For each extraction type (AI, risk, product):
```
Precision = True Positives / (True Positives + False Positives)
```

**Target**: ≥80% precision for each category

### Secondary Metrics
- **Coverage**: % of gold-set positives detected
- **Confidence calibration**: Do confidence scores correlate with correctness?

### Why Precision Over Recall
- Precision errors (false positives) pollute downstream signals
- Recall errors (false negatives) reduce signal strength but don't introduce noise
- With limited labeling capacity, precision validation is more tractable

## Validation Workflow

```
1. Run extraction pipeline on full corpus
          ↓
2. Sample documents for gold set
          ↓
3. Extract candidate sentences (pipeline outputs + random)
          ↓
4. Manual labeling (CSV format)
          ↓
5. Compute precision metrics
          ↓
6. Error analysis (categorize false positives)
          ↓
7. Iterate extraction rules if precision < 80%
```

## Error Analysis Categories

### AI Detection Errors
- **Metaphorical use**: "learning from our customers" (not ML)
- **Historical reference**: "since we introduced analytics in 2010"
- **Competitor mention**: "unlike competitor's AI"

### Risk Detection Errors
- **Positive framing**: "we mitigate risk through..."
- **Hypothetical**: "could potentially impact..."
- **Boilerplate**: Standard legal disclaimers

### Product Detection Errors
- **Generic reference**: "our platform" vs. named product
- **Partial match**: "workforce management" (generic) vs. "Workday Workforce Management"
- **Deprecated products**: Historical product names

## Documented Limitations

1. **Small sample size**: 500 sentences limits statistical power
2. **Single annotator**: No formal inter-rater reliability
3. **Selection bias**: Sampling strategy may miss edge cases
4. **Temporal drift**: Rules tuned on recent data may miss historical patterns

## Deliverables

- [ ] `data_manifests/gold_set_docs.csv` - Document sample list
- [ ] `data_manifests/gold_set_sentences.csv` - Labeled sentences
- [ ] `docs/validation_results.md` - Precision metrics and error analysis

# Leakage-Proof Modeling Plan

## Overview

This document defines the rules and safeguards for building a predictive model that is free from temporal leakage (look-ahead bias).

## Target Variable

### Definition
- **Target**: Next-quarter stock return direction (binary: up/down)
- **Calculation**: `sign(close_price[Q+1] - close_price[Q])`
- **Label**: `1` if positive return, `0` if negative/zero

### Timing
- Quarter Q label is based on price at end of Q+1
- Features for quarter Q use only data available before Q ends

## Temporal Splits

| Split | Period | Purpose | Quarters |
|-------|--------|---------|----------|
| Train | 2015–2019 | Model fitting | ~20 quarters |
| Validation | 2020–2021 | Hyperparameter tuning | ~8 quarters |
| Test | 2022–present | Final evaluation | ~10+ quarters |

### Split Rules
1. **Strict chronological order**: No random shuffling across time
2. **No validation/test contamination**: Model never sees future data during training
3. **Expanding window optional**: For robustness, can use expanding train window

## Feature Engineering Rules

### As-Of Timestamp Requirement

Every feature must have an explicit `as_of_date`:
```
feature_value = f(data available on as_of_date)
```

### Lagging Rules

| Feature Type | Lag | Rationale |
|--------------|-----|-----------|
| Quarterly signals | t-1 to t-4 | Use prior 4 quarters |
| Document counts | t-1 | Previous quarter only |
| Rolling averages | t-4 to t-1 | 4-quarter lookback |
| Year-over-year change | t-4 vs t-1 | Compare same quarter last year |

### Prohibited Features
- Any data from quarter t or later when predicting t+1
- Filing dates that occur after quarter-end
- Earnings call data before official release date
- Any feature with `NULL` as_of_date

## Document Timestamp Handling

### Publication Date Rules
1. **SEC filings**: Use filing date from EDGAR, not period-end date
2. **Earnings calls**: Use call date, not quarter being discussed
3. **Press releases**: Use release date
4. **Blog posts**: Use publication date
5. **News articles**: Use article date

### Example
```
10-K for FY2023 filed on 2024-02-15:
- Available for features: Q1 2024 onward
- NOT available for: Q4 2023 or earlier
```

## As-Of Joins

### Implementation Pattern
```sql
SELECT
    q.quarter_id,
    s.signal_value
FROM quarters q
LEFT JOIN signals s ON
    s.quarter_id < q.quarter_id  -- Strictly before
    AND s.as_of_date <= q.quarter_end_date
```

### Key Constraint
```
feature.as_of_date <= target.quarter_start_date
```

## Leakage Checks

### Automated Checks
1. **Timestamp validation**: Assert `feature_date < label_date` for all rows
2. **Document availability**: Verify document `published_at < quarter_end`
3. **Join audit**: Log all as-of joins with timestamps

### Manual Audit
- Sample 10% of feature rows
- Verify no future-looking information
- Document in validation report

## Model Specification

### Baseline Model
- **Algorithm**: Logistic Regression (interpretable)
- **Regularization**: L2 (Ridge), tune via validation set
- **Features**: Standardized (z-score using training set stats)

### Second Model (Optional)
- **Algorithm**: Random Forest or Gradient Boosting
- **Purpose**: Compare to linear baseline
- **Constraint**: Same feature set, same temporal rules

## Evaluation Protocol

### Metrics
- **Primary**: Accuracy, Balanced Accuracy
- **Secondary**: ROC-AUC, Precision, Recall
- **Directional**: % of quarters with correct direction

### Baseline Comparison
- **Naive baseline**: Always predict majority class
- **Random baseline**: 50% accuracy
- **Buy-and-hold**: Assume market goes up

### Statistical Significance
- Report confidence intervals (bootstrap)
- Note small sample size limitations

## Feature Importance

### For Logistic Regression
- Report standardized coefficients
- Interpret sign and magnitude

### For Tree Models
- Permutation importance
- SHAP values (if feasible)

## Reproducibility

### Random Seed
- Set `random_seed = 42` for all stochastic operations
- Document in config.yaml

### Version Control
- Pin all library versions
- Save model artifacts with metadata
- Log feature schema and training data hash

## Code Assertions

```python
def validate_no_leakage(features_df, labels_df):
    """Assert no temporal leakage in feature matrix."""
    merged = features_df.merge(labels_df, on='quarter_id')
    assert (merged['feature_as_of'] < merged['label_date']).all(), \
        "Leakage detected: features dated after label period"

def validate_train_test_split(train_df, test_df):
    """Assert chronological split."""
    assert train_df['quarter_id'].max() < test_df['quarter_id'].min(), \
        "Train/test overlap detected"
```

## Deliverables

- [ ] `model/features.py` - Feature engineering with as-of logic
- [ ] `model/train.py` - Training script with leakage checks
- [ ] `model/evaluate.py` - Evaluation with baseline comparisons
- [ ] `docs/model_results.md` - Final metrics and interpretation

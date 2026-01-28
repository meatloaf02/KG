# Risk Register

## Overview

This document tracks identified risks to the project, their potential impact, and mitigation strategies.

## Risk Matrix

| ID | Risk | Category | Likelihood | Impact | Mitigation | Status |
|----|------|----------|------------|--------|------------|--------|
| R1 | robots.txt violations | Legal | Low | High | Respect robots.txt; maintain domain allowlist | Active |
| R2 | Rate limiting/blocking | Technical | Medium | Medium | Throttling, retries, exponential backoff | Active |
| R3 | Paywalled content ingestion | Legal | Low | High | Public-only source policy; pre-crawl verification | Active |
| R4 | Document availability drift | Reproducibility | Medium | Medium | Record hashes, timestamps; use archive.org fallback | Active |
| R5 | Document misclassification | Data Quality | Medium | Medium | Rule-based fallbacks; manual audit set | Active |
| R6 | LLM hallucination (if used) | Modeling | Medium | High | Extractive prompts only; require evidence spans | Active |
| R7 | Temporal leakage | Modeling | Medium | Critical | Lagged features; as-of joins; automated checks | Active |
| R8 | Model overfitting | Scientific | Medium | Medium | Simple baselines; held-out test set; regularization | Active |
| R9 | Storage limits | Infrastructure | Low | Low | Exclude raw data from Git; use .gitignore | Active |
| R10 | Evaluation bias | Scientific | Medium | Medium | Manual audit set; transparent reporting; document limitations | Active |

## Detailed Risk Descriptions

### R1: robots.txt Violations
- **Description**: Crawling pages disallowed by robots.txt could result in IP blocking or legal issues
- **Trigger**: Automated crawling without robots.txt check
- **Mitigation**:
  - Check robots.txt before any new domain
  - Maintain explicit domain allowlist
  - Log all crawl decisions
- **Owner**: Ingestion module
- **Review**: Before each crawl session

### R2: Rate Limiting/Blocking
- **Description**: Aggressive crawling could trigger rate limits or IP blocks
- **Trigger**: Too many requests in short period
- **Mitigation**:
  - Minimum 1 second delay between requests
  - Exponential backoff on 429/503 errors
  - Maximum 1000 requests per domain per day
  - Rotate user-agent appropriately
- **Owner**: Ingestion module
- **Review**: Monitor response codes during ingestion

### R3: Paywalled Content Ingestion
- **Description**: Accidentally collecting content that requires subscription
- **Trigger**: URL appears public but redirects to paywall
- **Mitigation**:
  - Verify content accessibility before storage
  - Check for paywall indicators in response
  - Maintain disallowed source list
- **Owner**: Ingestion module
- **Review**: Spot-check collected documents

### R4: Document Availability Drift
- **Description**: Source documents removed or modified after collection
- **Trigger**: Websites update/remove content
- **Mitigation**:
  - Store content hash at collection time
  - Record fetch timestamp
  - Use archive.org for historical verification
  - Manifest files enable reproducibility discussion
- **Owner**: Data pipeline
- **Review**: Compare hashes on re-fetch

### R5: Document Misclassification
- **Description**: Incorrect document type assignment affects downstream analysis
- **Trigger**: Edge cases in document structure
- **Mitigation**:
  - Rule-based classifier with fallback to "unknown"
  - Manual review of uncertain classifications
  - Audit set includes edge cases
- **Owner**: Processing module
- **Review**: Check classification distribution

### R6: LLM Hallucination
- **Description**: If LLMs are used for extraction, they may generate non-existent information
- **Trigger**: Generative prompts without grounding
- **Mitigation**:
  - Use extractive prompts only (quote from source)
  - Require evidence span for every extraction
  - Validate extractions against source text
  - Prefer rule-based extraction where possible
- **Owner**: Extraction module
- **Review**: Sample extraction verification

### R7: Temporal Leakage
- **Description**: Features inadvertently use future information, inflating model performance
- **Trigger**: Incorrect timestamp handling in feature engineering
- **Mitigation**:
  - Strict as-of date requirements on all features
  - Automated leakage detection checks
  - Use document filing date, not period date
  - Code assertions for temporal ordering
- **Owner**: Model module
- **Review**: Pre-training validation suite

### R8: Model Overfitting
- **Description**: Model memorizes training data, fails on test set
- **Trigger**: Complex model with limited data
- **Mitigation**:
  - Start with simple logistic regression baseline
  - Use regularization (L2)
  - Strict train/validation/test split
  - Report both validation and test performance
- **Owner**: Model module
- **Review**: Compare train vs. test metrics

### R9: Storage Limits
- **Description**: Git repository becomes too large from data files
- **Trigger**: Committing raw HTML/PDF or large derived files
- **Mitigation**:
  - .gitignore excludes data/external, data/interim, data/processed
  - Only commit manifests and code
  - Document data recreation steps
- **Owner**: Repository management
- **Review**: Check repo size before commits

### R10: Evaluation Bias
- **Description**: Validation set not representative, leading to misleading metrics
- **Trigger**: Non-random or biased sampling
- **Mitigation**:
  - Stratified sampling across time/source type
  - Transparent reporting of sample sizes
  - Acknowledge limitations in documentation
  - Use multiple evaluation metrics
- **Owner**: Validation process
- **Review**: Audit sampling procedure

## Risk Review Schedule

| Milestone | Risks to Review |
|-----------|-----------------|
| M1 (Setup) | R9 (storage) |
| M2 (Ingestion) | R1, R2, R3, R4 |
| M3 (Processing) | R5, R6 |
| M4 (Signals) | R5, R10 |
| M5 (Modeling) | R7, R8 |
| M6 (Documentation) | All risks final review |

## Escalation Process

If a risk materializes:
1. Document the incident
2. Assess actual impact
3. Implement immediate mitigation
4. Update risk register with lessons learned
5. Adjust mitigation strategy if needed

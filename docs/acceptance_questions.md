# Knowledge Graph Acceptance Questions

These questions define the analytical capabilities the knowledge graph must support. The project is considered successful when SQL queries against the KG can answer each question with traceable evidence.

## Coverage Questions

1. **Document Coverage**: How many documents are in the KG by year and source type (SEC filing, transcript, press release, blog, media)?

2. **Temporal Coverage**: Are there any gaps in quarterly coverage from 2015 to present?

3. **Entity Coverage**: How many unique products, capabilities, and risk topics have been extracted?

## AI Language Evolution

4. **AI Intensity Trend**: How has the frequency of AI-related language in Workday's public communications changed from 2015 to present?

5. **AI Terminology Shift**: What specific AI terms (e.g., "machine learning", "artificial intelligence", "deep learning", "generative AI") appear in each year, and when did new terms first appear?

6. **AI in Risk Disclosures**: When did AI-related risks first appear in SEC filings, and how has their prominence changed?

## Product & Capability Analysis

7. **Capability Timeline**: When was each major AI capability (e.g., Skills Cloud, Workday Adaptive Planning, Workday Illuminate) first mentioned in public documents?

8. **Product-Capability Mapping**: Which products are associated with which AI capabilities based on document mentions?

9. **Capability Density**: Which quarters had the highest density of new capability announcements?

## Risk Disclosure Analysis

10. **Risk Topic Distribution**: What are the top 10 risk topics mentioned in SEC filings, and how has their relative frequency changed over time?

11. **AI Risk Emergence**: Which AI-specific risks (e.g., bias, data privacy, model reliability) are disclosed, and when did they first appear?

12. **Risk-Event Correlation**: Do periods with increased risk disclosure density correlate with specific events or market conditions?

## Predictive Signal Questions

13. **Signal Validity**: Do the computed quarterly signals (AI intensity, risk density, capability mentions) show meaningful variation over time?

14. **Lead-Lag Relationships**: Do changes in AI language intensity or risk disclosure precede or follow stock price movements?

15. **Feature Interpretability**: Which signals have the strongest coefficients in the predictive model, and is this interpretable given domain knowledge?

## Provenance & Traceability

For each question above, the answer must include:
- Source document IDs
- Evidence text spans
- Extraction timestamps
- Confidence scores (where applicable)

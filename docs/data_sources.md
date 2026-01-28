# Data Sources Policy

## Public-Only Requirement

This project uses **exclusively public data sources**. No paywalled, credentialed, or proprietary data may be collected or used.

## Allowed Sources

### SEC Filings (Highest Priority)
- **Source**: SEC EDGAR (https://www.sec.gov/cgi-bin/browse-edgar)
- **Filing Types**: 10-K, 10-Q, 8-K
- **Access**: Free, public, no authentication required
- **Notes**: Primary source for risk disclosures and official financial communications

### Investor Relations
- **Source**: Workday IR site (https://investor.workday.com)
- **Content**: Press releases, presentations, SEC filings
- **Access**: Public
- **Notes**: Check robots.txt; respect rate limits

### Earnings Call Transcripts
- **Allowed Sources**:
  - Workday investor relations (if posted publicly)
  - Seeking Alpha (public excerpts only)
  - The Motley Fool (public transcripts)
- **Disallowed**: FactSet, Bloomberg Terminal, Capital IQ
- **Notes**: Verify public availability before collection

### Press Releases
- **Source**: Workday newsroom (https://newsroom.workday.com)
- **Access**: Public
- **Notes**: AI and product-related releases prioritized

### Corporate Blog
- **Source**: Workday blog (https://blog.workday.com)
- **Access**: Public
- **Notes**: Technology and product posts only

### Public Media
- **Allowed**:
  - Major news outlets (Reuters, WSJ public articles)
  - Tech news (TechCrunch, VentureBeat)
  - Business news (Forbes, Fortune public content)
- **Disallowed**: Paywalled articles
- **Notes**: Archive.org for historical articles if original unavailable

## Disallowed Sources

| Source Type | Examples | Reason |
|-------------|----------|--------|
| Paywalled Analyst Reports | Gartner, Forrester, IDC | Requires paid subscription |
| Financial Terminals | Bloomberg, FactSet, Refinitiv | Credentialed access |
| Proprietary Databases | Capital IQ, PitchBook | Licensed data |
| Login-Protected Content | LinkedIn Premium, Glassdoor | Authentication required |
| APIs with Restrictive ToS | Some news APIs | Terms prohibit academic use |

## Fallback Strategies

### When Primary Source Unavailable

1. **SEC Filings**: Always available via EDGAR (no fallback needed)
2. **Transcripts**: Use public summary/quotes from news coverage
3. **Press Releases**: Check Internet Archive (archive.org)
4. **Blog Posts**: Check Internet Archive
5. **Media Articles**: Find alternative public coverage of same event

### Analyst/Media Signal Proxy

Since analyst reports are paywalled, use these proxies:
- Public analyst quotes in news articles
- Analyst ratings from Yahoo Finance (public)
- Media sentiment from public news coverage
- Social media mentions (Twitter/X public posts)

## Compliance Requirements

### robots.txt
- Check robots.txt before crawling any domain
- Respect all Disallow directives
- Use appropriate crawl delays

### Rate Limiting
- Maximum 1 request per second per domain
- Implement exponential backoff on errors
- Total daily limit: 1000 requests per domain

### User Agent
- Identify crawler: `WorkdayKG-Academic-Research/1.0`
- Include contact information in requests
- Do not masquerade as browser

### Data Retention
- Store only what is necessary
- Delete raw HTML/PDF after text extraction
- Keep only metadata and extracted text in database

## Domain Allowlist

```
sec.gov
investor.workday.com
newsroom.workday.com
blog.workday.com
seekingalpha.com
fool.com
reuters.com
techcrunch.com
venturebeat.com
```

## Verification Checklist

Before ingesting from a new source:
- [ ] URL is publicly accessible (no login)
- [ ] No paywall or subscription required
- [ ] robots.txt permits crawling
- [ ] Terms of service allow academic use
- [ ] Content is relevant to project scope

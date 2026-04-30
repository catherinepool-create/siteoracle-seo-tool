# SiteOracle

**AI-powered SEO + AEO + GEO + GBP website analysis.**  
Goes deeper than a basic scanner — crawls your site, runs 50+ rules-based checks across four dimensions, and optionally analyzes with AI for actionable recommendations.

## What it does

Drop in a URL. Get back a scored report across:

- **🔧 Technical SEO** — Meta tags, headings, schema, content depth, image alt text, internal links, robots control (15+ checks)
- **📝 Answer Engine Optimization (AEO)** — How well your site answers questions for Google AI Overviews, Perplexity, ChatGPT (7 dimensions: Q&A structure, concise answers, FAQ schema, structured content, authority, readability, entity depth)
- **🤖 Generative Engine Optimization (GEO)** — How likely AI search engines will cite your content (7 dimensions: brand authority, structured data, freshness, topical depth, citation readiness, multimedia, external references)
- **📍 Google Business Profile Alignment** — Local SEO: NAP consistency, LocalBusiness schema, Maps integration, local content, reviews, contact visibility (7 dimensions)

## Quick start

```bash
pip install -r requirements.txt

# Run with CLI (rules-based only)
python cli.py https://yoursite.com --no-ai

# Full analysis with AI
export DEEPSEEK_API_KEY=your_key_here
python cli.py https://yoursite.com -o report.html

# Or with OpenAI
export OPENAI_API_KEY=your_key_here
python cli.py https://yoursite.com --engine openai -o report.html

# Or with Claude
export ANTHROPIC_API_KEY=your_key_here
python cli.py https://yoursite.com --engine claude -o report.html

# Compare with a competitor
python cli.py https://yoursite.com --compare https://competitor.com

# Run the web UI
streamlit run app.py
```

## Project structure

```
siteoracle/
├── cli.py                 # CLI entry point
├── app.py                 # Streamlit web UI
├── crawler.py             # Fetches + parses pages
├── analyzer.py            # AI-powered analysis (OpenAI/Claude/DeepSeek)
├── reporter.py            # Generates formatted reports
├── check_seo.py           # Technical SEO checks (15+)
├── check_aeo.py           # Answer Engine Optimization (7 dimensions)
├── check_geo.py           # Generative Engine Optimization (7 dimensions)
├── check_gbp.py           # Google Business Profile alignment (7 dimensions)
├── report_template.html   # Beautiful HTML report template
├── requirements.txt
└── README.md
```

## Scoring

Each module scores out of 100. The combined score weights:

| Module | Weight |
|--------|--------|
| Technical SEO | 35% |
| AEO | 25% |
| GEO | 25% |
| GBP | 15% |

## Product Roadmap

- **Phase 1 (Done)** — Core crawler + technical SEO + AEO + GEO + GBP checks, CLI + HTML report
- **Phase 2 (In Progress)** — Competitive comparison, scheduled monitoring, white-label reports, API
- **Phase 3** — Vertical focus (e.g., local businesses), subscription SaaS, agency dashboard

## License

Built for Catherine's portfolio. Not for resale without permission.

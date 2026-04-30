"""AI-powered analysis engine for SEO, AEO, and GEO evaluation.

Supports OpenAI, Anthropic Claude, and DeepSeek as backends.
"""

import json
import os


SYSTEM_PROMPT = """You are an expert SEO/AEO/GEO analyst. You analyze websites and provide 
specific, actionable feedback. You do NOT give generic advice. Every recommendation must be 
specific to the site being analyzed.

Analyze across these dimensions:

1. VISITOR EXPERIENCE — What a first-time visitor sees. Friction points, layout issues, 
   clarity of purpose above the fold. Be specific about what's confusing or overwhelming.

2. HEADLINE STRENGTH — Whether the headlines and messaging immediately communicate value. 
   Suggest specific rewrites if weak.

3. SEARCH VISIBILITY GAPS — Technical SEO issues: missing meta data, weak title tags, 
   poor heading structure, missing schema, thin content, slow load signals.

4. ANSWER ENGINE OPTIMIZATION (AEO) — How well the site would get selected as an answer 
   by ChatGPT, Perplexity, Gemini. Does it use clear Q&A structure? Are there concise, 
   quotable answers? Does it have authority signals?

5. GENERATIVE ENGINE OPTIMIZATION (GEO) — How likely Google AI Overviews would cite this 
   site. Structured data, authoritative sources cited, clear sectioning, FAQ schema.

6. CONVERSION — Where visitors drop off. What would make existing traffic convert better.
   Missing CTAs, weak value props, trust signals.

For each dimension, provide:
- Score: 1-10
- What's working
- What's missing or weak
- Specific, actionable fix (not generic advice)

End with a PRIORITY ACTION LIST — top 3 things the owner should fix first, ordered by impact."""


def analyze_site(pages, engine="deepseek"):
    """Analyze crawled pages and return structured insights.

    Args:
        pages: List of parsed page dicts from crawler.py
        engine: One of 'openai', 'claude', 'deepseek'

    Returns:
        str: AI analysis text
    """
    site_summary = _build_summary(pages)

    if engine == "deepseek":
        return _analyze_deepseek(site_summary)
    elif engine == "claude":
        return _analyze_claude(site_summary)
    elif engine == "openai":
        return _analyze_openai(site_summary)
    else:
        return f"Unknown engine: {engine}. Supported: openai, claude, deepseek."


def _build_summary(pages):
    """Condense crawled pages into a LLM-friendly summary."""
    sections = []

    for p in pages:
        section = f"""
=== PAGE: {p.get('url', 'unknown')} ===
Title: {p.get('title', 'N/A')}
Meta Description: {p.get('meta_description', 'N/A')}
Word Count: {p.get('word_count', 0)}
Has Schema: {p.get('has_schema', False)}
Has Robots Meta: {p.get('has_robots_meta', False)}

H1s: {', '.join(p.get('h1', [])[:3])}
H2s: {', '.join(p.get('h2', [])[:5])}

Content (first ~1500 chars):
{p.get('paragraphs', [])[:20]}

Key Links: {[l['text'] for l in p.get('links', [])[:10]]}
Images: {len(p.get('images', []))} images, {sum(1 for i in p.get('images', []) if i.get('alt'))} with alt text
"""
        sections.append(section)

    return "\n---\n".join(sections)


def _analyze_openai(site_summary):
    """Use GPT-4o for analysis."""
    from openai import OpenAI
    client = OpenAI()

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this website:\n\n{site_summary}"}
        ],
        temperature=0.3,
        max_tokens=4000,
    )
    return resp.choices[0].message.content


def _analyze_claude(site_summary):
    """Use Claude for analysis."""
    import anthropic
    client = anthropic.Anthropic()

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Analyze this website:\n\n{site_summary}"}
        ],
    )
    return resp.content[0].text


def _analyze_deepseek(site_summary):
    """Use DeepSeek for analysis."""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
    )

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this website for SEO/AEO/GEO optimization. Be specific and actionable.\n\n{site_summary}"}
        ],
        temperature=0.3,
        max_tokens=4000,
    )
    return resp.choices[0].message.content


def analyze_screenshot(image_path):
    """Analyze a website screenshot using vision-capable model."""
    import base64

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    if os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this website screenshot across all 6 dimensions."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                    ]
                }
            ],
            max_tokens=4000,
        )
        return resp.choices[0].message.content

    return "Vision analysis requires an OpenAI API key. Set OPENAI_API_KEY environment variable."

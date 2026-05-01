"""Crawls a website, fetches pages, extracts structured content."""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re

USER_AGENT = "SiteOracle/1.0 (SEO Analysis Tool)"


def fetch_page(url):
    """Fetch a single page and return its HTML."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.text, resp.url
    except requests.RequestException as e:
        return None, str(e)


def parse_html(html, base_url):
    """Extract structured data from HTML."""
    soup = BeautifulSoup(html, "lxml")

    return {
        "title": soup.title.string.strip() if soup.title else "",
        "meta_description": soup.find("meta", attrs={"name": "description"})["content"]
        if soup.find("meta", attrs={"name": "description"})
        else "",
        "meta_keywords": soup.find("meta", attrs={"name": "keywords"})["content"]
        if soup.find("meta", attrs={"name": "keywords"})
        else "",
        "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
        "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
        "h3": [h.get_text(strip=True) for h in soup.find_all("h3")],
        "paragraphs": [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 20
        ],
        "links": [
            {"text": a.get_text(strip=True), "href": urljoin(base_url, a["href"])}
            for a in soup.find_all("a", href=True)
            if a.get_text(strip=True)
        ][:50],
        "images": [
            {"alt": img.get("alt", ""), "src": urljoin(base_url, img["src"])}
            for img in soup.find_all("img", src=True)
        ][:30],
        "og_title": soup.find("meta", property="og:title"),
        "og_description": soup.find("meta", property="og:description"),
        "canonical": soup.find("link", rel="canonical"),
        "scripts": len(soup.find_all("script")),
        "stylesheets": len(soup.find_all("link", rel="stylesheet")),
        "word_count": len(
            re.sub(r"\s+", " ", soup.get_text()).strip().split()
        ),
        "has_schema": bool(soup.find("script", type="application/ld+json")),
        "has_robots_meta": bool(
            soup.find("meta", attrs={"name": "robots"})
        ),
    }


def crawl(url, max_pages=5):
    """Crawl a website starting from a URL, fetch key pages."""
    domain = urlparse(url).netloc
    to_visit = [url]
    visited = set()
    pages = []

    while to_visit and len(visited) < max_pages:
        page_url = to_visit.pop(0)
        if page_url in visited:
            continue

        html, result = fetch_page(page_url)
        if html is None:
            continue

        visited.add(page_url)
        data = parse_html(html, page_url)
        data["url"] = page_url
        pages.append(data)

        # Find internal links to follow
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            parsed = urlparse(href)
            if parsed.netloc == domain and href not in visited and "#" not in href:
                # Only add reasonable pages
                if any(
                    keyword in parsed.path.lower()
                    for keyword in ["", "/", "about", "contact", "service", "product", "blog", "faq", "pricing"]
                ):
                    to_visit.append(href)

        time.sleep(0.5)  # Be polite

    return pages


def extract_schema(html):
    """Extract JSON-LD schema if present."""
    soup = BeautifulSoup(html, "lxml")
    schemas = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            schemas.append(json.loads(script.string))
        except:
            pass
    return schemas


# ── Robots.txt analysis ─────────────────────────────────────────

AI_BOTS = {
    "GPTBot": "OpenAI ChatGPT / GPTs",
    "ChatGPT-User": "OpenAI ChatGPT user queries",
    "Google-Extended": "Google AI Overviews / Gemini",
    "ClaudeBot": "Anthropic Claude",
    "Claude-Web": "Anthropic Claude (web)",
    "PerplexityBot": "Perplexity AI",
    "Applebot": "Apple Intelligence / Siri",
    "Bytespider": "ByteDance (TikTok AI)",
    "CCBot": "Common Crawl (AI training)",
    "FacebookBot": "Meta AI",
    "cohere-ai": "Cohere AI",
}

def fetch_robots_txt(url):
    """Fetch and parse robots.txt for AI bot access rules.

    Args:
        url: Full URL of the site (e.g. https://example.com)

    Returns:
        dict with:
            - has_robots_txt: bool
            - ai_bots: dict of {bot_name: {"allowed": bool, "disallowed_paths": [str]}}
            - rules_found: list of rule strings
            - raw_text: the raw robots.txt (first 2000 chars)
            - error: str if failed
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        resp = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code != 200:
            return {
                "has_robots_txt": False,
                "ai_bots": {},
                "rules_found": [],
                "raw_text": "",
                "error": f"HTTP {resp.status_code}",
            }

        raw = resp.text
        lines = raw.split("\n")
        rules_found = []
        ai_bots = {}

        current_agent = None
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Check if this is a bot we care about
            if stripped.lower().startswith("user-agent:"):
                agent = stripped.split(":", 1)[1].strip()
                if agent == "*":
                    current_agent = "*"
                elif agent in AI_BOTS:
                    current_agent = agent
                else:
                    current_agent = None
                continue

            if current_agent is None:
                continue

            if stripped.lower().startswith("disallow:"):
                path = stripped.split(":", 1)[1].strip()
                rules_found.append(f"{current_agent}: {stripped}")

                if current_agent not in ai_bots:
                    ai_bots[current_agent] = {
                        "name": current_agent,
                        "label": AI_BOTS.get(current_agent, current_agent),
                        "allowed": True,
                        "disallowed_paths": [],
                    }
                ai_bots[current_agent]["allowed"] = False
                ai_bots[current_agent]["disallowed_paths"].append(path or "/")

            elif stripped.lower().startswith("allow:"):
                path = stripped.split(":", 1)[1].strip()
                rules_found.append(f"{current_agent}: {stripped}")

        # For wildcard (*) — check if AI bots are covered by it
        if "*" in ai_bots:
            wildcard_rules = ai_bots["*"]
            for bot_name in AI_BOTS:
                if bot_name not in ai_bots:
                    # Inherits wildcard rules
                    ai_bots[bot_name] = {
                        "name": bot_name,
                        "label": AI_BOTS[bot_name],
                        "allowed": wildcard_rules["allowed"],
                        "disallowed_paths": list(wildcard_rules["disallowed_paths"]),
                        "inherited_from_wildcard": True,
                    }

        # Any bot not mentioned and not covered by wildcard defaults to allowed
        for bot_name, label in AI_BOTS.items():
            if bot_name not in ai_bots:
                ai_bots[bot_name] = {
                    "name": bot_name,
                    "label": label,
                    "allowed": True,
                    "disallowed_paths": [],
                    "no_rules_found": True,
                }

        return {
            "has_robots_txt": True,
            "ai_bots": ai_bots,
            "rules_found": rules_found,
            "raw_text": raw[:2000],
            "error": None,
        }

    except requests.RequestException as e:
        return {
            "has_robots_txt": False,
            "ai_bots": {},
            "rules_found": [],
            "raw_text": "",
            "error": str(e),
        }


def extract_schema_types(html):
    """Extract specific schema.org types from JSON-LD on the page.

    Args:
        html: Raw HTML string

    Returns:
        dict with types found and count
    """
    soup = BeautifulSoup(html, "lxml")
    types = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string)
            # Handle @graph arrays
            if isinstance(data, dict):
                items = [data]
            elif isinstance(data, list):
                items = data
            else:
                continue

            for item in items:
                schema_type = item.get("@type", "")
                if isinstance(schema_type, list):
                    for t in schema_type:
                        types[t] = types.get(t, 0) + 1
                else:
                    types[schema_type] = types.get(schema_type, 0) + 1
        except Exception:
            pass

    return types


IMPORTANT_SCHEMA_TYPES = [
    "Organization",
    "LocalBusiness",
    "Product",
    "FAQPage",
    "HowTo",
    "Article",
    "BlogPosting",
    "Review",
    "Event",
    "Person",
    "Service",
    "BreadcrumbList",
    "SiteNavigationElement",
    "WebSite",
    "WebPage",
    "ItemList",
    "Recipe",
    "VideoObject",
    "Course",
    "SoftwareApplication",
]

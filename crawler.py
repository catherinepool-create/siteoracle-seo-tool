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

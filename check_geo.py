"""Generative Engine Optimization (GEO) checks — how well a site performs in AI-generated search results."""

import re
from urllib.parse import urlparse


def check_geo(pages):
    """Analyze how well a site is optimized for generative AI search engines
    (Google AI Overviews, ChatGPT, Claude, Gemini, Perplexity).

    Args:
        pages: List of parsed page dicts from crawler.py

    Returns:
        dict with score, dimensions, issues, passes, summary
    """
    if not pages:
        return _empty_result("No pages to analyze")

    homepage = pages[0]
    all_text = _get_all_text(pages)
    all_headings = _get_all_headings(pages)
    all_links = _get_all_links(pages)

    dimensions = {
        "brand_authority": _check_brand_authority(pages, all_text),
        "structured_data": _check_structured_data(pages),
        "freshness": _check_freshness(pages, all_text),
        "topical_depth": _check_topical_depth(pages, all_headings),
        "citation_readiness": _check_citation_readiness(all_text),
        "multimedia": _check_multimedia(pages),
        "external_references": _check_external_references(all_links, all_text),
    }

    weights = {
        "brand_authority": 15,
        "structured_data": 20,
        "freshness": 10,
        "topical_depth": 25,
        "citation_readiness": 15,
        "multimedia": 10,
        "external_references": 5,
    }

    weighted_score = sum(
        dimensions[k]["score"] * weights[k] / 100 for k in weights
    )
    final_score = round(weighted_score)

    all_issues = []
    all_passes = []
    for dim in dimensions.values():
        all_issues.extend(dim.get("issues", []))
        all_passes.extend(dim.get("passes", []))

    return {
        "score": min(100, max(0, final_score)),
        "dimensions": dimensions,
        "issues": all_issues,
        "passes": all_passes,
        "summary": _build_summary(dimensions, weights),
    }


def _empty_result(reason):
    return {
        "score": 0,
        "dimensions": {},
        "issues": [{"severity": "critical", "check": "No data", "detail": reason}],
        "passes": [],
        "summary": reason,
    }


def _get_all_text(pages):
    return " ".join(" ".join(p.get("paragraphs", [])) for p in pages)


def _get_all_headings(pages):
    headings = []
    for p in pages:
        headings.extend(p.get("h1", []))
        headings.extend(p.get("h2", []))
        headings.extend(p.get("h3", []))
    return headings


def _get_all_links(pages):
    links = []
    for p in pages:
        links.extend(p.get("links", []))
    return links


# ── Dimension 1: Brand Authority ─────────────────────────────────

def _check_brand_authority(pages, all_text):
    issues = []
    passes = []
    score = 40

    # Check for author attribution
    author_patterns = [
        r"by\s+[A-Z][a-z]+ [A-Z][a-z]+",
        r"written by", r"author\s*:", r"posted by",
        r"published by",
    ]
    has_author = any(re.search(p, all_text, re.IGNORECASE) for p in author_patterns)

    if has_author:
        passes.append("Author attribution detected — strong E-E-A-T signal.")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "No author attribution found",
            "detail": "Generative AI prefers content with clear authorship. Add author bylines to key pages."
        })

    # Check for About page
    has_about = any(
        "about" in p.get("url", "").lower()
        or any("about" in h.lower() for h in p.get("h1", []))
        for p in pages
    )
    if has_about:
        passes.append("About page detected — important for brand authority signals.")
        score += 15
    else:
        issues.append({
            "severity": "warning",
            "check": "No About page found",
            "detail": "An About page with team credentials, history, and mission builds authority for AI."
        })

    # Check for trust signals
    trust_signals = [
        "trusted", "award", "certified", "accredited", "verified",
        "since", "est\.", "established", "years of experience",
        "BBB", "better business bureau",
    ]
    trust_count = sum(
        1 for sig in trust_signals if re.search(sig, all_text, re.IGNORECASE)
    )
    if trust_count >= 3:
        passes.append(f"Found {trust_count} trust signals — strong credibility markers.")
        score += 15
    elif trust_count >= 1:
        passes.append(f"Found {trust_count} trust signal(s).")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "No trust signals detected",
            "detail": "Consider adding awards, certifications, years in business, or testimonials."
        })

    # Check for contact page
    has_contact = any("contact" in p.get("url", "").lower() for p in pages)
    if has_contact:
        passes.append("Contact page found — adds transparency and trust.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "No dedicated contact page",
            "detail": "A contact page with physical address and phone number builds credibility."
        })

    # Check for professional bio/team page
    team_signals = ["team", "our team", "founder", "CEO", "lead", "expert"]
    has_team = any(
        re.search(sig, p.get("url", "").lower()) or
        any(re.search(sig, h.lower()) for h in p.get("h1", []))
        for p in pages
        for sig in team_signals
    )
    if has_team:
        passes.append("Team/personnel info detected — humanizes the brand.")
        score += 10

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 2: Structured Data ────────────────────────────────

def _check_structured_data(pages):
    issues = []
    passes = []
    score = 30

    # Check schema presence
    schema_pages = [p for p in pages if p.get("has_schema")]
    total_pages = len(pages)

    if schema_pages:
        passes.append(f"Schema detected on {len(schema_pages)}/{total_pages} pages.")
        score += 20
    else:
        issues.append({
            "severity": "critical",
            "check": "No structured data (schema markup) found",
            "detail": "Structured data is critical for generative AI citation. Add JSON-LD schema."
        })

    # Check for Open Graph tags
    og_count = sum(
        1 for p in pages
        if p.get("og_title") or p.get("og_description")
    )
    if og_count >= 1:
        passes.append("Open Graph meta tags detected — good for social and AI content understanding.")
        score += 15
    else:
        issues.append({
            "severity": "warning",
            "check": "No Open Graph meta tags found",
            "detail": "OG tags help AI models understand page content and improve link previews."
        })

    # Check for canonical URLs
    has_canonical = any(p.get("canonical") for p in pages)
    if has_canonical:
        passes.append("Canonical URLs detected — prevents duplicate content confusion.")
        score += 15
    else:
        issues.append({
            "severity": "warning",
            "check": "No canonical URLs found",
            "detail": "Canonical tags tell search engines and AI which URL is the authoritative version."
        })

    # Check for robots meta
    has_robots = any(p.get("has_robots_meta") for p in pages)
    if has_robots:
        passes.append("Robots meta tags present — proper crawl control.")
        score += 10

    # Schema coverage ratio bonus
    if schema_pages and total_pages > 1:
        ratio = len(schema_pages) / total_pages
        if ratio >= 0.75:
            passes.append(f"Schema coverage: {ratio:.0%} of pages — excellent.")
            score += 20
        elif ratio >= 0.5:
            passes.append(f"Schema coverage: {ratio:.0%} of pages — good.")
            score += 10
        else:
            issues.append({
                "severity": "warning",
                "check": f"Low schema coverage ({ratio:.0%})",
                "detail": "Aim for schema on all key pages, not just the homepage."
            })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 3: Content Freshness ───────────────────────────────

def _check_freshness(pages, all_text):
    issues = []
    passes = []
    score = 50

    # Look for dates in content
    date_patterns = [
        (r'\b(January|February|March|April|May|June|July|August|September|'
         r'October|November|December)\s+\d{1,2},?\s+\d{4}\b', "long"),
        (r'\b\d{1,2}/\d{1,2}/(202[0-9]|203[0-9])\b', "short"),
        (r'\b(202[0-9]|203[0-9])-\d{2}-\d{2}\b', "iso"),
        (r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b', "abbr"),
    ]
    date_count = 0
    for pattern, _ in date_patterns:
        date_count += len(re.findall(pattern, all_text))

    if date_count >= 3:
        passes.append(f"Found {date_count} date references — content freshness signals detected.")
        score += 20
    elif date_count >= 1:
        passes.append("Some date references found.")
        score += 10
    else:
        issues.append({
            "severity": "warning",
            "check": "No publication dates detected",
            "detail": "Generative AI favors recent content. Add visible timestamps to pages."
        })

    # Check for recency signals
    recency_terms = [
        r"\b\d{4}\b",  # Any four-digit year
        "updated", "last updated", "published", "posted",
        "new", "recently", "latest", "current",
    ]
    recency_count = 0
    for term in recency_terms:
        recency_count += len(re.findall(term, all_text, re.IGNORECASE))

    if recency_count >= 10:
        passes.append(f"Strong recency signals ({recency_count} instances).")
        score += 15
    elif recency_count >= 5:
        passes.append(f"Moderate recency signals ({recency_count} instances).")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "Weak recency signals",
            "detail": "Use 'Last updated' dates and mention current years in content."
        })

    # Check for blog/posts section (frequent updates indicator)
    blog_urls = [
        p.get("url", "") for p in pages
        if any(k in p.get("url", "").lower() for k in ["/blog", "/news", "/articles", "/posts"])
    ]
    if blog_urls:
        passes.append(f"Blog/news section detected ({len(blog_urls)} pages) — indicates active content pipeline.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No blog or news section detected",
            "detail": "A regularly updated blog is the strongest freshness signal for generative AI."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 4: Topical Depth ──────────────────────────────────

def _check_topical_depth(pages, all_headings):
    issues = []
    passes = []
    score = 40

    total_words = sum(p.get("word_count", 0) for p in pages)
    heading_count = len(all_headings)

    # Word count assessment
    if total_words >= 3000:
        passes.append(f"Total content: {total_words} words across {len(pages)} pages — strong topical coverage.")
        score += 20
    elif total_words >= 1500:
        passes.append(f"Total content: {total_words} words — adequate depth.")
        score += 10
    else:
        issues.append({
            "severity": "warning",
            "check": f"Thin total content ({total_words} words)",
            "detail": "Generative AI models favor comprehensive coverage. Consider expanding content."
        })

    # Heading depth per page
    if heading_count >= 15:
        passes.append(f"{heading_count} total headings — rich content structure.")
        score += 20
    elif heading_count >= 8:
        passes.append(f"{heading_count} headings — reasonable structure.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": f"Only {heading_count} headings across all pages",
            "detail": "More section headings help AI models navigate and understand content hierarchy."
        })

    # H2/H3 depth
    h2_count = sum(len(p.get("h2", [])) for p in pages)
    h3_count = sum(len(p.get("h3", [])) for p in pages)

    if h2_count >= 6 and h3_count >= 3:
        passes.append(f"Strong sub-topic coverage: {h2_count} H2s + {h3_count} H3s.")
        score += 20
    elif h2_count >= 3:
        passes.append(f"Reasonable sub-topic breadth ({h2_count} H2s).")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": f"Limited sub-topic coverage ({h2_count} H2s)",
            "detail": "Each H2 represents a subtopic. More targeted H2s improve topical authority."
        })

    # Check for table of contents / skip links
    toc_keywords = ["table of contents", "on this page", "in this article", "contents", "jump to"]
    all_text = _get_all_text(pages)
    has_toc = any(k in all_text.lower() for k in toc_keywords)
    if has_toc:
        passes.append("Table of contents found — excellent for AI content navigation.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "No table of contents",
            "detail": "A ToC helps AI models quickly find specific sections within long content."
        })

    # Internal linking depth
    internal_links = sum(len(p.get("links", [])) for p in pages)
    if internal_links >= 30:
        passes.append(f"Rich internal linking ({internal_links} links) — strong topical relationships.")
        score += 10
    elif internal_links >= 15:
        passes.append(f"Good internal linking ({internal_links} links).")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": f"Limited internal linking ({internal_links} links)",
            "detail": "Internal links help AI understand content relationships and site structure."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 5: Citation Readiness ──────────────────────────────

def _check_citation_readiness(all_text):
    issues = []
    passes = []
    score = 40

    # Check for statistics (numbers with context)
    stat_patterns = [
        r"\d+%", r"\d+ percent", r"over \d+", r"more than \d+",
        r"#\d+", r"\d+ out of \d+", r"1 in \d+", r"top \d+",
    ]
    stat_count = sum(len(re.findall(p, all_text, re.IGNORECASE)) for p in stat_patterns)

    if stat_count >= 8:
        passes.append(f"Found {stat_count} statistics — highly quotable by AI.")
        score += 20
    elif stat_count >= 3:
        passes.append(f"Found {stat_count} data points/statistics.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "Few statistics or data points",
            "detail": "AI models frequently cite specific statistics. Add data to strengthen quotability."
        })

    # Check for numbered findings
    numbered_items = len(re.findall(r"^\d+\.\s", all_text, re.MULTILINE))
    if numbered_items >= 5:
        passes.append(f"{numbered_items} numbered items — structured for easy AI extraction.")
        score += 15
    elif numbered_items >= 2:
        passes.append(f"{numbered_items} numbered items found.")
        score += 5

    # Check for quotable definitions / key statements
    key_statement_patterns = [
        r"[A-Z][a-z]+ is the [a-z]+", r"[A-Z][a-z]+ are [a-z]+",
        r"the key [a-z]+", r"the most important [a-z]+",
        r"crucially", r"importantly", r"notably", r"specifically",
    ]
    key_count = sum(len(re.findall(p, all_text)) for p in key_statement_patterns)

    if key_count >= 10:
        passes.append(f"Found {key_count} key statements — strong quotable content.")
        score += 15
    elif key_count >= 5:
        passes.append(f"Found {key_count} quotable statements.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "Few quotable key statements",
            "detail": "Use phrases like 'X is the...' and 'the key...' to create quotable snippets."
        })

    # Check for source attribution (statements with sources)
    source_patterns = [
        r"according to", r"per\s+[A-Z]", r"research shows", r"studies show",
        r"reported by", r"data from", r"source:",
    ]
    source_count = sum(len(re.findall(p, all_text, re.IGNORECASE)) for p in source_patterns)
    if source_count >= 3:
        passes.append(f"Sources attributed ({source_count} citations) — credible and quotable.")
        score += 15
    elif source_count >= 1:
        passes.append("Some source citations detected.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "No attributed sources",
            "detail": "Citing sources makes content more quotable for AI-generated answers."
        })

    # Check for clear takeaways/conclusion section
    conclusion_keywords = ["in conclusion", "to summarize", "key takeaways", "bottom line", "tl;dr"]
    has_conclusion = any(k in all_text.lower() for k in conclusion_keywords)
    if has_conclusion:
        passes.append("Conclusion/summary section found — easy for AI to extract key points.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No clear conclusion or summary section",
            "detail": "A 'Key Takeaways' section is easily extracted by AI for answer snippets."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 6: Multimedia ─────────────────────────────────────

def _check_multimedia(pages):
    issues = []
    passes = []
    score = 50

    total_images = sum(len(p.get("images", [])) for p in pages)
    images_with_alt = sum(
        sum(1 for img in p.get("images", []) if img.get("alt"))
        for p in pages
    )

    # Image presence
    if total_images >= 5:
        passes.append(f"{total_images} images across pages — good visual content.")
        score += 15
    elif total_images >= 2:
        passes.append(f"{total_images} images detected.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": f"Only {total_images} images found",
            "detail": "Visual content (images, diagrams, infographics) improves content quality signals."
        })

    # Alt text quality
    if total_images > 0 and images_with_alt == total_images:
        passes.append(f"All {total_images} images have alt text — excellent accessibility + SEO.")
        score += 20
    elif total_images > 0:
        alt_ratio = images_with_alt / total_images
        if alt_ratio >= 0.7:
            passes.append(f"Good alt text coverage ({alt_ratio:.0%} of images).")
            score += 10
        else:
            issues.append({
                "severity": "warning",
                "check": f"Only {alt_ratio:.0%} of images have alt text ({images_with_alt}/{total_images})",
                "detail": "Alt text is essential for accessibility and helps AI understand image content."
            })

    # Content variety check
    script_count = sum(p.get("scripts", 0) for p in pages)
    stylesheet_count = sum(p.get("stylesheets", 0) for p in pages)
    if script_count > 0:
        passes.append(f"JavaScript detected ({script_count} scripts) — interactive features possible.")
        score += 10

    # Check for video/embedded content indicators in links
    all_links = []
    for p in pages:
        all_links.extend([l.get("href", "") for l in p.get("links", [])])

    video_platforms = ["youtube.com", "youtu.be", "vimeo.com", "wistia.com", "loom.com"]
    has_video = any(
        any(platform in link.lower() for platform in video_platforms)
        for link in all_links
    )
    if has_video:
        passes.append("Embedded video content detected — strong multimedia signal.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No embedded video content found",
            "detail": "AI models increasingly cite video content. Consider adding explainer videos or tutorials."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 7: External References ─────────────────────────────

def _check_external_references(all_links, all_text):
    issues = []
    passes = []
    score = 50

    # Count outbound links to authoritative domains
    authoritative_domains = [
        "wikipedia.org", "w3.org", "google.com", "github.com",
        "scholar.google.com", "ncbi.nlm.nih.gov", "nature.com",
        "sciencedirect.com", "forbes.com", "bloomberg.com",
        "reuters.com", "bbc.com", "cnn.com", "nytimes.com",
        "wsj.com", "economist.com", "statista.com", "pewresearch.org",
    ]

    outbound_links = []
    authoritative_links = []
    for link in all_links:
        href = link.get("href", "")
        try:
            domain = urlparse(href).netloc
            if domain:
                outbound_links.append(domain)
                if any(auth in domain for auth in authoritative_domains):
                    authoritative_links.append(domain)
        except Exception:
            pass

    if authoritative_links:
        passes.append(f"Cited {len(set(authoritative_links))} authoritative external sources — strong credibility.")
        score += 25
    elif len(set(outbound_links)) >= 3:
        passes.append(f"Outbound links to {len(set(outbound_links))} external domains — reasonable referencing.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "Few outbound links to external sources",
            "detail": "Linking to authoritative sources (studies, official data, respected publications) builds trust for AI."
        })

    # Check for reference section
    reference_keywords = ["references", "sources", "further reading", "bibliography", "citations", "external links"]
    has_refs = any(k in all_text.lower() for k in reference_keywords)
    if has_refs:
        passes.append("References section detected — clear credibility markers.")
        score += 25
    else:
        issues.append({
            "severity": "info",
            "check": "No references section found",
            "detail": "A dedicated references/sources section makes it easy for AI to verify claims."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Summary Builder ──────────────────────────────────────────────

def _build_summary(dimensions, weights):
    best_dim = max(dimensions, key=lambda k: dimensions[k]["score"])
    worst_dim = min(dimensions, key=lambda k: dimensions[k]["score"])

    total_issues = sum(len(d.get("issues", [])) for d in dimensions.values())
    total_passes = sum(len(d.get("passes", [])) for d in dimensions.values())

    summary = (
        f"GEO Score: Best in '{best_dim.replace('_', ' ').title()}', "
        f"needs work on '{worst_dim.replace('_', ' ').title()}'."
        f" {total_passes} checks pass, {total_issues} areas to improve."
    )
    return summary

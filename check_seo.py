"""Technical SEO checks — no LLM needed, pure rules-based."""

from urllib.parse import urlparse


def check_technical_seo(pages):
    """Run rules-based technical SEO checks across all pages."""
    issues = []
    passes = []
    
    if not pages:
        return {"issues": ["No pages found to analyze"], "passes": [], "score": 0}
    
    homepage = pages[0]
    
    # Title tag
    if not homepage.get("title"):
        issues.append({"severity": "critical", "check": "Missing <title> tag", "detail": "Every page needs a unique title tag."})
    elif len(homepage["title"]) < 30:
        issues.append({"severity": "warning", "check": "Title tag too short", "detail": f"'{homepage['title']}' is only {len(homepage['title'])} chars. Aim for 50-60."})
    elif len(homepage["title"]) > 70:
        issues.append({"severity": "warning", "check": "Title tag too long", "detail": f"'{homepage['title']}' is {len(homepage['title'])} chars. May be truncated in SERPs."})
    else:
        passes.append("Title tag present and properly sized.")
    
    # Meta description
    if not homepage.get("meta_description"):
        issues.append({"severity": "critical", "check": "Missing meta description", "detail": "Meta descriptions appear in search results and impact CTR."})
    elif len(homepage["meta_description"]) < 50:
        issues.append({"severity": "warning", "check": "Meta description too short", "detail": f"Aim for 150-160 characters for best SERP display."})
    elif len(homepage["meta_description"]) > 165:
        issues.append({"severity": "info", "check": "Meta description may be truncated", "detail": f"Currently {len(homepage['meta_description'])} chars. Google typically displays ~155-160."})
    else:
        passes.append("Meta description present and well-sized.")
    
    # Heading structure
    h1_count = len(homepage.get("h1", []))
    if h1_count == 0:
        issues.append({"severity": "critical", "check": "No H1 tag found", "detail": "Every page should have exactly one H1."})
    elif h1_count > 1:
        issues.append({"severity": "warning", "check": f"{h1_count} H1 tags found", "detail": "Best practice is exactly one H1 per page."})
    else:
        passes.append("H1 structure is clean.")
    
    h2_count = len(homepage.get("h2", []))
    if h2_count == 0:
        issues.append({"severity": "warning", "check": "No H2 tags found", "detail": "H2s help structure content for both users and search engines."})
    else:
        passes.append(f"{h2_count} H2s found — good content structure.")
    
    # Schema
    if not homepage.get("has_schema"):
        issues.append({"severity": "warning", "check": "No JSON-LD schema found", "detail": "Schema markup helps search engines understand your content. LocalBusiness or Organization schema is recommended."})
    else:
        passes.append("JSON-LD schema detected.")
    
    # Word count
    wc = homepage.get("word_count", 0)
    if wc < 200:
        issues.append({"severity": "warning", "check": "Thin content", "detail": f"Only {wc} words on homepage. Aim for 300+ for meaningful ranking potential."})
    elif wc < 600:
        issues.append({"severity": "info", "check": "Content could be deeper", "detail": f"{wc} words. Consider expanding to 600+ for stronger topical signals."})
    else:
        passes.append(f"Content depth: {wc} words — solid.")
    
    # Image alt text
    all_images = []
    for p in pages:
        all_images.extend(p.get("images", []))
    
    total_images = len(all_images)
    missing_alt = sum(1 for i in all_images if not i.get("alt"))
    if total_images > 0 and missing_alt > 0:
        ratio = missing_alt / total_images
        if ratio > 0.5:
            issues.append({"severity": "warning", "check": f"{missing_alt}/{total_images} images missing alt text", "detail": "Alt text is important for accessibility and image search."})
        else:
            issues.append({"severity": "info", "check": f"{missing_alt}/{total_images} images missing alt text", "detail": "A few images missing alt text — easy fix."})
    
    # Robots meta
    if homepage.get("has_robots_meta"):
        passes.append("Robots meta tag present — good for crawl control.")
    
    # Internal links
    total_links = sum(len(p.get("links", [])) for p in pages)
    if total_links < 5:
        issues.append({"severity": "info", "check": "Very few internal links", "detail": "Internal linking helps distribute page authority."})
    
    # Multi-page analysis
    if len(pages) == 1:
        issues.append({"severity": "info", "check": "Only analyzed homepage", "detail": "For a full audit, we'd crawl deeper. Consider running with max_pages=10+."})
    
    # Score calculation
    score = 100
    for issue in issues:
        if issue["severity"] == "critical":
            score -= 20
        elif issue["severity"] == "warning":
            score -= 10
        else:
            score -= 5
    score = max(0, score)
    
    return {
        "score": score,
        "issues": issues,
        "passes": passes,
    }

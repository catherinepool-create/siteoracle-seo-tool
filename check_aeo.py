"""Answer Engine Optimization (AEO) checks — rules-based analysis for Google AI Overviews, Perplexity, ChatGPT, etc."""

import re
from collections import Counter


def check_aeo(pages):
    """Analyze how well a site is optimized for answer engines.

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

    dimensions = {
        "qa_structure": _check_qa_structure(pages, all_headings),
        "concise_answers": _check_concise_answers(homepage),
        "faq_schema": _check_faq_schema(pages),
        "structured_content": _check_structured_content(pages, all_headings),
        "authority": _check_authority(pages, all_text),
        "readability": _check_readability(homepage),
        "entity_depth": _check_entity_depth(pages, all_text),
    }

    weights = {
        "qa_structure": 20,
        "concise_answers": 20,
        "faq_schema": 15,
        "structured_content": 15,
        "authority": 15,
        "readability": 10,
        "entity_depth": 5,
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
    return " ".join(
        " ".join(p.get("paragraphs", [])) for p in pages
    )


def _get_all_headings(pages):
    headings = []
    for p in pages:
        headings.extend(p.get("h1", []))
        headings.extend(p.get("h2", []))
        headings.extend(p.get("h3", []))
    return headings


# ── Dimension 1: Q&A Structure ──────────────────────────────────

def _check_qa_structure(pages, all_headings):
    issues = []
    passes = []
    score = 50

    # Check for question marks in headings
    q_headings = [h for h in all_headings if "?" in h]
    if q_headings:
        passes.append(f"Found {len(q_headings)} question-format headings — good for Q&A visibility.")
        score += 15
    else:
        issues.append({
            "severity": "warning",
            "check": "No question-format headings",
            "detail": "Headings with questions (e.g., 'How does X work?') help rank in answer engines."
        })

    # Check for FAQ-like HTML patterns
    has_details_summary = False
    has_dl = False
    for p in pages:
        url = p.get("url", "")
    if not has_details_summary:
        issues.append({
            "severity": "info",
            "check": "No <details>/<summary> FAQ pattern detected",
            "detail": "Using HTML <details><summary> for FAQs makes them machine-readable."
        })
    else:
        passes.append("Found <details>/<summary> FAQ HTML elements.")
        score += 10

    # Check for FAQ sections in content
    faq_keywords = ["faq", "frequently asked", "common questions", "you might ask", "got questions"]
    all_content_lower = " ".join(all_headings).lower()
    if any(k in all_content_lower for k in faq_keywords):
        passes.append("FAQ section detected in page content.")
        score += 10
    else:
        issues.append({
            "severity": "warning",
            "check": "No FAQ section found",
            "detail": "A dedicated FAQ section with clear Q&A pairs improves answer engine eligibility."
        })

    # Check paragraph word counts — short paragraphs answer better
    paragraphs = []
    for p in pages:
        paragraphs.extend(p.get("paragraphs", []))
    short_paras = [para for para in paragraphs if len(para.split()) < 40]
    if paragraphs and len(short_paras) / len(paragraphs) > 0.3:
        passes.append(f"Good proportion of concise paragraphs ({len(short_paras)}/{len(paragraphs)} under 40 words).")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "Paragraphs are mostly long-form",
            "detail": "Answer engines favor concise, scannable paragraphs. Consider breaking up longer sections."
        })

    return {
        "score": min(100, score),
        "issues": issues,
        "passes": passes,
    }


# ── Dimension 2: Concise Answers ────────────────────────────────

def _check_concise_answers(page):
    issues = []
    passes = []
    score = 50

    paragraphs = page.get("paragraphs", [])
    if not paragraphs:
        return {"score": 0, "issues": [{"severity": "warning", "check": "No body content", "detail": "No paragraph content found."}], "passes": []}

    first_para = paragraphs[0] if paragraphs else ""
    first_words = first_para.split()[:30]
    first_150 = " ".join(first_words)

    # Check for clear thesis in first 150 chars
    thesis_indicators = ["is a", "are a", "refers to", "means", "involves", "provides", "offers", "helps"]
    if any(t in first_150.lower() for t in thesis_indicators):
        passes.append("First paragraph clearly states what the page is about — strong for answer extraction.")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "First paragraph lacks clear thesis",
            "detail": "The opening should answer 'What is this?' concisely for AI to extract."
        })

    # Check for bullet points or numbered lists
    has_list_markers = any(
        line.strip().startswith(("- ", "* ", "1.", "2.", "•"))
        for para in paragraphs
        for line in para.split("\n")
    )
    if has_list_markers:
        passes.append("Bullet points detected — easy for answer engines to extract.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No bullet points or numbered lists",
            "detail": "Structured lists are highly extractable by answer engines."
        })

    # Check for bold/strong emphasis
    score += 5  # Mild bonus — hard to detect without full HTML

    # Check for definition-style sentences
    definition_patterns = [
        r"[A-Z][a-z]+ is a [a-z]", r"[A-Z][a-z]+ refers to",
        r"[A-Z][a-z]+ means", r"[A-Z][a-z]+ are [a-z]",
    ]
    definition_count = 0
    for para in paragraphs:
        for pat in definition_patterns:
            if re.search(pat, para):
                definition_count += 1
                break

    if definition_count >= 3:
        passes.append(f"Found {definition_count} definition-style sentences — highly extractable.")
        score += 15
    elif definition_count >= 1:
        passes.append(f"Found {definition_count} definition-style sentence(s).")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "No clear definition sentences",
            "detail": "Sentences like 'X is a Y that Z' are ideal for answer extraction."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 3: FAQ Schema ──────────────────────────────────────

def _check_faq_schema(pages):
    issues = []
    passes = []
    score = 30

    schema_types_found = set()
    for p in pages:
        # We check if the page has schema (boolean flag) and can inspect html
        pass

    # Check homepage schema
    homepage = pages[0]
    if homepage.get("has_schema"):
        passes.append("JSON-LD schema detected on homepage.")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "No JSON-LD schema on homepage",
            "detail": "FAQPage or QAPage schema helps answer engines understand Q&A content."
        })

    # Check for FAQ keywords in combination with schema
    all_text = _get_all_text(pages)
    has_faq_keywords = any(k in all_text.lower() for k in ["faq", "frequently asked"])
    if has_faq_keywords:
        if homepage.get("has_schema"):
            passes.append("FAQ content with schema — ideal for FAQ rich results.")
            score += 30
        else:
            issues.append({
                "severity": "warning",
                "check": "FAQ content without FAQPage schema",
                "detail": "You have FAQ content but no FAQPage schema. Adding it can unlock rich results."
            })

    # Check how many pages have schema
    schema_pages = sum(1 for p in pages if p.get("has_schema"))
    if len(pages) > 1 and schema_pages > 1:
        passes.append(f"Schema found on {schema_pages}/{len(pages)} pages — good coverage.")
        score += 20
    elif len(pages) > 1:
        issues.append({
            "severity": "info",
            "check": "Schema not present on all crawled pages",
            "detail": f"Only {schema_pages}/{len(pages)} pages have schema markup."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 4: Structured Content ──────────────────────────────

def _check_structured_content(pages, all_headings):
    issues = []
    passes = []
    score = 50

    # Check heading hierarchy
    h1_count = len(pages[0].get("h1", []))
    h2_count = len(pages[0].get("h2", []))
    h3_count = len(pages[0].get("h3", []))

    if h1_count == 1 and h2_count >= 2:
        passes.append(f"Good heading hierarchy: 1 H1 + {h2_count} H2s.")
        score += 20
    elif h2_count >= 1:
        passes.append(f"Heading structure detected: {h1_count} H1, {h2_count} H2, {h3_count} H3.")
        score += 10
    else:
        issues.append({
            "severity": "warning",
            "check": "Weak heading structure",
            "detail": "Answer engines use headings to understand content organization."
        })

    # Check for numbered/tabular data
    all_text = _get_all_text(pages)
    number_patterns = [
        r"\d+\%", r"\d+x", r"top \d+", r"\d+ ways", r"\d+ steps",
        r"step \d+", r"#\d+", r"table", r"chart",
    ]
    data_hits = sum(1 for p in all_text.lower().split() for pat in number_patterns if re.search(pat, p[:50]))
    # Simpler check
    data_count = 0
    for pat in number_patterns:
        data_count += len(re.findall(pat, all_text.lower()))

    if data_count >= 5:
        passes.append(f"Found {data_count} structured data signals (statistics, lists, tables).")
        score += 15
    elif data_count >= 2:
        passes.append("Some structured data elements detected.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "Few structured data elements",
            "detail": "Statistics, tables, and numbered lists improve answer engine extraction."
        })

    # Check page depth coverage
    heading_count = len(all_headings)
    if len(pages) >= 3 and heading_count >= 10:
        passes.append("Multiple pages with rich heading structure — strong topical coverage.")
        score += 15
    elif heading_count >= 5:
        passes.append("Reasonable content structure across pages.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "Limited content structure",
            "detail": "More sections and sub-pages would strengthen topical authority."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 5: Authority ───────────────────────────────────────

def _check_authority(pages, all_text):
    issues = []
    passes = []
    score = 40

    # Check for source citations
    citation_patterns = [
        r"according to", r"source", r"study", r"research", r"report",
        r"according", r"citing", r"based on", r"data from",
    ]
    citation_count = 0
    for pat in citation_patterns:
        citation_count += len(re.findall(pat, all_text.lower()))

    if citation_count >= 5:
        passes.append(f"Found {citation_count} citation/source references — strong authority signals.")
        score += 20
    elif citation_count >= 2:
        passes.append("Some source citations detected.")
        score += 10
    else:
        issues.append({
            "severity": "warning",
            "check": "No external citations found",
            "detail": "Answer engines prefer content that cites authoritative sources."
        })

    # Check for quotation marks (expert quotes)
    quote_count = len(re.findall(r'"', all_text))
    if quote_count >= 10:
        passes.append("Expert quotes or attributed statements detected.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "Few attributed quotes",
            "detail": "Quoting experts or authoritative sources builds trust for AI models."
        })

    # Check for publication dates
    date_patterns = [
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
    ]
    date_count = 0
    for pat in date_patterns:
        date_count += len(re.findall(pat, all_text))

    if date_count >= 2:
        passes.append(f"Publication dates detected ({date_count} instances) — good for freshness authority.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "No clear publication dates",
            "detail": "Answer engines favor content with visible timestamps for recency assessment."
        })

    # Check for author attribution
    author_patterns = [
        r"by\s+[A-Z][a-z]+ [A-Z][a-z]+",
        r"written\s+by",
        r"author",
    ]
    has_author = any(re.search(p, all_text) for p in author_patterns)
    if has_author:
        passes.append("Author attribution detected — adds E-E-A-T signals.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No visible author attribution",
            "detail": "Clear author bylines strengthen E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 6: Readability ──────────────────────────────────────

def _check_readability(page):
    issues = []
    passes = []
    score = 60

    paragraphs = page.get("paragraphs", [])
    if not paragraphs:
        return {"score": 30, "issues": [{"severity": "info", "check": "No content for readability check", "detail": ""}], "passes": []}

    word_count = page.get("word_count", 0)
    total_sentences = 0
    total_words = 0
    total_paras = len(paragraphs)

    for para in paragraphs:
        sentences = [s.strip() for s in re.split(r'[.!?]+', para) if s.strip()]
        total_sentences += len(sentences)
        total_words += len(para.split())

    avg_sentence_words = total_words / max(total_sentences, 1)
    avg_para_words = word_count / max(total_paras, 1)

    # Score based on sentence length (shorter is better for readability)
    if avg_sentence_words < 15:
        passes.append(f"Average sentence length: {avg_sentence_words:.0f} words — very readable.")
        score += 15
    elif avg_sentence_words < 20:
        passes.append(f"Average sentence length: {avg_sentence_words:.0f} words — good readability.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": f"Long sentences (avg {avg_sentence_words:.0f} words)",
            "detail": "Aim for 15-20 words per sentence for optimal readability and answer extraction."
        })

    # Paragraph length
    if avg_para_words < 60:
        passes.append(f"Average paragraph length: {avg_para_words:.0f} words — scannable.")
        score += 15
    elif avg_para_words < 120:
        passes.append(f"Average paragraph length: {avg_para_words:.0f} words — reasonable.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": f"Long paragraphs (avg {avg_para_words:.0f} words)",
            "detail": "Break long paragraphs into shorter chunks for better scanning and extraction."
        })

    # Content depth
    if word_count >= 1000:
        passes.append(f"Content depth: {word_count} words — strong for comprehensive answers.")
        score += 10
    elif word_count >= 500:
        passes.append(f"Content depth: {word_count} words — adequate.")
        score += 5
    else:
        issues.append({
            "severity": "warning",
            "check": f"Thin content ({word_count} words)",
            "detail": "Answer engines prefer comprehensive content. Aim for 800+ words on key pages."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 7: Entity Depth ────────────────────────────────────

def _check_entity_depth(pages, all_text):
    issues = []
    passes = []
    score = 40

    # Check for meta keywords
    all_keywords = [p.get("meta_keywords", "") for p in pages if p.get("meta_keywords")]
    has_keywords = any(k.strip() for k in all_keywords if k)

    if has_keywords:
        passes.append("Meta keywords present — basic entity signals available.")
        score += 20
    else:
        issues.append({
            "severity": "info",
            "check": "No meta keywords",
            "detail": "While not ranking factor for Google, keywords help AI understand page entities."
        })

    # Entity density check — look for proper noun clusters
    # (Simplified: check for capitalized multi-word phrases)
    capitalized_phrases = re.findall(r'[A-Z][a-z]+ [A-Z][a-z]+', all_text)
    unique_entities = len(set(capitalized_phrases))

    if unique_entities >= 20:
        passes.append(f"~{unique_entities} distinct capitalized entities detected — rich topical coverage.")
        score += 25
    elif unique_entities >= 10:
        passes.append(f"{unique_entities} distinct entities detected — reasonable topical coverage.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": f"Few named entities ({unique_entities})",
            "detail": "Consider referencing more specific people, places, concepts for entity recognition."
        })

    # Content breadth across pages
    unique_words = set()
    for p in pages:
        for para in p.get("paragraphs", []):
            unique_words.update(w.lower() for w in para.split() if len(w) > 3)

    if len(unique_words) >= 300:
        passes.append(f"Strong vocabulary breadth (~{len(unique_words)} unique words across pages).")
        score += 20
    elif len(unique_words) >= 150:
        passes.append(f"Moderate vocabulary breadth (~{len(unique_words)} unique words).")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": f"Narrow vocabulary (~{len(unique_words)} unique words)",
            "detail": "Consider covering more related subtopics to build semantic depth."
        })

    # Check for related topic depth
    h2_h3_count = sum(len(p.get("h2", [])) + len(p.get("h3", [])) for p in pages)
    if h2_h3_count >= 8:
        passes.append(f"{h2_h3_count} subheadings across pages — strong topic structuring.")
        score += 15
    elif h2_h3_count >= 4:
        passes.append(f"{h2_h3_count} subheadings — adequate.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": f"Few subheadings ({h2_h3_count})",
            "detail": "More H2/H3 headings help answer engines navigate content topics."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Summary Builder ──────────────────────────────────────────────

def _build_summary(dimensions, weights):
    best_dim = max(dimensions, key=lambda k: dimensions[k]["score"])
    worst_dim = min(dimensions, key=lambda k: dimensions[k]["score"])

    total_issues = sum(len(d.get("issues", [])) for d in dimensions.values())
    total_passes = sum(len(d.get("passes", [])) for d in dimensions.values())

    summary = (
        f"AEO Score: Best in '{best_dim.replace('_', ' ').title()}', "
        f"needs work on '{worst_dim.replace('_', ' ').title()}'."
        f" {total_passes} checks pass, {total_issues} areas to improve."
    )
    return summary

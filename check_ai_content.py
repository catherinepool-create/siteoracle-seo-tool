"""
check_ai_content.py — AI Content Detection Module for SiteOracle (Phase 1)

Scores page content for AI-generation probability using pattern-based signals.
No ML, no external APIs — pure text statistics and heuristics.

Signals analyzed:
  1. Sentence length variance (AI is unnaturally consistent)
  2. Type-token ratio (vocabulary richness — AI is lower)
  3. Named entity density (AI uses fewer proper nouns)
  4. Transition phrase frequency ("Furthermore", "In conclusion")
  5. Paragraph length variance (AI is uniform)
  6. Readability grade (AI clusters around grade 8-10)
  7. Robots.txt AI bot policy
  8. Meta tag checks (ai-generated, noai)
"""
import re
import math
from collections import Counter


# Phrases that are overrepresented in AI-generated text
TRANSITION_PHRASES = [
    "furthermore", "in conclusion", "in summary", "to summarize",
    "it is important to note", "it is worth noting", "it is crucial",
    "it is essential", "in today's digital", "in the modern",
    "when it comes to", "in this article", "this article will",
    "we will explore", "let's delve", "let's dive",
    "the landscape of", "the realm of", "the world of",
    "as we navigate", "as we move forward", "in an era of",
    "undoubtedly", "arguably", "notably", "significantly",
    "moreover", "consequently", "additionally",
    "in the context of", "serves as", "plays a pivotal role",
    "a wide range of", "a variety of", "a number of",
    "tailored to", "designed to", "aimed at",
    "in an increasingly", "ever-evolving", "ever-changing",
    "it is imperative", "it goes without saying",
    "the importance of", "the power of", "the role of",
    "by leveraging", "by harnessing", "by utilizing",
]

# AI bots to check in robots.txt
AI_BOT_UA_PATTERNS = [
    "gptbot", "chatgpt-user", "gpt",
    "ccbot", "commoncrawl",
    "bytespider", "bytedance",
    "claude-web", "claude", "anthropic",
    "google-extended",
    "perplexitybot", "perplexity",
    "cohere-ai",
    "amazonbot",
    "meta-externalagent", "facebookexternalhit",
]


def _safe_readability_grade(text):
    """Estimate Flesch-Kincaid grade level from text.
    Returns a float (grade level) or None if insufficient text.
    """
    if len(text.split()) < 20:
        return None
    
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    
    if not sentences:
        return None
    
    word_count = len(text.split())
    sentence_count = len(sentences)
    syllable_count = sum(_count_syllables(w) for w in text.split())
    
    if sentence_count == 0 or word_count == 0:
        return None
    
    # Flesch-Kincaid Grade Level = 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
    fk_grade = 0.39 * (word_count / sentence_count) + 11.8 * (syllable_count / word_count) - 15.59
    return max(0, min(20, round(fk_grade, 1)))


def _count_syllables(word):
    """Simple syllable counter for English text."""
    word = word.lower().strip()
    if not word:
        return 0
    count = 0
    vowels = "aeiouy"
    prev_is_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    if word.endswith("e"):
        count = max(1, count - 1)
    if word.endswith("le") and len(word) > 2:
        count += 1
    return max(1, count)


def check_text_signals(text):
    """
    Analyze text content for AI-generation signals.
    
    Returns dict with individual signal scores (0-100) and a composite score.
    Higher score = more likely AI-generated.
    """
    if not text or len(text.strip()) < 100:
        return {
            "score": None,
            "confidence": "low",
            "signals": {},
            "note": "Insufficient text content to analyze (need 100+ characters)",
        }
    
    signals = {}
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    word_count = len(words)
    
    # 1. Sentence length variance
    if len(sentences) >= 3:
        sent_lengths = [len(s.split()) for s in sentences]
        mean_len = sum(sent_lengths) / len(sent_lengths)
        variance = sum((l - mean_len) ** 2 for l in sent_lengths) / len(sent_lengths)
        std_dev = math.sqrt(variance)
        
        # AI text has low variance (std_dev < 5 is suspicious)
        if std_dev < 3:
            signals["sentence_variance"] = {"score": 80, "detail": "Very uniform sentence length (std_dev=%.1f)" % std_dev}
        elif std_dev < 5:
            signals["sentence_variance"] = {"score": 50, "detail": "Somewhat uniform sentence length (std_dev=%.1f)" % std_dev}
        elif std_dev < 8:
            signals["sentence_variance"] = {"score": 20, "detail": "Natural variance in sentence length (std_dev=%.1f)" % std_dev}
        else:
            signals["sentence_variance"] = {"score": 5, "detail": "High variance in sentence length (std_dev=%.1f)" % std_dev}
        
        # Average sentence length
        if 16 < mean_len < 24:
            signals["avg_sentence_length"] = {"score": 40, "detail": "Avg sentence length %.0f words — AI sweet spot" % mean_len}
        else:
            signals["avg_sentence_length"] = {"score": 5, "detail": "Avg sentence length %.0f words — outside typical AI range" % mean_len}
    else:
        signals["sentence_variance"] = {"score": 0, "detail": "Too few sentences to analyze variance"}
    
    # 2. Type-token ratio (vocabulary richness)
    if word_count >= 50:
        unique_words = set(w.lower() for w in words)
        ttr = len(unique_words) / word_count
        
        if ttr < 0.35:
            signals["type_token_ratio"] = {"score": 60, "detail": "Low vocabulary diversity (TTR=%.2f)" % ttr}
        elif ttr < 0.45:
            signals["type_token_ratio"] = {"score": 30, "detail": "Moderate vocabulary diversity (TTR=%.2f)" % ttr}
        else:
            signals["type_token_ratio"] = {"score": 5, "detail": "Good vocabulary diversity (TTR=%.2f)" % ttr}
    else:
        signals["type_token_ratio"] = {"score": 0, "detail": "Insufficient text for vocabulary analysis"}
    
    # 3. Named entity density
    # Simple heuristic: uppercase words that are not sentence-start = proper nouns
    proper_nouns = 0
    for i, w in enumerate(words):
        if w[0].isupper() and i > 0 and words[i-1][-1] not in '.!?':
            proper_nouns += 1
    
    entity_density = proper_nouns / word_count if word_count > 0 else 0
    if entity_density < 0.02:
        signals["entity_density"] = {"score": 60, "detail": "Very few proper nouns (density=%.3f)" % entity_density}
    elif entity_density < 0.05:
        signals["entity_density"] = {"score": 30, "detail": "Some proper nouns (density=%.3f)" % entity_density}
    else:
        signals["entity_density"] = {"score": 5, "detail": "Healthy named entity density (density=%.3f)" % entity_density}
    
    # 4. Transition phrase frequency
    lc_text = text.lower()
    transition_count = 0
    for phrase in TRANSITION_PHRASES:
        count = lc_text.count(phrase)
        transition_count += count
    
    transition_rate = transition_count / word_count * 1000 if word_count > 0 else 0  # per 1000 words
    if transition_rate > 25:
        signals["transition_phrases"] = {"score": 70, "detail": "High transition phrase density (%.1f/1000 words)" % transition_rate}
    elif transition_rate > 8:
        signals["transition_phrases"] = {"score": 40, "detail": "Moderate transition phrase density (%.1f/1000 words)" % transition_rate}
    else:
        signals["transition_phrases"] = {"score": 5, "detail": "Natural transition phrase usage (%.1f/1000 words)" % transition_rate}
    
    # 5. Paragraph length variance (using paragraphs from text)
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 20]
    if len(paragraphs) >= 2:
        para_lengths = [len(p.split()) for p in paragraphs]
        mean_pl = sum(para_lengths) / len(para_lengths)
        para_variance = sum((l - mean_pl) ** 2 for l in para_lengths) / len(para_lengths)
        para_std = math.sqrt(para_variance)
        
        if para_std < 15:
            signals["paragraph_variance"] = {"score": 50, "detail": "Uniform paragraph lengths (std=%.0f)" % para_std}
        else:
            signals["paragraph_variance"] = {"score": 10, "detail": "Natural paragraph length variation (std=%.0f)" % para_std}
    else:
        signals["paragraph_variance"] = {"score": 0, "detail": "Too few paragraphs to analyze"}
    
    # 6. Readability grade
    grade = _safe_readability_grade(text)
    if grade is not None:
        if 7 <= grade <= 11:
            signals["readability"] = {"score": 35, "detail": "Reads at grade %.0f level — typical AI range" % grade}
        else:
            signals["readability"] = {"score": 5, "detail": "Reads at grade %.0f level — outside typical AI range" % grade}
    
    # Calculate composite score (weighted average)
    signal_scores = [s["score"] for s in signals.values()]
    if signal_scores:
        # Closer to 0 = human, closer to 100 = AI
        composite = sum(signal_scores) / len(signal_scores)
    else:
        composite = None
    
    # Determine confidence
    confidence = "low"
    if word_count >= 300:
        confidence = "high"
    elif word_count >= 150:
        confidence = "moderate"
    
    return {
        "score": round(composite, 0) if composite is not None else None,
        "confidence": confidence,
        "signals": signals,
        "word_count": word_count,
        "note": None,
    }


def check_robots_txt(robots_content):
    """
    Check robots.txt for AI bot blocking policies.
    
    Args:
        robots_content: Raw robots.txt content string, or None
    
    Returns:
        dict with bot policy analysis
    """
    result = {
        "has_robots_txt": robots_content is not None,
        "blocked_bots": [],
        "allowed_bots": [],
        "disallowed_paths": {},
    }
    
    if not robots_content:
        return result
    
    # Parse robots.txt for AI user-agents
    lines = robots_content.split('\n')
    current_ua = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        ua_match = re.match(r'^User-agent:\s*(.+)$', line, re.IGNORECASE)
        if ua_match:
            current_ua = ua_match.group(1).strip().lower()
            continue
        
        disallow_match = re.match(r'^Disallow:\s*(.+)$', line, re.IGNORECASE)
        if disallow_match and current_ua:
            path = disallow_match.group(1).strip()
            
            # Check if current UA matches any AI bot patterns
            matched_bots = []
            for pattern in AI_BOT_UA_PATTERNS:
                if pattern in current_ua or current_ua == '*':
                    bot_name = current_ua if current_ua != '*' else 'All bots'
                    if bot_name not in matched_bots:
                        matched_bots.append(bot_name)
            
            for bot in matched_bots:
                if path:
                    if bot not in result["disallowed_paths"]:
                        result["disallowed_paths"][bot] = []
                    result["disallowed_paths"][bot].append(path)
                    if bot not in result["blocked_bots"]:
                        result["blocked_bots"].append(bot)
    
    # Check for allow directives (if Disallow is empty, bot is allowed)
    for line in lines:
        line = line.strip()
        ua_match = re.match(r'^User-agent:\s*(.+)$', line, re.IGNORECASE)
        if ua_match:
            current_ua = ua_match.group(1).strip().lower()
        
        allow_match = re.match(r'^Allow:\s*/?\s*$', line, re.IGNORECASE)
        disallow_match = re.match(r'^Disallow:\s*$', line, re.IGNORECASE)
        
        if allow_match and current_ua:
            for pattern in AI_BOT_UA_PATTERNS:
                if pattern in current_ua:
                    result["allowed_bots"].append(current_ua)
        
        if disallow_match and current_ua:
            # Empty Disallow means allowed for that UA
            for pattern in AI_BOT_UA_PATTERNS:
                if pattern in current_ua and current_ua not in result["allowed_bots"]:
                    result["allowed_bots"].append(current_ua)
    
    return result


def check_meta_tags(html):
    """
    Check HTML for AI-related meta tags.
    
    Returns:
        dict with meta tag findings
    """
    result = {
        "ai_generated_tag": False,
        "noai_robots": False,
        "has_robots_meta": False,
    }
    
    if not html:
        return result
    
    # Check for ai-generated meta
    ai_gen = re.search(r'<meta[^>]*name=["\']ai-generated["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if ai_gen:
        result["ai_generated_tag"] = True
        result["ai_generated_value"] = ai_gen.group(1)
    
    # Check for noai in robots meta
    robots_meta = re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if robots_meta:
        result["has_robots_meta"] = True
        content = robots_meta.group(1).lower()
        if "noai" in content or "noimageai" in content:
            result["noai_robots"] = True
    
    return result


def check_ai_content(pages, html=None, robots_content=None, sitemap_content=None):
    """
    Main entry point — analyzes crawled pages for AI content detection.
    
    Includes:
    - Phase 1: Pattern-based text analysis + robots.txt + meta tags
    - Phase 2A: Cross-page consistency check
    - Phase 2B: Content velocity signal (via sitemap)
    - Phase 2C: Author entity validation
    
    Args:
        pages: list of parsed page dicts from crawler.py
        html: raw HTML of the home page (for meta tag checks)
        robots_content: raw robots.txt content
        sitemap_content: raw sitemap XML content
    
    Returns:
        dict with AI content detection results
    """
    # 1. Text signal analysis (on all pages)
    all_text = " ".join(p.get("paragraphs", []) for p in pages)
    
    text_results = check_text_signals(all_text)
    
    # 2. Robots.txt analysis
    robots_results = check_robots_txt(robots_content) if robots_content else check_robots_txt(None)
    
    # 3. Meta tag analysis
    meta_results = check_meta_tags(html) if html else {}
    
    # 4. Combine into a final score
    text_score = text_results.get("score") or 0
    
    # Robots signals: blocked bots add risk
    robots_risk = 0
    if robots_results["blocked_bots"]:
        robots_risk = 10  # Sites blocking AI crawlers are often AI-generated
    elif robots_results["has_robots_txt"]:
        robots_risk = -5  # Having robots.txt at all is neutral-to-positive
    
    # Meta signals: ai-generated tag is self-reporting
    meta_risk = 0
    if meta_results.get("ai_generated_tag"):
        meta_risk = 30  # Self-disclosed AI content
    if meta_results.get("noai_robots"):
        meta_risk += 5
    
    # ── Phase 2A: Cross-Page Consistency ──
    consistency_results = check_cross_page_consistency(pages)
    consistency_score = consistency_results.get("score", 0)
    
    # ── Phase 2B: Content Velocity ──
    velocity_results = check_content_velocity(sitemap_content) if sitemap_content else {"score": 0, "note": "No sitemap available"}
    velocity_score = velocity_results.get("score", 0)
    
    # ── Phase 2C: Author Entity Validation ──
    author_results = check_author_entities(pages)
    author_score = author_results.get("score", 0)
    
    # Final weighted score (0-100 scale)
    if text_score is not None:
        final_score = min(100, max(0, round(
            text_score * 0.50 +       # Phase 1: text signals (50%)
            robots_risk +              # Phase 1: robots.txt
            consistency_score * 0.6 +  # Phase 2A: cross-page (24% weight)
            velocity_score * 0.4 +     # Phase 2B: velocity (14% weight)
            author_score * 0.5 +       # Phase 2C: authors (7.5% weight)
            meta_risk                  # Phase 1: meta tags
        )))
    else:
        final_score = None
    
    # Build issues/passes for the standard SiteOracle result format
    issues = []
    passes = []
    
    if text_score is not None and text_score >= 60:
        issues.append({
            "check": "AI Content Generation Signals",
            "detail": "Text analysis detected patterns consistent with AI-generated content. Score: %d/100 (%s confidence)." % (text_score, text_results.get("confidence", "low")),
            "severity": "warning",
        })
    
    if robots_results["blocked_bots"]:
        issues.append({
            "check": "AI Crawler Blocking",
            "detail": "%d AI bot(s) blocked in robots.txt: %s. AI-generated sites often block AI crawlers to avoid detection." % (
                len(robots_results["blocked_bots"]),
                ", ".join(robots_results["blocked_bots"][:5])
            ),
            "severity": "warning",
        })
    
    if meta_results.get("ai_generated_tag"):
        issues.append({
            "check": "Self-Disclosed AI Content",
            "detail": 'Site uses <meta name="ai-generated"> tag, indicating AI-generated content.',
            "severity": "info",
        })
    
    if text_score is not None and text_score < 30 and not robots_results["blocked_bots"]:
        passes.append("Text signals appear natural — no strong AI generation indicators detected")
    
    if robots_results["has_robots_txt"] and not robots_results["blocked_bots"]:
        passes.append("robots.txt does not block AI crawlers — good transparency signal")
    
    # Phase 2 issues/passes
    if consistency_results.get("score", 0) >= 30:
        issues.append({
            "check": "Cross-Page Style Consistency",
            "detail": consistency_results.get("note", "Writing style is suspiciously uniform across pages"),
            "severity": "warning",
        })
    elif consistency_results.get("score", 0) >= 15:
        issues.append({
            "check": "Cross-Page Style Consistency",
            "detail": consistency_results.get("note", "Writing style is relatively uniform"),
            "severity": "info",
        })
    
    if velocity_results.get("flags"):
        for flag in velocity_results.get("flags", [])[:2]:
            issues.append({
                "check": "Publishing Velocity",
                "detail": flag,
                "severity": "warning",
            })
    
    if author_results.get("score", 0) >= 10:
        issues.append({
            "check": "Author Transparency",
            "detail": author_results.get("note", "Authors are not verifiable"),
            "severity": "info",
        })
    
    return {
        "score": final_score,
        "text_analysis": text_results,
        "robots_analysis": robots_results,
        "meta_analysis": meta_results,
        "issues": issues,
        "passes": passes,
        "consistency": consistency_results,
        "velocity": velocity_results,
        "authors": author_results,
        "dimensions": {
            "ai_content_detection": {
                "score": final_score or 0,
                "text_signals": text_results.get("score", 0),
                "robots_risk": robots_risk,
                "meta_risk": meta_risk,
                "confidence": text_results.get("confidence", "low"),
                "note": text_results.get("note"),
            }
        },
        "grade": _get_grade(final_score) if final_score is not None else "unknown",
    }


def _get_grade(score):
    if score is None:
        return "unknown"
    if score < 20:
        return "A"
    elif score < 40:
        return "B"
    elif score < 60:
        return "C"
    elif score < 80:
        return "D"
    else:
        return "F"


# ── Phase 2A: Cross-Page Consistency Check ─────────────────


def _style_vector(text):
    """
    Extract a style fingerprint vector from text.
    Vectors from the same human writer will vary naturally.
    AI-generated text across pages will be suspiciously uniform.
    """
    words = text.split()
    if len(words) < 50:
        return None

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if len(sentences) < 3:
        return None

    sent_lengths = [len(s.split()) for s in sentences]
    para_breaks = text.count('\n\n')

    return {
        "avg_sentence_len": sum(sent_lengths) / len(sent_lengths),
        "sentence_len_std": math.sqrt(sum((l - sum(sent_lengths)/len(sent_lengths))**2 for l in sent_lengths) / len(sent_lengths)),
        "type_token_ratio": len(set(w.lower() for w in words)) / len(words),
        "punctuation_ratio": sum(1 for c in text if c in '.,;:!?') / len(words),
        "avg_word_len": sum(len(w) for w in words) / len(words),
        "para_density": para_breaks / len(words) * 100 if para_breaks > 0 else 0,
    }


def _vector_similarity(v1, v2):
    """Compare two style vectors. Returns similarity 0-1 (1 = identical)."""
    if not v1 or not v2:
        return None

    # Normalized euclidean similarity across all metrics
    keys = [k for k in v1 if k in v2 and k != "sentence_len_std"]
    if not keys:
        return None

    diffs = []
    for k in keys:
        a, b = v1[k], v2[k]
        if a == 0 and b == 0:
            diffs.append(0)
        else:
            # Normalize difference relative to magnitude
            denom = max(abs(a), abs(b), 0.01)
            diffs.append(abs(a - b) / denom)

    # Convert to similarity (0.5 = moderate threshold)
    avg_diff = sum(diffs) / len(diffs)
    similarity = max(0, min(1, 1 - avg_diff))
    return similarity


def check_cross_page_consistency(pages):
    """
    Compare style vectors across multiple pages on the same site.
    
    If all pages have nearly identical writing style, it's suspicious.
    Human sites show natural variation between page types (about vs blog).
    
    Returns dict with consistency analysis.
    """
    if not pages or len(pages) < 2:
        return {
            "score": 0,
            "pages_analyzed": len(pages) if pages else 0,
            "note": "Need 2+ pages to compare consistency",
            "vectors": {},
        }

    vectors = {}
    for page in pages:
        text = " ".join(page.get("paragraphs", []))
        vec = _style_vector(text)
        if vec:
            vectors[page.get("url", "unknown")[:60]] = vec

    if len(vectors) < 2:
        return {
            "score": 0,
            "pages_analyzed": len(vectors),
            "note": "Insufficient text on pages for style comparison",
            "vectors": {},
        }

    # Compare all pairs
    similarities = []
    urls = list(vectors.keys())
    for i in range(len(urls)):
        for j in range(i + 1, len(urls)):
            sim = _vector_similarity(vectors[urls[i]], vectors[urls[j]])
            if sim is not None:
                similarities.append({
                    "pages": (urls[i][:40], urls[j][:40]),
                    "similarity": round(sim, 3),
                })

    if not similarities:
        return {"score": 0, "note": "Could not compare vectors", "vectors": vectors}

    avg_similarity = sum(s["similarity"] for s in similarities) / len(similarities)

    # Score: higher similarity = more suspicious
    if avg_similarity > 0.92:
        consistency_score = 40
        note = "Suspiciously consistent style across all pages — strong AI indicator"
    elif avg_similarity > 0.85:
        consistency_score = 20
        note = "Relatively uniform style across pages — possible AI pattern"
    elif avg_similarity > 0.75:
        consistency_score = 10
        note = "Natural variation in writing style across pages"
    else:
        consistency_score = 5
        note = "Good stylistic variation between pages — human-like"

    return {
        "score": consistency_score,
        "avg_similarity": round(avg_similarity, 3),
        "pages_analyzed": len(vectors),
        "pairs_compared": len(similarities),
        "top_similarities": sorted(similarities, key=lambda x: x["similarity"], reverse=True)[:3],
        "note": note,
        "vectors": {k: {sk: round(sv, 3) for sk, sv in v.items()} for k, v in vectors.items()},
    }


# ── Phase 2B: Content Velocity Signal ──


def check_content_velocity(sitemap_content):
    """
    Analyze sitemap timestamps for AI publishing patterns.
    
    Red flags:
    - Superhuman publishing speed (50+ posts/month for a small site)
    - Batched publishing (multiple posts same hour/minute)
    - Unnatural regularity (posts every X hours exactly)
    
    Args:
        sitemap_content: Raw sitemap XML content, or None
    
    Returns:
        dict with velocity analysis
    """
    if not sitemap_content:
        return {
            "score": 0,
            "has_sitemap": False,
            "note": "No sitemap found — cannot analyze publishing velocity",
        }

    # Extract lastmod dates
    dates = re.findall(r'<lastmod[^>]*>(.*?)</lastmod>', sitemap_content, re.IGNORECASE)
    urls_in_sitemap = len(re.findall(r'<url[ >]', sitemap_content, re.IGNORECASE))

    if not dates:
        # Try <lastmod> without explicit tags
        dates = re.findall(r'(\d{4}-\d{2}-\d{2})', sitemap_content)

    if not dates or len(dates) < 3:
        return {
            "score": 0,
            "has_sitemap": True,
            "urls_in_sitemap": urls_in_sitemap or len(re.findall(r'<loc[^>]*>(.*?)</loc>', sitemap_content)),
            "note": "Not enough timestamp data for velocity analysis",
        }

    try:
        from datetime import datetime
        parsed_dates = []
        for d in dates:
            d = d.strip()
            for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    parsed_dates.append(datetime.strptime(d[:19], fmt))
                    break
                except ValueError:
                    continue
    except Exception:
        return {"score": 0, "has_sitemap": True, "note": "Could not parse timestamps"}

    if len(parsed_dates) < 3:
        return {"score": 0, "has_sitemap": True, "note": "Not enough valid dates"}

    parsed_dates.sort()

    # 1. Velocity: posts per 30 days
    total_days = (parsed_dates[-1] - parsed_dates[0]).days or 1
    posts_per_30 = len(parsed_dates) / total_days * 30

    velocity_score = 0
    if posts_per_30 > 50:
        velocity_score = 25
    elif posts_per_30 > 30:
        velocity_score = 15
    elif posts_per_30 > 15:
        velocity_score = 8
    else:
        velocity_score = 2

    # 2. Batch publishing: same-hour posts
    from collections import Counter
    hour_buckets = Counter()
    for d in parsed_dates:
        key = d.strftime("%Y-%m-%d %H:00")
        hour_buckets[key] += 1

    max_same_hour = max(hour_buckets.values()) if hour_buckets else 0
    batch_score = 0
    if max_same_hour >= 10:
        batch_score = 15
    elif max_same_hour >= 5:
        batch_score = 8
    elif max_same_hour >= 3:
        batch_score = 3

    # 3. Regularity: check for suspiciously even spacing
    if len(parsed_dates) >= 5:
        gaps = [(parsed_dates[i+1] - parsed_dates[i]).total_seconds() for i in range(len(parsed_dates)-1)]
        avg_gap = sum(gaps) / len(gaps)
        gap_std = math.sqrt(sum((g - avg_gap)**2 for g in gaps) / len(gaps))

        regularity_score = 0
        if gap_std < 300:  # Less than 5 min std dev = bot
            regularity_score = 10
        elif gap_std < 1800:  # Less than 30 min std dev = suspicious
            regularity_score = 5
    else:
        regularity_score = 0
        gap_std = None

    total_velocity = min(35, velocity_score + batch_score + regularity_score)

    flags = []
    if velocity_score >= 15:
        flags.append("High publishing velocity (%.0f posts/30 days)" % posts_per_30)
    if batch_score >= 8:
        flags.append("Batch publishing detected (%d posts in same hour)" % max_same_hour)
    if regularity_score >= 5:
        flags.append("Suspiciously regular publishing schedule")

    return {
        "score": total_velocity,
        "has_sitemap": True,
        "urls_in_sitemap": urls_in_sitemap or len(parsed_dates),
        "posts_per_30_days": round(posts_per_30, 1),
        "max_same_hour_posts": max_same_hour,
        "gap_std_seconds": round(gap_std, 1) if gap_std is not None else None,
        "flags": flags,
        "note": " | ".join(flags) if flags else "Normal publishing cadence",
    }


# ── Phase 2C: Author Entity Validation ──


def check_author_entities(pages):
    """
    Check if authors listed on the site have verifiable digital identities.
    
    Extracts author names from:
    - schema.org/author JSON-LD
    - <meta name="author"> tags
    - Byline patterns in article text
    
    Then attempts verification via simple heuristics.
    Full Knowledge Graph API integration requires API key (Phase 3).
    """
    if not pages:
        return {"score": 0, "authors_found": 0, "verified_authors": 0, "note": "No pages to analyze"}

    authors_found = set()

    for page in pages:
        html_snippet = str(page.get("paragraphs", []))
        url = page.get("url", "")

        # Check author meta tags
        meta_author = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']*)["\']', html_snippet, re.IGNORECASE)
        if meta_author:
            name = meta_author.group(1).strip()
            if name and name.lower() not in ("", "admin", "staff", "editor", "author"):
                authors_found.add(name)

        # Check byline patterns
        for p in page.get("paragraphs", []):
            byline = re.search(r'^(?:By|Written by|Author:)\s+(.+?)(?:\.|$)', p.strip(), re.IGNORECASE)
            if byline:
                name = byline.group(1).strip()
                if name and len(name) > 3 and name.lower() not in ("admin", "staff"):
                    authors_found.add(name)

        # Check JSON-LD author
        jsonld = re.search(r'"author"\s*:\s*{"@type"\s*:\s*"Person"[^}]*"name"\s*:\s*"([^"]+)"', html_snippet, re.IGNORECASE)
        if jsonld:
            authors_found.add(jsonld.group(1).strip())

    # For now, do lightweight verification:
    # - If no authors found = red flag
    # - If only generic names = red flag
    # - Real names with first+last = neutral
    generic_names = {"admin", "staff", "editor", "author", "contributor", "writer", "team", "guest"}

    verified = 0
    unverified = 0
    for author in authors_found:
        if author.lower() in generic_names:
            unverified += 1
        elif len(author.split()) >= 2:  # Has first and last name
            verified += 1
        else:
            unverified += 1

    total = len(authors_found)

    if total == 0:
        score = 15
        note = "No authors found on any page — possible ghost authorship"
    elif verified == 0 and unverified > 0:
        score = 10
        note = "Authors found but no verifiable identities — all are generic or single-name"
    elif verified / total < 0.5:
        score = 5
        note = "Some authors have real names, but many appear generic"
    else:
        score = 2
        note = "Authors with real names found — good transparency signal"

    return {
        "score": score,
        "authors_found": list(authors_found),
        "verified_authors": verified,
        "unverified_authors": unverified,
        "note": note,
        "author_count": total,
    }


if __name__ == "__main__":
    # Run self-test with known AI text
    ai_text = """
    In today's digital landscape, it is important to note that artificial intelligence
    has revolutionized the way we approach content creation. Furthermore, the integration
    of machine learning algorithms has enabled unprecedented levels of automation and efficiency.
    
    In conclusion, it is crucial to understand that the landscape of modern technology
    is ever-evolving. As we navigate this complex terrain, we must remain mindful of
    the importance of responsible AI implementation.
    
    Additionally, it is worth noting that a wide range of applications have emerged
    across various industries. From healthcare to finance, the realm of AI continues
    to expand at a remarkable pace. Moreover, the role of data-driven decision making
    has become increasingly significant.
    
    When it comes to content generation, AI-powered tools have demonstrated remarkable
    capabilities. This article will explore the key considerations for leveraging these
    technologies effectively. It is essential to understand both the opportunities and
    challenges that lie ahead.
    
    Furthermore, research has shown that AI-generated content can achieve comparable
    quality to human-written text in many contexts. However, it is imperative to maintain
    human oversight and editorial review. By leveraging AI responsibly, organizations can
    enhance productivity while maintaining quality standards.
    """
    
    result = check_text_signals(ai_text)
    print("=== AI Text Test ===")
    print(f"Score: {result['score']}/100 ({result['confidence']} confidence)")
    for name, sig in result.get("signals", {}).items():
        print(f"  {name}: {sig['score']} — {sig['detail']}")
    
    human_text = """
    My grandmother taught me to bake bread when I was seven. I remember standing
    on a wooden stool in her tiny kitchen, flour dusting my nose, watching her work the
    dough with those gnarled hands that had done it a thousand times before.
    
    "Feel it," she'd say, pressing my small palm against the warm, elastic mass.
    """
    result2 = check_text_signals(human_text)
    print(f"\n=== Human Text Test ===")
    print(f"Score: {result2['score']}/100 ({result2['confidence']} confidence)")
    for name, sig in result2.get("signals", {}).items():
        print(f"  {name}: {sig['score']} — {sig['detail']}")
    
    # Test Phase 2 features
    print("\n=== Phase 2 Tests ===")
    
    # Cross-page consistency
    mock_pages = [
        {"url": "https://example.com/about", "paragraphs": ["We are a leading company in the industry. It is important to note that our mission focuses on customer satisfaction. Furthermore, we believe in innovation and excellence. Additionally, our team is dedicated to providing the best service possible."]},
        {"url": "https://example.com/blog/post1", "paragraphs": ["In today's digital world, it is crucial to stay ahead of the curve. This article will explore the key trends shaping our industry. Moreover, we will dive into the strategies that drive success."]},
    ]
    cc = check_cross_page_consistency(mock_pages)
    print(f"Cross-page consistency: {cc['score']}/40 — {cc['note']}")
    
    # Content velocity
    from datetime import datetime, timedelta
    now = datetime.now()
    sitemap_xml = '<?xml version="1.0"?><urlset>'
    for i in range(20):
        ts = now - timedelta(hours=i*2)
        sitemap_xml += f'<url><loc>https://ex.com/p{i}</loc><lastmod>{ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")}</lastmod></url>'
    for i in range(5):
        ts = now - timedelta(hours=1, minutes=i*2)
        sitemap_xml += f'<url><loc>https://ex.com/b{i}</loc><lastmod>{ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")}</lastmod></url>'
    sitemap_xml += '</urlset>'
    cv = check_content_velocity(sitemap_xml)
    print(f"Content velocity: {cv['score']}/35 — flags: {cv.get('flags', [])}")
    
    # Author entities
    ap = [{"url": "https://ex.com", "paragraphs": ['<meta name="author" content="John Smith">']}]
    ae = check_author_entities(ap)
    print(f"Author entities: {ae['score']}/15 — {ae['note']}")

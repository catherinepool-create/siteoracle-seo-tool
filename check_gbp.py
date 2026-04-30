"""Google Business Profile (GBP) alignment checks — how well a site supports local SEO."""

import re
from urllib.parse import urlparse


def check_gbp(pages, business_info=None):
    """Analyze how well a website aligns with Google Business Profile data.

    Args:
        pages: List of parsed page dicts from crawler.py
        business_info: Optional dict with 'name', 'phone', 'address', 'categories', 'hours'

    Returns:
        dict with score, dimensions, issues, passes, summary
    """
    if not pages:
        return _empty_result("No pages to analyze")

    homepage = pages[0]
    all_text = _get_all_text(pages)
    all_h1 = _get_all_h1(pages)
    all_links = _get_all_links(pages)
    all_html = " ".join(str(p) for p in pages)  # crude HTML for iframe detection

    if business_info is None:
        business_info = extract_business_info(pages)

    dimensions = {
        "nap_consistency": _check_nap(homepage, pages, business_info, all_text),
        "local_schema": _check_local_schema(pages),
        "maps_integration": _check_maps(pages, all_links, all_text),
        "local_content": _check_local_content(pages, all_text, all_h1),
        "service_clarity": _check_services(pages, all_h1, all_text),
        "reviews_reputation": _check_reviews(all_text),
        "contact_visibility": _check_contact(homepage, pages, all_text, all_links),
    }

    weights = {
        "nap_consistency": 25,
        "local_schema": 20,
        "contact_visibility": 15,
        "maps_integration": 10,
        "local_content": 15,
        "service_clarity": 10,
        "reviews_reputation": 5,
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
        "business_info_extracted": business_info,
        "issues": all_issues,
        "passes": all_passes,
        "summary": _build_summary(dimensions, weights, business_info),
    }


def extract_business_info(pages):
    """Try to auto-detect business details from website content and schema.

    Returns dict with keys: name, phone, address, categories, hours
    """
    info = {
        "name": None,
        "phone": None,
        "address": None,
        "categories": [],
        "hours": None,
    }

    # Use regex to find NAP data
    all_text = _get_all_text(pages)
    homepage = pages[0] if pages else {}

    # Phone number detection (US format)
    phone_patterns = [
        r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
        r'\+\d{1,2}\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
    ]
    for pat in phone_patterns:
        phones = re.findall(pat, all_text)
        if phones:
            info["phone"] = phones[0]
            break

    # Extract location from LocalBusiness schema
    for p in pages:
        url = p.get("url", "")
        # Check for schema JSON-LD in raw page would require fetching again
        # For now, use heuristics
        pass

    # Try to find address patterns
    address_patterns = [
        r'\d+\s+[A-Za-z\s]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl)\b',
        r'\d+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+\s+[A-Z]{2}\s+\d{5}',
    ]
    for pat in address_patterns:
        addresses = re.findall(pat, all_text)
        if addresses:
            info["address"] = addresses[0]
            break

    # Try to extract business name from title/H1
    title = homepage.get("title", "")
    h1s = homepage.get("h1", [])
    if title:
        # Usually "Name | Tagline" or "Name - Tagline"
        parts = re.split(r'\s*[|\-–—]\s*', title)
        if parts:
            info["name"] = parts[0].strip()
    if not info["name"] and h1s:
        info["name"] = h1s[0]

    return info


def _empty_result(reason):
    return {
        "score": 0,
        "dimensions": {},
        "issues": [{"severity": "critical", "check": "No data", "detail": reason}],
        "passes": [],
        "business_info_extracted": {},
        "summary": reason,
    }


def _get_all_text(pages):
    return " ".join(" ".join(p.get("paragraphs", [])) for p in pages)


def _get_all_h1(pages):
    h1s = []
    for p in pages:
        h1s.extend(p.get("h1", []))
    return h1s


def _get_all_links(pages):
    links = []
    for p in pages:
        links.extend(p.get("links", []))
    return links


# ── Dimension 1: NAP Consistency ────────────────────────────────

def _check_nap(homepage, pages, business_info, all_text):
    issues = []
    passes = []
    score = 30

    has_name = bool(business_info.get("name"))
    has_phone = bool(business_info.get("phone"))
    has_address = bool(business_info.get("address"))

    # Business name on homepage
    biz_name = business_info.get("name", "")
    if biz_name:
        name_in_h1 = any(biz_name.lower() in h.lower() for h in homepage.get("h1", []))
        name_in_title = biz_name.lower() in homepage.get("title", "").lower()
        name_in_content = biz_name.lower() in all_text.lower()

        signals = sum([name_in_h1, name_in_title, name_in_content])
        if signals >= 2:
            passes.append(f"Business name '{biz_name}' appears consistently ({signals}/3 checks).")
            score += 20
        elif signals >= 1:
            passes.append(f"Business name '{biz_name}' detected on homepage.")
            score += 10
        else:
            issues.append({
                "severity": "warning",
                "check": f"Business name '{biz_name}' not prominent on homepage",
                "detail": "Ensure your business name appears in the H1, title tag, and body content."
            })
    else:
        issues.append({
            "severity": "warning",
            "check": "Could not auto-detect business name",
            "detail": "Unable to confirm business name presence. Add it to title tag and H1."
        })

    # Phone number
    if has_phone:
        passes.append(f"Phone number detected: {business_info['phone']}")
        score += 20
    else:
        issues.append({
            "severity": "critical",
            "check": "No phone number found",
            "detail": "A phone number should appear on every page (typically in header/footer)."
        })

    # Address
    if has_address:
        passes.append(f"Physical address detected: {business_info['address']}")
        score += 15
    else:
        issues.append({
            "severity": "warning",
            "check": "No physical address detected",
            "detail": "Service-area businesses should list service areas. Physical businesses need a clear address."
        })

    # Check consistency across pages (NAP should match on all pages)
    if has_phone:
        phone_consistency = sum(
            1 for p in pages
            if business_info["phone"] in str(p)
        )
        if len(pages) > 1 and phone_consistency == len(pages):
            passes.append(f"Phone consistent across all {len(pages)} pages.")
            score += 15
        elif len(pages) > 1 and phone_consistency >= len(pages) * 0.5:
            passes.append(f"Phone found on {phone_consistency}/{len(pages)} pages.")
            score += 5

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 2: Local Schema ───────────────────────────────────

def _check_local_schema(pages):
    issues = []
    passes = []
    score = 30

    # Check for schema presence
    has_schema = any(p.get("has_schema") for p in pages)
    if has_schema:
        passes.append("JSON-LD schema detected — foundation for local SEO.")
        score += 20
    else:
        issues.append({
            "severity": "critical",
            "check": "No structured data (JSON-LD schema) found",
            "detail": "LocalBusiness schema is essential. Include name, address, phone, opening hours, and geo coordinates."
        })

    # Check schema coverage
    schema_pages = [p for p in pages if p.get("has_schema")]
    if has_schema and len(schema_pages) == len(pages):
        passes.append(f"Schema on all {len(pages)} pages — excellent coverage.")
        score += 20

    # Check for LocalBusiness specific indicators in content
    local_biz_signals = [
        "localbusiness", "local business", "store hours", "opening hours",
        "open today", "closed on", "hours of operation",
    ]
    all_text = _get_all_text(pages)
    biz_signal_count = sum(
        1 for s in local_biz_signals if s in all_text.lower()
    )
    if biz_signal_count >= 2:
        passes.append(f"Found {biz_signal_count} local business signals in content.")
        score += 15

    # Check for reviews/rating schema indicators
    review_signals = ["rating", "review", "stars", "average rating"]
    has_review_signals = any(s in all_text.lower() for s in review_signals)
    if has_review_signals:
        passes.append("Review signals detected — consider adding AggregateRating schema.")
        score += 10

    # Check for location-specific keywords near schema content
    location_patterns = [
        r"(serving|located in|based in|proudly serving)\s+[A-Za-z\s]+",
        r"(Los Angeles|New York|Chicago|San Francisco|Miami|Seattle|Austin|Denver|Portland|Boston|Dallas|Houston|Atlanta|Phoenix|Philadelphia)",
    ]
    for pat in location_patterns:
        locations = re.findall(pat, all_text, re.IGNORECASE)
        if locations:
            passes.append(f"Location detected in content: {locations[0]}")
            score += 10
            break

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 3: Maps Integration ──────────────────────────────

def _check_maps(pages, all_links, all_text):
    issues = []
    passes = []
    score = 30

    # Check for Google Maps links
    maps_links = [
        l.get("href", "") for l in all_links
        if "maps.google" in l.get("href", "").lower()
        or "maps.app.goo.gl" in l.get("href", "").lower()
        or "goo.gl/maps" in l.get("href", "").lower()
    ]
    if maps_links:
        passes.append(f"Google Maps link detected ({len(maps_links)} instance(s)).")
        score += 25
    else:
        issues.append({
            "severity": "warning",
            "check": "No Google Maps link found",
            "detail": "Add a 'Get Directions' link to your Google Maps location."
        })

    # Check for embedded map iframe
    iframe_patterns = [
        r'<iframe[^>]*maps\.google[^>]*>',
        r'<iframe[^>]*google\.com/maps[^>]*>',
    ]
    combined_text = " ".join(str(p) for p in pages)
    has_iframe = any(re.search(p, combined_text, re.IGNORECASE) for p in iframe_patterns)
    if has_iframe:
        passes.append("Embedded Google Maps iframe on page — excellent for local SEO.")
        score += 25
    else:
        issues.append({
            "severity": "info",
            "check": "No embedded Google Maps on page",
            "detail": "An embedded map helps both users and search engines confirm location."
        })

    # Check for "directions" link text
    direction_links = [
        l for l in all_links
        if any(k in l.get("text", "").lower() for k in ["directions", "get here", "find us"])
    ]
    if direction_links:
        passes.append(f"'{direction_links[0].get('text', '')}' link found.")
        score += 15

    # Check for neighborhood/city context
    neighborhood_patterns = [
        r"(near|close to|next to|across from|behind)\s+[A-Za-z\s]+",
    ]
    for pat in neighborhood_patterns:
        nearby = re.findall(pat, all_text, re.IGNORECASE)
        if nearby:
            passes.append(f"Nearby landmarks mentioned: {nearby[0]}")
            score += 10
            break

    # Check for embedded Google Maps iframe detection via raw string

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 4: Local Content ─────────────────────────────────

def _check_local_content(pages, all_text, all_h1):
    issues = []
    passes = []
    score = 40

    # City / neighborhood mentions
    us_cities = [
        "Los Angeles", "New York", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
        "Fort Worth", "Columbus", "Charlotte", "Indianapolis", "San Francisco",
        "Seattle", "Denver", "Nashville", "Oklahoma City", "El Paso", "Washington",
        "Boston", "Las Vegas", "Portland", "Memphis", "Louisville", "Baltimore",
        "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Sacramento", "Mesa",
        "Kansas City", "Atlanta", "Omaha", "Colorado Springs", "Raleigh",
        "Long Beach", "Virginia Beach", "Miami", "Oakland", "Minneapolis",
        "Tampa", "Tulsa", "Arlington", "New Orleans",
    ]

    city_mentions = []
    for city in us_cities:
        if city.lower() in all_text.lower():
            city_mentions.append(city)

    if city_mentions:
        passes.append(f"Local mentions: {', '.join(city_mentions[:5])}{'...' if len(city_mentions) > 5 else ''}")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "No local city/area mentions in content",
            "detail": "Mention your city, neighborhood, or service area in body content for local relevance."
        })

    # "Near me" optimization
    near_me_signals = ["near me", "nearby", "in the area", "local"]
    near_me_count = sum(1 for s in near_me_signals if s in all_text.lower())
    if near_me_count >= 2:
        passes.append(f"Local intent signals found: '{', '.join(near_me_signals[:near_me_count])}'")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "Weak 'near me' optimization",
            "detail": "Use phrases like 'near me' and 'in [city]' in content for local search visibility."
        })

    # Service areas mentioned
    area_patterns = [
        r"(serving|covering|available in|deliver to|service area)\s+[A-Za-z\s,]+",
    ]
    area_found = False
    for pat in area_patterns:
        matches = re.findall(pat, all_text, re.IGNORECASE)
        if matches:
            passes.append(f"Service area mentioned: {matches[0]}")
            score += 15
            area_found = True
            break

    if not area_found:
        issues.append({
            "severity": "info",
            "check": "No explicit service area description",
            "detail": "Clearly state where you provide service (e.g., 'Serving Los Angeles and Orange County')."
        })

    # Local events / community involvement
    community_signals = [
        "community", "local", "neighborhood", "supporting", "partnered",
        "charity", "sponsor", "local organization",
    ]
    community_count = sum(1 for s in community_signals if s in all_text.lower())
    if community_count >= 3:
        passes.append(f"Community involvement mentioned ({community_count} signals) — strong local relevance.")
        score += 15
    elif community_count >= 1:
        passes.append(f"Local community mention detected.")
        score += 5

    # Landmark references
    landmark_patterns = [r"(minutes from|steps from|blocks from|located near)\s+[A-Za-z\s]+"]
    for pat in landmark_patterns:
        landmarks = re.findall(pat, all_text, re.IGNORECASE)
        if landmarks:
            passes.append(f"Local landmarks referenced: {landmarks[0]}")
            score += 10
            break

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 5: Service Clarity ────────────────────────────────

def _check_services(pages, all_h1, all_text):
    issues = []
    passes = []
    score = 40

    # Check for dedicated service/product pages
    service_urls = [
        p.get("url", "") for p in pages
        if any(k in p.get("url", "").lower() for k in
               ["/service", "/services", "/product", "/products",
                "/pricing", "/work", "/portfolio", "/offerings"])
    ]
    if service_urls:
        passes.append(f"Dedicated service/product pages found ({len(service_urls)}).")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "No dedicated service/product pages",
            "detail": "Local businesses need clear pages for each service or product they offer."
        })

    # Service keywords in content
    service_keywords = [
        "we offer", "we provide", "our services", "our products",
        "we specialize", "services include", "we do",
    ]
    service_count = sum(1 for s in service_keywords if s in all_text.lower())
    if service_count >= 3:
        passes.append(f"Services clearly described in content ({service_count} signals).")
        score += 20
    elif service_count >= 1:
        passes.append("Services mentioned in content.")
        score += 10
    else:
        issues.append({
            "severity": "info",
            "check": "Services not clearly described in content",
            "detail": "Use clear language like 'We offer X, Y, and Z' on your homepage."
        })

    # Pricing visibility
    pricing_signals = ["pricing", "starting at", "as low as", "rates", "prices", "$"]
    has_pricing = any(s in all_text.lower() for s in pricing_signals)
    if has_pricing:
        passes.append("Pricing information available — helps customer decision-making.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No pricing information found",
            "detail": "Even approximate pricing helps with both users and local search signals."
        })

    # CTA presence
    cta_signals = [
        "book now", "schedule", "get a quote", "request", "contact us",
        "call now", "get started", "free consultation",
    ]
    cta_count = sum(1 for s in cta_signals if s in all_text.lower())
    if cta_count >= 2:
        passes.append(f"CTAs found: '{', '.join(cta_signals[:cta_count])}'")
        score += 15
    elif cta_count >= 1:
        passes.append("At least one CTA detected.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "No clear call-to-action buttons",
            "detail": "CTAs like 'Book Now' or 'Get a Free Quote' drive conversions."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 6: Reviews & Reputation ───────────────────────────

def _check_reviews(all_text):
    issues = []
    passes = []
    score = 40

    # Check for testimonials
    testimonial_keywords = [
        "testimonial", "testimonials", "what our customers say", "client love",
        "success stories", "case studies", "customer feedback",
    ]
    has_testimonials = any(k in all_text.lower() for k in testimonial_keywords)
    if has_testimonials:
        passes.append("Testimonials section detected — social proof for local SEO.")
        score += 20
    else:
        issues.append({
            "severity": "info",
            "check": "No testimonials or reviews section",
            "detail": "Customer testimonials build trust and provide unique content for local rankings."
        })

    # Check for star ratings
    star_pattern = re.compile(r'[★☆⭐]|star rating|\d+/?\d+\s*stars?')
    has_stars = bool(star_pattern.search(all_text))
    if has_stars:
        passes.append("Star ratings visible on site — review signals detected.")
        score += 20
    else:
        issues.append({
            "severity": "info",
            "check": "No visible star ratings or review scores",
            "detail": "Consider displaying review scores from Google, Yelp, or other platforms."
        })

    # Check for review platform links
    review_platforms = [
        "yelp.com", "google.com/reviews", "trustpilot.com", "bbb.org",
        "facebook.com/reviews", "angi.com",
    ]
    for link_text in [all_text]:
        platform_links = [p for p in review_platforms if p in link_text.lower()]
        if platform_links:
            passes.append(f"Review platform(s) mentioned: {', '.join(platform_links)}")
            score += 20
            break
    else:
        issues.append({
            "severity": "info",
            "check": "No review platform links",
            "detail": "Link to your Google Reviews, Yelp, or Trustpilot profile from the site."
        })

    # Star rating count/quality mention
    rating_pattern = r"\d\.\d\s*/\s*\d"
    has_rating = bool(re.search(rating_pattern, all_text))
    if has_rating:
        passes.append("Specific rating score found — strong reputation signal.")
        score += 15

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Dimension 7: Contact Visibility ─────────────────────────────

def _check_contact(homepage, pages, all_text, all_links):
    issues = []
    passes = []
    score = 30

    # Dedicated contact page
    contact_pages = [
        p.get("url", "") for p in pages
        if "contact" in p.get("url", "").lower()
        or any("contact" in h.lower() for h in p.get("h1", []))
    ]
    if contact_pages:
        passes.append(f"Contact page found.")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "No dedicated contact page",
            "detail": "A contact page is essential for local SEO. Include phone, email, address, and contact form."
        })

    # Phone in header/footer
    # Check first few and last paragraphs for phone
    paragraphs = homepage.get("paragraphs", [])
    header_footer_text = " ".join(paragraphs[:3] + paragraphs[-3:])
    phone_pattern = r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
    has_phone_prominent = bool(re.search(phone_pattern, header_footer_text))

    if has_phone_prominent:
        passes.append("Phone number prominently displayed in header/footer area.")
        score += 20
    else:
        issues.append({
            "severity": "warning",
            "check": "Phone number not prominently displayed",
            "detail": "Phone should appear in the header or footer of every page — ideally with a 'tap to call' link."
        })

    # Email
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, all_text)
    if emails:
        passes.append(f"Email contact found: {emails[0]}")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No email address found",
            "detail": "Add a contact email in the footer or on the contact page."
        })

    # Contact form
    form_patterns = [r'<form', r'contact-form', r'type="submit"', r'contact form']
    has_form = any(re.search(p, " ".join(str(pg) for pg in pages), re.IGNORECASE)
                   for p in form_patterns)
    if has_form:
        passes.append("Contact form detected — convenient for users.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No contact form found",
            "detail": "A contact form makes it easy for customers to reach out without leaving the site."
        })

    # Click-to-call phone (tel: links)
    tel_links = [l for l in all_links if "tel:" in l.get("href", "")]
    if tel_links:
        passes.append("Click-to-call phone link detected — mobile-friendly.")
        score += 15
    else:
        issues.append({
            "severity": "info",
            "check": "No click-to-call phone link (tel:)",
            "detail": "Use tel:+1234567890 links for mobile users to tap and call immediately."
        })

    # Hours of operation
    hours_keywords = ["hours", "open", "closed", "monday", "tuesday", "wednesday",
                       "thursday", "friday", "saturday", "sunday",
                       "mon", "tue", "wed", "thu", "fri", "sat", "sun",
                       "business hours", "store hours"]
    hours_count = sum(1 for k in hours_keywords if k in all_text.lower())
    if hours_count >= 5:
        passes.append("Business hours prominently displayed.")
        score += 15
    elif hours_count >= 3:
        passes.append("Business hours mentioned.")
        score += 5
    else:
        issues.append({
            "severity": "info",
            "check": "Business hours not found",
            "detail": "Display your hours of operation for both users and Google's local understanding."
        })

    return {"score": min(100, score), "issues": issues, "passes": passes}


# ── Summary Builder ──────────────────────────────────────────────

def _build_summary(dimensions, weights, business_info):
    best_dim = max(dimensions, key=lambda k: dimensions[k]["score"])
    worst_dim = min(dimensions, key=lambda k: dimensions[k]["score"])

    total_issues = sum(len(d.get("issues", [])) for d in dimensions.values())
    total_passes = sum(len(d.get("passes", [])) for d in dimensions.values())

    biz_name = business_info.get("name", "business")
    phone = business_info.get("phone", "no phone detected")

    summary = (
        f"GBP Alignment for '{biz_name}': Best in '{best_dim.replace('_', ' ').title()}', "
        f"needs work on '{worst_dim.replace('_', ' ').title()}'."
        f" {total_passes} checks pass, {total_issues} areas to improve."
        f" Phone: {phone}."
    )
    return summary

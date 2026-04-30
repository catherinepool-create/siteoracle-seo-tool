"""Competitive comparison — run SiteOracle on multiple sites and compare results."""

from check_seo import check_technical_seo
from check_aeo import check_aeo
from check_geo import check_geo
from check_gbp import check_gbp
from crawler import crawl


def compare_sites(sites, max_pages=5):
    """Run full analysis on multiple sites and return comparable results.

    Args:
        sites: list of dicts like [{"url": "...", "name": "..."}, ...]
               or list of URL strings (names auto-generated)
        max_pages: max pages to crawl per site

    Returns:
        dict with combined results for comparison rendering
    """
    # Normalize input
    normalized = []
    for s in sites:
        if isinstance(s, str):
            normalized.append({"url": s, "name": _short_name(s)})
        else:
            normalized.append(s)

    results = []
    for site in normalized:
        result = _analyze_site(site["url"], site["name"], max_pages)
        results.append(result)

    return _build_comparison(results)


def _short_name(url):
    """Extract a short name from a URL."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    return domain.replace("www.", "")


def _analyze_site(url, name, max_pages):
    """Run full analysis on a single site."""
    try:
        pages = crawl(url, max_pages=max_pages)
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "error": str(e),
            "seo": {"score": 0},
            "aeo": {"score": 0},
            "geo": {"score": 0},
            "gbp": {"score": 0},
            "combined": 0,
        }

    if not pages:
        return {
            "name": name,
            "url": url,
            "error": "Could not fetch site",
            "seo": {"score": 0},
            "aeo": {"score": 0},
            "geo": {"score": 0},
            "gbp": {"score": 0},
            "combined": 0,
        }

    seo = check_technical_seo(pages)
    aeo = check_aeo(pages)
    geo = check_geo(pages)
    gbp = check_gbp(pages)

    combined = round(
        seo["score"] * 0.35
        + aeo["score"] * 0.25
        + geo["score"] * 0.25
        + gbp["score"] * 0.15
    )

    return {
        "name": name,
        "url": url,
        "error": None,
        "seo": seo,
        "aeo": aeo,
        "geo": geo,
        "gbp": gbp,
        "combined": combined,
        "pages_analyzed": len(pages),
    }


def _build_comparison(results):
    """Build a comparison view from individual results."""
    # Find the winner
    winner = max(results, key=lambda r: r.get("combined", 0))
    loser = min(results, key=lambda r: r.get("combined", 0))

    # Build gap analysis
    gaps = []
    if winner.get("error") is None and loser.get("error") is None:
        w_seo = winner.get("seo", {}).get("score", 0)
        l_seo = loser.get("seo", {}).get("score", 0)
        if w_seo - l_seo >= 10:
            gaps.append({
                "area": "Technical SEO",
                "leader": winner["name"],
                "gap": w_seo - l_seo,
            })

        w_aeo = winner.get("aeo", {}).get("score", 0)
        l_aeo = loser.get("aeo", {}).get("score", 0)
        if w_aeo - l_aeo >= 10:
            gaps.append({
                "area": "Answer Engine Optimization (AEO)",
                "leader": winner["name"],
                "gap": w_aeo - l_aeo,
            })

        w_geo = winner.get("geo", {}).get("score", 0)
        l_geo = loser.get("geo", {}).get("score", 0)
        if w_geo - l_geo >= 10:
            gaps.append({
                "area": "Generative Engine Optimization (GEO)",
                "leader": winner["name"],
                "gap": w_geo - l_geo,
            })

        w_gbp = winner.get("gbp", {}).get("score", 0)
        l_gbp = loser.get("gbp", {}).get("score", 0)
        if w_gbp - l_gbp >= 10:
            gaps.append({
                "area": "Google Business Profile",
                "leader": winner["name"],
                "gap": w_gbp - l_gbp,
            })

    return {
        "sites": results,
        "winner": winner["name"],
        "loser": loser["name"],
        "winner_score": winner.get("combined", 0),
        "loser_score": loser.get("combined", 0),
        "gap": winner.get("combined", 0) - loser.get("combined", 0),
        "gaps": gaps,
        "error": None,
    }


def generate_comparison_report(comparison):
    """Generate a text summary of the comparison."""
    lines = []
    lines.append("═" * 60)
    lines.append("           SITEORACLE — COMPETITIVE COMPARISON")
    lines.append("═" * 60)
    lines.append("")

    for site in comparison["sites"]:
        status = "✅" if site.get("error") is None else "❌"
        lines.append(f"{status} {site['name']}")
        if site.get("error"):
            lines.append(f"   Error: {site['error']}")
        else:
            lines.append(f"   Combined: {site['combined']}/100")
            lines.append(f"   SEO: {site['seo']['score']}/100  AEO: {site['aeo']['score']}/100  "
                         f"GEO: {site['geo']['score']}/100  GBP: {site['gbp']['score']}/100")
            lines.append(f"   Pages: {site.get('pages_analyzed', 0)}")
        lines.append("")

    if comparison["gap"] > 0:
        lines.append(f"🏆 Winner: {comparison['winner']} ({comparison['winner_score']}/100)")
        lines.append(f"📉 Trail:  {comparison['loser']} ({comparison['loser_score']}/100)")
        lines.append(f"📊 Gap:    {comparison['gap']} points")
        lines.append("")

        if comparison.get("gaps"):
            lines.append("🔍 Key Differentiators:")
            for g in comparison["gaps"]:
                lines.append(f"   • {g['area']}: {g['leader']} leads by {g['gap']} points")

    return "\n".join(lines)

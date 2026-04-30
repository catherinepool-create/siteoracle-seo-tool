#!/usr/bin/env python3
"""SiteOracle CLI — analyze any website for SEO/AEO/GEO/GBP."""

import argparse
import sys
import os
from pathlib import Path

from crawler import crawl
from check_seo import check_technical_seo
from check_aeo import check_aeo
from check_geo import check_geo
from check_gbp import check_gbp
from analyzer import analyze_site
from reporter import generate_report, generate_html_report


def main():
    parser = argparse.ArgumentParser(
        description="SiteOracle — AI-powered SEO/AEO/GEO/GBP website analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py https://example.com
  python cli.py https://example.com --pages 10
  python cli.py https://example.com --engine openai -o report.html
  python cli.py https://example.com --compare https://competitor.com
  python cli.py https://example.com --no-ai
  python cli.py https://example.com --monitor weekly
        """,
    )
    parser.add_argument("url", help="Website URL to analyze")
    parser.add_argument("--pages", type=int, default=5,
                        help="Max pages to crawl (default: 5)")
    parser.add_argument("--output", "-o", help="Output HTML report to file")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI analysis (rules-based only)")
    parser.add_argument("--engine", choices=["openai", "claude", "deepseek"], default="deepseek",
                        help="AI engine for deep analysis (default: deepseek)")
    parser.add_argument("--screenshot", help="Analyze a screenshot instead of URL")
    parser.add_argument("--compare", help="Compare with a competitor URL")
    parser.add_argument("--monitor", choices=["daily", "weekly", "monthly"],
                        help="Set up scheduled monitoring")
    parser.add_argument("--business-name", help="Business name for GBP alignment")
    parser.add_argument("--business-phone", help="Business phone for GBP alignment")

    args = parser.parse_args()

    # Handle screenshot mode
    if args.screenshot:
        if not os.path.exists(args.screenshot):
            print(f"Error: Screenshot not found: {args.screenshot}")
            sys.exit(1)
        print(f"Analyzing screenshot: {args.screenshot}")
        from analyzer import analyze_screenshot
        result = analyze_screenshot(args.screenshot)
        print(result)
        return

    # Crawl primary site
    print(f"\nCrawling {args.url}...")
    pages = crawl(args.url, max_pages=args.pages)
    if not pages:
        print("Error: Could not fetch the website. Check the URL and try again.")
        sys.exit(1)
    print(f"Crawled {len(pages)} pages\n")

    # Build business info for GBP
    business_info = {}
    if args.business_name:
        business_info["name"] = args.business_name
    if args.business_phone:
        business_info["phone"] = args.business_phone

    # Run all checks
    print("Running Technical SEO checks...")
    seo_results = check_technical_seo(pages)

    print("Running Answer Engine Optimization (AEO) checks...")
    aeo_results = check_aeo(pages)

    print("Running Generative Engine Optimization (GEO) checks...")
    geo_results = check_geo(pages)

    print("Running Google Business Profile (GBP) alignment checks...")
    gbp_results = check_gbp(pages, business_info if business_info else None)

    # AI Analysis
    ai_analysis = ""
    if not args.no_ai:
        ai_analysis = _run_ai_analysis(pages, args.engine)

    # HTML report
    if args.output:
        html = generate_html_report(args.url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis)
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"\nHTML report saved to: {args.output}")

    # Print summary
    report = generate_report(args.url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis)
    print(report)

    # Combined score
    combined = round(
        seo_results["score"] * 0.35
        + aeo_results["score"] * 0.25
        + geo_results["score"] * 0.25
        + gbp_results["score"] * 0.15
    )
    print(f"Combined Score: {combined}/100")
    print(f"Report: {args.output or 'stdout'}")
    print("Done.")


def _run_ai_analysis(pages, engine):
    """Run AI-powered deep analysis with fallback handling."""
    api_key_env = {
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }.get(engine, "OPENAI_API_KEY")

    if not os.getenv(api_key_env):
        print(f"Warning: No {api_key_env} set. Skipping AI analysis.")
        return ""

    print(f"Running AI analysis ({engine})...", end=" ", flush=True)
    try:
        from analyzer import analyze_site
        result = analyze_site(pages, engine=engine)
        print("Done.")
        return result
    except Exception as e:
        print(f"AI analysis failed: {e}")
        return f"AI analysis attempted but failed: {e}"


if __name__ == "__main__":
    main()

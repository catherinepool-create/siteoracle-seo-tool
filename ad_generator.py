"""AI Ad Generator — turns SiteOracle scan results into ad scripts + Higgsfield video ads.

Pipeline:
  1. After a scan, extract the site's value prop, keywords, tone
  2. Generate an ad script (structured for Marketing Studio modes)
  3. Optionally generate the actual video via Higgsfield CLI

This is the bridge between "scan your site" and "advertise it".
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path


# ── Ad Script Templates ──────────────────────────────────────────

_AD_FORMATS = {
    "ugc": {
        "name": "UGC Testimonial",
        "description": "Authentic user-generated style testimonial — one person talking to camera about how the product/service solved their problem.",
        "duration": "15-30 seconds",
        "structure": [
            "Hook: Relatable problem statement (first 2-3 seconds)",
            "Discovery: How they found the solution",
            "Result: Before/after transformation",
            "CTA: Go to website / use promo code",
        ],
    },
    "product_showcase": {
        "name": "Product Showcase",
        "description": "Clean product-focused visual — features, benefits, close-ups.",
        "duration": "15-30 seconds",
        "structure": [
            "Hook: Visual of product in use",
            "Feature 1: Key benefit with on-screen text",
            "Feature 2: Differentiator vs competitors",
            "CTA: Visit site / learn more",
        ],
    },
    "tv_spot": {
        "name": "TV Spot / Brand Ad",
        "description": "Polished, high-production brand commercial — music, energy, fast cuts.",
        "duration": "15-30 seconds",
        "structure": [
            "Logo reveal + brand statement (first 2s)",
            "Lifestyle shots showing the problem",
            "Product as the hero solution",
            "Tagline + CTA with branding",
        ],
    },
    "ugc_unboxing": {
        "name": "Unboxing / First Look",
        "description": "Unboxing or first-impression style — genuine reaction to receiving the product.",
        "duration": "20-45 seconds",
        "structure": [
            "Package arrival / opening (first 3s)",
            "First impressions — what stands out",
            "Features demonstrated one by one",
            "Final verdict + CTA",
        ],
    },
}


def _run_higgsfield(args: list) -> dict:
    """Run a Higgsfield CLI command and return parsed result."""
    try:
        result = subprocess.run(
            ["higgsfield"] + args,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "higgsfield CLI not found. Install with: npm install -g @higgsfield/cli",
            "exit_code": -1,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Higgsfield command timed out after 120s",
            "exit_code": -1,
        }


def generate_ad_script(
    site_url: str,
    format_name: str = "ugc",
    brand_name: str = "",
    value_prop: str = "",
    keywords: list = None,
    tone: str = "professional",
) -> dict:
    """Generate a structured ad script based on site scan context.

    Args:
        site_url: The website URL being advertised
        format_name: Ad format key (ugc, product_showcase, tv_spot, ugc_unboxing)
        brand_name: Optional brand/company name
        value_prop: Optional value proposition from scan
        keywords: Optional list of keywords from scan
        tone: Brand voice tone (professional, casual, enthusiastic, authoritative)

    Returns:
        Dict with script structure, suggested hook, format info
    """
    fmt = _AD_FORMATS.get(format_name, _AD_FORMATS["ugc"])
    domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")

    # Build hook suggestions
    if not value_prop:
        value_prop = f"Check out {domain}"

    hooks = [
        f"Tired of [problem]? {domain} has the solution.",
        f"Everyone's talking about {domain} — here's why.",
        f"I found something you need to see: {domain}",
        f"Stop [doing thing the hard way]. Try {domain} instead.",
    ]

    if keywords:
        kw_hook = f"Looking for {' and '.join(keywords[:2])}? {domain} delivers."
        hooks.insert(0, kw_hook)

    return {
        "format": fmt,
        "brand": brand_name or domain,
        "domain": domain,
        "value_prop": value_prop,
        "suggested_hooks": hooks,
        "keywords": keywords or [],
        "tone": tone,
        "script_outline": fmt["structure"],
        "estimated_duration": fmt["duration"],
    }


def generate_video_ad(
    script: dict,
    mode: str = "ugc",
    product_url: str = "",
    duration: int = 15,
    aspect_ratio: str = "9:16",
) -> dict:
    """Submit an ad to Higgsfield Marketing Studio for video generation.

    Args:
        script: The script dict from generate_ad_script()
        mode: Marketing Studio mode (ugc, product_showcase, tv_spot, ugc_unboxing)
        product_url: URL to fetch product from
        duration: Video duration in seconds
        aspect_ratio: Video aspect ratio

    Returns:
        Dict with generation result
    """
    # Check if Higgsfield is installed
    which = subprocess.run(["which", "higgsfield"], capture_output=True, text=True)
    if which.returncode != 0:
        return {
            "success": False,
            "status": "cli_not_found",
            "message": "higgsfield CLI not available on this server. Install with: npm install -g @higgsfield/cli",
        }

    prompt = f"{script.get('value_prop', '')} — {script.get('brand', '')}"
    if script.get("keywords"):
        prompt += f". Keywords: {', '.join(script['keywords'][:5])}"

    results = []

    # Step 1: Fetch product if URL provided
    if product_url:
        results.append({
            "step": "fetch_product",
            "status": "pending",
            "message": f"Would fetch product from {product_url}",
        })

    # Step 2: Generate ad
    cmd = [
        "generate", "create", "marketing_studio_video",
        "--prompt", prompt,
        "--mode", mode,
        "--duration", str(duration),
        "--aspect_ratio", aspect_ratio,
        "--resolution", "720p",
        "--wait",
    ]

    if product_url:
        cmd.extend(["--url", product_url])

    hf_result = _run_higgsfield(cmd)

    results.append({
        "step": "generate_ad",
        "status": "completed" if hf_result["success"] else "failed",
        "message": hf_result["stdout"][:500] if hf_result["success"] else hf_result["stderr"][:500],
        "raw": hf_result,
    })

    return {
        "success": hf_result["success"],
        "results": results,
        "job_output": hf_result.get("stdout", ""),
    }


def get_available_formats() -> dict:
    """Return all available ad formats with descriptions."""
    return {k: {"name": v["name"], "description": v["description"], "duration": v["duration"]}
            for k, v in _AD_FORMATS.items()}

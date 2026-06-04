"""
SiteOracle unified API server — sits in front of Streamlit.
Handles /api/* routes directly, proxies everything else to Streamlit.
"""

import json
import os
import sys
import argparse

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pydantic import BaseModel
from emailer import capture_lead, send_drip_now
import uvicorn
import httpx

app = FastAPI(title="SiteOracle API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Streamlit backend URL (set via CLI arg)
STREAMLIT_URL = "http://127.0.0.1:8501"


def run_scan(target_url: str, max_pages: int = 5, biz_name: str | None = None):
    """Run the full scan pipeline and return results dict."""
    from crawler import crawl as _crawl, fetch_page as _fetch_page
    from check_seo import check_technical_seo as _seo
    from check_aeo import check_aeo as _aeo
    from check_geo import check_geo as _geo
    from check_gbp import check_gbp as _gbp

    pages = _crawl(target_url, max_pages=max_pages)
    if not pages:
        return {"error": f"Could not fetch {target_url}"}

    html, _ = _fetch_page(target_url)
    biz_info = {"name": biz_name} if biz_name else None
    seo = _seo(pages)
    aeo = _aeo(pages)
    geo = _geo(pages, html=html, url=target_url)
    gbp_check = _gbp(pages, biz_info)
    ai_vis = geo.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)

    combined = round(
        seo["score"] * 0.20
        + aeo["score"] * 0.15
        + geo["score"] * 0.25
        + gbp_check["score"] * 0.10
        + ai_vis * 0.30
    )

    return {
        "url": target_url,
        "scores": {
            "seo": seo["score"],
            "aeo": aeo["score"],
            "geo": geo["score"],
            "gbp": gbp_check["score"],
            "ai_visibility": ai_vis,
            "combined": combined,
        },
        "issues": {
            "seo": seo.get("issues", []),
            "aeo": aeo.get("issues", []),
            "geo": geo.get("issues", []),
            "gbp": gbp_check.get("issues", []),
        },
        "passes": {
            "seo": seo.get("passes", []),
            "aeo": aeo.get("passes", []),
            "geo": geo.get("passes", []),
            "gbp": gbp_check.get("passes", []),
        },
        "summary": {
            "pages_crawled": len(pages),
            "total_issues": (
                len(seo.get("issues", []))
                + len(aeo.get("issues", []))
                + len(geo.get("issues", []))
                + len(gbp_check.get("issues", []))
            ),
        },
    }


@app.get("/api/scan")
async def api_scan(
    url: str = Query(..., description="URL to scan"),
    pages: int = Query(5, description="Max pages to crawl"),
    biz: str | None = Query(None, description="Business name for GBP check"),
):
    """Scan a URL and return JSON results."""
    if not url.startswith("http"):
        url = "https://" + url
    result = run_scan(url, max_pages=pages, biz_name=biz)
    return JSONResponse(content=result)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


class LeadCapture(BaseModel):
    email: str
    source: str = "popup"


@app.post("/api/lead-capture")
async def api_lead_capture(lead: LeadCapture):
    """Capture a lead email and send drip email #1 immediately."""
    captured = capture_lead(lead.email, lead.source)
    if captured:
        ok = send_drip_now(lead.email, 0)
        return {
            "status": "ok",
            "email": lead.email,
            "drip_email_1_sent": ok,
            "message": "Checklist sent! Check your inbox.",
        }
    return {"status": "ok", "email": lead.email, "message": "Already subscribed."}


@app.get("/api/lead-capture")
async def api_lead_capture_get(email: str = Query(...), source: str = "popup"):
    """GET variant — simpler for popup forms."""
    if not email or "@" not in email:
        return JSONResponse({"status": "error", "message": "Invalid email"}, status_code=400)
    captured = capture_lead(email, source)
    if captured:
        ok = send_drip_now(email, 0)
        return {"status": "ok", "email": email, "drip_email_1_sent": ok}
    return {"status": "ok", "email": email, "message": "Already subscribed."}


@app.get("/api/drip-stats")
async def api_drip_stats():
    """Get drip sequence stats."""
    from emailer import _load_leads
    leads = _load_leads()
    total = len(leads)
    unsubscribed = sum(1 for l in leads if l.get("unsubscribed"))
    by_state = {}
    for l in leads:
        s = l.get("drip_state", 0)
        by_state[s] = by_state.get(s, 0) + 1
    return {
        "total_leads": total,
        "unsubscribed": unsubscribed,
        "active": total - unsubscribed,
        "by_drip_state": by_state,
    }


@app.post("/api/process-drip")
async def api_process_drip():
    """Trigger the drip processor manually."""
    from emailer import process_drip as _pd
    result = _pd()
    return {"status": "ok", "result": result}


# ── Catch-all: proxy everything else to Streamlit ──────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def proxy_to_streamlit(request: Request, path: str):
    """Proxy non-API requests to the Streamlit backend."""
    target_url = f"{STREAMLIT_URL}/{path}"
    query = str(request.url.query)
    if query:
        target_url += f"?{query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=await request.body(),
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
    except httpx.ConnectError:
        return HTMLResponse("<h1>503 — Streamlit backend not available</h1>", status_code=503)
    except Exception as e:
        return HTMLResponse(f"<h1>502 — Proxy error: {e}</h1>", status_code=502)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    parser.add_argument("--streamlit-url", default="http://127.0.0.1:8501")
    args = parser.parse_args()
    STREAMLIT_URL = args.streamlit_url
    uvicorn.run(app, host="0.0.0.0", port=args.port)

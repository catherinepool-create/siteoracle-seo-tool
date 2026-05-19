"""SiteOracle JSON API — lightweight HTTP server for Canva App integration.
Runs alongside the Streamlit app on a configurable port (default: 8081).
"""

import json
import os
import re
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread

# Import existing scan modules
from crawler import crawl, fetch_page
from check_seo import check_technical_seo
from check_aeo import check_aeo
from check_geo import check_geo
from check_gbp import check_gbp


API_PORT = int(os.environ.get("API_PORT", "8081"))
HOST = "0.0.0.0"


class ScanAPIHandler(BaseHTTPRequestHandler):
    """Handles JSON API requests for site scanning."""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/scan":
            urls = params.get("url", [])
            if not urls:
                self._send_json({"error": "Missing ?url= parameter"}, status=400)
                return

            url = urls[0]
            if not url.startswith("http"):
                url = "https://" + url

            max_pages = int(params.get("pages", [5])[0])
            biz_name = params.get("biz", [None])[0]

            try:
                result = self._run_scan(url, max_pages, biz_name)
                self._send_json(result)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._add_cors_headers()
        self.end_headers()

    def _add_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._add_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _run_scan(self, url: str, max_pages: int, biz_name: str = None) -> dict:
        """Run a full scan and return JSON results."""
        pages = crawl(url, max_pages=max_pages)
        if not pages:
            return {"error": f"Could not fetch {url}. Check the URL and try again."}

        homepage_html, _ = fetch_page(url)

        seo = check_technical_seo(pages)
        aeo = check_aeo(pages)
        geo = check_geo(pages, html=homepage_html, url=url)
        biz_info = {"name": biz_name} if biz_name else None
        gbp = check_gbp(pages, biz_info)

        ai_vis_score = geo.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)
        combined = round(
            seo["score"] * 0.20
            + aeo["score"] * 0.15
            + geo["score"] * 0.25
            + gbp["score"] * 0.10
            + ai_vis_score * 0.30
        )

        def _collect_items(data, key):
            items = []
            for item in data.get(key, []):
                if isinstance(item, dict):
                    items.append(item)
                else:
                    items.append({"text": str(item)})
            return items

        return {
            "url": url,
            "scores": {
                "seo": seo["score"],
                "aeo": aeo["score"],
                "geo": geo["score"],
                "gbp": gbp["score"],
                "ai_visibility": ai_vis_score,
                "combined": combined,
            },
            "issues": {
                "seo": _collect_items(seo, "issues"),
                "aeo": _collect_items(aeo, "issues"),
                "geo": _collect_items(geo, "issues"),
                "gbp": _collect_items(gbp, "issues"),
            },
            "passes": {
                "seo": _collect_items(seo, "passes"),
                "aeo": _collect_items(aeo, "passes"),
                "geo": _collect_items(geo, "passes"),
                "gbp": _collect_items(gbp, "passes"),
            },
            "summary": {
                "pages_crawled": len(pages),
                "total_issues": (
                    len(seo.get("issues", []))
                    + len(aeo.get("issues", []))
                    + len(geo.get("issues", []))
                    + len(gbp.get("issues", []))
                ),
            },
        }


def start_api_server():
    """Start the API server in the current thread."""
    server = HTTPServer((HOST, API_PORT), ScanAPIHandler)
    print(f"[SiteOracle API] Listening on http://{HOST}:{API_PORT}")
    server.serve_forever()


def start_api_in_background():
    """Start the API server in a background thread. Call this from start.sh or app.py."""
    thread = Thread(target=start_api_server, daemon=True)
    thread.start()
    print(f"[SiteOracle API] Started in background on port {API_PORT}")
    return thread


if __name__ == "__main__":
    start_api_server()

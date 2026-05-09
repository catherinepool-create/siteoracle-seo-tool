"""Resend email integration — triggers drip sequence after a free scan."""

import os
import json
import urllib.request
import urllib.error


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = "Catherine <catherine@squadconsole.com>"


def _send(to: str, subject: str, html: str) -> bool:
    """Send a single email via Resend API. Returns True on success."""
    if not RESEND_API_KEY:
        return False
    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=8)
        return True
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def send_scan_report(
    to: str,
    site_url: str,
    seo_score: int,
    aeo_score: int,
    geo_score: int,
    gbp_score: int,
    ai_score: int,
    combined: int,
    top_issues: list,
) -> bool:
    """Email 1 — immediate scan report."""
    score_color = "#22c55e" if combined >= 70 else "#f59e0b" if combined >= 40 else "#ef4444"
    issues_html = "".join(
        f'<tr><td style="padding:10px 0; border-bottom:1px solid #30363d; color:#e6edf3;">'
        f'<span style="color:{"#ef4444" if i.get("severity")=="critical" else "#f59e0b"}">●</span> '
        f'<strong>{i.get("check","")}</strong><br>'
        f'<span style="color:#8b949e;font-size:13px;">{i.get("detail","")}</span></td></tr>'
        for i in top_issues[:3]
    )
    html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="text-align:center;margin-bottom:32px;">
    <span style="font-size:28px;font-weight:800;color:#e6edf3;">🔍 SiteOracle</span>
  </div>
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <p style="color:#8b949e;margin:0 0 8px;">Your scan results for</p>
    <p style="color:#58a6ff;font-weight:700;margin:0 0 24px;font-size:18px;">{site_url}</p>
    <div style="text-align:center;margin-bottom:28px;">
      <div style="font-size:72px;font-weight:800;color:{score_color};line-height:1;">{combined}</div>
      <div style="color:#8b949e;font-size:14px;margin-top:4px;">Combined Score / 100</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center;">
      <div style="background:#0e1117;border-radius:8px;padding:12px;">
        <div style="font-size:24px;font-weight:700;color:#e6edf3;">{seo_score}</div>
        <div style="font-size:11px;color:#8b949e;">SEO</div>
      </div>
      <div style="background:#0e1117;border-radius:8px;padding:12px;">
        <div style="font-size:24px;font-weight:700;color:#e6edf3;">{aeo_score}</div>
        <div style="font-size:11px;color:#8b949e;">AEO</div>
      </div>
      <div style="background:#0e1117;border-radius:8px;padding:12px;">
        <div style="font-size:24px;font-weight:700;color:#e6edf3;">{geo_score}</div>
        <div style="font-size:11px;color:#8b949e;">GEO</div>
      </div>
      <div style="background:#0e1117;border-radius:8px;padding:12px;">
        <div style="font-size:24px;font-weight:700;color:#e6edf3;">{gbp_score}</div>
        <div style="font-size:11px;color:#8b949e;">GBP</div>
      </div>
    </div>
  </div>
  {'<div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px 32px;margin-bottom:24px;"><h3 style="color:#e6edf3;margin:0 0 16px;">🎯 Top Issues to Fix</h3><table style="width:100%;border-collapse:collapse;">' + issues_html + '</table></div>' if issues_html else ''}
  <div style="text-align:center;margin-bottom:24px;">
    <a href="https://squadconsole.com/#scan" style="display:inline-block;background:#ff6b6b;color:#fff;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:700;font-size:16px;">Run Another Scan →</a>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">SiteOracle by SquadConsole · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a></p>
</div>
</body></html>"""
    return _send(to, f"Your SiteOracle Report — {site_url} scored {combined}/100", html)

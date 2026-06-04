"""
Email integration — sends via Brevo API.

- Immediate scan report email
- Lead capture + drip sequence (5 emails over 14 days)
- Partnership outreach emails

Requires BREVO_API_KEY in environment.
"""

import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
FROM_NAME = "Catherine"
FROM_ADDRESS = "catherine@squadconsole.com"

# ── Lead storage ────────────────────────────────────────────────
LEADS_FILE = os.path.expanduser("~/.siteoracle/leads.json")
_LEADS_LOCK = False  # poor man's lock, replaced by file atomicity


def _load_leads() -> list:
    """Load all leads from JSON storage."""
    if not os.path.exists(LEADS_FILE):
        return []
    try:
        with open(LEADS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_leads(leads: list) -> None:
    """Save leads to JSON storage."""
    os.makedirs(os.path.dirname(LEADS_FILE), exist_ok=True)
    with open(LEADS_FILE, "w") as f:
        json.dump(leads, f, indent=2)


def capture_lead(email: str, source: str = "popup") -> dict:
    """
    Capture a new lead or update an existing one.
    Returns the lead dict with drip_state info.
    """
    leads = _load_leads()
    now = datetime.now(timezone.utc).isoformat()

    # Check if this email already exists
    for lead in leads:
        if lead.get("email") == email:
            lead["last_seen"] = now
            lead["source"] = source
            _save_leads(leads)
            return lead

    new_lead = {
        "email": email,
        "source": source,
        "captured_at": now,
        "last_seen": now,
        "drip_state": 0,          # 0 = none sent yet, 1-5 = last email sent
        "drip_sent_at": None,     # ISO timestamp of last drip email sent
        "unsubscribed": False,
        "metadata": {},
    }
    leads.append(new_lead)
    _save_leads(leads)
    return new_lead


# ── Drip templates ──────────────────────────────────────────────

DRIP_TEMPLATES = [
    {
        "subject": "Your AI Visibility Checklist is here",
        "delay_days": 0,  # send immediately
        "html": """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <p style="color:#ff6b6b;font-weight:700;font-size:13px;letter-spacing:.12em;text-transform:uppercase;margin:0 0 12px;">Free Download</p>
    <h2 style="color:#e6edf3;font-size:22px;margin:0 0 16px;">✅ AI Visibility Checklist</h2>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 20px;">Here's your 10-point checklist for getting your site cited by ChatGPT, Perplexity, Gemini, and Google AI Overviews.</p>
    <div style="background:#0e1117;border-radius:8px;padding:16px;margin-bottom:20px;">
      <ol style="color:#e6edf3;font-size:14px;line-height:2;margin:0;padding-left:20px;">
        <li>✅ AI crawler access via robots.txt</li>
        <li>✅ JSON-LD structured data present</li>
        <li>✅ FAQPage schema type</li>
        <li>✅ Content citability signals</li>
        <li>✅ Author attribution (schema / byline)</li>
        <li>✅ Sentence length variance</li>
        <li>✅ Vocabulary diversity</li>
        <li>✅ Transition phrase usage</li>
        <li>✅ Readability grade</li>
        <li>✅ No AI-written indicators</li>
      </ol>
    </div>
    <p style="color:#8b949e;font-size:14px;line-height:1.6;">Run these checks on any site with <a href="https://squadconsole.com" style="color:#58a6ff;">SiteOracle's free scanner</a> — it scores all 10 automatically in 60 seconds.</p>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">
    Sent by SiteOracle · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a><br>
    <a href="%%unsubscribe%%" style="color:#30363d;">Unsubscribe</a>
  </p>
</div></body></html>""",
    },
    {
        "subject": "Tip: The #1 schema that gets you cited by ChatGPT",
        "delay_days": 1,
        "html": """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <h2 style="color:#e6edf3;font-size:20px;margin:0 0 16px;">🧠 FAQPage Schema = ChatGPT Gold</h2>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;">When someone asks "How do I improve my site's SEO?" in ChatGPT, the AI pulls answers from FAQPage schema markup. Sites with clear Q&A structured data are <strong style="color:#e6edf3;">3x more likely</strong> to be cited in AI responses.</p>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;">Quick win: Add FAQPage schema to your most-visited pages. Each question + answer pair becomes citation fuel for every AI that indexes your site.</p>
    <div style="background:#0e1117;border-radius:8px;padding:16px;">
      <p style="color:#e6edf3;font-size:13px;font-weight:700;margin:0 0 8px;">Example JSON-LD snippet:</p>
      <code style="color:#8b949e;font-size:12px;line-height:1.6;display:block;">
{<br>
&nbsp;"@type": "FAQPage",<br>
&nbsp;"mainEntity": [{<br>
&nbsp;&nbsp;"@type": "Question",<br>
&nbsp;&nbsp;"name": "Your question here",<br>
&nbsp;&nbsp;"acceptedAnswer": {<br>
&nbsp;&nbsp;&nbsp;"@type": "Answer",<br>
&nbsp;&nbsp;&nbsp;"text": "Your answer here"<br>
&nbsp;&nbsp;}<br>
&nbsp;}]<br>
}
      </code>
    </div>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">
    SiteOracle by SquadConsole · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a><br>
    <a href="%%unsubscribe%%" style="color:#30363d;">Unsubscribe</a>
  </p>
</div></body></html>""",
    },
    {
        "subject": "Deep dive: How Perplexity picks its sources",
        "delay_days": 4,
        "html": """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <h2 style="color:#e6edf3;font-size:20px;margin:0 0 16px;">🔍 How Perplexity Decides Who to Cite</h2>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;">Perplexity's citation algorithm looks for three things:</p>
    <ol style="color:#e6edf3;font-size:15px;line-height:2;padding-left:20px;">
      <li><strong>Freshness</strong> — Recently updated content ranks higher. Pages with <code style="color:#58a6ff;">dateModified</code> schema get priority.</li>
      <li><strong>Authority signals</strong> — Author bylines and <code style="color:#58a6ff;">author</code> schema markup dramatically increase trust scores.</li>
      <li><strong>Structured clarity</strong> — Pages with clear headings, tables, and lists are more likely to be extracted for answers.</li>
    </ol>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:16px 0 0;">Run a free <a href="https://squadconsole.com" style="color:#58a6ff;">SiteOracle scan</a> to see exactly how Perplexity evaluates your site today.</p>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">
    SiteOracle by SquadConsole · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a><br>
    <a href="%%unsubscribe%%" style="color:#30363d;">Unsubscribe</a>
  </p>
</div></body></html>""",
    },
    {
        "subject": "Case study: From 0 to 3 AI citations in 2 weeks",
        "delay_days": 7,
        "html": """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <h2 style="color:#e6edf3;font-size:20px;margin:0 0 16px;">📈 Real Results: Small SaaS, Big AI Presence</h2>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;">A B2B SaaS client in the project management space was getting zero AI citations. They were already ranking #3-5 on Google for key terms, but ChatGPT and Perplexity never mentioned them.</p>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;"><strong style="color:#e6edf3;">What we fixed:</strong></p>
    <ul style="color:#e6edf3;font-size:15px;line-height:2;padding-left:20px;">
      <li>Unblocked GPTBot in robots.txt (was blocking all AI crawlers)</li>
      <li>Added FAQPage schema to 5 key pages</li>
      <li>Restructured comparison pages into table format</li>
      <li>Added author attribution with schema markup</li>
    </ul>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:16px 0 0;"><strong style="color:#e6edf3;">Result:</strong> Within 14 days, they were cited by ChatGPT (in 2 responses), Perplexity (in 3), and Google AI Overview (once). Their combined score went from 32 → 71.</p>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">
    <a href="https://squadconsole.com" style="color:#58a6ff;font-weight:700;">Run your free scan →</a><br><br>
    SiteOracle by SquadConsole · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a><br>
    <a href="%%unsubscribe%%" style="color:#30363d;">Unsubscribe</a>
  </p>
</div></body></html>""",
    },
    {
        "subject": "Your full AI visibility score is waiting",
        "delay_days": 10,
        "html": """<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:40px 20px;">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;margin-bottom:24px;">
    <h2 style="color:#e6edf3;font-size:20px;margin:0 0 16px;">🎯 One Click. Full Scan. Free.</h2>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 16px;">You've got the checklist. You've got the tips. Now see exactly where your site stands.</p>
    <p style="color:#8b949e;font-size:15px;line-height:1.6;margin:0 0 20px;">SiteOracle scans your site across <strong style="color:#e6edf3;">5 dimensions</strong> — SEO, AEO, GEO, GBP, AI Visibility — and gives you a combined score out of 100 with prioritized fixes. Free, no login required.</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="https://squadconsole.com" style="display:inline-block;background:#ff6b6b;color:#fff;padding:16px 40px;border-radius:10px;text-decoration:none;font-weight:700;font-size:18px;">Scan Your Site Now →</a>
    </div>
  </div>
  <p style="color:#30363d;font-size:12px;text-align:center;">
    SiteOracle by SquadConsole · <a href="https://squadconsole.com" style="color:#30363d;">squadconsole.com</a><br>
    <a href="%%unsubscribe%%" style="color:#30363d;">Unsubscribe</a>
  </p>
</div></body></html>""",
    },
]


# ── Core email send ─────────────────────────────────────────────

def _send(to: str, subject: str, html_content: str) -> bool:
    """Send a single email via Brevo API. Returns True on success."""
    if not BREVO_API_KEY:
        print("No BREVO_API_KEY set — skipping send")
        return False
    payload = json.dumps({
        "sender": {"name": FROM_NAME, "email": FROM_ADDRESS},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content,
    }).encode()
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Brevo API error ({e.code}): {body[:300]}")
        return False
    except Exception as e:
        print(f"Brevo send error: {e}")
        return False


# ── Drip engine ─────────────────────────────────────────────────

def process_drip() -> dict:
    """
    Process the drip queue for all active leads.
    Called by cron — checks who's due for their next email and sends it.

    Returns a report dict: {sent: N, skipped: N, errors: [...], total_checked: N}
    """
    leads = _load_leads()
    now = datetime.now(timezone.utc)
    result = {"sent": 0, "skipped": 0, "errors": [], "total_checked": len(leads)}

    for lead in leads:
        if lead.get("unsubscribed"):
            result["skipped"] += 1
            continue

        drip_state = lead.get("drip_state", 0)
        if drip_state >= len(DRIP_TEMPLATES):
            # All emails sent — nothing more to do
            result["skipped"] += 1
            continue

        template = DRIP_TEMPLATES[drip_state]
        # Calculate when this email should be sent
        captured = datetime.fromisoformat(lead["captured_at"])
        due_time = captured.timestamp() + (template["delay_days"] * 86400)

        if now.timestamp() >= due_time:
            # Send it
            html = template["html"].replace("%%unsubscribe%%", "#")
            ok = _send(lead["email"], template["subject"], html)
            if ok:
                lead["drip_state"] = drip_state + 1
                lead["drip_sent_at"] = now.isoformat()
                result["sent"] += 1
            else:
                result["errors"].append(lead["email"])
        else:
            result["skipped"] += 1

    _save_leads(leads)
    return result


def send_drip_now(email: str, template_index: int = 0) -> bool:
    """
    Send a specific drip email to a lead right now.
    Used for sending Email #1 immediately after capture.
    """
    if template_index >= len(DRIP_TEMPLATES):
        return False
    template = DRIP_TEMPLATES[template_index]
    html = template["html"].replace("%%unsubscribe%%", "#")
    return _send(email, template["subject"], html)


# ── Scan report email ───────────────────────────────────────────

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
    """Email 1 — immediate scan report via Brevo."""
    score_color = "#22c55e" if combined >= 70 else "#f59e0b" if combined >= 40 else "#ef4444"
    issues_html = "".join(
        f'<tr><td style="padding:10px 0; border-bottom:1px solid #30363d; color:#e6edf3;">'
        f'<span color:{"#ef4444" if i.get("severity")=="critical" else "#f59e0b"}>●</span> '
        f'<strong>{i.get("check","")}</strong><br>'
        f'<span style="color:#8b949e;font-size:13px;">{i.get("detail","")}</span></td></tr>'
        for i in top_issues[:3]
    )
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0e1117;font-family:Inter,sans-serif;">
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


# ── Partnership outreach ────────────────────────────────────────

def send_partnership_email(to: str, subject: str, body_text: str) -> bool:
    """Send a plain-text partnership outreach email via Brevo."""
    if not BREVO_API_KEY:
        return False
    payload = json.dumps({
        "sender": {"name": FROM_NAME, "email": FROM_ADDRESS},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body_text,
    }).encode()
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Brevo partnership send error ({e.code}): {body[:300]}")
        return False
    except Exception as e:
        print(f"Brevo partnership send error: {e}")
        return False


# ── CLI mode for cron ───────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "process-drip":
        result = process_drip()
        print(json.dumps(result))
    elif len(sys.argv) > 1 and sys.argv[1] == "list-leads":
        leads = _load_leads()
        for lead in leads:
            print(f'{lead["email"]} | drip_state={lead["drip_state"]} | source={lead["source"]} | unsubscribed={lead.get("unsubscribed",False)}')
        print(f"\nTotal: {len(leads)} leads")
    elif len(sys.argv) > 2 and sys.argv[1] == "capture":
        email = sys.argv[2]
        source = sys.argv[3] if len(sys.argv) > 3 else "cli"
        lead = capture_lead(email, source)
        ok = send_drip_now(email, 0)
        print(f"Captured {email} (source={source}) — drip email #1 sent: {ok}")
    else:
        print("Usage:")
        print("  python emailer.py process-drip     # Process drip queue")
        print("  python emailer.py list-leads       # List all leads")
        print("  python emailer.py capture <email>  # Capture one lead + send drip #1")

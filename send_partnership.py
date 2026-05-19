#!/usr/bin/env python3
"""
Send SiteOracle partnership outreach emails via Brevo.
Usage:
    python3 send_partnership.py --to partner@company.com --template hosting --name "John"
    python3 send_partnership.py --to partner@company.com --template agency
    python3 send_partnership.py --to partner@company.com --template platform --name "Sarah"
    python3 send_partnership.py --to partner@company.com --template lender --company "First Mortgage"
"""

import sys
import os
import json
import urllib.request
import urllib.error

# Add workspace to path
sys.path.insert(0, os.path.expanduser("~/workspace/siteoracle"))
from emailer import send_partnership_email

TEMPLATES = {
    "hosting": {
        "subject": "Free SEO audit tool for your hosting customers",
        "body": """Hi {name},

Quick intro: I built SiteOracle — an SEO + AI visibility scanner that checks websites across 5 dimensions (technical SEO, answer engines, generative engine optimization, local search, and AI bot crawlability).

Your customers build websites with {company}. SiteOracle tells them if those sites are actually discoverable.

I'd love to offer it as a free value-add for your hosting plans:
- Free scan: no login, 60-second results
- White-label option available
- Pro reports ($49/mo) — revenue share on upgrades
- Zero engineering on your end (iframe embed or API)

Quick demo: https://siteoracle-seo-tool-production.up.railway.app/

Want to hop on a quick call?

Catherine
catherine@squadconsole.com
""",
    },
    "agency": {
        "subject": "White-label AI visibility reports for your agency",
        "body": """Hi {name},

SiteOracle scans websites across 5 dimensions most tools miss: technical SEO, AEO, GEO, local search, and AI bot visibility.

Your clients need this. Semrush and Moz don't cover it yet.

I'm looking for agency partners to resell white-label reports:
- Agency tier: $149/mo — unlimited scans, your logo, client dashboard
- Typical resell: $199-499/mo per client
- Batch scanning (up to 50 sites) + API access
- Zero setup — start sending reports today

Run a test scan: https://siteoracle-seo-tool-production.up.railway.app/

Catherine
catherine@squadconsole.com
""",
    },
    "platform": {
        "subject": "SEO audit layer for {company} users",
        "body": """Hi {name},

SiteOracle gives small businesses a free 5-dimension website audit (SEO, AEO, GEO, local search, AI visibility) in under 60 seconds — no account required.

I think it'd be a natural fit for {company}'s users:
- Embed a free scan — your brand, our engine
- White-label option available
- Revenue share on Pro upgrades ($49/mo)
- Increases engagement for your existing users

Demo: https://siteoracle-seo-tool-production.up.railway.app/

Catherine
catherine@squadconsole.com
""",
    },
    "lender": {
        "subject": "Co-branded SEO audit tools for your referral agents",
        "body": """Hi {name},

Your loan officers work with real estate agents who need better web presence. SiteOracle gives agents a free 5-dimension audit of their website — SEO, AI visibility, answer engines, and local search.

I'm offering a co-branded version for lenders:
- Your logo, your brand on every report
- Free for your referral agents
- Positions your lender as providing real value beyond the loan
- Pro upgrades at $49/mo — revenue share available

Simple embed, no engineering overhead.

Demo: https://siteoracle-seo-tool-production.up.railway.app/

Catherine
catherine@squadconsole.com
""",
    },
}


def send_from_args():
    import argparse
    parser = argparse.ArgumentParser(description="Send SiteOracle partnership email")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--template", required=True, choices=list(TEMPLATES.keys()), help="Email template")
    parser.add_argument("--name", default="there", help="Recipient name")
    parser.add_argument("--company", default="your company", help="Company name (for platform/lender templates)")
    args = parser.parse_args()

    tpl = TEMPLATES[args.template]
    body = tpl["body"].format(name=args.name, company=args.company)

    print(f"Sending to: {args.to}")
    print(f"Subject: {tpl['subject']}")
    print(f"---")
    print(body)
    print(f"---")

    confirm = input("Send? (y/N): ")
    if confirm.lower() == "y":
        ok = send_partnership_email(args.to, tpl["subject"], body)
        if ok:
            print(f"✅ Sent to {args.to}")
        else:
            print(f"❌ Failed to send to {args.to}")
    else:
        print("Cancelled.")


if __name__ == "__main__":
    send_from_args()

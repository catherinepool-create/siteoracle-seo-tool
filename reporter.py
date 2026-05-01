"""Report generation — plain text + HTML using template."""

import datetime
import re
from pathlib import Path


def generate_report(url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis=""):
    """Generate a comprehensive plain-text report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Extract AI Visibility score from GEO dimensions
    ai_vis_score = geo_results.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)

    report = f"""
╔══════════════════════════════════════════════════════╗
║                 SITEORACLE REPORT                    ║
║              SEO + AEO + GEO + GBP                   ║
╚══════════════════════════════════════════════════════╝

Site: {url}
Date: {now}
Pages Analyzed: {len(pages)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TECHNICAL SEO SCORE: {seo_results['score']}/100
AEO SCORE:             {aeo_results['score']}/100
GEO SCORE:             {geo_results['score']}/100
GBP ALIGNMENT:         {gbp_results['score']}/100
AI VISIBILITY:         {ai_vis_score}/100
"""
    # Combined score
    combined = round(
        seo_results["score"] * 0.20
        + aeo_results["score"] * 0.15
        + geo_results["score"] * 0.25
        + gbp_results["score"] * 0.10
        + ai_vis_score * 0.30
    )
    report += f"COMBINED SCORE:       {combined}/100\n\n"

    # ── Priority Fix List ──
    priority_list = _build_priority_fix_list(seo_results, aeo_results, geo_results, gbp_results)
    if priority_list:
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "PRIORITY FIX LIST — Fix These First\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += f"Estimated score after fixing all: +{_estimate_improvement(priority_list)} points\n\n"
        report += _format_priority_list(priority_list, format="text")
        report += "\n\n"

    if seo_results.get("issues"):
        report += "─── TECHNICAL SEO ISSUES ───\n\n"
        for issue in seo_results["issues"]:
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            report += f"{badge} [{issue['severity'].upper()}] {issue['check']}\n"
            report += f"   {issue['detail']}\n\n"

    if aeo_results.get("issues"):
        report += "─── AEO ISSUES ───\n\n"
        for issue in aeo_results["issues"]:
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            report += f"{badge} [{issue['severity'].upper()}] {issue['check']}\n"
            report += f"   {issue['detail']}\n\n"

    if geo_results.get("issues"):
        report += "─── GEO ISSUES ───\n\n"
        for issue in geo_results["issues"]:
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            report += f"{badge} [{issue['severity'].upper()}] {issue['check']}\n"
            report += f"   {issue['detail']}\n\n"

    if gbp_results.get("issues"):
        report += "─── GBP ISSUES ───\n\n"
        for issue in gbp_results["issues"]:
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            report += f"{badge} [{issue['severity'].upper()}] {issue['check']}\n"
            report += f"   {issue['detail']}\n\n"

    if seo_results.get("passes"):
        report += "─── PASSES ───\n\n"
        for p in seo_results["passes"]:
            report += f"✅ {p}\n"

    if aeo_results.get("passes"):
        report += "\n─── AEO PASSES ───\n\n"
        for p in aeo_results["passes"]:
            report += f"✅ {p}\n"

    if geo_results.get("passes"):
        report += "\n─── GEO PASSES ───\n\n"
        for p in geo_results["passes"]:
            report += f"✅ {p}\n"

    if gbp_results.get("passes"):
        report += "\n─── GBP PASSES ───\n\n"
        for p in gbp_results["passes"]:
            report += f"✅ {p}\n"

    if ai_analysis:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "DEEP AI ANALYSIS\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += ai_analysis

    return report


def generate_html_report(url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis=""):
    """Generate a styled HTML report using the template."""
    template_path = Path(__file__).parent / "report_template.html"
    if not template_path.exists():
        return "<html><body><h1>Template not found</h1></body></html>"

    html = template_path.read_text(encoding="utf-8")

    now = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Extract AI Visibility score
    ai_vis_score = geo_results.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)

    # ── Combined Score ──
    combined = round(
        seo_results.get("score", 0) * 0.20
        + aeo_results.get("score", 0) * 0.15
        + geo_results.get("score", 0) * 0.25
        + gbp_results.get("score", 0) * 0.10
        + ai_vis_score * 0.30
    )
    combined_color = "#22c55e" if combined >= 70 else "#f59e0b" if combined >= 40 else "#ef4444"

    # ── Technical SEO ──
    score = seo_results.get("score", 0)
    critical_count = len([i for i in seo_results.get("issues", []) if i.get("severity") == "critical"])
    warn_count = len([i for i in seo_results.get("issues", []) if i.get("severity") == "warning"])
    info_count = len([i for i in seo_results.get("issues", []) if i.get("severity") == "info"])
    pass_count = len(seo_results.get("passes", []))

    # Score ring offset
    circumference = 251.2
    offset = circumference - (score / 100 * circumference)
    score_color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"

    # ── Issues HTML ──
    all_issues = seo_results.get("issues", [])
    issues_html = ""
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    sorted_issues = sorted(all_issues, key=lambda i: severity_order.get(i.get("severity", "info"), 3))

    for issue in sorted_issues:
        sev = issue.get("severity", "info")
        issues_html += f"""
        <div class="issue-item {sev}">
            <span class="issue-severity" style="color: {'#ef4444' if sev == 'critical' else '#f59e0b' if sev == 'warning' else '#3b82f6'}">
                {sev.upper()}
            </span>
            <span class="issue-check">{issue.get('check', '')}</span>
            <div class="issue-detail">{issue.get('detail', '')}</div>
        </div>"""

    # ── Passes HTML ──
    passes_html = "\n".join(f"<li>{p}</li>" for p in seo_results.get("passes", []))

    # ── Pages HTML ──
    pages_html = ""
    for p in pages:
        title = (p.get("title", "") or "")[:60]
        pages_html += f"""
        <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; word-break: break-all;">
                <a href="{p.get('url', '')}" style="color: #3b82f6; text-decoration: none;">{p.get('url', '')[:50]}</a>
            </td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{p.get('word_count', 0)}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{title}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{"✅" if p.get('has_schema') else "❌"}</td>
        </tr>"""

    # ── AI Section ──
    if ai_analysis:
        ai_html = f"""
        <div class="section" id="ai">
            <h2>🤖 AI-Powered Analysis</h2>
            <div class="ai-content">
                {_htmlize(ai_analysis)}
            </div>
        </div>"""
    else:
        ai_html = ""

    # ── AEO Section ──
    aeo_badge = ""
    aeo_section = ""
    if aeo_results.get("dimensions"):
        aeo_score = aeo_results["score"]
        aeo_color = "#22c55e" if aeo_score >= 70 else "#f59e0b" if aeo_score >= 40 else "#ef4444"
        aeo_badge = f'<span class="badge">📝 AEO: {aeo_score}/100</span>'

        dims_html = ""
        for name, dim in aeo_results["dimensions"].items():
            dscore = dim.get("score", 0)
            dcolor = "#22c55e" if dscore >= 70 else "#f59e0b" if dscore >= 40 else "#ef4444"
            dim_issues = len(dim.get("issues", []))
            dim_passes = len(dim.get("passes", []))
            dims_html += f"""
            <div class="dimension-card">
                <div class="dim-name">{name.replace('_', ' ')}</div>
                <div class="dim-score" style="color: {dcolor};">{dscore}</div>
                <div class="dim-issues">{'🔴' + str(dim_issues) if dim_issues else ''}</div>
                <div class="dim-passes">{'✅' + str(dim_passes) if dim_passes else ''}</div>
            </div>"""

        aeo_section = f"""
        <div class="score-card">
            <h2 style="color: {aeo_color}; font-size: 18px; margin-bottom: 4px;">📝 Answer Engine Optimization (AEO)</h2>
            <div style="font-size: 36px; font-weight: 700; color: {aeo_color};">{aeo_score}/100</div>
            <div class="dimension-grid">{dims_html}</div>
        </div>"""

    # ── GEO Section ──
    geo_badge = ""
    geo_section = ""
    if geo_results.get("dimensions"):
        geo_score = geo_results["score"]
        geo_color = "#22c55e" if geo_score >= 70 else "#f59e0b" if geo_score >= 40 else "#ef4444"
        geo_badge = f'<span class="badge">🤖 GEO: {geo_score}/100</span>'

        dims_html = ""
        for name, dim in geo_results["dimensions"].items():
            dscore = dim.get("score", 0)
            dcolor = "#22c55e" if dscore >= 70 else "#f59e0b" if dscore >= 40 else "#ef4444"
            dim_issues = len(dim.get("issues", []))
            dim_passes = len(dim.get("passes", []))
            dims_html += f"""
            <div class="dimension-card">
                <div class="dim-name">{name.replace('_', ' ')}</div>
                <div class="dim-score" style="color: {dcolor};">{dscore}</div>
                <div class="dim-issues">{'🔴' + str(dim_issues) if dim_issues else ''}</div>
                <div class="dim-passes">{'✅' + str(dim_passes) if dim_passes else ''}</div>
            </div>"""

        geo_section = f"""
        <div class="score-card">
            <h2 style="color: {geo_color}; font-size: 18px; margin-bottom: 4px;">🤖 Generative Engine Optimization (GEO)</h2>
            <div style="font-size: 36px; font-weight: 700; color: {geo_color};">{geo_score}/100</div>
            <div class="dimension-grid">{dims_html}</div>
        </div>"""

    # ── GBP Section ──
    gbp_badge = ""
    gbp_section = ""
    if gbp_results.get("dimensions"):
        gbp_score = gbp_results["score"]
        gbp_color = "#22c55e" if gbp_score >= 70 else "#f59e0b" if gbp_score >= 40 else "#ef4444"
        gbp_badge = f'<span class="badge">📍 GBP: {gbp_score}/100</span>'

        dims_html = ""
        for name, dim in gbp_results["dimensions"].items():
            dscore = dim.get("score", 0)
            dcolor = "#22c55e" if dscore >= 70 else "#f59e0b" if dscore >= 40 else "#ef4444"
            dim_issues = len(dim.get("issues", []))
            dim_passes = len(dim.get("passes", []))
            dims_html += f"""
            <div class="dimension-card">
                <div class="dim-name">{name.replace('_', ' ')}</div>
                <div class="dim-score" style="color: {dcolor};">{dscore}</div>
                <div class="dim-issues">{'🔴' + str(dim_issues) if dim_issues else ''}</div>
                <div class="dim-passes">{'✅' + str(dim_passes) if dim_passes else ''}</div>
            </div>"""

        biz_info = gbp_results.get("business_info_extracted", {})
        biz_name = biz_info.get("name", "")
        biz_phone = biz_info.get("phone", "")
        biz_extras = ""
        if biz_name or biz_phone:
            biz_extras = f'<div style="margin-top: 12px; font-size: 14px; color: #64748b;">Detected: {biz_name}{" · " + biz_phone if biz_phone else ""}</div>'

        gbp_section = f"""
        <div class="score-card">
            <h2 style="color: {gbp_color}; font-size: 18px; margin-bottom: 4px;">📍 Google Business Profile Alignment</h2>
            <div style="font-size: 36px; font-weight: 700; color: {gbp_color};">{gbp_score}/100</div>
            {biz_extras}
            <div class="dimension-grid">{dims_html}</div>
        </div>"""

    # ── Fill Template ──
    total_checks = sum(len(v.get("issues", [])) + len(v.get("passes", []))
                       for v in [seo_results, aeo_results, geo_results, gbp_results])

    # ── Priority Fix List ──
    priority_list = _build_priority_fix_list(seo_results, aeo_results, geo_results, gbp_results)
    if priority_list:
        fix_count = len(priority_list)
        improvement = _estimate_improvement(priority_list)
        priority_html = _format_priority_list(priority_list, format="html")

        # Count critical/warning/info
        crit = sum(1 for i in priority_list if i["severity"] == "critical")
        warn = sum(1 for i in priority_list if i["severity"] == "warning")
        info = sum(1 for i in priority_list if i["severity"] == "info")
        sev_summary = []
        if crit: sev_summary.append(f"🔴 {crit} critical")
        if warn: sev_summary.append(f"🟡 {warn} important")
        if info: sev_summary.append(f"🔵 {info} suggestions")
        sev_summary_str = " · ".join(sev_summary)
    else:
        fix_count = 0
        improvement = 0
        priority_html = '<p style="color: #22c55e; font-weight: 600;">✅ No issues found — your site is in great shape!</p>'
        sev_summary_str = ""

    expected = f"{combined + improvement}" if improvement > 0 else str(combined)

    replacements = {
        "{{TITLE}}": f"SiteOracle Report — {url}",
        "{{URL}}": url,
        "{{DATE}}": now,
        "{{PAGES}}": str(len(pages)),
        "{{DEPTH}}": str(total_checks),
        "{{SCORE}}": str(score),
        "{{SCORE_COLOR}}": score_color,
        "{{SCORE_OFFSET}}": str(offset),
        "{{CRITICAL_COUNT}}": str(critical_count),
        "{{WARN_COUNT}}": str(warn_count),
        "{{INFO_COUNT}}": str(info_count),
        "{{PASS_COUNT}}": str(pass_count),
        "{{PAGE_COUNT}}": str(len(pages)),
        "{{ISSUES_HTML}}": issues_html,
        "{{PASSES_HTML}}": passes_html,
        "{{PAGES_HTML}}": pages_html,
        "{{AI_SECTION}}": ai_html,
        "{{AEO_BADGE}}": aeo_badge,
        "{{GEO_BADGE}}": geo_badge,
        "{{GBP_BADGE}}": gbp_badge,
        "{{AEO_SECTION}}": aeo_section,
        "{{GEO_SECTION}}": geo_section,
        "{{GBP_SECTION}}": gbp_section,
        "{{PRIORITY_HTML}}": priority_html,
        "{{FIX_COUNT}}": str(fix_count),
        "{{IMPROVEMENT}}": str(improvement),
        "{{EXPECTED_SCORE}}": expected,
        "{{COMBINED_SCORE}}": str(combined),
        "{{COMBINED_COLOR}}": combined_color,
        "{{SEV_SUMMARY}}": sev_summary_str,
        "{{AI_VIS_SCORE}}": str(ai_vis_score),
    }

    for key, val in replacements.items():
        html = html.replace(key, val)

    return html


def generate_pdf_report(url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis=""):
    """Generate a PDF report from the HTML template.

    Uses WeasyPrint for clean HTML→PDF conversion with full CSS support.
    Falls back gracefully if WeasyPrint is not available.

    Returns:
        bytes: PDF content, or None if generation fails
    """
    html = generate_html_report(url, pages, seo_results, aeo_results, geo_results, gbp_results, ai_analysis)
    if not html or html.startswith("<html><body><h1>Template not found"):
        return None

    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        return None
    except Exception as e:
        print(f"PDF generation failed: {e}")
        return None


def _estimate_improvement(priority_list):
    """Estimate score improvement if all priority items are fixed.

    Args:
        priority_list: List from _build_priority_fix_list()

    Returns:
        int: Estimated points of improvement
    """
    # Each critical fix ≈ 8 points, warning ≈ 4, info ≈ 2
    points = sum(
        {"critical": 8, "warning": 4, "info": 2}.get(i["severity"], 2)
        for i in priority_list
    )
    return min(points, 50)


def _build_priority_fix_list(seo_results, aeo_results, geo_results, gbp_results):
    """Build a numbered priority fix list from all issues across modules.

    Collects all issues, deduplicates by check name, sorts by severity
    (critical → warning → info), and returns an ordered list.

    Returns:
        list of dicts: [{"priority": 1, "area": "SEO", "severity": "critical",
                         "check": "...", "detail": "..."}, ...]
    """
    all_issues = []

    for area, results in [
        ("Technical SEO", seo_results),
        ("AEO", aeo_results),
        ("GEO", geo_results),
        ("GBP", gbp_results),
    ]:
        for issue in results.get("issues", []):
            all_issues.append({
                "area": area,
                "severity": issue.get("severity", "info"),
                "check": issue.get("check", ""),
                "detail": issue.get("detail", ""),
            })

    # Deduplicate by check name (keep highest severity)
    seen = {}
    for issue in all_issues:
        key = issue["check"].lower().strip()
        if key not in seen:
            seen[key] = issue
        else:
            # Keep the one with higher severity
            sev_order = {"critical": 0, "warning": 1, "info": 2}
            if sev_order.get(issue["severity"], 2) < sev_order.get(seen[key]["severity"], 2):
                seen[key] = issue

    # Sort: severity (critical first), then area
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    sorted_issues = sorted(
        seen.values(),
        key=lambda i: (severity_order.get(i["severity"], 2), i["area"]),
    )

    # Number them
    for idx, issue in enumerate(sorted_issues, 1):
        issue["priority"] = idx

    return sorted_issues


def _format_priority_list(priority_list, format="text"):
    """Format priority fix list as text or HTML.

    Args:
        priority_list: List from _build_priority_fix_list()
        format: "text" or "html"

    Returns:
        str: Formatted list
    """
    if not priority_list:
        return ""

    if format == "html":
        items = []
        for item in priority_list:
            sev_color = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            items.append(f"""<div class="priority-item {item['severity']}">
                <span class="priority-number">{item['priority']}</span>
                <div class="priority-content">
                    <div class="priority-header">
                        <span class="priority-severity" style="color:{sev_color.get(item['severity'], '#94a3b8')};">
                            {badge.get(item['severity'], '⚪')} {item['severity'].upper()}
                        </span>
                        <span class="priority-area">{item['area']}</span>
                    </div>
                    <div class="priority-check">{item['check']}</div>
                    <div class="priority-detail">{item['detail']}</div>
                </div>
            </div>""")
        return "\n".join(items)
    else:
        items = []
        for item in priority_list:
            badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            items.append(
                f"{item['priority']}. {badge.get(item['severity'], '⚪')} "
                f"[{item['severity'].upper()}] [{item['area']}] "
                f"{item['check']}\n   {item['detail']}"
            )
        return "\n\n".join(items)


def _htmlize(text):
    """Convert plain text with markdown-like formatting to HTML."""
    if not text:
        return ""

    # Escape HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Headers
    text = re.sub(r'^### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)

    # Bold and italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Bullet lists
    text = re.sub(r'^[-*] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)

    # Numbered lists
    text = re.sub(r'^\d+\.\s(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)

    # Wrap consecutive <li> in <ul>/<ol>
    text = re.sub(r'(<li>.*?</li>(\s*<li>.*?</li>)*)', r'<ul>\1</ul>', text)

    # Divider
    text = text.replace("---", "<hr>")

    # Paragraphs
    paragraphs = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if not block.startswith("<h") and not block.startswith("<ul") and not block.startswith("<hr"):
            block = f"<p>{block}</p>"
        paragraphs.append(block)

    return "\n".join(paragraphs)

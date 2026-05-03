"""SiteOracle Streamlit web interface — full feature suite."""

import streamlit as st
import os
import datetime
import hashlib
import json
from pathlib import Path

from crawler import crawl, fetch_page
from check_seo import check_technical_seo
from check_aeo import check_aeo
from check_geo import check_geo
from check_gbp import check_gbp, extract_business_info
from analyzer import analyze_site, analyze_screenshot
from reporter import generate_report, generate_html_report, generate_pdf_report, _build_priority_fix_list, _estimate_improvement
from comparison import compare_sites, generate_comparison_report
from monitor import setup_monitor, load_monitors, save_snapshot, get_trend, generate_trend_report
from auth import render_sidebar_auth, is_pro_or_above, is_agency, get_user_plan, render_upgrade_card, STRIPE_LINK_PRO, STRIPE_LINK_AGENCY

st.set_page_config(
    page_title="SiteOracle",
    page_icon="/static/favicon.svg",
    layout="wide",
)

# ── Rate Limiting ──────────────────────────────────────────────
RATE_LIMIT_FILE = Path("/tmp/siteoracle_ratelimit.json")

def _load_rate_limits():
    if RATE_LIMIT_FILE.exists():
        return json.loads(RATE_LIMIT_FILE.read_text())
    return {}

def _save_rate_limits(data):
    RATE_LIMIT_FILE.write_text(json.dumps(data))

def _get_client_id():
    """Create a consistent ID from the user's IP (via forwarded headers) or session."""
    forwarded = os.environ.get("HTTP_X_FORWARDED_FOR", "") or \
                os.environ.get("X_FORWARDED_FOR", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        # Fall back to session-based ID for local dev
        if "client_id" not in st.session_state:
            st.session_state.client_id = hashlib.md5(
                str(datetime.datetime.now().timestamp()).encode()
            ).hexdigest()[:12]
        return st.session_state.client_id
    return hashlib.md5(ip.encode()).hexdigest()[:16]

def _check_rate_limit():
    """Check if this client has used their free scan today. Returns True if allowed."""
    client_id = _get_client_id()
    limits = _load_rate_limits()
    today = datetime.date.today().isoformat()

    if client_id in limits:
        entry = limits[client_id]
        if entry.get("date") == today and entry.get("count", 0) >= 1:
            return False
    return True

def _is_pro_user():
    """Check if user has an active Pro or Agency subscription via Stripe."""
    return is_pro_or_above()

def _record_scan():
    """Record a free scan for this client."""
    client_id = _get_client_id()
    limits = _load_rate_limits()
    today = datetime.date.today().isoformat()
    limits[client_id] = {"date": today, "count": 1}
    _save_rate_limits(limits)

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { padding: 1rem; }
    h1, h2, h3 { color: inherit !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; padding: 4px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; }
    .metric-box { text-align: center; padding: 1rem; border-radius: 10px; margin-bottom: 0.5rem; }
    .metric-value { font-size: 32px; font-weight: 700; }
    .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; }
    .stButton button { width: 100%; }
    .streamlit-expanderContent { font-size: 14px; }
    .stDownloadButton button { width: 100%; }
    div[data-testid="stStatusWidget"] { color: inherit; }
    /* Upgrade card styling */
    .upgrade-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #ff5555;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
    }
    .upgrade-card h2 { color: #ff5555 !important; margin-bottom: 0.5rem; }
    .upgrade-card p { color: #94a3b8; margin-bottom: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar Auth ────────────────────────────────────────────────
render_sidebar_auth()

# ── Header ──────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🔍 SiteOracle")
    st.markdown("**SEO + AEO + GEO + GBP** — comprehensive website analysis")
with col2:
    st.markdown("")
    st.markdown(f"<div style='text-align:right; font-size:12px; color:#94a3b8;'>{datetime.datetime.now().strftime('%b %d, %Y')}</div>", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────
tab_analyze, tab_compare, tab_monitor, tab_settings = st.tabs([
    "🌐 Analyze Site",
    "⚔️ Compare",
    "📊 Monitoring",
    "⚙️ Settings",
])

# ══════════════════════════════════════════════════════════════════
# TAB: ANALYZE
# ══════════════════════════════════════════════════════════════════
with tab_analyze:
    col1, col2 = st.columns([2, 1])
    with col1:
        url = st.text_input("Website URL", placeholder="https://example.com",
                            help="Enter the full URL including https://")
    with col2:
        max_pages = st.slider("Pages to crawl", 1, 20, 5)

    col1, col2, col3 = st.columns(3)
    with col1:
        use_ai = st.checkbox("AI Deep Analysis", value=True,
                             help="Uses DeepSeek AI for comprehensive analysis")
    with col2:
        biz_name = st.text_input("Business name (for GBP)", placeholder="Optional",
                                 help="Helps with Google Business Profile alignment checks")
    with col3:
        st.markdown("")  # spacer

    col1, col2 = st.columns([1, 1])
    with col1:
        run_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    with col2:
        demo_btn = st.button("👀 Try Sample Report", use_container_width=True,
                             help="See a live demo report without scanning")

    screenshot_file = st.file_uploader("Or upload screenshot for AI analysis",
                                        type=["png", "jpg", "jpeg", "webp"],
                                        help="Can't crawl a site? Upload a screenshot instead.")

    if screenshot_file:
        ext = screenshot_file.name.rsplit(".", 1)[-1]
        temp_path = Path(f"/tmp/siteoracle_screenshot.{ext}")
        temp_path.write_bytes(screenshot_file.getvalue())
        st.image(screenshot_file, caption="Uploaded Screenshot", use_container_width=True)

        if st.button("📸 Analyze Screenshot", type="primary"):
            if not _check_rate_limit():
                st.warning("You've used your free scan for today. You get 1 free scan every 24 hours — upgrade for unlimited access.")
            elif not os.getenv("OPENAI_API_KEY"):
                st.warning("Screenshot analysis uses OpenAI Vision — set your key in Settings (Advanced) or upgrade to Pro for included access.")
            else:
                with st.spinner("Analyzing screenshot..."):
                    result = analyze_screenshot(str(temp_path))
                st.markdown("### 📸 Screenshot Analysis")
                st.markdown(result)

    elif run_btn and url:
        if not url.startswith("http"):
            url = "https://" + url

        # ── Rate limit check (Pro/Agency bypass) ──
        if not _is_pro_user() and not _check_rate_limit():
            st.warning("You've used your free scan for today. You get 1 free scan every 24 hours.")
            st.markdown(f"""
            <div class="upgrade-card">
                <h2>🚀 Upgrade to SiteOracle Pro</h2>
                <p>Unlock unlimited scans, all AI engines, PDF reports, competitor monitoring, and more.</p>
                <a href="{STRIPE_LINK_PRO}" target="_blank"
                   style="display:inline-block; background:#ff5555; color:white; padding:10px 24px;
                          border-radius:8px; text-decoration:none; font-weight:700; margin-top:8px;">
                    ⚡ Get Pro — $49/mo
                </a>
            </div>
            """, unsafe_allow_html=True)
            st.stop()

    elif demo_btn:
        # ── Demo Mode — show a pre-loaded sample report ──
        st.markdown("### 👀 Sample Report — squadconsole.com")
        st.caption("This is a demo showing what SiteOracle finds. No crawl needed.")

        # Pre-built demo results for squadconsole.com
        seo = {
            "score": 62, "issues": [
                {"severity": "critical", "check": "Missing meta description on 3 pages",
                 "detail": "3 of 5 crawled pages have no meta description. Add unique meta descriptions to improve CTR in search results."},
                {"severity": "warning", "check": "No canonical URLs detected",
                 "detail": "Canonical tags prevent duplicate content issues. Add rel=canonical to all pages."},
                {"severity": "info", "check": "Thin content on 2 pages (under 300 words)",
                 "detail": "Consider expanding content on these pages to improve topical authority."},
            ], "passes": ["HTTPS enabled and redirects correctly", "Responsive meta tag present",
                          "Page speed score above 70 on mobile", "No broken internal links found",
                          "Clean URL structure with no query parameters"]
        }
        aeo = {
            "score": 45, "dimensions": {
                "faq_schema": {"score": 30, "issues": [{"severity": "critical", "check": "No FAQPage schema", "detail": "Add FAQ schema to help voice search."}], "passes": []},
                "howto_schema": {"score": 40, "issues": [{"severity": "warning", "check": "No HowTo schema", "detail": "HowTo markup helps with procedural queries."}], "passes": []},
                "question_keywords": {"score": 55, "issues": [], "passes": ["Some question-phrased headings found"]},
                "featured_snippet": {"score": 50, "issues": [{"severity": "info", "check": "Weak snippet structure", "detail": "Use bullet points and numbered lists more."}], "passes": []},
                "voice_search": {"score": 40, "issues": [], "passes": ["Conversational tone detected"]},
                "people_also_ask": {"score": 50, "issues": [], "passes": []},
                "content_breadth": {"score": 50, "issues": [], "passes": []},
            }, "issues": [
                {"severity": "critical", "check": "No FAQPage schema found", "detail": "FAQ schema directly influences featured snippets and voice answers."},
                {"severity": "warning", "check": "Limited structured Q&A content", "detail": "Add FAQ sections to key pages."},
            ], "passes": ["Conversational tone detected", "Some question-style headings found"]
        }
        geo = {
            "score": 38, "dimensions": {
                "brand_authority": {"score": 50, "issues": [], "passes": []},
                "structured_data": {"score": 35, "issues": [], "passes": []},
                "freshness": {"score": 30, "issues": [], "passes": []},
                "topical_depth": {"score": 45, "issues": [], "passes": []},
                "citation_readiness": {"score": 40, "issues": [], "passes": []},
                "multimedia": {"score": 25, "issues": [], "passes": []},
                "external_references": {"score": 30, "issues": [], "passes": []},
                "ai_visibility": {"score": 55, "issues": [
                    {"severity": "warning", "check": "2 AI bots blocked in robots.txt",
                     "detail": "PerplexityBot and Bytespider are disallowed. Update robots.txt to allow them."},
                    {"severity": "info", "check": "Missing FAQPage schema",
                     "detail": "Adding FAQPage schema improves citation likelihood."},
                ], "passes": ["robots.txt found — governance in place",
                              "GPTBot and ClaudeBot allowed — ChatGPT and Claude can crawl",
                              "Article schema detected on blog pages",
                              "Some Q&A-style content found",
                              "Clear definition statements found"],
                    "robots_info": {"has_robots_txt": True, "blocked_bots": [
                        {"name": "PerplexityBot", "label": "Perplexity AI"},
                        {"name": "Bytespider", "label": "ByteDance (TikTok AI)"},
                    ]}},
            }, "issues": [
                {"severity": "warning", "check": "No FAQPage schema", "detail": "Critical for AI citation."},
                {"severity": "warning", "check": "2 AI bots blocked", "detail": "Perplexity and Bytespider blocked."},
            ], "passes": ["robots.txt found", "GPTBot and ClaudeBot allowed"]
        }
        gbp = {
            "score": 70, "dimensions": {}, "issues": [], "passes": [
                "Google Business Profile likely exists",
                "Name consistency across detected pages",
            ], "business_info_extracted": {"name": "SquadConsole"}
        }

        url = "https://squadconsole.com"
        ai_vis_score = 55
        combined = round(62 * 0.20 + 45 * 0.15 + 38 * 0.25 + 70 * 0.10 + 55 * 0.30)
        combined = 49  # override for demo
        ai_text = ""  # skip AI analysis for demo
        pages = []  # skip pages for demo
        priority_list = []
        expected = 49

        # Show results
        s_c, a_c, g_c, gbp_c, ai_c, comb_c = st.columns(6)
        with s_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#f59e0b">62</div><div class="metric-label">Technical SEO</div></div>""", unsafe_allow_html=True)
        with a_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#ef4444">45</div><div class="metric-label">AEO</div></div>""", unsafe_allow_html=True)
        with g_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#ef4444">38</div><div class="metric-label">GEO</div></div>""", unsafe_allow_html=True)
        with gbp_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#22c55e">70</div><div class="metric-label">GBP</div></div>""", unsafe_allow_html=True)
        with ai_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#f59e0b">55</div><div class="metric-label">AI Visibility</div></div>""", unsafe_allow_html=True)
        with comb_c:
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:#f59e0b">49</div><div class="metric-label">Combined</div></div>""", unsafe_allow_html=True)

        # Priority fix list
        st.markdown("### 🎯 Priority Fix List")
        st.caption("Fix these 6 items to reach an estimated score of **76/100** (+27 pts)")
        demo_priority = [
            (1, "critical", "AEO", "No FAQPage schema found", "FAQ schema directly influences featured snippets and voice search answers."),
            (2, "critical", "Technical SEO", "Missing meta description on 3 pages", "3 of 5 crawled pages have no meta description."),
            (3, "warning", "GEO", "2 AI bots blocked in robots.txt", "PerplexityBot and Bytespider are disallowed."),
            (4, "warning", "AEO", "Limited structured Q&A content", "Add FAQ sections to key pages."),
            (5, "warning", "Technical SEO", "No canonical URLs detected", "Add rel=canonical to all pages."),
            (6, "info", "Technical SEO", "Thin content on 2 pages", "Expand content to improve topical authority."),
        ]
        for num, sev, area, check, detail in demo_priority:
            emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}[sev]
            border = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}[sev]
            st.markdown(f"""
            <div style="display: flex; gap: 12px; padding: 12px; margin-bottom: 8px;
                        background: #1e293b; border-radius: 8px; border-left: 4px solid {border};">
                <div style="flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
                            background: #0f172a; border-radius: 50%; font-weight: 700; font-size: 13px;">{num}</div>
                <div style="flex: 1;">
                    <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 2px;">
                        <span style="font-size: 11px; font-weight: 700; color: {border};">{emoji} {sev.upper()}</span>
                        <span style="font-size: 11px; color: #64748b; background: #0f172a; padding: 2px 8px; border-radius: 4px;">{area}</span>
                    </div>
                    <div style="font-weight: 600; color: #f1f5f9; font-size: 14px;">{check}</div>
                    <div style="font-size: 13px; color: #94a3b8;">{detail}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Show AI Visibility expander
        with st.expander("🤖 AI Visibility — Can AI Bots See Your Site?", expanded=True):
            st.markdown(f"""<div class="metric-box" style="margin-bottom: 8px;">
                <div class="metric-value" style="color:#f59e0b; font-size:48px;">55</div>
                <div class="metric-label">AI Visibility Score</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("### 🚫 Blocked AI Bots")
            st.markdown("🔴 **PerplexityBot** — Perplexity AI")
            st.markdown("🔴 **Bytespider** — ByteDance (TikTok AI)")
            st.caption("These bots cannot crawl your site. Update your robots.txt to allow them.")
            st.markdown("### ✅ Allowed AI Bots")
            st.markdown("✅ GPTBot (ChatGPT) · ClaudeBot (Claude) · Google-Extended (Gemini) · Applebot · CCBot · FacebookBot · cohere-ai · ChatGPT-User")

        # Report download
        st.markdown("---")
        st.markdown("### 📄 Run a real scan to download your report")

    # ── Crawl & analyze ──
    elif run_btn and url:
        with st.status("🔍 Crawling site...") as status:
            pages = crawl(url, max_pages=max_pages)
            if not pages:
                st.error("Could not fetch the website. Check the URL and try again.")
                st.stop()
            status.update(label=f"✅ Crawled {len(pages)} pages", state="complete")

        # Also fetch homepage raw HTML for schema analysis
        homepage_html, _ = fetch_page(url)

        # ── Run Checks ──
        with st.status("Running checks...") as status:
            seo = check_technical_seo(pages)
            status.update(label="✅ Technical SEO done")

            aeo = check_aeo(pages)
            status.update(label="✅ AEO done")

            geo = check_geo(pages, html=homepage_html, url=url)
            status.update(label="✅ GEO + AI Visibility done")

            biz_info = {"name": biz_name} if biz_name else None
            gbp = check_gbp(pages, biz_info)
            status.update(label="✅ GBP done")

        # ── AI Analysis (Pro feature) ──
        ai_text = ""
        if use_ai:
            if not _is_pro_user():
                ai_text = ""  # skip — shown as upgrade prompt below
            else:
                deepseek_key = os.getenv("DEEPSEEK_API_KEY")
                if deepseek_key:
                    with st.spinner("Running AI analysis..."):
                        try:
                            ai_text = analyze_site(pages, engine="deepseek")
                        except Exception as e:
                            st.warning(f"AI analysis failed: {e}")
                            ai_text = ""
                else:
                    st.info("AI analysis unavailable — server configuration issue. Results still show below.")

        # ── Display Scores ──
        # Extract AI Visibility score from GEO dimensions if available
        ai_vis_score = geo.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)
        # Combined: SEO 25%, AEO 20%, GEO (incl AI Vis) 30%, GBP 10%, AI Visibility standalone 15%
        combined = round(
            seo["score"] * 0.20 +
            aeo["score"] * 0.15 +
            geo["score"] * 0.25 +
            gbp["score"] * 0.10 +
            ai_vis_score * 0.30
        )

        s_c, a_c, g_c, gbp_c, ai_c, comb_c = st.columns(6)
        with s_c:
            color = "#22c55e" if seo["score"] >= 70 else "#f59e0b" if seo["score"] >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{seo["score"]}</div><div class="metric-label">Technical SEO</div></div>""", unsafe_allow_html=True)
        with a_c:
            color = "#22c55e" if aeo["score"] >= 70 else "#f59e0b" if aeo["score"] >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{aeo["score"]}</div><div class="metric-label">AEO</div></div>""", unsafe_allow_html=True)
        with g_c:
            color = "#22c55e" if geo["score"] >= 70 else "#f59e0b" if geo["score"] >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{geo["score"]}</div><div class="metric-label">GEO</div></div>""", unsafe_allow_html=True)
        with gbp_c:
            color = "#22c55e" if gbp["score"] >= 70 else "#f59e0b" if gbp["score"] >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{gbp["score"]}</div><div class="metric-label">GBP</div></div>""", unsafe_allow_html=True)
        with ai_c:
            color = "#22c55e" if ai_vis_score >= 70 else "#f59e0b" if ai_vis_score >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{ai_vis_score}</div><div class="metric-label">AI Visibility</div></div>""", unsafe_allow_html=True)
        with comb_c:
            color = "#22c55e" if combined >= 70 else "#f59e0b" if combined >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{combined}</div><div class="metric-label">Combined</div></div>""", unsafe_allow_html=True)

        # ── Priority Fix List ──
        priority_list = _build_priority_fix_list(seo, aeo, geo, gbp)
        if priority_list:
            improvement = _estimate_improvement(priority_list)
            expected = combined + improvement

            st.markdown("### 🎯 Priority Fix List")
            st.caption(f"Fix these {len(priority_list)} items to reach an estimated score of **{expected}/100** (+{improvement} pts)")

            for item in priority_list:
                sev = item["severity"]
                emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")
                border = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
                st.markdown(f"""
                <div style="display: flex; gap: 12px; padding: 12px; margin-bottom: 8px;
                            background: #1e293b; border-radius: 8px; border-left: 4px solid {border[sev]};">
                    <div style="flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
                                background: #0f172a; border-radius: 50%; font-weight: 700; font-size: 13px;">{item['priority']}</div>
                    <div style="flex: 1;">
                        <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 2px;">
                            <span style="font-size: 11px; font-weight: 700; color: {border[sev]};">{emoji} {sev.upper()}</span>
                            <span style="font-size: 11px; color: #64748b; background: #0f172a; padding: 2px 8px; border-radius: 4px;">{item['area']}</span>
                        </div>
                        <div style="font-weight: 600; color: #f1f5f9; font-size: 14px;">{item['check']}</div>
                        <div style="font-size: 13px; color: #94a3b8;">{item['detail']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ No issues found — your site is in great shape!")
            expected = combined

        # ── Record scan for free users (rate limiting) ──
        if not _is_pro_user():
            _record_scan()

        # ── Detail Sections ──
        with st.expander("🔧 Technical SEO Details", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                for issue in seo.get("issues", []):
                    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
                    st.markdown(f"{emoji} **{issue['check']}**")
                    st.caption(issue["detail"])
            with col2:
                for p in seo.get("passes", []):
                    st.markdown(f"✅ {p}")

        with st.expander("📝 Answer Engine Optimization (AEO)"):
            _show_dimensions(aeo)

        with st.expander("🤖 AI Visibility — Can AI Bots See Your Site?", expanded=True):
            _show_ai_visibility(geo)

        with st.expander("🤖 Generative Engine Optimization (GEO)"):
            _show_dimensions(geo)

        with st.expander("📍 Google Business Profile Alignment"):
            _show_dimensions(gbp)
            if gbp.get("business_info_extracted"):
                info = gbp["business_info_extracted"]
                parts = [f"**{k}:** {v}" for k, v in info.items() if v]
                if parts:
                    st.markdown("Auto-detected: " + " · ".join(parts))

        # ── AI Analysis ──
        if ai_text:
            with st.expander("🤖 AI Deep Analysis", expanded=True):
                st.markdown(ai_text)
        elif use_ai and not _is_pro_user():
            with st.expander("🤖 AI Deep Analysis — Pro Feature"):
                render_upgrade_card("AI Deep Analysis")

        # ── Report Download ──
        col1, col2, col3 = st.columns(3)
        with col1:
            html = generate_html_report(url, pages, seo, aeo, geo, gbp, ai_text)
            report_filename_base = f"siteoracle_{url.replace('https://', '').replace('/', '_')[:30]}"
            st.download_button(
                "📄 Download HTML Report",
                html,
                file_name=f"{report_filename_base}.html",
                mime="text/html",
                use_container_width=True,
            )
        with col2:
            text = generate_report(url, pages, seo, aeo, geo, gbp, ai_text)
            st.download_button(
                "📝 Download Text Report",
                text,
                file_name=f"{report_filename_base}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col3:
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf_report(url, pages, seo, aeo, geo, gbp, ai_text)
            if pdf_bytes:
                st.download_button(
                    "📕 Download PDF Report",
                    pdf_bytes,
                    file_name=f"{report_filename_base}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.button("📕 PDF (unavailable)", disabled=True, use_container_width=True)

        # ── Upgrade Prompt ──
        # Find best and worst dimensions for personalization
        dim_names = {
            "seo_score": ("SEO", seo["score"]),
            "aeo_score": ("AEO", aeo["score"]),
            "geo_score": ("GEO", geo["score"]),
            "gbp_score": ("GBP", gbp["score"]),
        }
        worst_dim = min(dim_names.values(), key=lambda x: x[1])
        best_dim = max(dim_names.values(), key=lambda x: x[1])

        # ── Upgrade prompt (only for free users) ──
        if not _is_pro_user():
            st.markdown(f"""
            <div class="upgrade-card">
                <h2>🚀 Your site scored {combined}/100</h2>
                <p><strong>{worst_dim[0]}</strong> is your weakest area ({worst_dim[1]}/100).<br>
                Upgrade to unlock unlimited scans, AI deep analysis, competitor comparison, monitoring and PDF reports.</p>
                <a href="{STRIPE_LINK_PRO}" target="_blank"
                   style="display:inline-block; background:#ff5555; color:white; padding:10px 24px;
                          border-radius:8px; text-decoration:none; font-weight:700; margin-top:8px;">
                    ⚡ Get Pro — $49/mo
                </a>
            </div>
            """, unsafe_allow_html=True)

        # ── Offer Monitoring (Pro feature) ──
        if not _is_pro_user():
            if st.button("📊 Start Monitoring This Site (Pro)", use_container_width=True):
                st.info("Log in with your Pro account email in the sidebar to unlock monitoring.")


# ══════════════════════════════════════════════════════════════════
# TAB: COMPARE
# ══════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown("### ⚔️ Compare Two Sites")
    st.caption("Analyze and compare your site against a competitor. (Pro feature)")

    col1, col2 = st.columns(2)
    with col1:
        site_a = st.text_input("Your site", placeholder="https://yoursite.com", key="comp_a")
    with col2:
        site_b = st.text_input("Competitor", placeholder="https://competitor.com", key="comp_b")

    comp_pages = st.slider("Pages to crawl per site", 1, 10, 3, key="comp_pages")

    if st.button("⚔️ Compare", type="primary", use_container_width=True) and site_a and site_b:
        if not _is_pro_user():
            render_upgrade_card("Competitor Comparison")
        else:
            with st.spinner("Crawling and comparing both sites..."):
                try:
                    results = compare_sites(site_a, site_b, max_pages=comp_pages)
                    report = generate_comparison_report(results)
                    st.markdown(report, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Comparison failed: {e}")


# ══════════════════════════════════════════════════════════════════
# TAB: MONITORING
# ══════════════════════════════════════════════════════════════════
with tab_monitor:
    st.markdown("### 📊 Site Monitoring")
    st.caption("Track scores over time with scheduled snapshots.")

    if not _is_pro_user():
        render_upgrade_card("Site Monitoring")
    else:
        mon_url = st.text_input("Site to monitor", placeholder="https://yoursite.com", key="mon_url")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Add to Monitoring", type="primary", use_container_width=True) and mon_url:
                with st.spinner("Setting up monitor..."):
                    try:
                        setup_monitor(mon_url)
                        st.success(f"✅ Monitoring started for {mon_url}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
        with col2:
            if st.button("📈 View Trends", use_container_width=True):
                try:
                    monitors = load_monitors()
                    if monitors:
                        for site, data in monitors.items():
                            st.markdown(f"**{site}**")
                            trend = get_trend(site)
                            if trend:
                                st.line_chart(trend)
                    else:
                        st.info("No monitors set up yet. Add a site above.")
                except Exception as e:
                    st.error(f"Could not load monitors: {e}")


# ══════════════════════════════════════════════════════════════════
# TAB: SETTINGS
# ══════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("### ⚙️ Advanced Settings")
    st.caption("For power users who want to use their own API keys.")

    with st.expander("🔐 Subscription Status"):
        plan = get_user_plan()
        email = st.session_state.get("user_email", None)
        if email:
            st.markdown(f"**Email:** {email}  \n**Plan:** {plan.capitalize()}")
            if plan == "free":
                st.markdown(f"[⚡ Upgrade to Pro — $49/mo]({STRIPE_LINK_PRO})")
                st.markdown(f"[🏢 Upgrade to Agency — $149/mo]({STRIPE_LINK_AGENCY})")
        else:
            st.info("Log in via the sidebar to verify your subscription.")

    with st.expander("🔑 Bring Your Own API Key (Optional)"):
        st.markdown("""
        Optionally use your own API key to run AI deep analysis with a specific engine.
        SiteOracle uses DeepSeek by default — no key required for basic scans.
        """)

        key_names = ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
        for name in key_names:
            server_has_key = bool(os.getenv(name, ""))
            label = f"{name} {'✅ set by server' if server_has_key else ''}"
            user_val = st.session_state.get(f"user_{name}", "")
            entered = st.text_input(label, value=user_val, type="password",
                                    placeholder="Paste your key here to override" if server_has_key else "Paste your key here",
                                    key=f"input_{name}")
            if entered:
                st.session_state[f"user_{name}"] = entered

        st.caption("Your keys are only used for this session and never stored on our servers.")

    st.markdown("---")
    st.markdown("""
    ### About SiteOracle

    **Version**: 1.1  
    **Capabilities**:  
    - 🔧 Technical SEO (15+ rules-based checks, scored /100)  
    - 📝 Answer Engine Optimization (7 dimensions)  
    - 🤖 **AI Visibility Score** — checks which AI bots can see your site (ChatGPT, Claude, Perplexity, Gemini)  
    - 🤖 Generative Engine Optimization (8 dimensions incl. AI Visibility)  
    - 📍 Google Business Profile alignment (7 dimensions)  
    - 🤖 AI deep analysis (via DeepSeek AI)  
    - ⚔️ Competitive comparison (Pro)  
    - 📊 Scheduled monitoring (Pro)  
    - 📄 Beautiful HTML reports

    Built with ❤️ — ask Catherine about it.
    """)


# ── Helpers ──────────────────────────────────────────────────────

def _show_dimensions(results):
    """Display dimension breakdown for AEO/GEO/GBP results."""
    dims = results.get("dimensions", {})
    if not dims:
        st.info("No dimension data available.")
        return

    cols = st.columns(min(len(dims), 4))
    for i, (name, dim) in enumerate(dims.items()):
        with cols[i % len(cols)]:
            score = dim.get("score", 0)
            color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box" style="margin-bottom: 8px;">
                <div class="metric-value" style="color:{color}; font-size:24px;">{score}</div>
                <div class="metric-label">{name.replace('_', ' ')}</div>
            </div>""", unsafe_allow_html=True)

    # Issues and passes
    all_issues = results.get("issues", [])
    all_passes = results.get("passes", [])
    if all_issues:
        st.markdown("**Issues**")
        for issue in all_issues:
            emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            st.markdown(f"{emoji} **{issue['check']}** — {issue['detail']}")
    if all_passes:
        st.markdown("**Passes**")
        for p in all_passes:
            st.markdown(f"✅ {p}")


def _show_ai_visibility(geo_results):
    """Display the AI Visibility section — the flagship feature."""
    dims = geo_results.get("dimensions", {})
    ai_vis = dims.get("ai_visibility", {})

    if not ai_vis:
        st.info("AI Visibility data not available.")
        return

    score = ai_vis.get("score", 0)
    color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"

    # Big score at top
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""<div class="metric-box" style="margin-bottom: 8px;">
            <div class="metric-value" style="color:{color}; font-size:48px;">{score}</div>
            <div class="metric-label">AI Visibility Score</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
        **What this checks:**
        - 🤖 Which AI bots (ChatGPT, Claude, Perplexity, Gemini) can access your site via robots.txt
        - 🏷️ Schema.org types present — how well AI understands your content
        - 📝 Content structure — how easily AI can extract and cite your information
        """)

    # Blocked bots section
    robots_info = ai_vis.get("robots_info", {})
    blocked = robots_info.get("blocked_bots", [])
    has_robots = robots_info.get("has_robots_txt", False)

    if blocked:
        st.markdown("### 🚫 Blocked AI Bots")
        for bot in blocked:
            st.markdown(f"🔴 **{bot['name']}** — {bot['label']}")
        st.caption("These bots cannot crawl your site. Update your robots.txt to allow them.")
    elif has_robots:
        st.markdown("### ✅ All AI Bots Allowed")
        st.caption("Your robots.txt doesn't block major AI crawlers. Good.")

    if not has_robots:
        st.markdown("### ⚠️ No robots.txt Found")
        st.caption("Without robots.txt, AI bots default to allowed — but you lose control. Consider adding one.")

    # Issues and passes (filtered to AI visibility)
    all_issues = ai_vis.get("issues", [])
    all_passes = ai_vis.get("passes", [])

    if all_issues:
        st.markdown("### 🔧 Issues Found")
        for issue in all_issues:
            emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "⚪")
            st.markdown(f"{emoji} **{issue['check']}** — {issue['detail']}")
    if all_passes:
        st.markdown("### ✅ What's Working")
        for p in all_passes:
            st.markdown(f"✅ {p}")

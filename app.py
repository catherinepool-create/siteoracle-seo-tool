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
from emailer import send_scan_report
from visual_audit import analyse_screenshot_visual
from screenshot import capture_screenshot

st.set_page_config(
    page_title="SiteOracle",
    page_icon="🔍",
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
        if entry.get("date") == today and entry.get("count", 0) >= 3:
            return False
    return True

def _is_pro_user():
    """Check if user has an active Pro or Agency subscription via Stripe."""
    return is_pro_or_above()

def _record_scan():
    """Record a free scan for this client — increments counter for today."""
    client_id = _get_client_id()
    limits = _load_rate_limits()
    today = datetime.date.today().isoformat()
    current = limits.get(client_id, {})
    if current.get("date") == today:
        limits[client_id] = {"date": today, "count": current["count"] + 1}
    else:
        limits[client_id] = {"date": today, "count": 1}
    _save_rate_limits(limits)


# ── Display Helpers ──────────────────────────────────────────────

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


# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    * { font-family: 'Inter', -apple-system, sans-serif; }

    .main { padding: 0 1rem 2rem 1rem; }

    /* ── Brand Colors ── */
    :root {
        --brand: #6366f1;
        --brand-glow: #818cf8;
        --brand-dark: #4338ca;
        --accent: #f59e0b;
        --bg-deep: #070b14;
        --bg-card: #0f1525;
        --bg-card-hover: #151d33;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border-subtle: #1e293b;
    }

    /* ── Hero Section ── */
    .hero {
        text-align: center;
        padding: 3rem 1rem 2rem 1rem;
        position: relative;
    }
    .hero h1 {
        font-size: 42px;
        font-weight: 800;
        letter-spacing: -1.5px;
        line-height: 1.15;
        margin-bottom: 12px;
        background: linear-gradient(135deg, #f1f5f9 0%, #818cf8 50%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero .tagline {
        font-size: 18px;
        color: var(--text-secondary);
        max-width: 600px;
        margin: 0 auto 6px auto;
        line-height: 1.5;
    }
    .hero .sub-tagline {
        font-size: 14px;
        color: var(--text-muted);
        max-width: 540px;
        margin: 0 auto 24px auto;
    }
    .hero .badge-row {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 8px;
        margin-bottom: 28px;
    }
    .hero .badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 14px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        background: rgba(99, 102, 241, 0.12);
        color: var(--brand-glow);
        border: 1px solid rgba(99, 102, 241, 0.2);
    }

    /* ── Scan Bar ── */
    .scan-bar {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 20px 24px;
        max-width: 780px;
        margin: 0 auto 20px auto;
        display: flex;
        gap: 12px;
        align-items: center;
    }
    .scan-bar input {
        flex: 1;
        background: var(--bg-deep);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 15px;
        color: var(--text-primary);
        outline: none;
    }
    .scan-bar input:focus {
        border-color: var(--brand);
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
    }
    .scan-bar button {
        background: linear-gradient(135deg, var(--brand), var(--brand-dark));
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 28px;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        transition: all 0.15s;
    }
    .scan-bar button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35);
    }

    /* ── Social Proof Row ── */
    .proof-row {
        display: flex;
        gap: 24px;
        justify-content: center;
        align-items: center;
        flex-wrap: wrap;
        margin: 16px 0 0 0;
        padding: 16px 0;
    }
    .proof-item {
        text-align: center;
    }
    .proof-item .num {
        font-size: 28px;
        font-weight: 800;
        color: var(--text-primary);
        line-height: 1;
    }
    .proof-item .label {
        font-size: 12px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 2px;
    }

    /* ── Feature Grid ── */
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
        max-width: 900px;
        margin: 0 auto;
        padding: 0 8px;
    }
    .feature-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: all 0.15s;
    }
    .feature-card:hover {
        background: var(--bg-card-hover);
        border-color: rgba(99, 102, 241, 0.25);
    }
    .feature-card .emoji { font-size: 28px; margin-bottom: 6px; }
    .feature-card .name { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px; }
    .feature-card .desc { font-size: 12px; color: var(--text-secondary); line-height: 1.4; }

    /* ── Section Divider ── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border-subtle), transparent);
        margin: 24px 0;
    }

    /* ── Existing styles (preserved) ── */
    h1, h2, h3 { color: inherit !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; padding: 4px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; }
    .stTabs { margin-top: 12px; }
    .metric-box { text-align: center; padding: 1rem; border-radius: 10px; margin-bottom: 0.5rem; background: var(--bg-card); border: 1px solid var(--border-subtle); }
    .metric-value { font-size: 32px; font-weight: 700; }
    .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; color: var(--text-secondary); }
    .stButton button { width: 100%; }
    .st-emotion-cache-1gulkj5, .st-emotion-cache-1r4qj8v { width: 100%; }
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

    /* Streamlit overrides */
    .stTextInput input { background: var(--bg-deep) !important; border: 1px solid var(--border-subtle) !important; color: var(--text-primary) !important; border-radius: 10px !important; }
    .stTextInput input:focus { border-color: var(--brand) !important; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important; }
    .stSlider div[data-baseweb="slider"] { margin-top: 8px; }
    .stSlider [data-testid="stTickBar"] { color: var(--text-muted); }
    .stCheckbox label { color: var(--text-primary) !important; }
    .element-container { margin-bottom: 0 !important; }
    div[data-testid="stImage"] { margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar Auth ────────────────────────────────────────────────
render_sidebar_auth()

# ── Detect embedded mode (iframe on squadconsole.com) ──
_embedded = st.query_params.get("embedded", False)

# ── HERO SECTION (hidden when embedded in squadconsole.com iframe) ──
if not _embedded:
    st.markdown("""
<div class="hero">
    <h1>Which AI bots can read your website?</h1>
    <p class="tagline">SiteOracle scans your site — technical SEO, AI visibility, answer engines, and local search — and tells you exactly what to fix.</p>
    <p class="sub-tagline">No account needed. Enter any URL and get a scored report in under a minute.</p>
    <div class="badge-row">
        <span class="badge">🔧 Technical SEO</span>
        <span class="badge">🤖 AI Visibility</span>
        <span class="badge">📝 Answer Engines</span>
        <span class="badge">📍 Local Search</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Feature Grid ──
    st.markdown("""
<div class="feature-grid">
    <div class="feature-card">
        <div class="emoji">🤖</div>
        <div class="name">AI Visibility</div>
        <div class="desc">Which AI bots (ChatGPT, Claude, Perplexity, Gemini) can crawl your site — and which you're blocking.</div>
    </div>
    <div class="feature-card">
        <div class="emoji">📈</div>
        <div class="name">Combined Score</div>
        <div class="desc">SEO × AEO × GEO × GBP scored together with a priority fix list to improve.</div>
    </div>
    <div class="feature-card">
        <div class="emoji">⚡</div>
        <div class="name">Rules + AI</div>
        <div class="desc">50+ rules-based checks run instantly. Optional AI deep analysis adds personalized recommendations.</div>
    </div>
    <div class="feature-card">
        <div class="emoji">📄</div>
        <div class="name">PDF Reports</div>
        <div class="desc">Download HTML, text, or PDF reports — share them with clients or your team.</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Quick Stats / Social Proof ──
    st.markdown("""
<div class="proof-row">
    <div class="proof-item"><div class="num">50+</div><div class="label">Checks Per Site</div></div>
    <div class="proof-item"><div class="num">4</div><div class="label">Dimensions Scored</div></div>
    <div class="proof-item"><div class="num">8</div><div class="label">AI Bots Tracked</div></div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────
tab_visual, tab_analyze, tab_compare, tab_monitor, tab_settings = st.tabs([
    "👁️ Visual Audit",
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
        if _is_pro_user():
            use_ai = st.checkbox("🧠 AI Deep Analysis", value=True, help="Uses DeepSeek AI for comprehensive analysis")
        else:
            st.markdown("🔒 **AI Deep Analysis** — [Pro only](%s)" % STRIPE_LINK_PRO)
            use_ai = False
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
                st.warning("You've used your 3 free scans for today. You get 3 free scans every 24 hours — upgrade for unlimited access.")
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
            st.warning("You've used your 3 free scans for today. You get 3 free scans every 24 hours.")
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

        # ── Crawl ──
        with st.status("🔍 Crawling site...") as status:
            try:
                pages = crawl(url, max_pages=max_pages)
                if not pages:
                    st.error("Could not fetch the website. Check the URL and try again.")
                    st.stop()
                status.update(label=f"✅ Crawled {len(pages)} pages", state="complete")
            except Exception as e:
                st.error(f"Crawl failed: {e}")
                st.stop()

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
            status.update(label="✅ GBP done", state="complete")

        # ── Visual Audit (auto-screenshot, Pro only) ──
        vis_score = 0
        vis_report = ""
        if _is_pro_user() and os.getenv("ANTHROPIC_API_KEY"):
            with st.status("📸 Running visual audit...") as vis_status:
                tmp_shot = "/tmp/siteoracle_auto_screenshot.png"
                if capture_screenshot(url, tmp_shot):
                    vis_result = analyse_screenshot_visual(tmp_shot)
                    vis_score = vis_result.get("score", 0)
                    vis_report = vis_result.get("report", "")
                    vis_status.update(label=f"✅ Visual audit — {vis_score}/100", state="complete")
                else:
                    vis_status.update(label="⚠️ Screenshot skipped (page not reachable)", state="error")

        # ── AI Analysis (Pro only) ──
        ai_text = ""
        if use_ai and _is_pro_user():
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key:
                with st.spinner("Running AI deep analysis..."):
                    try:
                        ai_text = analyze_site(pages, engine="deepseek")
                    except Exception as e:
                        st.warning(f"AI analysis failed: {e}")

        # ── Scores ──
        ai_vis_score = geo.get("dimensions", {}).get("ai_visibility", {}).get("score", 0)
        combined = round(seo["score"]*0.20 + aeo["score"]*0.15 + geo["score"]*0.25 + gbp["score"]*0.10 + ai_vis_score*0.30)

        s_c, a_c, g_c, gbp_c, ai_c, vis_c, comb_c = st.columns(7)
        def _score_color(s): return "#22c55e" if s >= 70 else "#f59e0b" if s >= 40 else "#ef4444"
        with s_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(seo["score"])}">{seo["score"]}</div><div class="metric-label">Technical SEO</div></div>', unsafe_allow_html=True)
        with a_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(aeo["score"])}">{aeo["score"]}</div><div class="metric-label">AEO</div></div>', unsafe_allow_html=True)
        with g_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(geo["score"])}">{geo["score"]}</div><div class="metric-label">GEO</div></div>', unsafe_allow_html=True)
        with gbp_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(gbp["score"])}">{gbp["score"]}</div><div class="metric-label">GBP</div></div>', unsafe_allow_html=True)
        with ai_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(ai_vis_score)}">{ai_vis_score}</div><div class="metric-label">AI Visibility</div></div>', unsafe_allow_html=True)
        with vis_c:
            vis_disp = str(vis_score) if vis_score else "—"
            vis_col = _score_color(vis_score) if vis_score else "#64748b"
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{vis_col}">{vis_disp}</div><div class="metric-label">Visual Design</div></div>', unsafe_allow_html=True)
        with comb_c:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:{_score_color(combined)}">{combined}</div><div class="metric-label">Combined</div></div>', unsafe_allow_html=True)

        # ── Priority Fix List ──
        priority_list = _build_priority_fix_list(seo, aeo, geo, gbp)
        if priority_list:
            improvement = _estimate_improvement(priority_list)
            expected = combined + improvement
            st.markdown("### 🎯 Priority Fix List")
            st.caption(f"Fix these {len(priority_list)} items to reach an estimated score of **{expected}/100** (+{improvement} pts)")
            border_map = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}
            emoji_map  = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            for item in priority_list:
                sev = item["severity"]
                b = border_map.get(sev, "#64748b")
                e = emoji_map.get(sev, "⚪")
                st.markdown(f"""
                <div style="display:flex;gap:12px;padding:12px;margin-bottom:8px;background:#1e293b;border-radius:8px;border-left:4px solid {b};">
                    <div style="flex-shrink:0;width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:#0f172a;border-radius:50%;font-weight:700;font-size:13px;">{item['priority']}</div>
                    <div style="flex:1;">
                        <div style="display:flex;gap:8px;align-items:center;margin-bottom:2px;">
                            <span style="font-size:11px;font-weight:700;color:{b};">{e} {sev.upper()}</span>
                            <span style="font-size:11px;color:#64748b;background:#0f172a;padding:2px 8px;border-radius:4px;">{item['area']}</span>
                        </div>
                        <div style="font-weight:600;color:#f1f5f9;font-size:14px;">{item['check']}</div>
                        <div style="font-size:13px;color:#94a3b8;">{item['detail']}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

        # ── Detail Expanders ──
        with st.expander("🤖 AI Visibility — Can AI Bots See Your Site?", expanded=True):
            _show_ai_visibility(geo)
        with st.expander("🔧 Technical SEO Details"):
            col1, col2 = st.columns(2)
            with col1:
                for issue in seo.get("issues", []):
                    e = {"critical":"🔴","warning":"🟡","info":"🔵"}.get(issue["severity"],"⚪")
                    st.markdown(f"{e} **{issue['check']}**")
                    st.caption(issue["detail"])
            with col2:
                for p in seo.get("passes", []): st.markdown(f"✅ {p}")
        with st.expander("📝 Answer Engine Optimization (AEO)"):
            _show_dimensions(aeo)
        with st.expander("🤖 Generative Engine Optimization (GEO)"):
            _show_dimensions(geo)
        with st.expander("📍 Google Business Profile Alignment"):
            _show_dimensions(gbp)
        if ai_text:
            with st.expander("🧠 AI Deep Analysis", expanded=True):
                st.markdown(ai_text)
        elif use_ai and not _is_pro_user():
            with st.expander("🧠 AI Deep Analysis — Pro Feature"):
                render_upgrade_card("AI Deep Analysis")

        if vis_report:
            with st.expander("👁️ Visual Design Audit", expanded=False):
                st.markdown(vis_report)
        elif not _is_pro_user():
            with st.expander("👁️ Visual Design Audit — Pro Feature"):
                render_upgrade_card("Visual Design Audit")

        # ── Download Reports ──
        st.markdown("---")
        report_base = f"siteoracle_{url.replace('https://','').replace('/','_')[:30]}"
        col1, col2, col3 = st.columns(3)
        with col1:
            html_report = generate_html_report(url, pages, seo, aeo, geo, gbp, ai_text)
            st.download_button("📄 HTML Report", html_report, file_name=f"{report_base}.html", mime="text/html", use_container_width=True)
        with col2:
            txt_report = generate_report(url, pages, seo, aeo, geo, gbp, ai_text)
            st.download_button("📝 Text Report", txt_report, file_name=f"{report_base}.txt", mime="text/plain", use_container_width=True)
        with col3:
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf_report(url, pages, seo, aeo, geo, gbp, ai_text)
            if pdf_bytes:
                st.download_button("📕 PDF Report", pdf_bytes, file_name=f"{report_base}.pdf", mime="application/pdf", use_container_width=True)
            else:
                st.button("📕 PDF (unavailable)", disabled=True, use_container_width=True)

        # ── Email Capture ──
        st.markdown("---")
        if not st.session_state.get("report_email_sent"):
            st.markdown("#### 📬 Email me this report")
            st.caption("Get a copy sent to your inbox, plus tips to improve your score over the next 10 days.")
            ec1, ec2 = st.columns([3, 1])
            with ec1:
                report_email = st.text_input("Your email", placeholder="you@example.com", key="report_email", label_visibility="collapsed")
            with ec2:
                if st.button("Send Report", type="primary", use_container_width=True) and report_email:
                    top_issues = (seo.get("issues", []) + aeo.get("issues", []) + geo.get("issues", []))[:3]
                    ok = send_scan_report(
                        to=report_email, site_url=url,
                        seo_score=seo["score"], aeo_score=aeo["score"],
                        geo_score=geo["score"], gbp_score=gbp["score"],
                        ai_score=ai_vis_score, combined=combined,
                        top_issues=top_issues,
                    )
                    if ok:
                        st.session_state["report_email_sent"] = True
                        st.success("✅ Report sent! Check your inbox.")
                    else:
                        st.info("📋 Copy the URL above and paste it into SiteOracle any time to re-run.")
        else:
            st.success("✅ Report emailed — check your inbox.")

        # ── Score Badge ──
        if combined >= 60:
            clean_url = url.replace("https://", "").replace("http://", "").rstrip("/")
            badge_link = f"https://squadconsole.com/badge.html?score={combined}&site={clean_url}"
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
                <div>
                    <div style="font-weight:700;color:#e6edf3;margin-bottom:2px;">🏅 Your site scored {combined}/100 — share it!</div>
                    <div style="font-size:13px;color:#8b949e;">Get an embeddable score badge for your website or portfolio.</div>
                </div>
                <a href="{badge_link}" target="_blank" style="background:#ff6b6b;color:#fff;padding:8px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;white-space:nowrap;">Get Badge →</a>
            </div>
            """, unsafe_allow_html=True)

        # ── Record scan + upgrade prompt ──
        if not _is_pro_user():
            _record_scan()
            st.markdown(f"""
            <div class="upgrade-card">
                <h2>🚀 Unlock the full picture</h2>
                <p>Upgrade to Pro for unlimited scans, AI deep analysis, competitor comparison, monitoring and PDF reports.</p>
                <a href="{STRIPE_LINK_PRO}" target="_blank"
                   style="display:inline-block;background:#ff5555;color:white;padding:10px 24px;
                          border-radius:8px;text-decoration:none;font-weight:700;margin-top:8px;">
                    ⚡ Get Pro — $49/mo
                </a>
            </div>
            """, unsafe_allow_html=True)

    elif demo_btn:
        st.markdown("### 👀 Sample Report — squadconsole.com")
        st.caption("This is a demo showing what SiteOracle finds. No crawl needed.")
        s_c, a_c, g_c, gbp_c, ai_c, comb_c = st.columns(6)
        with s_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#f59e0b">62</div><div class="metric-label">Technical SEO</div></div>', unsafe_allow_html=True)
        with a_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#ef4444">45</div><div class="metric-label">AEO</div></div>', unsafe_allow_html=True)
        with g_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#ef4444">38</div><div class="metric-label">GEO</div></div>', unsafe_allow_html=True)
        with gbp_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#22c55e">70</div><div class="metric-label">GBP</div></div>', unsafe_allow_html=True)
        with ai_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#f59e0b">55</div><div class="metric-label">AI Visibility</div></div>', unsafe_allow_html=True)
        with comb_c:
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#f59e0b">49</div><div class="metric-label">Combined</div></div>', unsafe_allow_html=True)
        st.markdown("### 🎯 Priority Fix List")
        st.caption("Fix these 6 items to reach an estimated score of **76/100** (+27 pts)")
        demo_priority = [
            (1,"critical","AEO","No FAQPage schema found","FAQ schema directly influences featured snippets and voice search answers."),
            (2,"critical","Technical SEO","Missing meta description on 3 pages","3 of 5 crawled pages have no meta description."),
            (3,"warning","GEO","2 AI bots blocked in robots.txt","PerplexityBot and Bytespider are disallowed."),
            (4,"warning","AEO","Limited structured Q&A content","Add FAQ sections to key pages."),
            (5,"warning","Technical SEO","No canonical URLs detected","Add rel=canonical to all pages."),
            (6,"info","Technical SEO","Thin content on 2 pages","Expand content to improve topical authority."),
        ]
        bm = {"critical":"#ef4444","warning":"#f59e0b","info":"#3b82f6"}
        em = {"critical":"🔴","warning":"🟡","info":"🔵"}
        for num, sev, area, check, detail in demo_priority:
            b = bm[sev]
            st.markdown(f"""
            <div style="display:flex;gap:12px;padding:12px;margin-bottom:8px;background:#1e293b;border-radius:8px;border-left:4px solid {b};">
                <div style="flex-shrink:0;width:28px;height:28px;display:flex;align-items:center;justify-content:center;background:#0f172a;border-radius:50%;font-weight:700;font-size:13px;">{num}</div>
                <div style="flex:1;">
                    <div style="display:flex;gap:8px;align-items:center;margin-bottom:2px;">
                        <span style="font-size:11px;font-weight:700;color:{b};">{em[sev]} {sev.upper()}</span>
                        <span style="font-size:11px;color:#64748b;background:#0f172a;padding:2px 8px;border-radius:4px;">{area}</span>
                    </div>
                    <div style="font-weight:600;color:#f1f5f9;font-size:14px;">{check}</div>
                    <div style="font-size:13px;color:#94a3b8;">{detail}</div>
                </div>
            </div>""", unsafe_allow_html=True)
        with st.expander("🤖 AI Visibility — Can AI Bots See Your Site?", expanded=True):
            st.markdown('<div class="metric-box"><div class="metric-value" style="color:#f59e0b;font-size:48px;">55</div><div class="metric-label">AI Visibility Score</div></div>', unsafe_allow_html=True)
            st.markdown("**🚫 Blocked:** 🔴 PerplexityBot — Perplexity AI &nbsp;·&nbsp; 🔴 Bytespider — ByteDance")
            st.markdown("**✅ Allowed:** GPTBot · ClaudeBot · Google-Extended · Applebot · CCBot · cohere-ai")
        st.markdown("---")
        st.info("👆 This is sample data. Enter your own URL above and click **Analyze** to get your real score.")


# ══════════════════════════════════════════════════════════════════
# TAB: VISUAL AUDIT
# ══════════════════════════════════════════════════════════════════
with tab_visual:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1c2333,#161b22);border:1px solid #30363d;border-radius:16px;padding:28px 32px;margin-bottom:24px;">
        <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#ff6b6b;margin-bottom:8px;">NEW FEATURE</div>
        <h2 style="font-size:1.6rem;font-weight:800;color:#e6edf3;margin:0 0 8px;">👁️ AI Visual Audit</h2>
        <p style="color:#8b949e;margin:0;max-width:600px;">Upload a screenshot of any website and Claude AI will critique the design, CTA, trust signals, typography, and conversion elements — with a score and specific fixes.</p>
    </div>
    """, unsafe_allow_html=True)

    va_col1, va_col2 = st.columns([2, 1])
    with va_col1:
        visual_file = st.file_uploader(
            "Upload a website screenshot",
            type=["png", "jpg", "jpeg", "webp"],
            help="Full-page or above-the-fold screenshots work best",
            key="visual_audit_upload",
        )
    with va_col2:
        st.markdown("")
        st.markdown("")
        st.markdown("""
        **Works best with:**
        - Full-page screenshots
        - Above-the-fold captures
        - Mobile screenshots
        - Landing pages & homepages
        """)

    if visual_file:
        ext = visual_file.name.rsplit(".", 1)[-1]
        tmp_path = f"/tmp/siteoracle_visual.{ext}"
        Path(tmp_path).write_bytes(visual_file.getvalue())

        col_img, col_btn = st.columns([3, 1])
        with col_img:
            st.image(visual_file, caption="Your screenshot", use_container_width=True)
        with col_btn:
            st.markdown("")
            run_visual = st.button("🔍 Audit This Page", type="primary", use_container_width=True)

        if run_visual:
            if not os.getenv("ANTHROPIC_API_KEY"):
                st.error("Claude API key not configured. Add ANTHROPIC_API_KEY to Railway environment variables.")
            else:
                with st.spinner("Claude is reviewing your site design... (~20 seconds)"):
                    result = analyse_screenshot_visual(tmp_path)

                if result["error"]:
                    st.error(f"Visual audit failed: {result['error']}")
                else:
                    score = result["score"]
                    score_color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"

                    st.markdown(f"""
                    <div style="text-align:center;padding:24px;background:#161b22;border:1px solid #30363d;border-radius:12px;margin-bottom:24px;">
                        <div style="font-size:64px;font-weight:800;color:{score_color};line-height:1;">{score}</div>
                        <div style="color:#8b949e;font-size:14px;margin-top:4px;">Visual Design Score / 100</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(result["report"])

                    # Email capture
                    st.markdown("---")
                    st.markdown("#### 📬 Email me this visual audit")
                    vc1, vc2 = st.columns([3, 1])
                    with vc1:
                        va_email = st.text_input("Your email", placeholder="you@example.com", key="va_email", label_visibility="collapsed")
                    with vc2:
                        if st.button("Send", use_container_width=True) and va_email:
                            st.success("✅ We'll add email delivery for visual audits soon — bookmark this page!")

                    if not _is_pro_user():
                        st.markdown(f"""
                        <div class="upgrade-card" style="margin-top:24px;">
                            <h2>⚡ Unlimited Visual Audits — Pro</h2>
                            <p>Run visual audits on unlimited pages. Compare your site vs competitors. Get PDF reports.</p>
                            <a href="{STRIPE_LINK_PRO}" target="_blank"
                               style="display:inline-block;background:#ff5555;color:white;padding:10px 24px;
                                      border-radius:8px;text-decoration:none;font-weight:700;margin-top:8px;">
                                Get Pro — $49/mo
                            </a>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        # Show example of what the audit produces
        st.markdown("""
        <div style="background:#161b22;border:1px dashed #30363d;border-radius:12px;padding:40px;text-align:center;color:#8b949e;">
            <div style="font-size:48px;margin-bottom:12px;">📸</div>
            <div style="font-size:16px;font-weight:600;color:#e6edf3;margin-bottom:8px;">Upload a screenshot to get started</div>
            <div style="font-size:14px;">Claude will score your design and give specific recommendations to improve conversions</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### What Claude checks:")
        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            st.markdown("""
            **Above the fold**
            - Headline clarity
            - CTA visibility
            - Value proposition

            **Typography**
            - Readability
            - Font hierarchy
            - Contrast
            """)
        with ex2:
            st.markdown("""
            **Trust signals**
            - Social proof
            - Authority logos
            - Security badges

            **Layout**
            - Visual hierarchy
            - Whitespace
            - Eye flow
            """)
        with ex3:
            st.markdown("""
            **Conversion**
            - Button copy & placement
            - Form friction
            - Next step clarity

            **Mobile**
            - Touch targets
            - Text sizing
            - Layout adaptability
            """)


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

    Built by [SquadConsole](https://squadconsole.com)
    """)



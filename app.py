"""SiteOracle Streamlit web interface — full feature suite."""

import streamlit as st
import os
import datetime
from pathlib import Path

from crawler import crawl
from check_seo import check_technical_seo
from check_aeo import check_aeo
from check_geo import check_geo
from check_gbp import check_gbp, extract_business_info
from analyzer import analyze_site, analyze_screenshot
from reporter import generate_report, generate_html_report
from comparison import compare_sites, generate_comparison_report
from monitor import setup_monitor, load_monitors, save_snapshot, get_trend, generate_trend_report

st.set_page_config(
    page_title="SiteOracle",
    page_icon="🔍",
    layout="wide",
)

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { padding: 1rem; }
    .stApp { background: #f8fafc; }
    h1, h2, h3 { color: #0f172a !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; background: #e2e8f0; padding: 4px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; }
    .report-box { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin: 1rem 0; border: 1px solid #e2e8f0; }
    .metric-box { text-align: center; padding: 1rem; background: white; border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .metric-value { font-size: 32px; font-weight: 700; }
    .metric-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px; }
    .status-pass { color: #22c55e; }
    .status-warn { color: #f59e0b; }
    .status-fail { color: #ef4444; }
</style>
""", unsafe_allow_html=True)

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
                             help="Uses DeepSeek/OpenAI/Claude for 6-dimension analysis")
    with col2:
        engine = st.selectbox("AI Engine", ["deepseek", "openai", "claude"],
                              help="Requires the corresponding API key in Settings")
    with col3:
        biz_name = st.text_input("Business name (for GBP)", placeholder="Optional",
                                 help="Helps with Google Business Profile alignment checks")

    col1, col2 = st.columns([1, 1])
    with col1:
        run_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    with col2:
        screenshot_file = st.file_uploader("Or upload screenshot", type=["png", "jpg", "jpeg", "webp"],
                                            label_visibility="collapsed")

    if screenshot_file:
        # Screenshot mode
        ext = screenshot_file.name.rsplit(".", 1)[-1]
        temp_path = Path(f"/tmp/siteoracle_screenshot.{ext}")
        temp_path.write_bytes(screenshot_file.getvalue())
        st.image(screenshot_file, caption="Uploaded Screenshot", use_container_width=True)

        if st.button("📸 Analyze Screenshot", type="primary"):
            if not os.getenv("OPENAI_API_KEY"):
                st.error("Screenshot analysis requires an OpenAI API key. Set it in Settings tab.")
                st.stop()
            with st.spinner("Analyzing screenshot..."):
                result = analyze_screenshot(str(temp_path))
            st.markdown("### 📸 Screenshot Analysis")
            st.markdown(result)

    elif run_btn and url:
        if not url.startswith("http"):
            url = "https://" + url

        # ── Crawl ──
        with st.status("🔍 Crawling site...") as status:
            pages = crawl(url, max_pages=max_pages)
            if not pages:
                st.error("Could not fetch the website. Check the URL and try again.")
                st.stop()
            status.update(label=f"✅ Crawled {len(pages)} pages", state="complete")

        # ── Run Checks ──
        with st.status("Running checks...") as status:
            seo = check_technical_seo(pages)
            status.update(label="✅ Technical SEO done")

            aeo = check_aeo(pages)
            status.update(label="✅ AEO done")

            geo = check_geo(pages)
            status.update(label="✅ GEO done")

            biz_info = {"name": biz_name} if biz_name else None
            gbp = check_gbp(pages, biz_info)
            status.update(label="✅ GBP done")

        # ── AI Analysis ──
        ai_text = ""
        if use_ai:
            api_key = {
                "deepseek": os.getenv("DEEPSEEK_API_KEY"),
                "openai": os.getenv("OPENAI_API_KEY"),
                "claude": os.getenv("ANTHROPIC_API_KEY"),
            }.get(engine)

            if api_key:
                with st.spinner(f"Running AI analysis ({engine})..."):
                    try:
                        ai_text = analyze_site(pages, engine=engine)
                    except Exception as e:
                        st.warning(f"AI analysis failed: {e}")
                        ai_text = ""
            else:
                st.info(f"No {engine.upper()}_API_KEY found. AI analysis skipped. Configure in Settings tab.")

        # ── Display Scores ──
        combined = round(seo["score"] * 0.35 + aeo["score"] * 0.25 + geo["score"] * 0.25 + gbp["score"] * 0.15)

        s_c, a_c, g_c, gbp_c, comb_c = st.columns(5)
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
        with comb_c:
            color = "#22c55e" if combined >= 70 else "#f59e0b" if combined >= 40 else "#ef4444"
            st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{combined}</div><div class="metric-label">Combined</div></div>""", unsafe_allow_html=True)

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

        # ── Report Download ──
        col1, col2 = st.columns(2)
        with col1:
            html = generate_html_report(url, pages, seo, aeo, geo, gbp, ai_text)
            report_filename = f"siteoracle_{url.replace('https://', '').replace('/', '_')[:30]}.html"
            st.download_button(
                "📄 Download HTML Report",
                html,
                file_name=report_filename,
                mime="text/html",
                use_container_width=True,
            )
        with col2:
            text = generate_report(url, pages, seo, aeo, geo, gbp, ai_text)
            st.download_button(
                "📝 Download Text Report",
                text,
                file_name=report_filename.replace(".html", ".txt"),
                mime="text/plain",
                use_container_width=True,
            )

        # ── Offer Monitoring ──
        if st.button("📊 Start Monitoring This Site", use_container_width=True):
            config = setup_monitor(url, schedule="weekly", max_pages=max_pages)
            # Also save the current snapshot
            snapshot_results = {
                "seo": seo, "aeo": aeo, "geo": geo, "gbp": gbp,
                "combined": combined, "pages_analyzed": len(pages)
            }
            save_snapshot(config["id"], snapshot_results)
            st.success(f"Monitoring started for {url}! Check the Monitoring tab.")


# ══════════════════════════════════════════════════════════════════
# TAB: COMPARE
# ══════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown("### ⚔️ Compare Two Sites")
    st.caption("Analyze and compare your site against a competitor.")

    col1, col2 = st.columns(2)
    with col1:
        site_a = st.text_input("Your site", placeholder="https://yoursite.com", key="comp_a")
    with col2:
        site_b = st.text_input("Competitor", placeholder="https://competitor.com", key="comp_b")

    comp_pages = st.slider("Pages to crawl per site", 1, 10, 3, key="comp_pages")

    if st.button("⚔️ Compare", type="primary", use_container_width=True) and site_a and site_b:
        if not site_a.startswith("http"): site_a = "https://" + site_a
        if not site_b.startswith("http"): site_b = "https://" + site_b

        with st.spinner("Analyzing both sites..."):
            comparison = compare_sites([site_a, site_b], max_pages=comp_pages)

        if comparison.get("error"):
            st.error(f"Comparison failed: {comparison['error']}")
        else:
            # Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                s = comparison["sites"][0]
                color = "#22c55e" if s["combined"] >= 70 else "#f59e0b"
                st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{s["combined"]}</div><div class="metric-label">{s["name"]}</div></div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""<div class="metric-box" style="font-size:24px;">vs</div>""", unsafe_allow_html=True)
            with col3:
                s = comparison["sites"][1]
                color = "#22c55e" if s["combined"] >= 70 else "#f59e0b"
                st.markdown(f"""<div class="metric-box"><div class="metric-value" style="color:{color}">{s["combined"]}</div><div class="metric-label">{s["name"]}</div></div>""", unsafe_allow_html=True)

            # Breakdown
            st.markdown("### 📊 Score Breakdown")
            for site in comparison["sites"]:
                if site.get("error"):
                    st.warning(f"{site['name']}: {site['error']}")
                else:
                    with st.expander(f"🔍 {site['name']}"):
                        cols = st.columns(4)
                        cols[0].metric("SEO", f"{site['seo']['score']}/100")
                        cols[1].metric("AEO", f"{site['aeo']['score']}/100")
                        cols[2].metric("GEO", f"{site['geo']['score']}/100")
                        cols[3].metric("GBP", f"{site['gbp']['score']}/100")

            # Gap analysis
            if comparison.get("gaps"):
                st.markdown("### 🔍 Key Differentiators")
                for g in comparison["gaps"]:
                    st.markdown(f"**{g['area']}**: {g['leader']} leads by **{g['gap']}** points")

            # Full report
            report_text = generate_comparison_report(comparison)
            st.text(report_text)


# ══════════════════════════════════════════════════════════════════
# TAB: MONITORING
# ══════════════════════════════════════════════════════════════════
with tab_monitor:
    st.markdown("### 📊 Site Monitoring")
    st.caption("Track scores over time with scheduled snapshots.")

    monitors = load_monitors()
    if not monitors:
        st.info("No monitors set up yet. Run an analysis and click 'Start Monitoring' to begin.")
    else:
        for mon in monitors:
            with st.expander(f"📊 {mon.get('name', mon['url'])} — {mon.get('schedule', '?')}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("Snapshots", len(mon.get("history", [])))
                with col2: st.metric("Schedule", mon.get("schedule", "unknown"))
                with col3: st.metric("Last Run", mon.get("last_run", "never")[:10] if mon.get("last_run") else "never")

                trend = get_trend(mon["id"])
                if trend:
                    st.markdown("#### Trend (Last 10 Snapshots)")
                    st.line_chart({k: [s[k] for s in trend] for k in ["seo_score", "aeo_score", "geo_score", "combined_score"]})

                    # Mini report
                    report = generate_trend_report(mon["id"])
                    st.text(report)


# ══════════════════════════════════════════════════════════════════
# TAB: SETTINGS
# ══════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("### ⚙️ API Keys")
    st.caption("Set API keys for AI analysis features. Keys are stored in environment variables.")

    keys = {
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
    }

    for name, val in keys.items():
        masked = val[:8] + "..." + val[-4:] if len(val) > 12 else ("<not set>" if not val else val)
        st.text_input(name, value=val, type="password",
                      help=f"Current: {masked}")

    st.markdown("---")
    st.markdown("""
    ### About SiteOracle
    
    **Version**: 1.0  
    **Capabilities**:  
    - 🔧 Technical SEO (15+ rules-based checks, scored /100)  
    - 📝 Answer Engine Optimization (7 dimensions)  
    - 🤖 Generative Engine Optimization (7 dimensions)  
    - 📍 Google Business Profile alignment (7 dimensions)  
    - 🤖 AI deep analysis (6 dimensions via DeepSeek/OpenAI/Claude)  
    - ⚔️ Competitive comparison  
    - 📊 Scheduled monitoring  
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

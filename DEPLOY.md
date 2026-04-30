# Deploy to Railway, Render, or Fly.io

# Environment variables needed:
# DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY

# ── Railway ──────────────────────────────────────
# 1. Install Railway CLI
# 2. railway login
# 3. railway init
# 4. Add these env vars: DEEPSEEK_API_KEY=your_key
# 5. railway up

# ── Render ───────────────────────────────────────
# 1. New Web Service → Connect repo
# 2. Build command: pip install -r requirements.txt
# 3. Start command: streamlit run app.py --server.port=10000
# 4. Add env vars in dashboard

# ── Fly.io ───────────────────────────────────────
# fly launch
# fly secrets set DEEPSEEK_API_KEY=your_key
# fly deploy

# ── Local ────────────────────────────────────────
# docker build -t siteoracle .
# docker run -p 8501:8501 -e DEEPSEEK_API_KEY=your_key siteoracle

FROM python:3.11-slim

WORKDIR /app

# Playwright browsers installed here so non-root user can access them after chown
ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers

# Install system dependencies for WeasyPrint (PDF generation)
# WeasyPrint needs: pango, cairo, gdk-pixbuf, GLib
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nginx \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install Python dependencies then Playwright Chromium (with its OS deps)
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

# Create non-root user; grant write to nginx tmp dirs
RUN useradd -m -u 1000 siteoracle && chown -R siteoracle:siteoracle /app \
    && mkdir -p /tmp/nginx_client_body /tmp/nginx_proxy /tmp/nginx_fastcgi \
                /tmp/nginx_uwsgi /tmp/nginx_scgi \
    && chown -R siteoracle:siteoracle /tmp/nginx_* \
    && chmod +x /app/start.sh
USER siteoracle

# nginx on :8501 (public), Streamlit on :8502 (internal)
EXPOSE 8501

# Health check hits nginx → Streamlit
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["/app/start.sh"]

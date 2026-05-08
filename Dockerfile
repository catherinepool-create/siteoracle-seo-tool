FROM python:3.11-slim

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers

# Install system dependencies for WeasyPrint (PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install Python dependencies then Playwright Chromium (with its OS deps)
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

# Create non-root user
RUN useradd -m -u 1000 siteoracle && chown -R siteoracle:siteoracle /app \
    && chmod +x /app/start.sh
USER siteoracle

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8501}/_stcore/health || exit 1

CMD ["/app/start.sh"]

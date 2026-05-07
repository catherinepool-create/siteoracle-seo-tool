#!/bin/bash
set -e

# nginx runs on :8501 (public), proxies to Streamlit on :8502 (internal)
nginx -c /app/nginx.conf -g "daemon off;" &

exec streamlit run app.py \
    --server.port=8502 \
    --server.address=127.0.0.1

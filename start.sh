#!/bin/bash
set -e

PORT=${PORT:-8080}
STREAMLIT_PORT=${STREAMLIT_PORT:-8501}
API_PORT=${API_PORT:-8000}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"

# Start Streamlit on internal port
echo "Starting Streamlit on port $STREAMLIT_PORT..."
cd "$SCRIPT_DIR" && python -m streamlit run "$SCRIPT_DIR/app.py" \
    --server.port=$STREAMLIT_PORT \
    --server.address=127.0.0.1 \
    --server.headless=true &
STREAMLIT_PID=$!

# Start the API server on the public port (handles /api/* routes, proxies everything else)
echo "Starting API server on port $PORT..."
cd "$SCRIPT_DIR" && python api_server.py \
    --port=$PORT \
    --streamlit-url=http://127.0.0.1:$STREAMLIT_PORT \
    --lead-file="$HOME/.siteoracle/leads.json"

# Cleanup
kill $STREAMLIT_PID 2>/dev/null

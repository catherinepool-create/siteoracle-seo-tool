#!/bin/bash
set -e

PORT=${PORT:-8080}
API_PORT=${API_PORT:-8000}

# Get the script's directory (works both locally and in Docker)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start the JSON API server in the background
echo "Starting JSON API server on port $API_PORT..."
cd "$SCRIPT_DIR" && python api_server.py --port $API_PORT &
API_PID=$!

# Start Streamlit on the main port
echo "Starting Streamlit on port $PORT..."
exec streamlit run "$SCRIPT_DIR/app.py" \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true

# If Streamlit exits, kill the API server
kill $API_PID 2>/dev/null

#!/bin/bash
set -e

PORT=${PORT:-8080}
API_PORT=${API_PORT:-8081}

# Start the JSON API server in the background
python api.py &

# Start the Streamlit app
exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true

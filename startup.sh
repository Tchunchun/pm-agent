#!/bin/bash
# Azure App Service — Custom Startup Command for Streamlit
# Azure Linux App Service uses PORT env var (defaults to 8000)

PORT="${PORT:-8000}"

# Create persistent data directories on Azure's /home mount
mkdir -p /home/pm_agent_data
mkdir -p /home/pm_agent_inbox

# Install dependencies (Oryx may have already done this, but belt-and-suspenders)
pip install -r agent-claude/requirements.txt --quiet 2>/dev/null || true

python -m streamlit run agent-claude/app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false

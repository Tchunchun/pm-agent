#!/bin/bash
# Azure App Service — Custom Startup Command for Streamlit
# Azure Linux App Service uses PORT env var (defaults to 8000)

PORT="${PORT:-8000}"

cd /home/site/wwwroot

# Install dependencies (belt-and-suspenders — also done by Oryx build)
pip install -r agent-claude/requirements.txt --quiet

# Create persistent data directory on Azure's /home mount
# /home is backed by Azure Storage and survives restarts + redeployments
mkdir -p /home/pm_agent_data
mkdir -p /home/pm_agent_inbox

python -m streamlit run agent-claude/app.py \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false

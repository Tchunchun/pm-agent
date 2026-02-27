#!/bin/bash
cd "/Users/chunchun/Documents/ccfiles/PM Agent"
source .venv/bin/activate
streamlit run agent-claude/app.py --server.port 8502

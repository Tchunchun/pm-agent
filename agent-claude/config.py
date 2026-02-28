import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from the app directory (works regardless of cwd)
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = Path.home() / "pm_agent_inbox"
OUTPUT_DIR = BASE_DIR / "output"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
INBOX_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------ #
# API credentials                                                      #
# ------------------------------------------------------------------ #

# Shared API key — used for both standard OpenAI and Azure OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Azure OpenAI — set these to switch from standard OpenAI to Azure
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# Model / deployment name
# • Standard OpenAI: model name, e.g. "gpt-4o-mini"
# • Azure OpenAI:    your deployment name (set via AZURE_OPENAI_DEPLOYMENT)
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

APP_TITLE = "PM Agent"
APP_ICON = "🧭"

# Analyst low-data warning threshold
MIN_REQUESTS_FOR_ANALYSIS = 10


def make_openai_client():
    """
    Return an AzureOpenAI client if AZURE_OPENAI_ENDPOINT is configured,
    otherwise a standard OpenAI client.

    All agents call this instead of constructing OpenAI() directly,
    so switching between standard and Azure is a one-line .env change.
    """
    if AZURE_OPENAI_ENDPOINT:
        from openai import AzureOpenAI
        return AzureOpenAI(
            api_key=OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=5,
            timeout=60.0,
        )
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY, max_retries=5, timeout=60.0)

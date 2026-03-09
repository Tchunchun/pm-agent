import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from the app directory (works regardless of cwd)
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

BASE_DIR = Path(__file__).parent

# Azure App Service: use /home mount for persistent storage so data
# survives redeployments.  Local dev keeps the original paths.
_AZURE = os.environ.get("WEBSITE_SITE_NAME")  # set automatically by Azure App Service

if _AZURE:
    DATA_DIR  = Path("/home/pm_agent_data")
    INBOX_DIR = Path("/home/pm_agent_inbox")
else:
    DATA_DIR  = BASE_DIR / "data"
    INBOX_DIR = Path.home() / "pm_agent_inbox"

OUTPUT_DIR = BASE_DIR / "output"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
INBOX_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------ #
# API credentials  (Azure OpenAI is the default path)                  #
# ------------------------------------------------------------------ #

# Azure OpenAI (primary)
AZURE_OPENAI_ENDPOINT    = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY         = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# Fallback: standard OpenAI API key (used only when Azure endpoint is NOT set)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Model / deployment name
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")

APP_TITLE = "PM Agent"
APP_ICON = "🧭"

# Analyst low-data warning threshold
MIN_REQUESTS_FOR_ANALYSIS = 10

# ------------------------------------------------------------------ #
# Google OAuth2 credentials                                            #
# ------------------------------------------------------------------ #
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_URL              = os.environ.get("APP_URL", "http://localhost:8501")


def has_valid_credentials() -> bool:
    """Return True if enough credentials are set to create an LLM client."""
    if AZURE_OPENAI_ENDPOINT and (AZURE_OPENAI_KEY or OPENAI_API_KEY):
        return True
    if OPENAI_API_KEY:          # fallback to standard OpenAI
        return True
    return False


def make_openai_client():
    """
    Return an AzureOpenAI client (default) or a standard OpenAI client.

    Azure OpenAI is the primary path.  Set AZURE_OPENAI_ENDPOINT and
    AZURE_OPENAI_KEY (or OPENAI_API_KEY) in your environment / .env.
    If AZURE_OPENAI_ENDPOINT is *not* set, falls back to standard OpenAI.
    """
    if AZURE_OPENAI_ENDPOINT:
        from openai import AzureOpenAI
        _key = AZURE_OPENAI_KEY or OPENAI_API_KEY
        return AzureOpenAI(
            api_key=_key,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=5,
            timeout=60.0,
        )
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY, max_retries=5, timeout=60.0)


def get_agno_model(max_tokens: int | None = None):
    """
    Return an Agno model instance configured for the current environment.

    Uses AzureOpenAI when AZURE_OPENAI_ENDPOINT is set, otherwise standard
    OpenAI. The model/deployment name comes from the MODEL constant.
    """
    if AZURE_OPENAI_ENDPOINT:
        from agno.models.azure import AzureOpenAI as AgnoAzure
        _key = AZURE_OPENAI_KEY or OPENAI_API_KEY
        return AgnoAzure(
            id=MODEL,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_deployment=MODEL,
            api_key=_key,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=5,
            max_completion_tokens=max_tokens,
        )
    from agno.models.openai import OpenAIChat
    return OpenAIChat(
        id=MODEL,
        api_key=OPENAI_API_KEY,
        max_retries=5,
        max_completion_tokens=max_tokens,
    )

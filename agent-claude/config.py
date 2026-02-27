import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = Path.home() / "pm_agent_inbox"
OUTPUT_DIR = BASE_DIR / "output"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
INBOX_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL = "gpt-4o-mini"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

APP_TITLE = "PM Agent"
APP_ICON = "🧭"

# Analyst low-data warning threshold
MIN_REQUESTS_FOR_ANALYSIS = 10

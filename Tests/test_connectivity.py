"""Quick connectivity test — run from project root with the venv active."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-claude"))

from config import make_openai_client, MODEL, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, OPENAI_API_KEY

_active_key = AZURE_OPENAI_KEY or OPENAI_API_KEY
print(f"Python:   {sys.executable}")
print(f"Endpoint: {AZURE_OPENAI_ENDPOINT or '(standard OpenAI)'}")
print(f"Model:    {MODEL}")
print(f"API key:  {'set (' + str(len(_active_key)) + ' chars)' if _active_key else 'MISSING'}")

client = make_openai_client()
print(f"Client:   {type(client).__name__}\n")

for i in range(3):
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": "hi"}], max_tokens=5
        )
        print(f"  Call {i+1}: OK  ({time.time()-t0:.1f}s) — {resp.choices[0].message.content}")
    except Exception as e:
        print(f"  Call {i+1}: FAIL ({time.time()-t0:.1f}s) — {type(e).__name__}: {e}")

print("\nDone.")

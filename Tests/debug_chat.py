"""Debug script: test sending a message in the test workroom."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-claude"))

from storage import StorageManager
from agents import Orchestrator

storage = StorageManager()
orch = Orchestrator(storage)

ws = storage.get_workroom("8d713c30")
if not ws:
    print("Workroom 8d713c30 not found")
    sys.exit(1)

print(f"Workroom: {ws.title}")
print(f"Active agents: {ws.active_agents}")
print(f"Discussion mode: {ws.discussion_mode}")

msgs = storage.load_workroom_messages("8d713c30")
print(f"Existing messages: {len(msgs)}")

test_msg = "What are the key requirements for the denial prediction model?"
print(f"\nSending: {test_msg}")

try:
    result = orch.handle_message(
        test_msg,
        file_bytes=None,
        filename="",
        date="2026-02-27",
        document_context=None,
        conversation_history=msgs,
        active_agents=ws.active_agents,
        workroom=ws,
    )
    print(f"Result agent: {result.get('agent', '')}")
    print(f"Result text (first 300): {result.get('text', '')[:300]}")
    mr = result.get("multi_response") or []
    print(f"Multi response: {len(mr)} items")
    for r in mr:
        print(f"  - {r.get('agent', '?')}: {r.get('text', '')[:100]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

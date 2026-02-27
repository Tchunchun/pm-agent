"""Complete the facilitator opening for Test ROOM 1."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-claude"))

from storage import StorageManager
from agents.facilitator_agent import FacilitatorAgent

def main():
    storage = StorageManager()
    workrooms = storage.list_workrooms()
    ws = None
    for w in workrooms:
        if w.title == "Test ROOM 1":
            ws = w
            break

    if not ws:
        print("ERROR: Test ROOM 1 not found")
        return

    print(f"Found workroom: {ws.id}")
    print(f"Active agents: {ws.active_agents}")

    # Check if messages already exist
    existing = storage.load_workroom_messages(ws.id)
    if existing:
        print(f"Messages already exist ({len(existing)}), skipping.")
        return

    AGENT_REGISTRY = [
        {"key": "intake",     "label": "Intake",      "emoji": "\U0001f4e5", "tier": 1, "description": "Log requests - Process files - Document Q&A"},
        {"key": "planner",    "label": "Planner",     "emoji": "\U0001f4c5", "tier": 1, "description": "Plan your day - Synthesise priorities"},
        {"key": "analyst",    "label": "Analyst",     "emoji": "\U0001f4ca", "tier": 1, "description": "Trends - Gaps - Risks - Decisions"},
        {"key": "challenger", "label": "Challenger",  "emoji": "\u2694\ufe0f",  "tier": 2, "description": "Red-team ideas - Argue the opposing view"},
        {"key": "writer",     "label": "Writer",      "emoji": "\u270d\ufe0f",  "tier": 2, "description": "Draft emails - Teams messages - Exec briefs"},
        {"key": "researcher", "label": "Researcher",  "emoji": "\U0001f50d", "tier": 2, "description": "Deep dives - Industry context - Customer background"},
    ]

    for ca in storage.list_custom_agents():
        AGENT_REGISTRY.append({
            "key": ca.key, "label": ca.label, "emoji": ca.emoji,
            "tier": 3, "description": ca.description or ca.system_prompt[:80],
        })

    init_msgs = []

    pdf_name = "Pre-Claim Denial Intelligence PRD.doc.pdf"
    init_msgs.append({
        "role": "user",
        "content": f"Material uploaded: **{pdf_name}**\n\nThis document is available as context for our discussion.",
    })

    print("Running FacilitatorAgent.open_session...")
    facilitator = FacilitatorAgent()
    agent_details = [a for a in AGENT_REGISTRY if a["key"] in ws.active_agents]
    opening_msg = facilitator.open_session(ws, agent_details)
    print(f"\n--- Facilitator Opening ---\n{opening_msg}\n---")

    init_msgs.append({
        "role": "assistant",
        "content": opening_msg,
        "agent": "Facilitator",
    })

    storage.save_workroom_messages(ws.id, init_msgs)
    print(f"\nDONE - {len(init_msgs)} messages saved for '{ws.title}'")

if __name__ == "__main__":
    main()

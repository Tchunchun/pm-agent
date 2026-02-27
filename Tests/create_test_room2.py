"""Create Test ROOM 2 workroom using test data with fresh agent selection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent-claude"))

from config import OPENAI_API_KEY
from storage import StorageManager
from models.workroom import WorkroomSession
from agents.topic_classifier import TopicClassifier
from agents.facilitator_agent import FacilitatorAgent
from utils.file_parser import extract_text_from_file


def main():
    topic = "Test ROOM 2"
    objective = (
        "Customer has shared the business requirement for the Denial Intelligence, "
        "and more specifically, the models that they need help with. "
        "Discuss the requirement and define the model requirements."
    )
    outcome = "Draft model requirement document + follow-up questions with customer"

    print(f"Topic:     {topic}")
    print(f"Objective: {objective}")
    print(f"Outcome:   {outcome}")

    # Read the PDF
    pdf_path = Path(__file__).resolve().parent / "Pre-Claim Denial Intelligence PRD.doc.pdf"
    pdf_bytes = pdf_path.read_bytes()
    doc_text = extract_text_from_file(pdf_bytes, pdf_path.name)
    print(f"\nPDF parsed: {len(doc_text):,} chars")

    # Build full agent registry including custom agents
    AGENT_REGISTRY = [
        {"key": "intake",     "label": "Intake",      "emoji": "\U0001f4e5", "tier": 1, "description": "Log requests - Process files - Document Q&A"},
        {"key": "planner",    "label": "Planner",     "emoji": "\U0001f4c5", "tier": 1, "description": "Plan your day - Synthesise priorities"},
        {"key": "analyst",    "label": "Analyst",     "emoji": "\U0001f4ca", "tier": 1, "description": "Trends - Gaps - Risks - Decisions"},
        {"key": "challenger", "label": "Challenger",  "emoji": "\u2694\ufe0f",  "tier": 2, "description": "Red-team ideas - Argue the opposing view"},
        {"key": "writer",     "label": "Writer",      "emoji": "\u270d\ufe0f",  "tier": 2, "description": "Draft emails - Teams messages - Exec briefs"},
        {"key": "researcher", "label": "Researcher",  "emoji": "\U0001f50d", "tier": 2, "description": "Deep dives - Industry context - Customer background"},
    ]

    storage = StorageManager()
    all_agents = list(AGENT_REGISTRY)
    for ca in storage.list_custom_agents():
        all_agents.append({
            "key": ca.key, "label": ca.label, "emoji": ca.emoji,
            "tier": 3, "description": ca.description or ca.system_prompt[:80],
        })

    print(f"\nTotal agents available: {len(all_agents)}")
    for a in all_agents:
        print(f"  [{a['tier']}] {a['emoji']} {a['key']}: {a['description'][:60]}")

    print("\nRunning TopicClassifier...")
    classifier = TopicClassifier()
    result = classifier.classify(topic=topic, objective=objective, outcome=outcome, available_agents=all_agents)
    recommended = result.get("recommended", [])
    rationale = result.get("rationale", {})
    print(f"Recommended agents: {recommended}")
    for k, v in rationale.items():
        print(f"  {k}: {v}")

    # Create workroom
    full_goal = f"{objective}\n\nDesired outcome: {outcome}"
    final_agents = recommended if recommended else ["intake", "analyst", "writer"]

    new_ws = WorkroomSession(
        title="Test ROOM 2",
        goal=full_goal,
        key_outcome=outcome,
        mode="work",
        output_type="requirements",
        active_agents=final_agents,
        topic_description=topic,
        ai_recommended_agents=recommended,
        facilitator_enabled=True,
        facilitator_intro_sent=True,
    )
    storage.save_workroom(new_ws)
    print(f"\nWorkroom created: id={new_ws.id}")
    print(f"Active agents: {new_ws.active_agents}")

    # Initial messages
    init_msgs = []
    init_msgs.append({
        "role": "user",
        "content": f"Material uploaded: **{pdf_path.name}**\n\nThis document is available as context for our discussion.",
    })

    print("FacilitatorAgent opening session...")
    facilitator = FacilitatorAgent()
    agent_details = [a for a in all_agents if a["key"] in new_ws.active_agents]
    opening_msg = facilitator.open_session(new_ws, agent_details)
    print(f"\n--- Facilitator Opening ---\n{opening_msg}\n---")

    init_msgs.append({
        "role": "assistant",
        "content": opening_msg,
        "agent": "Facilitator",
    })

    storage.save_workroom_messages(new_ws.id, init_msgs)
    print(f'\nDONE - Workroom "{new_ws.title}" (id: {new_ws.id}) is ready.')
    print(f"Messages saved: {len(init_msgs)}")
    print("Open the app and click on this workroom in the sidebar.")


if __name__ == "__main__":
    main()

"""
FacilitatorAgent — drives a workroom session toward its stated objective.

Responsibilities:
  1. open_session()      — generates the opening message when a workroom is created
  2. should_summarise()  — returns True every N user messages
  3. generate_summary()  — synthesises progress and suggests next focus
"""

import logging
from config import MODEL, make_openai_client

logger = logging.getLogger(__name__)

FACILITATOR_SYSTEM = """You are a skilled meeting facilitator embedded in a multi-agent AI workroom.

Your role:
- Keep the conversation focused on the stated objective and desired outcome.
- Acknowledge progress, highlight gaps, and suggest concrete next steps.
- Be concise and direct — this is a working session, not a lecture.
- Use markdown for structure when helpful (bullet points, bold headers).
- Address the human PM by role (e.g., "For the next step, you may want to...").
- Do NOT impersonate other agents or make decisions on their behalf.
"""


class FacilitatorAgent:
    def __init__(self):
        self.client = make_openai_client()

    # ------------------------------------------------------------------ #
    # Opening message                                                      #
    # ------------------------------------------------------------------ #

    def open_session(self, workroom, agents: list[dict]) -> str:
        """
        Generates the first message in a new workroom.
        Introduces the session objective, agents present, and asks an
        opening question to kick things off.

        workroom: WorkroomSession instance
        agents: list of agent dicts with keys: key, label, emoji, description
        """
        agent_lines = "\n".join(
            f"- {a.get('emoji', '🤖')} **{a['label']}**: {a.get('description', '')}"
            for a in agents
        )

        prompt = f"""You are opening a new workroom session. Use the details below to write a focused, energising opening message.

Session title: {workroom.title}
Topic: {workroom.topic_description or workroom.title}
Objective: {workroom.goal}
Desired outcome: {workroom.key_outcome or "Not specified"}

Agents in this session:
{agent_lines}

Write the opening message. It should:
1. Briefly restate the objective and desired outcome (1-2 sentences)
2. List the agents present and what each brings to this session (short bullets)
3. Ask one sharp opening question to get the conversation started

Keep the total length under 200 words."""

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=700,
                temperature=0.5,
                messages=[
                    {"role": "system", "content": FACILITATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.exception("FacilitatorAgent.open_session failed: %s", exc)
            return (
                f"**Welcome to this workroom session.**\n\n"
                f"**Objective:** {workroom.goal}\n\n"
                f"Let's get started. What's the first thing you'd like to explore?"
            )

    # ------------------------------------------------------------------ #
    # Periodic summary                                                     #
    # ------------------------------------------------------------------ #

    def should_summarise(self, user_message_count: int, interval: int) -> bool:
        """True when it's time to insert a facilitator check-in."""
        return user_message_count > 0 and user_message_count % interval == 0

    def generate_summary(self, messages: list[dict], objective: str) -> str:
        """
        Reads recent conversation and produces a concise progress summary
        with suggested next focus.
        """
        # Build a compact transcript (last 20 messages at most)
        recent = messages[-20:]
        transcript_lines = []
        for m in recent:
            role = m.get("role", "")
            agent = m.get("agent", "")
            content = m.get("content", "")
            if role == "user":
                transcript_lines.append(f"PM: {content}")
            elif role == "assistant":
                label = agent if agent else "Agent"
                transcript_lines.append(f"{label}: {content[:300]}{'...' if len(content) > 300 else ''}")
        transcript = "\n".join(transcript_lines)

        prompt = f"""You are facilitating a workroom session with this objective:
"{objective}"

Recent conversation transcript:
---
{transcript}
---

Write a brief facilitator check-in (under 150 words) that:
1. Summarises what has been covered or decided so far (2-3 bullet points)
2. Identifies any open questions or gaps
3. Suggests what to focus on next

Use markdown formatting."""

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=600,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": FACILITATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.exception("FacilitatorAgent.generate_summary failed: %s", exc)
            return "**Facilitator check-in:** Let's pause and review progress. What has been decided so far, and what still needs resolution?"

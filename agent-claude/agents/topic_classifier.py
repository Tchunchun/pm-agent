"""
TopicClassifier — recommends the right subset of agents for a workroom session.

Given a topic description, meeting objective, desired outcome, and the full list
of available agents, it calls OpenAI once and returns:
  {
    "recommended": ["intake", "analyst", ...],
    "rationale":   {"intake": "one-sentence reason", ...}
  }
"""

import json
import logging

from agno.agent import Agent

from config import get_agno_model

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM = """You are an expert meeting facilitator and product management coach.

Your job is to recommend the most relevant AI agents for a focused workroom session,
based on the topic, objective, and desired outcome provided by the user.

Rules:
- Choose between 2 and 5 agents. Quality over quantity.
- Prefer agents whose specialties directly address the stated objective.
- Always include at least one agent that can synthesise or document (e.g. Writer, Requirements Writer).
- Return ONLY valid JSON — no markdown fences, no explanation outside the JSON.

Output format:
{
  "recommended": ["agent_key1", "agent_key2"],
  "rationale": {
    "agent_key1": "One sentence explaining why this agent is needed.",
    "agent_key2": "One sentence explaining why this agent is needed."
  }
}"""


class TopicClassifier:
    def __init__(self):
        pass

    def classify(
        self,
        topic: str,
        objective: str,
        outcome: str,
        available_agents: list[dict],
    ) -> dict:
        """
        Returns dict with keys:
          "recommended": list[str]   — agent keys in priority order
          "rationale":   dict[str, str] — per-agent one-sentence rationale
        Falls back to empty recommended list on any error.
        """
        agent_list_text = "\n".join(
            f"- key: {a['key']} | label: {a['label']} | description: {a.get('description', '')}"
            for a in available_agents
        )

        user_message = f"""Topic: {topic}

Meeting objective: {objective}

Desired outcome: {outcome}

Available agents:
{agent_list_text}

Please recommend the best subset of agents for this session."""

        try:
            agent = Agent(
                name="TopicClassifier",
                model=get_agno_model(max_tokens=800),
                instructions=CLASSIFIER_SYSTEM,
                markdown=False,
                add_datetime_to_context=False,
            )
            result_output = agent.run(input=user_message)
            raw = result_output.content.strip() if isinstance(result_output.content, str) else str(result_output.content).strip()
            result = json.loads(raw)
            # Validate shape
            if "recommended" not in result or "rationale" not in result:
                raise ValueError("Missing required keys in classifier response")
            # Filter out any keys not in available agents
            valid_keys = {a["key"] for a in available_agents}
            result["recommended"] = [k for k in result["recommended"] if k in valid_keys]
            result["rationale"] = {
                k: v for k, v in result["rationale"].items() if k in valid_keys
            }
            return result
        except Exception as exc:
            logger.exception("TopicClassifier failed: %s", exc)
            return {"recommended": [], "rationale": {}}

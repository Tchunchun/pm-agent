"""
AgentDesigner — generates a team of domain expert agents from a problem description.

Given a free-form problem or challenge, it calls OpenAI once and returns:
  {
    "reasoning": "One to two paragraphs explaining what expertise is needed and why.",
    "agents": [
      {
        "key":          "cost_analyst",
        "label":        "Cost Analyst",
        "emoji":        "💰",
        "description":  "TCO modelling · Build vs buy economics",
        "system_prompt": "You are a Cost Analyst...",
        "category":     "professional"
      },
      ...
    ]
  }
Falls back to {"reasoning": "", "agents": []} on any error.
"""

import json
import logging

from agno.agent import Agent

from config import get_agno_model

logger = logging.getLogger(__name__)

DESIGNER_SYSTEM = """You are an expert at designing AI agent teams for complex problem-solving.

Given a problem or challenge, you:
1. Identify what distinct domain expertise would be most valuable to address it
2. Explain your reasoning — why these experts, what gap each one fills
3. Propose 3–5 specialist agents as concrete, actionable personas

Rules:
- Each agent must have a clear, non-overlapping specialty
- System prompts must be detailed enough to produce useful outputs (4–8 sentences minimum)
- Keys must be lowercase snake_case slugs, unique within the proposed set
- Pick an emoji that clearly reflects the role
- Category: use "pm_workflow" for PM/business/work tools, "ai_product" for AI or ML product development, "career" for professional growth/job search/skills, "life" for personal wellness/leisure/lifestyle — or a short descriptive word (e.g. "legal", "creative", "marketing") for anything else. Never leave blank.
- Return ONLY valid JSON — no markdown fences, no text outside the JSON object

Output format:
{
  "reasoning": "One to two paragraphs explaining what expertise this problem requires and why each role matters.",
  "agents": [
    {
      "key": "agent_key",
      "label": "Agent Name",
      "emoji": "🎯",
      "description": "Short tagline · max 60 chars",
      "system_prompt": "You are a [Role] specialising in... Your job is to...",
      "category": "professional"
    }
  ]
}"""


class AgentDesigner:
    def __init__(self):
        pass

    def design(self, problem: str) -> dict:
        """
        Returns dict with keys:
          "reasoning": str — explanation of why these experts are needed
          "agents":    list[dict] — proposed agent specs (key, label, emoji, description,
                                    system_prompt, category)
        Falls back to {"reasoning": "", "agents": []} on any error.
        """
        user_message = f"""Problem or challenge to solve:

{problem.strip()}

Please identify the domain experts needed and propose a specialist agent team."""

        try:
            agent = Agent(
                name="AgentDesigner",
                model=get_agno_model(max_tokens=2000),
                instructions=DESIGNER_SYSTEM,
                markdown=False,
                add_datetime_to_context=False,
            )
            result_output = agent.run(input=user_message)
            raw = result_output.content.strip() if isinstance(result_output.content, str) else str(result_output.content).strip()
            result = json.loads(raw)

            # Validate top-level shape
            if "reasoning" not in result or "agents" not in result:
                raise ValueError("Missing required keys: 'reasoning' and/or 'agents'")

            # Validate and filter agent entries
            valid_agents = []
            seen_keys = set()
            for agent in result.get("agents", []):
                if not isinstance(agent, dict):
                    continue
                if not agent.get("key") or not agent.get("label") or not agent.get("system_prompt"):
                    continue
                # Sanitise key: lowercase snake_case, deduplicate within this result
                key = agent["key"].lower().replace(" ", "_").replace("-", "_")
                if key in seen_keys:
                    key = f"{key}_2"
                seen_keys.add(key)
                valid_agents.append({
                    "key": key,
                    "label": agent.get("label", ""),
                    "emoji": agent.get("emoji", "🤖"),
                    "description": agent.get("description", ""),
                    "system_prompt": agent.get("system_prompt", ""),
                    "category": agent.get("category", "").strip(),
                })

            return {
                "reasoning": result.get("reasoning", ""),
                "agents": valid_agents,
            }

        except Exception as exc:
            logger.exception("AgentDesigner failed: %s", exc)
            return {"reasoning": "", "agents": []}

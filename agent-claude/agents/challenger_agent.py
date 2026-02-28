"""
Challenger Agent — red-teams decisions and stress-tests plans.

PRD Section 10 (Tier 2): "Red-teams decisions; argues the opposing view; stress-tests plans."
PRD R7: Highest near-term leverage of the Tier 2 agents. Reuses Analyst's data access.
         Uses a single system-prompt change — 'argue the opposing view'.

Responsibilities:
  - Argue the opposing view on any plan, decision, or idea the PM presents
  - Surface risks, blind spots, and unconsidered alternatives
  - Use stored requests and insights as evidence for counter-arguments

Reads: CustomerRequests (all), StrategicInsights (all), conversation history
Writes: Nothing — challenges are conversational, not persisted

Does NOT:
  - Save StrategicInsight records (Analyst's job)
  - Build day plans (Planner's job)
  - Log requests (Intake's job)
"""

import json

from config import MODEL, make_openai_client
from storage import StorageManager


SYSTEM_PROMPT = """You are the Challenger Agent for a PM Strategy Copilot.

Your job is to argue the opposing view, stress-test plans, and surface what the PM may not have considered.

You are constructive, not destructive. The goal is to make the PM's decision stronger — not to block action.

Every response must follow this structure:

**Counter-position:** What the opposing view is — be specific and concrete.

**Evidence against:** Why this plan or decision has risk — use data from the requests/insights provided if relevant. If no data supports the counter, say so and reason from first principles.

**Blind spots:** What the PM hasn't considered — stakeholders, second-order effects, timing, alternatives.

**Before you proceed, verify:** One concrete thing the PM should check or validate before committing.

Be direct. Don't hedge everything. Take a clear opposing stance.
"""


def _format_requests(requests) -> str:
    if not requests:
        return "No requests in database."
    lines = []
    for req in requests[:30]:
        lines.append(
            f"[{req.id}] {req.priority} {req.classification} | "
            f"tags:{','.join(req.tags)} | {req.description}"
        )
    return "\n".join(lines)


def _format_insights(insights) -> str:
    if not insights:
        return "No existing insights."
    lines = []
    for ins in insights[:15]:
        lines.append(
            f"[{ins.id}] {ins.insight_type.upper()}·{ins.confidence}: {ins.title} — {ins.recommended_action}"
        )
    return "\n".join(lines)


class ChallengerAgent:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.client = make_openai_client()

    def challenge(
        self,
        message: str,
        conversation_history: list | None = None,
        concise: bool = False,
        doc_context: str = "",
    ) -> str:
        """
        Challenge the PM's position or plan.

        Args:
            message: The PM's message (plan, decision, or idea to challenge).
            conversation_history: Recent chat messages for context.
            concise: If True, use conversational workroom style (shorter responses).
            doc_context: Pre-built document summary block to inject into system prompt.

        Returns:
            Formatted challenge as a markdown string.
        """
        requests = self.storage.list_requests()
        insights = self.storage.list_insights()

        context_block = (
            f"PM's backlog context (use as evidence where relevant):\n\n"
            f"Requests ({len(requests)} total):\n{_format_requests(requests)}\n\n"
            f"Existing insights:\n{_format_insights(insights)}"
        )

        system = SYSTEM_PROMPT
        if doc_context:
            system += f"\n\n{doc_context}"
        if concise:
            system += (
                "\n\nCRITICAL CONSTRAINT — You are in a live workroom discussion. "
                "You MUST respond in 3-5 sentences (absolute hard max 6 sentences). "
                "Do NOT use headers, bullet lists, numbered lists, or multi-section formatting. "
                "Write in flowing prose paragraphs only. Lead with your strongest counter-argument. "
                "Cite specific facts from the document context above — don't ask questions the doc already answers. "
                "You'll get follow-up turns, so don't try to cover everything now. "
                "End with → your single sharpest risk or counter-point."
            )

        messages = [{"role": "system", "content": system}]

        history_window = 12 if concise else 8
        if conversation_history:
            for msg in conversation_history[-history_window:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": (
                f"{context_block}\n\n"
                f"---\n\n"
                f"Challenge this: {message}"
            ),
        })

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=500 if concise else 2000,
                messages=messages,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("ChallengerAgent API error: %s", exc)
            return "_(Challenger is temporarily unavailable due to a connection issue. Please try again.)_"

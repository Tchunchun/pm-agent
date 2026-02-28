"""
Researcher Agent — deep dives on topics relevant to the PM's work.

PRD Section 10 (Tier 2): "Deep dives: competitive landscape, industry trends, customer context."

Responsibilities:
  - Provide deep context on requested topics
  - Ground research in the PM's actual backlog where relevant
  - Distinguish clearly between data from the PM's backlog vs. general knowledge
  - Be specific and actionable, not generic

Reads: CustomerRequests (all), conversation history
Writes: Nothing — research is conversational output, not persisted

Does NOT:
  - Log requests (Intake's job)
  - Generate StrategicInsight records (Analyst's job)
  - Build day plans (Planner's job)
"""

from config import MODEL, make_openai_client
from storage import StorageManager


SYSTEM_PROMPT = """You are the Researcher Agent for a Technical Program Manager (TPM) at Microsoft.

Your job is to provide deep, specific, actionable context on topics relevant to enterprise software, customer engagements, and TPM work.

Coverage areas:
- Enterprise software patterns, integrations, and APIs
- Industry trends in healthcare IT, fintech, or other relevant verticals
- Customer problem framing and technical context
- Competitive landscape for specific features or capabilities
- Standards, compliance requirements, and regulatory context

How to frame your response:
1. **From the PM's backlog** — cite specific requests or patterns from the data provided. This is the most grounded source.
2. **From general knowledge** — clearly flag when you're drawing on training knowledge. Indicate confidence level.

Format: Use clear headers. Be specific — give names, numbers, and examples. Avoid vague statements like "there may be challenges."

If the topic is too broad, narrow it to the most relevant sub-question for a TPM context.
"""


def _format_requests(requests) -> str:
    if not requests:
        return "No requests in database."
    lines = []
    for req in requests[:30]:
        lines.append(
            f"[{req.id}] {req.priority} | tags:{','.join(req.tags)} | {req.description}"
        )
    return "\n".join(lines)


class ResearcherAgent:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.client = make_openai_client()

    def research(
        self,
        message: str,
        conversation_history: list | None = None,
        concise: bool = False,
        doc_context: str = "",
    ) -> str:
        """
        Research a topic and return a deep-dive summary.

        Args:
            message: The PM's research request.
            conversation_history: Recent chat messages for context.
            concise: If True, use conversational workroom style (shorter responses).
            doc_context: Pre-built document summary block to inject into system prompt.

        Returns:
            Formatted research output as a markdown string.
        """
        requests = self.storage.list_requests()

        context_block = (
            f"PM's backlog ({len(requests)} requests — use to ground the research):\n"
            f"{_format_requests(requests)}"
        )

        system = SYSTEM_PROMPT
        if doc_context:
            system += f"\n\n{doc_context}"
        if concise:
            system += (
                "\n\nCRITICAL CONSTRAINT — You are in a live workroom discussion. "
                "You MUST respond in 3-5 sentences (absolute hard max 6 sentences). "
                "Do NOT use headers, bullet lists, numbered lists, or multi-section formatting. "
                "Write in flowing prose paragraphs only. "
                "Cite specific facts from the document context above — don't ask questions the doc already answers. "
                "You'll get follow-up turns — save the deep dive for when asked. "
                "End with → the single most important finding or gap."
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
                f"Research request: {message}"
            ),
        })

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=500 if concise else 2500,
                messages=messages,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("ResearcherAgent API error: %s", exc)
            return "_(Researcher is temporarily unavailable due to a connection issue. Please try again.)_"

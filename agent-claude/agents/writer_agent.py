"""
Writer Agent — drafts professional PM communications.

PRD Section 10 (Tier 2): "Drafts emails, Teams messages, exec briefs; edits for tone and clarity."

Responsibilities:
  - Draft emails, Teams messages, exec briefs, and stakeholder summaries
  - Ground drafts in the PM's actual request and insight data where relevant
  - Match TPM tone: direct, concise, data-backed, professional

Reads: CustomerRequests (recent), StrategicInsights (recent), conversation history
Writes: Nothing — drafts are conversational outputs, not persisted

Does NOT:
  - Log requests (Intake's job)
  - Generate StrategicInsight records (Analyst's job)
  - Build day plans (Planner's job)
"""

from config import MODEL, make_openai_client
from storage import StorageManager


SYSTEM_PROMPT = """You are the Writer Agent for a Technical Program Manager (TPM).

Your job is to draft professional communications that are ready to send with minimal or no edits.

Communication types you produce:
- **Email** — subject line + body, professional tone, clear ask or update
- **Teams message** — shorter, more conversational, direct
- **Exec brief** — structured summary: situation, data, recommendation, ask
- **Stakeholder update** — status-oriented, outcome-focused, concise
- **Meeting prep note** — agenda points, key context, questions to raise

Tone: Direct. Concise. Data-backed where possible. No filler phrases like "I hope this email finds you well."

Format: Always output the draft inside a clearly labelled block. Example:

---
**Draft: Email to [Recipient]**
**Subject:** [Subject line]

[Body]

---

If the PM provides customer request data or insight context, weave in specific facts (numbers, request counts, dates) to make the draft concrete.

Ask yourself: Would a senior TPM send this without edits? If not, revise it.
"""


def _format_context(requests, insights) -> str:
    lines = []
    if requests:
        lines.append(f"Recent requests ({len(requests)}):")
        for req in requests[:8]:
            lines.append(f"  - [{req.priority}] {req.description} (tags: {', '.join(req.tags) or 'none'})")
    if insights:
        lines.append(f"\nRecent insights ({len(insights)}):")
        for ins in insights[:5]:
            lines.append(f"  - {ins.insight_type.upper()}: {ins.title} → {ins.recommended_action}")
    return "\n".join(lines) if lines else "No backlog context available."


class WriterAgent:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.client = make_openai_client()

    def write(
        self,
        message: str,
        conversation_history: list | None = None,
        concise: bool = False,
        doc_context: str = "",
    ) -> str:
        """
        Draft a professional communication based on the PM's request.

        Args:
            message: The PM's request (e.g. "draft an email to Stripe about the webhook delay").
            conversation_history: Recent chat messages for context.
            concise: If True, use conversational workroom style (shorter responses).
            doc_context: Pre-built document summary block to inject into system prompt.

        Returns:
            Formatted draft as a markdown string.
        """
        requests = self.storage.list_requests()
        insights = self.storage.list_insights()

        context_block = _format_context(requests[:10], insights[:5])

        system = SYSTEM_PROMPT
        if doc_context:
            system += f"\n\n{doc_context}"
        if concise:
            system += (
                "\n\nIMPORTANT: You are in a live workroom discussion. "
                "Keep drafts short and focused (3-5 sentences, hard max 6). "
                "Use specifics from the document context above — don't ask questions the doc already answers. "
                "You'll get follow-up turns — provide a tight first draft, not a comprehensive one. "
                "End with → the single most important thing to get right in this communication."
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
                f"Backlog context (use where relevant to add specifics):\n{context_block}\n\n"
                f"---\n\n"
                f"Request: {message}"
            ),
        })

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=1200 if concise else 2000,
                messages=messages,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("WriterAgent API error: %s", exc)
            return "_(Writer is temporarily unavailable due to a connection issue. Please try again.)_"

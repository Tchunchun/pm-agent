"""
CustomAgentRunner — executes user-defined agents with their own system prompt.
"""

from openai import OpenAI
from config import MODEL, OPENAI_API_KEY
from models.workroom import CustomAgent


class CustomAgentRunner:
    def __init__(self, agent_def: CustomAgent):
        self.agent_def = agent_def
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def respond(
        self,
        message: str,
        conversation_history: list | None = None,
        document_context: dict | None = None,
        concise: bool = False,
        doc_context: str = "",
    ) -> str:
        # Build system prompt — append document-awareness note when a doc is active
        system_prompt = self.agent_def.system_prompt
        if concise:
            system_prompt += (
                "\n\nIMPORTANT: You are in a live workroom discussion. "
                "Respond in 3-5 sentences (hard max 6). Lead with your key insight or recommendation. "
                "Cite specific facts from the document context — don't ask questions the doc already answers. "
                "You'll get follow-up turns — don't try to cover everything now. "
                "End with → your single most important takeaway, question, or recommendation."
            )
        # Prefer pre-built summary (doc_context) over raw document text for cost efficiency
        if doc_context:
            system_prompt += f"\n\n{doc_context}"
        elif document_context:
            filename = document_context.get("filename", "the uploaded document")
            system_prompt += (
                f"\n\nA reference document has been uploaded to this session: **{filename}**. "
                "The full text of this document is embedded directly in the user message under "
                "'Document context'. You already have access to all of its content — do NOT say "
                "you cannot access the file. Read the embedded text and use it to answer."
            )

        messages = [{"role": "system", "content": system_prompt}]

        history_window = 12 if concise else 8
        if conversation_history:
            for msg in conversation_history[-history_window:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Skip any prior confused "cannot access" messages to avoid reinforcing them
                if not content or role not in ("user", "assistant"):
                    continue
                if "cannot access" in content.lower() or "i need to extract" in content.lower():
                    continue
                messages.append({"role": role, "content": content})

        user_content = message
        # Only embed full doc text if no pre-built summary was provided (non-workroom mode)
        if document_context and not doc_context:
            doc_text = document_context.get("text", "")[:8000]
            user_content = (
                f"Document context ({document_context.get('filename', '')}):\n"
                f"---\n{doc_text}\n---\n\n{message}"
            )

        messages.append({"role": "user", "content": user_content})

        response = self.client.chat.completions.create(
            model=MODEL,
            max_tokens=800 if concise else 1500,
            messages=messages,
        )
        return response.choices[0].message.content.strip()

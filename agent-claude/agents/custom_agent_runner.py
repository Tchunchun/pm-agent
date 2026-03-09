"""
CustomAgentRunner — executes user-defined agents using Agno framework.

Each CustomAgent definition (key, label, system_prompt, skill_names) is turned
into an Agno Agent instance.  The Agno Agent handles the LLM call, tool-call
loop, and result assembly automatically.
"""

import logging
from typing import Generator, Optional

from agno.agent import Agent, RunEvent
from agno.models.message import Message

from config import get_agno_model
from models.workroom import CustomAgent

logger = logging.getLogger(__name__)

# Base formatting instruction — always applied unless overridden
_FORMAT_INSTRUCTION = (
    "\n\nIMPORTANT — Format your response for readability. "
    "Use bullet points, numbered lists, **bold** for key terms, "
    "and short paragraphs. Use markdown headers (##) to organize "
    "longer answers. Never return a wall of unformatted text."
)

# Concise mode constraint for multi-agent workroom sessions (round-table / open)
_CONCISE_CONSTRAINT = (
    "\n\nCONSTRAINT — You are in a multi-agent workroom discussion. "
    "Keep your response concise (3-6 sentences or equivalent bullet points). "
    "Use **bold**, bullet points, or numbered lists for scannability. "
    "Cite specific facts from the document context — don't ask questions the doc already answers. "
    "You'll get follow-up turns — don't try to cover everything now. "
    "End with → your single most important takeaway, question, or recommendation."
)

# Focused mode constraint — single agent, thorough + well-formatted
_FOCUSED_CONSTRAINT = (
    "\n\nYou are the sole active agent in a focused workroom session. "
    "Use clear formatting to make your response easy to scan: "
    "bullet points, numbered lists, bold text, and short paragraphs are encouraged. "
    "Structure longer answers with markdown headers (##) when appropriate. "
    "Keep your response well-organized but thorough — you are the only responder. "
    "End with → a clear next-step question or recommendation."
)


def _resolve_tools(skill_names: list[str] | None) -> list:
    """Map skill_names from the CustomAgent definition to Agno tool functions."""
    if not skill_names:
        return []
    try:
        from skills.tools import get_current_date, search_backlog, get_recent_insights
    except ImportError:
        logger.warning("CustomAgentRunner: skills.tools not available")
        return []

    name_to_func = {
        "get_current_date": get_current_date,
        "search_backlog": search_backlog,
        "get_recent_insights": get_recent_insights,
    }
    tools = [name_to_func[n] for n in skill_names if n in name_to_func]
    if len(tools) < len(skill_names):
        missing = [n for n in skill_names if n not in name_to_func]
        logger.warning("CustomAgentRunner: unknown skills ignored: %s", missing)
    return tools


class CustomAgentRunner:
    def __init__(self, agent_def: CustomAgent, storage=None):
        self.agent_def = agent_def
        self._storage = storage
        self._tools = _resolve_tools(agent_def.skill_names)

    def respond(
        self,
        message: str,
        conversation_history: list | None = None,
        document_context: dict | None = None,
        concise: bool = False,
        focused: bool = False,
        doc_context: str = "",
    ) -> str:
        # ---- Build dynamic instructions ----
        instructions = self.agent_def.system_prompt
        if focused:
            instructions += _FOCUSED_CONSTRAINT
        elif concise:
            instructions += _CONCISE_CONSTRAINT
        else:
            instructions += _FORMAT_INSTRUCTION
        if doc_context:
            instructions += f"\n\n{doc_context}"
        elif document_context:
            filename = document_context.get("filename", "the uploaded document")
            instructions += (
                f"\n\nA reference document has been uploaded to this session: **{filename}**. "
                "The full text of this document is embedded directly in the user message under "
                "'Document context'. You already have access to all of its content — do NOT say "
                "you cannot access the file. Read the embedded text and use it to answer."
            )

        # ---- Build Agno Agent for this call ----
        deps = {"storage": self._storage} if self._storage else {}
        agent = Agent(
            name=self.agent_def.label,
            model=get_agno_model(max_tokens=2000),
            instructions=instructions,
            tools=self._tools or None,
            tool_call_limit=5,
            dependencies=deps,
            markdown=True,
            add_datetime_to_context=False,
        )

        # ---- Build conversation input ----
        messages: list[Message] = []
        history_window = 12 if concise else 8
        if conversation_history:
            for msg in conversation_history[-history_window:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if not content or role not in ("user", "assistant"):
                    continue
                if "cannot access" in content.lower() or "i need to extract" in content.lower():
                    continue
                messages.append(Message(role=role, content=content))

        # Build user message with optional doc text
        user_content = message
        if document_context and not doc_context:
            doc_text = document_context.get("text", "")[:8000]
            user_content = (
                f"Document context ({document_context.get('filename', '')}):\n"
                f"---\n{doc_text}\n---\n\n{message}"
            )
        messages.append(Message(role="user", content=user_content))

        # ---- Run agent ----
        try:
            result = agent.run(input=messages)
            content = result.content if result.content else ""
            if isinstance(content, str):
                return content.strip()
            return str(content).strip()
        except Exception as exc:
            logger.exception("CustomAgentRunner API error: %s", exc)
            return (
                f"_({self.agent_def.label} is temporarily unavailable due to a "
                "connection issue. Please try again.)_"
            )

    def respond_stream(
        self,
        message: str,
        conversation_history: list | None = None,
        document_context: dict | None = None,
        concise: bool = False,
        focused: bool = False,
        doc_context: str = "",
    ) -> Generator[str, None, None]:
        """Streaming variant of respond(). Yields text chunks as they arrive."""
        # ---- Build dynamic instructions (same as respond) ----
        instructions = self.agent_def.system_prompt
        if focused:
            instructions += _FOCUSED_CONSTRAINT
        elif concise:
            instructions += _CONCISE_CONSTRAINT
        else:
            instructions += _FORMAT_INSTRUCTION
        if doc_context:
            instructions += f"\n\n{doc_context}"
        elif document_context:
            filename = document_context.get("filename", "the uploaded document")
            instructions += (
                f"\n\nA reference document has been uploaded to this session: **{filename}**. "
                "The full text of this document is embedded directly in the user message under "
                "'Document context'. You already have access to all of its content — do NOT say "
                "you cannot access the file. Read the embedded text and use it to answer."
            )

        # ---- Build Agno Agent ----
        deps = {"storage": self._storage} if self._storage else {}
        agent = Agent(
            name=self.agent_def.label,
            model=get_agno_model(max_tokens=2000),
            instructions=instructions,
            tools=self._tools or None,
            tool_call_limit=5,
            dependencies=deps,
            markdown=True,
            add_datetime_to_context=False,
        )

        # ---- Build conversation input (same as respond) ----
        messages: list[Message] = []
        history_window = 12 if concise else 8
        if conversation_history:
            for msg in conversation_history[-history_window:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if not content or role not in ("user", "assistant"):
                    continue
                if "cannot access" in content.lower() or "i need to extract" in content.lower():
                    continue
                messages.append(Message(role=role, content=content))

        user_content = message
        if document_context and not doc_context:
            doc_text = document_context.get("text", "")[:8000]
            user_content = (
                f"Document context ({document_context.get('filename', '')}):\n"
                f"---\n{doc_text}\n---\n\n{message}"
            )
        messages.append(Message(role="user", content=user_content))

        # ---- Run agent with streaming ----
        try:
            for chunk in agent.run(input=messages, stream=True):
                if hasattr(chunk, "event") and chunk.event == RunEvent.run_content.value:
                    if chunk.content:
                        yield str(chunk.content)
        except Exception as exc:
            logger.exception("CustomAgentRunner streaming error: %s", exc)
            yield (
                f"_({self.agent_def.label} is temporarily unavailable due to a "
                "connection issue. Please try again.)_"
            )

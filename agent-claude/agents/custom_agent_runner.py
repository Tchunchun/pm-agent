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

# Concise mode constraint appended to system prompt in workroom sessions (round-table / open)
_CONCISE_CONSTRAINT = (
    "\n\nCRITICAL CONSTRAINT — You are in a live workroom discussion. "
    "Keep your response concise (aim for 4-8 sentences, hard max ~150 words). "
    "Use clear formatting to make your response scannable: "
    "**bold** key terms, use bullet points for lists, and short paragraphs. "
    "Structure: lead with your key insight or recommendation, then supporting details. "
    "Cite specific facts from the document context — don't ask questions the doc already answers. "
    "You'll get follow-up turns — don't try to cover everything now. "
    "End with → your single most important takeaway, question, or recommendation."
)

# Action-bias constraint — reduces endless clarification loops
_ACTION_BIAS_CONSTRAINT = (
    "\n\nACTION BIAS RULE: Do NOT ask multiple clarifying questions across turns. "
    "If information is missing, assume reasonable defaults, state your assumptions clearly, "
    "and deliver a concrete answer or plan. You may include ONE focused follow-up question "
    "at the end if truly critical information is missing — but always provide a usable "
    "output first. Never respond with ONLY questions and no content."
)

# Frustration-mode constraint — injected when user shows impatience signals
_FRUSTRATION_MODE_CONSTRAINT = (
    "\n\nURGENT: The user has signalled impatience or frustration. Switch to DELIVERY MODE "
    "immediately. Do NOT ask any more questions. Instead:\n"
    "1. Use whatever information you already have (plus reasonable assumptions)\n"
    "2. Produce an actionable, concrete output NOW\n"
    "3. Clearly label any assumptions you made\n"
    "4. The user wants RESULTS, not more discussion"
)

# Turn-awareness thresholds
_DELIVERY_TURN_THRESHOLD = 3  # After this many user messages, prioritise delivery

# Focused mode constraint — single agent, richer formatting allowed
_FOCUSED_CONSTRAINT = (
    "\n\nYou are the sole active agent in a focused workroom session. "
    "Use clear formatting to make your response easy to scan: "
    "bullet points, numbered lists, bold text, and short paragraphs are encouraged. "
    "Structure longer answers with markdown headers (##) when appropriate. "
    "Keep your response well-organized but thorough — you are the only responder. "
    "End with → a clear next-step question or recommendation."
)


def _build_toolkit_factories() -> dict:
    """Lazy-loaded factory dict for Agno Toolkit instances.

    Each entry maps a skill name to a callable that returns a Toolkit.
    Toolkits are instantiated per-agent (not shared) so state stays isolated.
    Adding a future integration = one new entry here + pip install.
    """
    factories: dict = {}

    # -- Web Search (DuckDuckGo meta-search, no API key needed) ----------
    try:
        from agno.tools.websearch import WebSearchTools
        factories["web_search"] = lambda: WebSearchTools(cache_results=True)
    except ImportError:
        logger.info("WebSearchTools not available (install ddgs)")

    return factories


# Built once at module load; toolkit instances are created per-agent call.
_TOOLKIT_FACTORIES = _build_toolkit_factories()


def _resolve_tools(skill_names: list[str] | None) -> list:
    """Map skill_names from the CustomAgent definition to Agno tool functions.

    Supports two kinds of entries in skill_names:
    - Plain function names ("get_current_date", "search_backlog", ...)
    - Toolkit names ("web_search", "google_maps", ...)
    Agno Agent(tools=[...]) accepts both plain functions and Toolkit objects.
    """
    if not skill_names:
        return []

    # --- plain function tools ---
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

    tools: list = []
    missing: list[str] = []

    for name in skill_names:
        if name in name_to_func:
            tools.append(name_to_func[name])
        elif name in _TOOLKIT_FACTORIES:
            toolkit = _TOOLKIT_FACTORIES[name]()
            if toolkit is not None:
                tools.append(toolkit)
        else:
            missing.append(name)

    if missing:
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
        frustration_detected: bool = False,
    ) -> str:
        # ---- Build dynamic instructions ----
        instructions = self.agent_def.system_prompt
        if focused:
            instructions += _FOCUSED_CONSTRAINT
        elif concise:
            instructions += _CONCISE_CONSTRAINT

        # Always add action-bias to reduce clarification loops
        if concise or focused:
            instructions += _ACTION_BIAS_CONSTRAINT

        # Turn-awareness: after enough user messages, push agents to deliver
        user_turn_count = sum(1 for m in (conversation_history or []) if m.get("role") == "user")
        if user_turn_count >= _DELIVERY_TURN_THRESHOLD:
            instructions += (
                f"\n\nTURN AWARENESS: The user has sent {user_turn_count} messages in this session. "
                "You MUST deliver concrete, actionable output now — not ask more questions. "
                "State assumptions and provide a complete answer."
            )

        # Frustration mode: override to pure delivery
        if frustration_detected:
            instructions += _FRUSTRATION_MODE_CONSTRAINT

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
        frustration_detected: bool = False,
    ) -> Generator[str, None, None]:
        """Streaming variant of respond(). Yields text chunks as they arrive."""
        # ---- Build dynamic instructions (same as respond) ----
        instructions = self.agent_def.system_prompt
        if focused:
            instructions += _FOCUSED_CONSTRAINT
        elif concise:
            instructions += _CONCISE_CONSTRAINT

        # Always add action-bias to reduce clarification loops
        if concise or focused:
            instructions += _ACTION_BIAS_CONSTRAINT

        # Turn-awareness: after enough user messages, push agents to deliver
        user_turn_count = sum(1 for m in (conversation_history or []) if m.get("role") == "user")
        if user_turn_count >= _DELIVERY_TURN_THRESHOLD:
            instructions += (
                f"\n\nTURN AWARENESS: The user has sent {user_turn_count} messages in this session. "
                "You MUST deliver concrete, actionable output now — not ask more questions. "
                "State assumptions and provide a complete answer."
            )

        # Frustration mode: override to pure delivery
        if frustration_detected:
            instructions += _FRUSTRATION_MODE_CONSTRAINT

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

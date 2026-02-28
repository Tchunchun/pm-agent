"""
Orchestrator — persistent multi-turn session manager and intent router.

Responsibilities:
  - Preserve conversation context across messages
  - Route user intent to the right agent
  - Handle simple read queries directly without delegating
  - Label every response with the agent that produced it

Routing table:
  | Intent signal              | Routes to                    |
  |----------------------------|------------------------------|
  | Challenge an idea          | challenger (CustomAgent)     |
  | Draft a message            | writer (CustomAgent)         |
  | Research a topic           | researcher (CustomAgent)     |
  | Document Q&A               | Direct (built-in LLM call)  |
  | Workroom messages          | smart_route → CustomAgent(s) |
  | Ambiguous                  | Asks for clarification       |
"""

import re
from typing import Optional

from openai import OpenAI  # kept for type hints only

from config import MODEL, make_openai_client
from storage import StorageManager
from agents.custom_agent_runner import CustomAgentRunner
from agents.facilitator_agent import FacilitatorAgent
from models.workroom import CustomAgent, WorkroomSession, Decision, GeneratedOutput, OUTPUT_TYPE_META


CONVERSATIONAL_MODE = (
    "CRITICAL CONSTRAINT — You are in a live workroom discussion. "
    "You MUST respond in 3-5 sentences (absolute hard max 6 sentences). "
    "Do NOT use headers, bullet lists, numbered lists, or multi-section formatting. "
    "Write in flowing prose paragraphs only. "
    "Lead with your key insight, recommendation, or answer. "
    "Add supporting reasoning only when it's non-obvious. "
    "You will get follow-up turns — do NOT try to cover everything in one response. "
    "If the user answers a question you asked, acknowledge it and build on it. "
    "If you need more information, ask ONE focused follow-up question. "
    "Stay in your expert role — don't water down your expertise, just communicate it efficiently. "
    "End with your single most important takeaway: a recommendation, risk, or question for the group, prefixed with '→'."
)

DOCUMENT_QA_SYSTEM = """You are a helpful PM assistant. Answer questions using both the provided document and any relevant context shared earlier in the conversation.

If the document does not contain the answer but the conversation includes relevant context (e.g. meeting notes, customer quotes, stakeholder input), synthesize from that context instead — and be explicit about the source.

For requests involving drafting, writing, or creating content (e.g. requirements, feature requests, summaries), do so proactively using all available information. Do not refuse just because the document alone lacks detail.

Do not fabricate information that was not provided in the document or conversation."""

# Maximum chars of summary to inject into agent context (keeps tokens low)
_DOC_SUMMARY_MAX_CHARS = 3000

GENERATE_OUTPUT_SYSTEM = """You are a synthesis agent for a Multi-Agent Workroom.

Your job is to compile a multi-agent discussion into a high-quality, structured document.

Output requirements by type:
- **PRD**: Title, Overview, Problem Statement, Goals, Target Users, Key Features (prioritised), Non-Goals, Success Metrics, Open Questions
- **Architecture**: Overview, Components, Data Flow, API / Integration points, Trade-offs, Risks, Next Steps
- **Requirements**: Functional Requirements (numbered), Non-Functional Requirements, Constraints, Assumptions
- **Decision Log**: Chronological list of decisions made — each with context, options considered, decision taken, rationale
- **Event Plan**: Goal, Date/Time, Attendees, Agenda (timed), Logistics, Budget (if mentioned), Action Items
- **Summary**: TL;DR (2-3 sentences), Key Points (bullets), Decisions Made, Open Questions, Next Steps
- **Custom**: Interpret the user's custom request and produce the most useful structured output

Rules:
- Be concrete — use actual names, numbers, and quotes from the discussion
- Do not invent details not present in the conversation
- Use clear markdown headers and bullet points
- Length: comprehensive but not padded — quality over quantity

Return only the document content in markdown. No preamble like "Here is the document:".
"""

DECISION_KEYWORDS_STRONG = [
    r"\bdecided\s+(to|that|on)\b",
    r"\bwe('ll| will)\s+(go\s+with|ship|build|use|adopt|implement|proceed)\b",
    r"\blet'?s\s+(go\s+with|use|build|ship|adopt|commit)\b",
    r"\bagreed\s+(to|that|on)\b",
    r"\baction\s+item\s*:",
    r"\bdecision\s*:",
    r"\bcommitted\s+to\b",
]

DECISION_KEYWORDS_WEAK = [
    r"\bwe\s+should\b",
    r"\bwe\s+(need|must|have)\s+to\b",
    r"\bnext\s+step\b",
    r"\btake\s+away\b",
    r"\bcommitment\b",
]

# Minimum length for decision detection — short advisory sentences are not decisions
_DECISION_MIN_LENGTH = 120

# @mention → agent key map
MENTION_MAP = {
    "@challenger": "challenger", "@challenge": "challenger",
    "@devil": "challenger", "@redteam": "challenger",
    "@writer": "writer", "@write": "writer", "@draft": "writer",
    "@researcher": "researcher", "@research": "researcher",
    "@facilitator": "facilitator", "@fac": "facilitator",
}


def _detect_mentions(message: str, active_agents: Optional[list] = None, all_known_agents: Optional[list] = None) -> list[str]:
    """Return list of mentioned agent keys (supports multiple @mentions).
    
    Checks the hardcoded MENTION_MAP first, then falls back to matching
    @<agent_key> against all_known_agents (if provided) or active_agents.
    De-duplicates while preserving order.
    """
    msg_lower = message.lower()
    found_keys: list[str] = []
    seen: set[str] = set()

    # Build pool of matchable agent keys: all known > active
    match_pool = set(all_known_agents or []) | set(active_agents or [])

    # 1. Check all @tokens in message order
    tokens = re.findall(r"@(\w+)", msg_lower)
    for token in tokens:
        mention = f"@{token}"
        # Check hardcoded aliases
        if mention in MENTION_MAP:
            key = MENTION_MAP[mention]
            if key not in seen:
                found_keys.append(key)
                seen.add(key)
        # Check dynamic agents (custom / workroom agents)
        elif token in match_pool:
            if token not in seen:
                found_keys.append(token)
                seen.add(token)

    return found_keys


def _is_decision(text: str) -> bool:
    """Heuristic: does this text contain a real decision or commitment?

    Uses two tiers:
      - Strong keywords (decided to, agreed on, let's go with) → immediate match
      - Weak keywords (we should, next step) → require 2+ matches to trigger

    Also enforces a minimum text length to avoid flagging short advisory lines.
    """
    if len(text) < _DECISION_MIN_LENGTH:
        return False
    text_lower = text.lower()
    # Strong match — a single hit is enough
    if any(re.search(p, text_lower) for p in DECISION_KEYWORDS_STRONG):
        return True
    # Weak match — require at least 3 different weak patterns
    weak_hits = sum(1 for p in DECISION_KEYWORDS_WEAK if re.search(p, text_lower))
    return weak_hits >= 3


# ------------------------------------------------------------------ #
# Intent detection patterns                                           #
# ------------------------------------------------------------------ #

CHALLENGE_PATTERNS = [
    r"\bchallenge\s+this\b",
    r"\bargue\s+against\b",
    r"\bred.?team\b",
    r"\bsteel.?man\b",
    r"\bopposing\s+view\b",
    r"\bwhat.{0,20}wrong\s+with\b",
    r"\bcounter.?argument\b",
    r"\bdevil.{0,5}s?\s+advocate\b",
    r"\bflip\s+side\b",
    r"\bchallenge\s+my\b",
    r"\bpoke\s+holes\b",
    r"\bwhat\s+(am|are)\s+i\s+missing\b",
    r"\bwhere\s+(am|are)\s+i\s+wrong\b",
]

WRITE_PATTERNS = [
    r"\bdraft\s+(an?\s+)?(email|message|brief|summary|note|update)\b",
    r"\bwrite\s+(an?\s+)?(email|message|brief|summary|update)\b",
    r"\bcompose\s+(an?\s+)?(email|message)\b",
    r"\bexec\s+brief\b",
    r"\bstakeholder\s+(summary|update|brief|note)\b",
    r"\bmeeting\s+prep\b",
    r"\bteams\s+message\b",
    r"\bdraft\s+this\b",
]

RESEARCH_PATTERNS = [
    r"\bresearch\b",
    r"\bdeep.?dive\b",
    r"\btell\s+me\s+more\s+about\b",
    r"\bwhat\s+do\s+you\s+know\s+about\b",
    r"\bindustry\s+context\b",
    r"\bcompetiti(ve|or)\b",
    r"\bbackground\s+on\b",
    r"\bexplain\s+\w+\s+to\s+me\b",
    r"\bhow\s+does\s+\w+\s+work\b",
]


def _match(text: str, patterns: list[str]) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _detect_intent(message: str) -> str:
    """
    Returns one of:
      "challenge", "write", "research", "ambiguous"
    """
    if _match(message, CHALLENGE_PATTERNS):
        return "challenge"
    if _match(message, WRITE_PATTERNS):
        return "write"
    if _match(message, RESEARCH_PATTERNS):
        return "research"
    return "ambiguous"


class Orchestrator:
    """
    Manages multi-turn conversation and routes intent to sub-agents.

    Each call to `handle_message` returns a dict:
      {
        "agent": str,          # [Planner] | [Analyst] | [Intake] | [System]
        "text": str,           # Main response text
        "data": dict | None,   # Structured data (e.g., saved DayPlan, insights)
        "warning": str | None, # Low-data warning etc.
        "pending_action": str | None,  # e.g. "confirm_requests"
        "pending_data": any,   # Data waiting for PM confirmation
      }
    """

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._openai = make_openai_client()
        # Custom agent runners — loaded lazily from storage
        self._custom_runners: dict[str, CustomAgentRunner] = {}

        # Document summary cache: {filename: summary_text}
        self._doc_summary_cache: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Document summarization (one-time, cached)                           #
    # ------------------------------------------------------------------ #

    def summarize_document(self, document_context: dict) -> str:
        """Return a concise summary of the uploaded document.

        The summary is cached by filename so it's only computed once.
        This is what gets injected into agent prompts to save tokens —
        the full text is only used for direct document Q&A.
        """
        if not document_context:
            return ""

        filename = document_context.get("filename", "document")
        if filename in self._doc_summary_cache:
            return self._doc_summary_cache[filename]

        doc_text = document_context.get("text", "")
        if not doc_text:
            return ""

        # Use first 12K chars to produce the summary (cost-efficient)
        truncated = doc_text[:12000]

        try:
            response = self._openai.chat.completions.create(
                model=MODEL,
                max_tokens=1200,
                temperature=0,
                messages=[
                    {"role": "system", "content": (
                        "You are a document summarizer for a TPM working session. "
                        "Produce a structured summary that captures ALL key facts, "
                        "requirements, numbers, names, and technical details. "
                        "This summary will be the ONLY context agents see, so be thorough "
                        "but concise. Use bullet points. Keep under 2000 chars."
                    )},
                    {"role": "user", "content": (
                        f"Summarize this document: **{filename}**\n\n"
                        f"---\n{truncated}\n---\n\n"
                        "Include: key stakeholders, problem statement, requirements, "
                        "data/technical details, open questions, and any specific asks."
                    )},
                ],
            )
            summary = response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Document summarization API error: %s", exc)
            # Fallback: use raw truncated text as context
            summary = f"[Summary unavailable — using raw excerpt]\n\n{truncated[:2000]}"
        self._doc_summary_cache[filename] = summary
        return summary

    def _get_doc_context_block(self, document_context: Optional[dict]) -> str:
        """Build a compact context block from a document for injection into agent prompts.

        Returns empty string if no document context.
        """
        if not document_context:
            return ""
        filename = document_context.get("filename", "document")
        summary = self.summarize_document(document_context)
        if not summary:
            return ""
        return (
            f"\n\n📄 Reference Document: **{filename}**\n"
            f"Summary:\n{summary[:_DOC_SUMMARY_MAX_CHARS]}\n\n"
            "GROUNDING RULE: First, cite 1-2 specific facts from this document that are most relevant "
            "to your expertise and the current question. Then give your analysis building on those facts. "
            "Do NOT ask generic questions that the document already answers."
        )

    def _get_custom_runner(self, key: str) -> Optional[CustomAgentRunner]:
        if key in self._custom_runners:
            return self._custom_runners[key]
        for ca in self.storage.list_custom_agents():
            if ca.key == key:
                runner = CustomAgentRunner(ca)
                self._custom_runners[key] = runner
                return runner
        return None

    def handle_message(
        self,
        message: str,
        file_bytes: Optional[bytes] = None,
        filename: str = "",
        date: str = "",
        document_context: Optional[dict] = None,
        conversation_history: Optional[list] = None,
        active_agents: Optional[list] = None,
        workroom: Optional[WorkroomSession] = None,
    ) -> dict:
        """
        Route a user message to the appropriate agent.

        Args:
            message: User's text message.
            file_bytes: Unused (kept for API compatibility).
            filename: Unused (kept for API compatibility).
            date: Unused (kept for API compatibility).
            document_context: {"filename": str, "text": str} of a previously
                              uploaded document the user may be asking about.
            conversation_history: Recent chat messages [{role, content}] for
                                  context-aware document Q&A.
            active_agents: List of agent keys that are active in this session
                           (e.g. ["challenger", "writer", "researcher"]).
                           None or empty = all agents active (no restriction).
        """
        # ---- @mention: direct routing (supports multiple @mentions) ----
        # Build full list of all known agent keys for mention detection
        all_known = list(MENTION_MAP.values())
        for ca in self.storage.list_custom_agents():
            all_known.append(ca.key)
        mention_keys = _detect_mentions(message, active_agents, all_known_agents=all_known)
        if mention_keys:
            # Check if mentioned agents are in this session
            not_in_session = [k for k in mention_keys if active_agents and k not in active_agents]
            if not_in_session:
                labels = ", ".join(f"**{k}**" for k in not_in_session)
                active_list = ", ".join(active_agents or [])
                return self._respond(
                    "[System]",
                    f"{labels} {'is' if len(not_in_session) == 1 else 'are'} not in this session.\n\n"
                    f"Active agents: {active_list}.\n\n"
                    f"Add them via the agent selector above, or @mention one of the active agents.",
                )
            if len(mention_keys) == 1:
                return self._route_by_key(
                    mention_keys[0], message, conversation_history,
                    document_context, active_agents, workroom=workroom
                )
            else:
                # Multiple agents mentioned — mini round table with just those agents
                return self.round_table(
                    message,
                    active_agents=mention_keys,
                    conversation_history=conversation_history,
                    document_context=document_context,
                    workroom=workroom,
                )

        # ---- Workroom: bypass intent detection, use smart_route ----
        # In workroom mode, let smart_route (LLM-driven) decide which agents
        # respond. Intent-based routing was designed for the solo chat tab
        # and doesn't understand workroom context (concise mode, team
        # awareness, conversation history). Without this early exit,
        # messages containing words like "blocking" or "priorities" trigger
        # solo-chat handlers that return error messages or static prompts
        # instead of engaging the workroom agents conversationally.
        if workroom and active_agents and len(active_agents) > 0:
            return self.smart_route(
                message,
                active_agents=active_agents,
                conversation_history=conversation_history,
                document_context=document_context,
                workroom=workroom,
            )

        # ---- Detect intent from message (solo chat only) ----
        intent = _detect_intent(message)

        if intent == "challenge":
            if not self._agent_allowed("challenger", active_agents):
                return self._agent_blocked("Challenger", active_agents)
            return self._route_by_key("challenger", message, conversation_history, document_context, active_agents)

        if intent == "write":
            if not self._agent_allowed("writer", active_agents):
                return self._agent_blocked("Writer", active_agents)
            return self._route_by_key("writer", message, conversation_history, document_context, active_agents)

        if intent == "research":
            if not self._agent_allowed("researcher", active_agents):
                return self._agent_blocked("Researcher", active_agents)
            return self._route_by_key("researcher", message, conversation_history, document_context, active_agents)

        # ---- Document Q&A — answer from active document context ----
        if document_context:
            return self._handle_document_query(message, document_context, conversation_history)

        # Ambiguous — general chat fallback: show available agents
        active_list = active_agents or ["challenger", "writer", "researcher"]
        examples = []
        if "challenger" in active_list:
            examples.append("- **Challenge an idea**: 'Challenge this: [plan]' or 'Red team this'")
        if "writer" in active_list:
            examples.append("- **Draft a message**: 'Draft an email to [recipient] about [topic]'")
        if "researcher" in active_list:
            examples.append("- **Research a topic**: 'Research: [topic]' or 'Deep dive on [subject]'")

        return self._respond(
            "[System]",
            "I'm not sure what you'd like to do. Here are your options with the active agents:\n\n"
            + "\n".join(examples),
        )

    # ------------------------------------------------------------------ #
    # Agent availability helpers                                          #
    # ------------------------------------------------------------------ #

    def _agent_allowed(self, agent_key: str, active_agents: Optional[list]) -> bool:
        """Return True if the agent is active in this session."""
        if not active_agents:  # None or empty = all agents active
            return True
        return agent_key in active_agents

    def _agent_blocked(self, agent_name: str, active_agents: Optional[list]) -> dict:
        """Return a friendly 'agent not in session' response."""
        available = ", ".join(
            a.title() for a in (active_agents or [])
        ) or "none"
        return self._respond(
            "[System]",
            f"**{agent_name}** isn't in this session.\n\n"
            f"Active agents: {available}.\n\n"
            f"Use the agent selector above the chat to add **{agent_name}** to your session.",
        )

    # ------------------------------------------------------------------ #
    # Document Q&A                                                        #
    # ------------------------------------------------------------------ #

    def _handle_document_query(self, question: str, document_context: dict, conversation_history: Optional[list] = None) -> dict:
        """Answer a free-form question about the active uploaded document, using conversation history for additional context."""
        filename = document_context.get("filename", "document")
        doc_text = document_context.get("text", "")

        # Truncate to avoid token overflow
        truncated = doc_text[:12000]
        if len(doc_text) > 12000:
            truncated += "\n\n[...document truncated for length...]"

        messages = [{"role": "system", "content": DOCUMENT_QA_SYSTEM}]

        # Include recent conversation for context (skip file-heavy messages)
        if conversation_history:
            for msg in conversation_history[-12:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})

        # Final turn: document + question
        messages.append({
            "role": "user",
            "content": (
                f"Document: **{filename}**\n\n"
                f"---\n{truncated}\n---\n\n"
                f"Question: {question}"
            ),
        })

        try:
            response = self._openai.chat.completions.create(
                model=MODEL,
                max_tokens=1500,
                messages=messages,
            )
            answer = response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Document Q&A API error: %s", exc)
            answer = "_(Unable to process document query due to a connection issue. Please try again.)_"
        return self._respond(
            "[Document Q&A]",
            f"_{filename}_\n\n{answer}",
        )

    # ------------------------------------------------------------------ #
    # Helper                                                              #
    # ------------------------------------------------------------------ #

    def _respond(
        self,
        agent: str,
        text: str,
        data: dict | None = None,
        warning: str | None = None,
        pending_action: str | None = None,
        pending_data=None,
    ) -> dict:
        return {
            "agent": agent,
            "text": text,
            "data": data,
            "warning": warning,
            "pending_action": pending_action,
            "pending_data": pending_data,
        }

    # ------------------------------------------------------------------ #
    # @mention routing                                                    #
    # ------------------------------------------------------------------ #

    def _route_by_key(
        self,
        key: str,
        message: str,
        conversation_history: Optional[list],
        document_context: Optional[dict],
        active_agents: Optional[list],
        workroom: Optional[WorkroomSession] = None,
    ) -> dict:
        """Dispatch to a built-in or custom agent by its key string.
        
        When workroom is set, agents use conversational mode (concise responses)
        and receive full conversation history for multi-turn follow-ups.
        """
        if not self._agent_allowed(key, active_agents):
            return self._agent_blocked(key.capitalize(), active_agents)

        is_workroom = workroom is not None

        # Build document context block (summary) for agent injection
        doc_block = self._get_doc_context_block(document_context) if is_workroom else ""

        # Team-awareness: tell each agent who else is in the room
        if is_workroom and active_agents and len(active_agents) > 1:
            other_agents = [a for a in active_agents if a != key]
            if other_agents:
                team_block = (
                    f"\n\n👥 Team context: Other agents present: {', '.join(other_agents)}. "
                    f"Focus on YOUR unique specialty — do not duplicate what "
                    f"{', '.join(other_agents)} would cover. "
                    "If a point overlaps with another agent's area, mention it briefly and move on."
                )
                doc_block = team_block + doc_block

        if key == "facilitator":
            fac = FacilitatorAgent()
            summary = fac.generate_summary(conversation_history or [], message)
            return self._respond("[Facilitator]", summary)

        # Try custom agent
        runner = self._get_custom_runner(key)
        if runner:
            label = f"[{runner.agent_def.emoji} {runner.agent_def.label}]"
            # In workroom mode, pass the summary as doc_context string instead of raw document_context
            # to save tokens. The summary is already computed and cached.
            result = runner.respond(message, conversation_history, document_context,
                                    concise=is_workroom, doc_context=doc_block)
            return self._respond(label, result)

        return self._respond(
            "[System]",
            f"Agent `{key}` not found. Check the spelling or create a custom agent with that key.",
        )

    # ------------------------------------------------------------------ #
    # Smart Route — pick best 1-2 agents instead of round-tabling all   #
    # ------------------------------------------------------------------ #

    SMART_ROUTE_SYSTEM = (
        "You are an AI routing assistant for a multi-agent workroom.\n"
        "Given a user message and the list of available agents, pick the 1-2 agents "
        "best suited to answer. Only pick 2 if the question clearly spans two distinct "
        "areas of expertise. Prefer fewer agents.\n\n"
        "If the user is asking a broad question like 'what does everyone think' or "
        "'discuss this', return ALL agents.\n\n"
        "Respond ONLY with a JSON array of agent keys, e.g. [\"analyst\", \"challenger\"]. "
        "No explanation, no markdown, just the JSON array."
    )

    _OPEN_ENDED_PATTERNS = [
        "what does everyone think", "what do you all think", "share your thoughts",
        "discuss this", "your perspectives", "weigh in", "round table",
        "thoughts on this", "team thoughts", "all of you", "open discussion",
        "what do you think", "each of you", "go around",
    ]

    def _is_open_ended(self, message: str) -> bool:
        """Detect broad/open-ended messages that should go to ALL agents."""
        msg_lower = message.lower().strip()
        # Short messages without a clear @mention are likely open-ended
        if len(msg_lower.split()) <= 6 and "@" not in msg_lower and "?" not in msg_lower:
            return True
        return any(p in msg_lower for p in self._OPEN_ENDED_PATTERNS)

    def smart_route(
        self,
        message: str,
        active_agents: list,
        conversation_history: Optional[list] = None,
        document_context: Optional[dict] = None,
        workroom: Optional[WorkroomSession] = None,
    ) -> dict:
        """
        Use LLM to pick the best 1-2 agents for a message, then dispatch.
        Falls back to round_table if the LLM picks all agents or on error.
        For open-ended messages, skips LLM and goes directly to round_table
        to respect the user's curated team.
        """
        import json as _json

        # Open-ended messages → respect curated team, use all agents
        if self._is_open_ended(message):
            return self.round_table(
                message,
                active_agents=active_agents,
                conversation_history=conversation_history,
                document_context=document_context,
                workroom=workroom,
            )

        # Build agent descriptions for the LLM
        all_opts = self._build_agent_descriptions(active_agents)
        agent_desc_text = "\n".join(
            f"- {a['key']}: {a['description']}" for a in all_opts
        )

        # Recent conversation context (last 4 messages)
        recent = ""
        if conversation_history:
            for m in conversation_history[-4:]:
                role = m.get("role", "user")
                content = m.get("content", "")[:200]
                recent += f"{role}: {content}\n"

        user_prompt = (
            f"Available agents:\n{agent_desc_text}\n\n"
            f"Recent conversation:\n{recent}\n"
            f"User message: {message}\n\n"
            f"Which agent(s) should respond? Return JSON array of keys."
        )

        try:
            resp = self._openai.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.SMART_ROUTE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=100,
            )
            raw = resp.choices[0].message.content.strip()
            # Parse JSON array from response
            # Handle possible markdown wrapping
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            selected = _json.loads(raw)

            # Validate: must be a list of strings that are in active_agents
            if not isinstance(selected, list):
                selected = active_agents
            selected = [k for k in selected if k in active_agents]
            if not selected:
                selected = active_agents
        except Exception:
            # On any error, fall back to round table
            selected = active_agents

        # If LLM selected all or most agents, just round table
        if len(selected) >= len(active_agents) or len(selected) > 2:
            return self.round_table(
                message,
                active_agents=active_agents,
                conversation_history=conversation_history,
                document_context=document_context,
                workroom=workroom,
            )

        # Single agent — direct route
        if len(selected) == 1:
            return self._route_by_key(
                selected[0], message, conversation_history,
                document_context, active_agents, workroom=workroom
            )

        # Two agents — mini round table with just those two
        return self.round_table(
            message,
            active_agents=selected,
            conversation_history=conversation_history,
            document_context=document_context,
            workroom=workroom,
        )

    def _build_agent_descriptions(self, active_agents: list) -> list[dict]:
        """Build a list of {key, description} dicts for active agents."""
        # Built-in descriptions
        BUILTIN_DESC = {
            "facilitator": "Facilitates discussion, summarises progress",
        }
        result = []
        for key in active_agents:
            if key in BUILTIN_DESC:
                result.append({"key": key, "description": BUILTIN_DESC[key]})
            else:
                # Custom agent — try to get description
                runner = self._get_custom_runner(key)
                if runner:
                    desc = runner.agent_def.description or f"Custom agent: {runner.agent_def.label}"
                    result.append({"key": key, "description": desc})
                else:
                    result.append({"key": key, "description": f"Agent: {key}"})
        return result

    # ------------------------------------------------------------------ #
    # Round Table — every active agent responds in parallel              #
    # ------------------------------------------------------------------ #

    def round_table(
        self,
        message: str,
        active_agents: Optional[list],
        conversation_history: Optional[list] = None,
        document_context: Optional[dict] = None,
        workroom: Optional[WorkroomSession] = None,
    ) -> dict:
        """
        Ask every active agent to respond to the same message in parallel.

        All agents receive shared conversation history and document context.
        Responses are collected via ThreadPoolExecutor for lower latency.

        Returns:
            {
              "agent": "[Round Table]",
              "text": "<combined markdown>",
              "multi_response": [{"agent": label, "text": content}, ...],
              "data": None,
              "warning": None,
              ...
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import logging

        logger = logging.getLogger(__name__)

        # Determine which agents to call
        all_builtin = ["facilitator"]
        custom_keys = [ca.key for ca in self.storage.list_custom_agents()]

        if active_agents:
            ordered = [k for k in all_builtin if k in active_agents]
            ordered += [k for k in active_agents if k not in all_builtin]
        else:
            ordered = all_builtin

        def _call_agent(key: str) -> dict:
            """Call a single agent with retry logic. Runs in a thread."""
            try:
                result = self._route_by_key(
                    key, message, list(conversation_history or []),
                    document_context, active_agents, workroom=workroom,
                )
                return {
                    "key": key,
                    "agent": result.get("agent", f"[{key.capitalize()}]"),
                    "text": result.get("text", ""),
                }
            except Exception as e:
                logger.warning("Round table agent %s failed (%s), retrying...", key, e)
                import time
                time.sleep(2)
                try:
                    result = self._route_by_key(
                        key, message, list(conversation_history or []),
                        document_context, active_agents, workroom=workroom,
                    )
                    return {
                        "key": key,
                        "agent": result.get("agent", f"[{key.capitalize()}]"),
                        "text": result.get("text", ""),
                    }
                except Exception as e2:
                    logger.exception("Round table agent %s retry also failed: %s", key, e2)
                    return {
                        "key": key,
                        "agent": f"[{key.capitalize()}]",
                        "text": "_(Temporarily unavailable. Please resend your message to try again.)_",
                    }

        # Fire all agents in parallel
        results_by_key: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=len(ordered)) as pool:
            futures = {pool.submit(_call_agent, key): key for key in ordered}
            for future in as_completed(futures):
                result = future.result()
                results_by_key[result["key"]] = result

        # Reassemble in original order
        responses: list[dict] = []
        for key in ordered:
            r = results_by_key.get(key)
            if r:
                responses.append({"agent": r["agent"], "text": r["text"]})
                # Auto-detect decisions
                if workroom and _is_decision(r["text"]):
                    decision = Decision(content=r["text"][:300], context=message[:200])
                    self.storage.add_workroom_decision(workroom.id, decision)

        # Build combined markdown for the "text" field
        parts = []
        for r in responses:
            parts.append(f"**{r['agent']}**\n\n{r['text']}")
        combined = "\n\n---\n\n".join(parts)

        return {
            "agent": "[Round Table]",
            "text": combined,
            "multi_response": responses,
            "data": None,
            "warning": None,
            "pending_action": None,
            "pending_data": None,
        }

    # ------------------------------------------------------------------ #
    # Generate Output — synthesise session to a structured document      #
    # ------------------------------------------------------------------ #

    def generate_output(
        self,
        output_type: str,
        messages: list[dict],
        workroom: Optional[WorkroomSession] = None,
        custom_description: str = "",
    ) -> str:
        """
        Synthesise a full workroom conversation into a structured document.

        Args:
            output_type:         One of prd | architecture | decision_log | event_plan |
                                 requirements | summary | custom.
            messages:            Full list of {role, content} message dicts.
            workroom:            WorkroomSession for metadata (title, goal, decisions).
            custom_description:  User-supplied description for "custom" output type.

        Returns:
            Markdown string of the generated document.
        """
        # Build transcript of the conversation (skip file-upload lines)
        transcript_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if not content or len(content) < 5:
                continue
            speaker = "User" if role == "user" else m.get("agent", "Assistant").strip("[]")
            transcript_parts.append(f"**{speaker}:** {content}")

        transcript = "\n\n".join(transcript_parts[-60:])  # last 60 turns max

        # Build the user prompt
        context_parts = []
        if workroom:
            context_parts.append(f"Session title: {workroom.title}")
            context_parts.append(f"Session goal: {workroom.goal}")
            if workroom.decisions:
                decisions_text = "\n".join(
                    f"- {d.content[:200]}" for d in workroom.decisions
                )
                context_parts.append(f"Logged decisions:\n{decisions_text}")

        if custom_description:
            context_parts.append(f"Custom output description: {custom_description}")

        context_block = "\n".join(context_parts)
        output_label = output_type.upper().replace("_", " ")

        user_prompt = (
            f"Generate a **{output_label}** from the following multi-agent workroom discussion.\n\n"
        )
        if context_block:
            user_prompt += f"Session context:\n{context_block}\n\n"
        user_prompt += f"Conversation transcript:\n\n{transcript}"

        try:
            response = self._openai.chat.completions.create(
                model=MODEL,
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": GENERATE_OUTPUT_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content.strip()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("generate_output API error: %s", exc)
            content = "_(Unable to generate output due to a connection issue. Please try again.)_"

        # Persist to workroom if provided
        if workroom:
            from models.workroom import OUTPUT_TYPE_META
            meta = OUTPUT_TYPE_META.get(output_type, {})
            title = f"{meta.get('label', output_label)} — {workroom.title}"
            generated = GeneratedOutput(
                output_type=output_type,
                title=title,
                content=content,
            )
            self.storage.add_workroom_output(workroom.id, generated)

        return content

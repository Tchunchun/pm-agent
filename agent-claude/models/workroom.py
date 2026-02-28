"""
Workroom models — Multi-Agent Workroom sessions.

WorkroomSession: A named, goal-driven chat session with a team of agents.
CustomAgent:     User-defined agent with a custom system prompt.
Decision:        A key decision detected or logged during a session.
GeneratedOutput: A structured document synthesised from session discussion.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


# ------------------------------------------------------------------ #
# Decision — auto-detected or manually logged                        #
# ------------------------------------------------------------------ #

class Decision(BaseModel):
    id: str = Field(default_factory=_short_id)
    content: str
    context: str = ""          # snippet of the message that led to this decision
    made_at: str = Field(default_factory=_now)


# ------------------------------------------------------------------ #
# GeneratedOutput — a synthesised document from the session          #
# ------------------------------------------------------------------ #

OUTPUT_TYPES = Literal[
    "prd",
    "architecture",
    "decision_log",
    "event_plan",
    "requirements",
    "summary",
    "custom",
]


class GeneratedOutput(BaseModel):
    id: str = Field(default_factory=_short_id)
    output_type: OUTPUT_TYPES
    title: str
    content: str               # full markdown content
    generated_at: str = Field(default_factory=_now)


# ------------------------------------------------------------------ #
# CustomAgent — user-defined agent                                   #
# ------------------------------------------------------------------ #

class CustomAgent(BaseModel):
    id: str = Field(default_factory=_short_id)
    key: str                   # slug used for routing e.g. "my_pm"
    label: str                 # display name e.g. "My PM"
    emoji: str = "🤖"
    description: str = ""
    system_prompt: str
    category: str = ""         # "professional", "life", or "" for user-created
    is_default: bool = False   # True for pre-built agents shipped with the app
    # Skills this agent can invoke via OpenAI function-calling.
    # Each entry is a registered skill name (e.g. "get_current_date").
    # Empty list = no tool-use (default, backward-compatible).
    skill_names: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


# ------------------------------------------------------------------ #
# WorkroomSession                                                     #
# ------------------------------------------------------------------ #

WORKROOM_MODES = Literal["work", "life"]
DISCUSSION_MODES = Literal["open", "round_table", "focused"]


class WorkroomSession(BaseModel):
    id: str = Field(default_factory=_short_id)
    title: str
    goal: str
    key_outcome: str = ""       # expected key outcome / deliverable
    mode: WORKROOM_MODES = "work"
    output_type: OUTPUT_TYPES = "summary"

    # which discussion style is active
    discussion_mode: DISCUSSION_MODES = "open"
    focused_agent: Optional[str] = None    # agent key when discussion_mode == "focused"

    # agents participating in this session
    active_agents: list[str] = Field(default_factory=list)

    # accumulated decisions and generated documents
    decisions: list[Decision] = Field(default_factory=list)
    generated_outputs: list[GeneratedOutput] = Field(default_factory=list)

    created_at: str = Field(default_factory=_now)
    status: Literal["active", "completed", "archived"] = "active"

    # wizard-sourced metadata
    topic_description: str = ""              # freeform topic text from Step 1
    ai_recommended_agents: list[str] = Field(default_factory=list)  # classifier output

    # uploaded document context — persisted so it survives page refreshes
    # Shape: {"filename": str, "text": str} or None
    document_context: Optional[dict] = None

    # facilitator agent settings
    facilitator_enabled: bool = True
    facilitator_intro_sent: bool = False
    facilitator_summary_interval: int = 6   # summarise every N user messages


# ------------------------------------------------------------------ #
# Output type metadata (for UI display)                              #
# ------------------------------------------------------------------ #

OUTPUT_TYPE_META = {
    "prd": {
        "label": "PRD",
        "emoji": "📋",
        "description": "Product Requirements Document — goals, user stories, scope, non-goals",
    },
    "architecture": {
        "label": "Architecture",
        "emoji": "🏗️",
        "description": "System design, components, data flow, trade-offs",
    },
    "decision_log": {
        "label": "Decision Log",
        "emoji": "📓",
        "description": "All decisions made in this session with rationale",
    },
    "event_plan": {
        "label": "Event Plan",
        "emoji": "🗓️",
        "description": "Agenda, logistics, attendees, action items",
    },
    "requirements": {
        "label": "Requirements",
        "emoji": "📝",
        "description": "Functional and non-functional requirements list",
    },
    "summary": {
        "label": "Summary",
        "emoji": "📄",
        "description": "Concise summary of key points and next steps",
    },
    "custom": {
        "label": "Custom",
        "emoji": "✨",
        "description": "Custom output — describe what you want when generating",
    },
}

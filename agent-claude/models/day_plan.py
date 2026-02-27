from pydantic import BaseModel, Field
from typing import Literal, Optional
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class FocusItem(BaseModel):
    rank: int
    title: str
    what: str
    why: str
    source_type: Literal[
        "customer_request", "calendar", "email", "teams", "insight", "backlog"
    ]
    source_ref: str = ""
    linked_request_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int = 30
    done: bool = False


class DayPlan(BaseModel):
    id: str = Field(default_factory=_short_id)
    date: str  # YYYY-MM-DD
    generated_at: str = Field(default_factory=_now)
    briefing_source: str = "pasted"
    focus_items: list[FocusItem] = Field(default_factory=list)
    context_summary: str = ""
    meetings_today: list[dict] = Field(default_factory=list)

from pydantic import BaseModel, Field
from typing import Literal, Optional
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class EditRecord(BaseModel):
    timestamp: str = Field(default_factory=_now)
    field: str
    old_value: str
    new_value: str


class CustomerRequest(BaseModel):
    id: str = Field(default_factory=_short_id)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    deleted: bool = False

    description: str
    raw_input: str
    source: Literal["chat", "csv", "pdf", "docx", "copilot_briefing"]
    source_ref: str = "typed"

    classification: Literal[
        "feature_request", "bug_report", "integration", "support", "feedback"
    ]
    classification_rationale: str

    priority: Literal["P0", "P1", "P2", "P3"]
    priority_rationale: str

    status: Literal["new", "triaged", "in_review", "linked", "closed"] = "new"
    tags: list[str] = Field(default_factory=list)

    last_surfaced_at: Optional[str] = None
    surface_count: int = 0

    linked_insight_ids: list[str] = Field(default_factory=list)
    edit_history: list[EditRecord] = Field(default_factory=list)

    def mark_surfaced(self) -> None:
        self.last_surfaced_at = _now()
        self.surface_count += 1
        self.updated_at = _now()

    def update_field(self, field: str, new_value) -> None:
        old_value = str(getattr(self, field, ""))
        setattr(self, field, new_value)
        self.updated_at = _now()
        self.edit_history.append(
            EditRecord(field=field, old_value=old_value, new_value=str(new_value))
        )

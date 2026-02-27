from pydantic import BaseModel, Field
from typing import Literal
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return "r" + uuid.uuid4().hex[:7]


class StrategicInsight(BaseModel):
    id: str = Field(default_factory=_short_id)
    created_at: str = Field(default_factory=_now)

    insight_type: Literal["trend", "gap", "risk", "decision"]
    title: str
    what: str
    why: str
    recommended_action: str

    confidence: Literal["high", "medium", "low"]
    period: str = "last-30-days"

    linked_request_ids: list[str] = Field(default_factory=list)
    in_day_plan: bool = False

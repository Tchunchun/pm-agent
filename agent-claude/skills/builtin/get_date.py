"""
GetCurrentDateSkill — returns today's date in ISO 8601 format.

This is the simplest possible skill and serves as the canonical example
of how to implement a no-parameter skill.
"""

from datetime import datetime, timezone

from skills.base import Skill


class GetCurrentDateSkill(Skill):
    """Returns today's UTC date as YYYY-MM-DD."""

    @property
    def name(self) -> str:
        return "get_current_date"

    @property
    def description(self) -> str:
        return (
            "Returns today's date in ISO 8601 format (YYYY-MM-DD). "
            "Use this when the user asks about today's date, current week, "
            "or any time-sensitive planning question."
        )

    def execute(self, **kwargs) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"Today's date is {today}."

"""
GetInsightsSkill — returns recent strategic insights from storage.

Requires a StorageManager instance injected at registration time.
"""

from skills.base import Skill


class GetInsightsSkill(Skill):
    """
    Returns the most recent StrategicInsight records stored by the Analyst.

    Useful for grounding recommendations in actual analysis.
    """

    def __init__(self, storage=None):
        self._storage = storage

    @property
    def name(self) -> str:
        return "get_recent_insights"

    @property
    def description(self) -> str:
        return (
            "Returns the most recent strategic insights stored by the Analyst. "
            "Use this to ground your recommendations in actual analysis rather than "
            "general knowledge. Each insight has a type (TREND, RISK, GAP, DECISION), "
            "a title, and a recommended action."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of insights to return. Default is 5.",
                }
            },
            "required": [],
        }

    def execute(self, limit: int = 5, **kwargs) -> str:
        if not self._storage:
            return "[GetInsightsSkill: storage not configured]"

        limit = max(1, int(limit))
        insights = self._storage.list_insights()[:limit]

        if not insights:
            return "No strategic insights found. The Analyst has not generated any insights yet."

        lines = [f"Recent {len(insights)} strategic insight(s):"]
        for ins in insights:
            lines.append(
                f"  [{ins.insight_type.upper()}] {ins.title} → {ins.recommended_action}"
            )
        return "\n".join(lines)

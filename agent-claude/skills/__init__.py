"""
Skills package — Agno-compatible tool functions.

Tool functions live in skills.tools and are resolved by
CustomAgentRunner._resolve_tools() based on CustomAgent.skill_names.
"""

from skills.tools import get_current_date, search_backlog, get_recent_insights

__all__ = [
    "get_current_date",
    "search_backlog",
    "get_recent_insights",
]

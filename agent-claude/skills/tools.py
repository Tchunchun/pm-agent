"""
Agno tool functions — plain Python functions used as Agent tools.

These replace the old Skill class hierarchy. Agno auto-generates JSON schemas
from docstrings and type hints.

Functions that need data access receive ``run_context: RunContext`` which
provides ``run_context.dependencies["storage"]`` (a StorageManager instance).

Usage:
    from skills.tools import get_current_date, search_backlog, get_recent_insights

    agent = Agent(
        tools=[get_current_date, search_backlog, get_recent_insights],
        dependencies={"storage": storage_manager},
    )
"""

from datetime import datetime, timezone

from agno.run import RunContext


def get_current_date() -> str:
    """Returns today's date in ISO 8601 format (YYYY-MM-DD).

    Use this when the user asks about today's date, current week,
    or any time-sensitive planning question.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"Today's date is {today}."


def search_backlog(run_context: RunContext, keyword: str) -> str:
    """Search the PM's customer request backlog for entries matching a keyword.

    Returns matching requests with their ID, priority, tags, and description.
    Use this to ground recommendations in real backlog data.

    Args:
        keyword: Keyword to search for in request descriptions and tags (case-insensitive).
    """
    storage = run_context.dependencies.get("storage") if run_context.dependencies else None
    if not storage:
        return "[search_backlog: storage not configured]"

    if not keyword.strip():
        return "[search_backlog: keyword must not be empty]"

    requests = storage.list_requests()
    kw = keyword.strip().lower()
    matches = [
        r for r in requests
        if kw in r.description.lower()
        or any(kw in t.lower() for t in r.tags)
    ]

    if not matches:
        return f"No requests found matching '{keyword}'."

    lines = [f"Found {len(matches)} request(s) matching '{keyword}':"]
    for req in matches[:10]:
        tag_str = ", ".join(req.tags) if req.tags else "none"
        lines.append(
            f"  [{req.id}] {req.priority} | tags: {tag_str} | {req.description}"
        )
    if len(matches) > 10:
        lines.append(f"  ... and {len(matches) - 10} more (showing first 10).")

    return "\n".join(lines)


def get_recent_insights(run_context: RunContext, limit: int = 5) -> str:
    """Return the most recent strategic insights stored by the Analyst.

    Use this to ground your recommendations in actual analysis rather than
    general knowledge. Each insight has a type (TREND, RISK, GAP, DECISION),
    a title, and a recommended action.

    Args:
        limit: Maximum number of insights to return. Default is 5.
    """
    storage = run_context.dependencies.get("storage") if run_context.dependencies else None
    if not storage:
        return "[get_recent_insights: storage not configured]"

    limit = max(1, int(limit))
    insights = storage.list_insights()[:limit]

    if not insights:
        return "No strategic insights found. The Analyst has not generated any insights yet."

    lines = [f"Recent {len(insights)} strategic insight(s):"]
    for ins in insights:
        lines.append(
            f"  [{ins.insight_type.upper()}] {ins.title} → {ins.recommended_action}"
        )
    return "\n".join(lines)

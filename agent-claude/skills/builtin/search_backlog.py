"""
SearchBacklogSkill — searches the PM's CustomerRequest backlog by keyword.

Requires a StorageManager instance injected at registration time.
"""

from skills.base import Skill


class SearchBacklogSkill(Skill):
    """
    Searches CustomerRequests by keyword across description and tags.

    Returns up to 10 matching requests with ID, priority, tags, and description.
    """

    def __init__(self, storage=None):
        # StorageManager injected at bootstrap; can be None in unit tests
        self._storage = storage

    @property
    def name(self) -> str:
        return "search_backlog"

    @property
    def description(self) -> str:
        return (
            "Searches the PM's customer request backlog for entries that match "
            "a keyword. Returns matching requests with their ID, priority, tags, "
            "and description. Use this to ground recommendations in real backlog data."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "Keyword to search for in request descriptions and tags. "
                        "Case-insensitive."
                    ),
                }
            },
            "required": ["keyword"],
        }

    def execute(self, keyword: str = "", **kwargs) -> str:
        if not self._storage:
            return "[SearchBacklogSkill: storage not configured]"

        if not keyword.strip():
            return "[SearchBacklogSkill: keyword must not be empty]"

        requests = self._storage.list_requests()
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

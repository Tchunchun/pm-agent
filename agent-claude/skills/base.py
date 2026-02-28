"""
Base class for agent skills.

A Skill exposes a callable tool to an LLM via OpenAI function-calling.
Each skill has:
  - name        — unique snake_case identifier
  - description — natural-language description shown to the LLM
  - parameters  — JSON Schema dict describing the function's arguments
  - execute()   — performs the action and returns a string result

Usage (defining a new skill):

    from skills.base import Skill

    class GetCurrentDateSkill(Skill):
        @property
        def name(self) -> str:
            return "get_current_date"

        @property
        def description(self) -> str:
            return "Returns today's date in ISO 8601 format."

        def execute(self, **kwargs) -> str:
            from datetime import datetime, timezone
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
"""

from abc import ABC, abstractmethod


class Skill(ABC):
    """Abstract base class for all agent skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique snake_case identifier, e.g. 'get_current_date'."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Natural-language description shown to the LLM."""
        ...

    @property
    def parameters(self) -> dict:
        """
        JSON Schema for the function's arguments.

        Override in subclasses that accept parameters.
        Default: no parameters.
        """
        return {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Execute the skill.

        Args:
            **kwargs: Argument values matched to the parameters schema.

        Returns:
            A string result that will be injected back into the LLM
            conversation as a tool response.
        """
        ...

    def to_openai_tool(self) -> dict:
        """Return the OpenAI tool definition dict for this skill."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"<Skill name={self.name!r}>"

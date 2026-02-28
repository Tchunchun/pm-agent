"""
SkillRegistry — central registry for all agent skills.

Usage:
    from skills.registry import registry

    # Register a skill
    registry.register(GetCurrentDateSkill())

    # Look up a skill by name
    skill = registry.get("get_current_date")

    # Convert a list of skill names to OpenAI tool dicts
    tools = registry.to_openai_tools(["get_current_date", "search_backlog"])

    # Execute a skill by name (handles missing / errors gracefully)
    result = registry.execute("get_current_date")
"""

import logging

from skills.base import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry that maps skill names to Skill instances."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                        #
    # ------------------------------------------------------------------ #

    def register(self, skill: Skill) -> None:
        """Register a skill. Overwrites any existing skill with the same name."""
        if skill.name in self._skills:
            logger.warning(
                "SkillRegistry: overwriting existing skill '%s'", skill.name
            )
        self._skills[skill.name] = skill
        logger.debug("SkillRegistry: registered skill '%s'", skill.name)

    # ------------------------------------------------------------------ #
    # Lookup                                                              #
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Skill | None:
        """Return the skill with the given name, or None if not found."""
        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        """Return all registered skills."""
        return list(self._skills.values())

    def names(self) -> list[str]:
        """Return all registered skill names."""
        return list(self._skills.keys())

    # ------------------------------------------------------------------ #
    # OpenAI integration                                                  #
    # ------------------------------------------------------------------ #

    def to_openai_tools(self, skill_names: list[str] | None = None) -> list[dict]:
        """
        Return OpenAI tool dicts for the given skill names.

        Args:
            skill_names: If None, returns tools for all registered skills.
                         If provided, only returns tools for matching skills
                         (silently skips unknown names with a warning).

        Returns:
            List of OpenAI tool dicts ready to pass as ``tools=[...]``.
        """
        if skill_names is None:
            skills = self.list_all()
        else:
            skills = [self._skills[n] for n in skill_names if n in self._skills]
            missing = [n for n in skill_names if n not in self._skills]
            if missing:
                logger.warning(
                    "SkillRegistry: unknown skills requested: %s", missing
                )
        return [s.to_openai_tool() for s in skills]

    # ------------------------------------------------------------------ #
    # Execution                                                           #
    # ------------------------------------------------------------------ #

    def execute(self, name: str, **kwargs) -> str:
        """
        Execute a registered skill by name.

        Returns a string result, or an error message string if the skill
        is not found or raises an exception.
        """
        skill = self.get(name)
        if skill is None:
            logger.warning("SkillRegistry: skill '%s' not found for execution", name)
            return f"[Skill '{name}' is not registered. Available: {self.names()}]"
        try:
            return skill.execute(**kwargs)
        except Exception as exc:
            logger.exception(
                "SkillRegistry: error executing skill '%s': %s", name, exc
            )
            return f"[Skill '{name}' raised an error: {exc}]"

    def __repr__(self) -> str:
        return f"<SkillRegistry skills={self.names()}>"


# ------------------------------------------------------------------ #
# Global singleton                                                    #
# ------------------------------------------------------------------ #

registry = SkillRegistry()

"""
Skills package — agent tool-use framework.

Quick-start:

    # At app startup (after storage is ready):
    from skills.bootstrap import bootstrap_skills
    bootstrap_skills(storage=storage_manager)

    # In an agent — assign skills to a CustomAgent via skill_names:
    agent = CustomAgent(
        key="my_agent",
        label="My Agent",
        system_prompt="...",
        skill_names=["get_current_date", "search_backlog"],
    )
    # CustomAgentRunner automatically loads and executes skills.

    # To add a new skill, subclass Skill and register it:
    from skills.base import Skill
    from skills.registry import registry

    class MySkill(Skill):
        @property
        def name(self) -> str: return "my_skill"
        @property
        def description(self) -> str: return "Does something useful."
        def execute(self, **kwargs) -> str: return "result"

    registry.register(MySkill())
"""

from skills.base import Skill
from skills.registry import SkillRegistry, registry
from skills.builtin import GetCurrentDateSkill, SearchBacklogSkill, GetInsightsSkill

__all__ = [
    # Core abstractions
    "Skill",
    "SkillRegistry",
    "registry",
    # Built-in skills
    "GetCurrentDateSkill",
    "SearchBacklogSkill",
    "GetInsightsSkill",
]

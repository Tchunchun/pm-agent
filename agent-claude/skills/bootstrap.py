"""
bootstrap_skills — registers all built-in skills with the global registry.

Call once at application startup after StorageManager is available:

    from skills.bootstrap import bootstrap_skills
    bootstrap_skills(storage=st.session_state.storage)

Skills that require storage (SearchBacklogSkill, GetInsightsSkill) are
registered with the storage instance so they can access live data.
Skills that don't need storage (GetCurrentDateSkill) are always registered.
"""

import logging

from skills.registry import registry
from skills.builtin.get_date import GetCurrentDateSkill
from skills.builtin.search_backlog import SearchBacklogSkill
from skills.builtin.get_insights import GetInsightsSkill

logger = logging.getLogger(__name__)


def bootstrap_skills(storage=None) -> None:
    """
    Register all built-in skills with the global registry.

    Args:
        storage: StorageManager instance for skills that need data access.
                 If None, storage-dependent skills are still registered but
                 will return a 'storage not configured' message when executed.
    """
    registry.register(GetCurrentDateSkill())
    registry.register(SearchBacklogSkill(storage=storage))
    registry.register(GetInsightsSkill(storage=storage))

    logger.info(
        "Skills bootstrapped: %s",
        registry.names(),
    )

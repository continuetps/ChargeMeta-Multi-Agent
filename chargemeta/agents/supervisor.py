from ..config import get_settings
from ..graph.state import InventoryState

PLAN = ["metadata", "governance", "relation", "quality"]


async def supervisor_agent(state: InventoryState) -> InventoryState:
    """Deterministic supervisor: bounded routing, no free-form agent conversation."""
    completed = list(state.get("completed_agents", []))
    retry_count = state.get("governance_retry_count", 0)
    settings = get_settings()
    if state.get("retry_governance") and retry_count < settings.governance_max_retries:
        return {
            **state,
            "next_agent": "governance",
            "retry_governance": False,
            "governance_retry_count": retry_count + 1,
            "current_agent": "supervisor",
        }
    if state.get("retry_governance") and retry_count >= settings.governance_max_retries:
        completed = list(dict.fromkeys([*completed, "governance", "quality"]))
        return {
            **state,
            "next_agent": "finalize",
            "retry_governance": False,
            "review_required": True,
            "completed_agents": completed,
            "current_agent": "supervisor",
        }
    for agent in PLAN:
        if agent not in completed:
            return {**state, "next_agent": agent, "current_agent": "supervisor", "plan": PLAN}
    return {**state, "next_agent": "finalize", "current_agent": "supervisor", "plan": PLAN}

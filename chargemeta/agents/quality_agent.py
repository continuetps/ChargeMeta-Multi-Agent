from ..graph.state import InventoryState
from ..tools.quality_tools import inspect_quality
from ..tools.run_tracking import set_job_stage, track_agent


async def quality_agent(state: InventoryState) -> InventoryState:
    attempt = state.get("governance_retry_count", 0) + 1
    set_job_stage(state["job_id"], "quality_agent")
    with track_agent(
        state["job_id"],
        "quality_agent",
        attempt,
        {"source_id": state["source_id"], "governance_attempt": attempt},
    ) as (output, metrics):
        report = inspect_quality(state["job_id"], state["source_id"])
        output.update(report)
        metrics.update(
            {
                "average_confidence": report["average_confidence"],
                "pending_ratio": report["pending_ratio"],
                "recommended_rules": report["recommended_rules"],
            }
        )
    completed = list(dict.fromkeys([*state.get("completed_agents", []), "quality"]))
    agent_metrics = {**state.get("agent_metrics", {}), "quality": metrics}
    if report["retry_governance"]:
        completed = [agent for agent in completed if agent not in {"governance", "quality"}]
    return {
        **state,
        "current_agent": "quality",
        "completed_agents": completed,
        "quality_report": report,
        "quality_passed": report["quality_passed"],
        "review_required": report["review_required"],
        "retry_governance": report["retry_governance"],
        "agent_metrics": agent_metrics,
    }

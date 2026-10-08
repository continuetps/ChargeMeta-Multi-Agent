from ..graph.state import InventoryState
from ..tools.relation_tools import infer_relations
from ..tools.run_tracking import set_job_stage, track_agent


async def relation_agent(state: InventoryState) -> InventoryState:
    set_job_stage(state["job_id"], "relation_agent")
    with track_agent(state["job_id"], "relation_agent", 1, {"source_id": state["source_id"]}) as (
        output,
        metrics,
    ):
        result = infer_relations(state["source_id"])
        output.update(result)
        metrics.update(
            {"inferred_relations": result["relations"], "pending_review": result["pending_review"]}
        )
    completed = list(dict.fromkeys([*state.get("completed_agents", []), "relation"]))
    agent_metrics = {**state.get("agent_metrics", {}), "relation": metrics}
    return {
        **state,
        "current_agent": "relation",
        "completed_agents": completed,
        "relation_count": result["relations"],
        "agent_metrics": agent_metrics,
    }

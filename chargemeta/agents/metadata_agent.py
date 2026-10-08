from ..graph.state import InventoryState
from ..tools.metadata_tools import collect_and_profile
from ..tools.run_tracking import set_job_stage, track_agent


async def metadata_agent(state: InventoryState) -> InventoryState:
    set_job_stage(state["job_id"], "metadata_agent")
    with track_agent(state["job_id"], "metadata_agent", 1, {"source_id": state["source_id"]}) as (
        output,
        metrics,
    ):
        result = collect_and_profile(state["source_id"])
        output.update(result)
        metrics.update({"processed_tables": result["tables"], "processed_columns": result["columns"]})
    completed = list(dict.fromkeys([*state.get("completed_agents", []), "metadata"]))
    agent_metrics = {**state.get("agent_metrics", {}), "metadata": metrics}
    return {
        **state,
        "current_agent": "metadata",
        "completed_agents": completed,
        "table_count": result["tables"],
        "column_count": result["columns"],
        "agent_metrics": agent_metrics,
    }

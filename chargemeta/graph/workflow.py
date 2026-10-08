from langgraph.graph import END, START, StateGraph

from ..agents.governance_agent import governance_agent
from ..agents.metadata_agent import metadata_agent
from ..agents.quality_agent import quality_agent
from ..agents.relation_agent import relation_agent
from ..agents.supervisor import supervisor_agent
from ..db import SessionLocal
from ..models import DataSource, InventoryJob, utc_now
from .state import InventoryState


def route_supervisor(state: InventoryState) -> str:
    return state["next_agent"]


async def finalize(state: InventoryState) -> InventoryState:
    with SessionLocal() as db:
        job = db.get(InventoryJob, state["job_id"])
        source = db.get(DataSource, state["source_id"])
        job.status = "completed_with_review" if state.get("review_required") else "completed"
        job.stage = "completed"
        job.stats = {
            "tables": state.get("table_count", 0),
            "columns": state.get("column_count", 0),
            "relations": state.get("relation_count", 0),
            "workflow": "supervisor_multi_agent",
            "quality_passed": state.get("quality_passed", False),
            "review_required": state.get("review_required", False),
            "governance_retries": state.get("governance_retry_count", 0),
            "agent_metrics": state.get("agent_metrics", {}),
            "quality_report": state.get("quality_report", {}),
        }
        job.finished_at = utc_now()
        source.last_scanned_at = utc_now()
        db.commit()
    return {**state, "current_agent": "finalize", "next_agent": "finalize"}


builder = StateGraph(InventoryState)
builder.add_node("supervisor", supervisor_agent)
builder.add_node("metadata", metadata_agent)
builder.add_node("governance", governance_agent)
builder.add_node("relation", relation_agent)
builder.add_node("quality", quality_agent)
builder.add_node("finalize", finalize)
builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
        "metadata": "metadata",
        "governance": "governance",
        "relation": "relation",
        "quality": "quality",
        "finalize": "finalize",
    },
)
for agent in ("metadata", "governance", "relation", "quality"):
    builder.add_edge(agent, "supervisor")
builder.add_edge("finalize", END)
multi_agent_graph = builder.compile()


async def run_inventory(job_id: int) -> dict:
    with SessionLocal() as db:
        job = db.get(InventoryJob, job_id)
        initial: InventoryState = {
            "job_id": job.id,
            "source_id": job.source_id,
            "objective": "完成数据源盘点、语义治理、关系推断与质量门禁",
            "plan": [],
            "completed_agents": [],
            "governance_retry_count": 0,
            "retry_governance": False,
            "review_required": False,
            "quality_passed": False,
            "agent_metrics": {},
        }
    try:
        return await multi_agent_graph.ainvoke(initial, {"recursion_limit": 20})
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(InventoryJob, job_id)
            job.status, job.stage, job.error, job.finished_at = "failed", "failed", str(exc)[:1000], utc_now()
            db.commit()
        raise

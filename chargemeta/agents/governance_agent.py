from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..graph.state import InventoryState
from ..models import AssetTable
from ..services.embedding import embed_text
from ..services.llm import get_llm_provider
from ..tools.run_tracking import set_job_stage, track_agent


async def governance_agent(state: InventoryState) -> InventoryState:
    """Generate semantic metadata with local/cloud routing and build vector documents."""
    retry = state.get("governance_retry_count", 0)
    attempt = retry + 1
    set_job_stage(state["job_id"], "governance_agent")
    llm = get_llm_provider(force_cloud=retry > 0)
    settings = get_settings()
    with track_agent(
        state["job_id"],
        "governance_agent",
        attempt,
        {"source_id": state["source_id"], "provider": llm.name, "retry": retry},
    ) as (output, metrics):
        processed = auto_published = pending = 0
        confidence_sum = 0.0
        with SessionLocal() as db:
            tables = db.scalars(select(AssetTable).where(AssetTable.source_id == state["source_id"])).all()
            for table in tables:
                neighbor_names = [column.name for column in table.columns]
                for column in table.columns:
                    if retry > 0 and column.review_status != "pending":
                        continue
                    semantic = await llm.infer(
                        {
                            "table_name": table.name,
                            "table_domain": table.domain,
                            "column_name": column.name,
                            "data_type": column.data_type,
                            "nullable": column.nullable,
                            "samples": column.profile.get("samples", []),
                            "neighbor_columns": neighbor_names,
                            "sensitivity": column.sensitivity,
                        }
                    )
                    column.business_name, column.ai_comment = semantic.business_name, semantic.description
                    column.semantic_type, column.confidence = semantic.semantic_type, semantic.confidence
                    column.evidence = list(
                        dict.fromkeys([*column.evidence, *semantic.evidence, f"模型路由:{llm.name}"])
                    )
                    column.review_status = (
                        "auto_published"
                        if semantic.confidence >= settings.auto_publish_threshold
                        else "pending"
                    )
                    column.search_text = " ".join(
                        filter(
                            None,
                            [
                                table.name,
                                table.domain,
                                column.name,
                                column.business_name,
                                column.ai_comment,
                                column.semantic_type,
                            ],
                        )
                    )
                    column.embedding = await embed_text(column.search_text)
                    processed += 1
                    confidence_sum += semantic.confidence
                    auto_published += column.review_status == "auto_published"
                    pending += column.review_status == "pending"
                db.commit()
        average_confidence = round(confidence_sum / processed, 4) if processed else 0
        output.update(
            {
                "provider": llm.name,
                "processed": processed,
                "auto_published": auto_published,
                "pending": pending,
                "average_confidence": average_confidence,
            }
        )
        metrics.update(
            {
                "processed_columns": processed,
                "average_confidence": average_confidence,
                "auto_publish_rate": round(auto_published / processed, 4) if processed else 0,
            }
        )
    completed = list(dict.fromkeys([*state.get("completed_agents", []), "governance"]))
    agent_metrics = {**state.get("agent_metrics", {}), "governance": metrics}
    return {
        **state,
        "current_agent": "governance",
        "completed_agents": completed,
        "agent_metrics": agent_metrics,
        "retry_governance": False,
    }

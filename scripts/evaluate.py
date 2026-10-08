"""Evaluate semantic governance, retrieval and every specialized agent."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from chargemeta.config import get_settings
from chargemeta.db import SessionLocal
from chargemeta.models import AgentRun, AssetColumn, EvaluationRun, InventoryJob
from chargemeta.services.search import search_assets

ANNOTATION_GROUND_TRUTH = {
    "dev_sn": "设备序列号",
    "station_id": "充电站ID",
    "gun_no": "充电枪编号",
    "soc_val": "电池剩余电量",
    "rated_kw": "额定功率",
    "mobile_phone": "客户手机号码",
    "plate_number": "车牌号码",
    "actual_amt": "实际支付金额",
    "charged_energy": "充电电量",
    "collect_time": "采集时间",
}
SEARCH_CASES = [
    ("哪些表保存了客户手机号", "mobile_phone"),
    ("设备能够承受的最大输出功率", "rated_kw"),
    ("查找车辆车牌信息", "plate_number"),
    ("充电过程中采集了多少电量", "charged_energy"),
    ("哪些字段记录采集时间", "collect_time"),
]


async def evaluate() -> dict:
    with SessionLocal() as db:
        columns = db.scalars(select(AssetColumn).where(AssetColumn.name.in_(ANNOTATION_GROUND_TRUTH))).all()
        exact = sum(column.business_name == ANNOTATION_GROUND_TRUTH[column.name] for column in columns)
        sensitive = [column for column in columns if column.name in {"mobile_phone", "plate_number"}]
        reciprocal_ranks = []
        recalls = []
        for query, expected in SEARCH_CASES:
            results = await search_assets(db, query, 5)
            names = [item["asset"].split(".")[-1] for item in results]
            recalls.append(float(expected in names))
            reciprocal_ranks.append(1 / (names.index(expected) + 1) if expected in names else 0)
        latest_job = db.scalar(select(InventoryJob).order_by(InventoryJob.id.desc()))
        agent_runs = (
            db.scalars(select(AgentRun).where(AgentRun.job_id == latest_job.id)).all() if latest_job else []
        )
        required_agents = {"metadata_agent", "governance_agent", "relation_agent", "quality_agent"}
        successful_agents = {run.agent_name for run in agent_runs if run.status == "completed"}
        metrics = {
            "annotation_exact_match": round(exact / len(columns), 4) if columns else 0,
            "sensitive_recall": round(
                sum(c.sensitivity == "L3-个人敏感" for c in sensitive) / len(sensitive), 4
            )
            if sensitive
            else 0,
            "retrieval_recall_at_5": round(sum(recalls) / len(recalls), 4),
            "retrieval_mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
            "agent_success_rate": round(len(required_agents & successful_agents) / len(required_agents), 4),
            "bounded_retry_passed": bool(
                latest_job
                and latest_job.stats.get("governance_retries", 0) <= get_settings().governance_max_retries
            ),
            "quality_passed": bool(latest_job and latest_job.stats.get("quality_passed")),
            "evaluated_column_instances": len(columns),
            "search_cases": len(SEARCH_CASES),
        }
        db.add(
            EvaluationRun(
                model_name=get_settings().llm_provider, prompt_version="governance-v2", metrics=metrics
            )
        )
        db.commit()
        return metrics


if __name__ == "__main__":
    print(asyncio.run(evaluate()))

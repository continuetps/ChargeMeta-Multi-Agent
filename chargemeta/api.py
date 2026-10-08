from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .connectors import SQLAlchemyConnector
from .db import get_db
from .models import (
    AgentRun,
    AssetColumn,
    AssetRelation,
    AssetTable,
    AuditLog,
    DataSource,
    EvaluationRun,
    InventoryJob,
    MetadataChange,
    ReviewTask,
    utc_now,
)
from .schemas import ReviewRequest, SearchRequest, SourceCreate, SourceOut
from .services.search import search_assets
from .worker import inventory_task

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "service": "ChargeMeta Agent"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    count = lambda model: db.scalar(select(func.count()).select_from(model)) or 0
    return {
        "sources": count(DataSource),
        "tables": count(AssetTable),
        "columns": count(AssetColumn),
        "pending_reviews": db.scalar(
            select(func.count()).select_from(AssetColumn).where(AssetColumn.review_status == "pending")
        )
        or 0,
        "sensitive_columns": db.scalar(
            select(func.count()).select_from(AssetColumn).where(AssetColumn.sensitivity != "L1-公开")
        )
        or 0,
    }


@router.post("/sources", response_model=SourceOut)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    source = DataSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.scalars(select(DataSource).order_by(DataSource.id)).all()


@router.post("/sources/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(DataSource, source_id)
    if not source:
        raise HTTPException(404, "数据源不存在")
    return {"success": SQLAlchemyConnector(source.url).test_connection()}


@router.post("/sources/{source_id}/scan")
def scan(source_id: int, db: Session = Depends(get_db)):
    if not db.get(DataSource, source_id):
        raise HTTPException(404, "数据源不存在")
    job = InventoryJob(source_id=source_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    task = inventory_task.delay(job.id)
    return {"job_id": job.id, "task_id": task.id, "status": job.status}


@router.get("/jobs")
def jobs(db: Session = Depends(get_db)):
    rows = db.scalars(select(InventoryJob).order_by(InventoryJob.id.desc()).limit(30)).all()
    return [
        {
            "id": j.id,
            "source_id": j.source_id,
            "status": j.status,
            "stage": j.stage,
            "stats": j.stats,
            "error": j.error,
        }
        for j in rows
    ]


@router.get("/jobs/{job_id}/agents")
def job_agents(job_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentRun).where(AgentRun.job_id == job_id).order_by(AgentRun.id)).all()
    return [
        {
            "id": row.id,
            "agent_name": row.agent_name,
            "attempt": row.attempt,
            "status": row.status,
            "input": row.input_summary,
            "output": row.output_summary,
            "metrics": row.metrics,
            "error": row.error,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]


@router.get("/tables")
def tables(domain: str | None = None, db: Session = Depends(get_db)):
    stmt = select(AssetTable).options(joinedload(AssetTable.columns)).order_by(AssetTable.name)
    if domain:
        stmt = stmt.where(AssetTable.domain == domain)
    rows = db.scalars(stmt).unique().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "schema": t.schema_name,
            "domain": t.domain,
            "comment": t.ai_comment or t.comment,
            "confidence": t.confidence,
            "column_count": len(t.columns),
        }
        for t in rows
    ]


@router.get("/tables/{table_id}")
def table_detail(table_id: int, db: Session = Depends(get_db)):
    table = db.scalar(
        select(AssetTable).options(joinedload(AssetTable.columns)).where(AssetTable.id == table_id)
    )
    if not table:
        raise HTTPException(404, "资产不存在")
    return {
        "id": table.id,
        "name": table.name,
        "domain": table.domain,
        "comment": table.ai_comment,
        "columns": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.data_type,
                "business_name": c.business_name,
                "description": c.ai_comment,
                "sensitivity": c.sensitivity,
                "confidence": c.confidence,
                "evidence": c.evidence,
                "profile": c.profile,
                "review_status": c.review_status,
            }
            for c in table.columns
        ],
    }


@router.patch("/columns/{column_id}/review")
def review(column_id: int, payload: ReviewRequest, db: Session = Depends(get_db)):
    column = db.get(AssetColumn, column_id)
    if not column:
        raise HTTPException(404, "字段不存在")
    if payload.business_name is not None:
        column.business_name = payload.business_name
    if payload.description is not None:
        column.ai_comment = payload.description
    if payload.domain is not None:
        column.table.domain = payload.domain
    column.review_status = payload.status
    review_task = db.scalar(
        select(ReviewTask)
        .where(ReviewTask.column_id == column.id, ReviewTask.status == "pending")
        .order_by(ReviewTask.id.desc())
    )
    if review_task:
        review_task.status = "resolved"
        review_task.resolution = payload.model_dump()
        review_task.resolved_at = utc_now()
    db.add(AuditLog(action="review", target_type="column", target_id=column.id, detail=payload.model_dump()))
    db.commit()
    return {"success": True, "status": column.review_status}


@router.get("/reviews")
def reviews(status: str = "pending", db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ReviewTask).where(ReviewTask.status == status).order_by(ReviewTask.id.desc()).limit(200)
    ).all()
    result = []
    for row in rows:
        column = db.get(AssetColumn, row.column_id)
        result.append(
            {
                "id": row.id,
                "job_id": row.job_id,
                "column_id": row.column_id,
                "asset": f"{column.table.name}.{column.name}",
                "reason": row.reason,
                "priority": row.priority,
                "status": row.status,
                "ai_snapshot": row.ai_snapshot,
                "created_at": row.created_at,
            }
        )
    return result


@router.post("/search")
async def search(payload: SearchRequest, db: Session = Depends(get_db)):
    return {"query": payload.query, "results": await search_assets(db, payload.query, payload.limit)}


@router.get("/changes")
def changes(db: Session = Depends(get_db)):
    rows = db.scalars(select(MetadataChange).order_by(MetadataChange.id.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "asset_type": row.asset_type,
            "asset_name": row.asset_name,
            "change_type": row.change_type,
            "before": row.before,
            "after": row.after,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/evaluations")
def evaluations(db: Session = Depends(get_db)):
    rows = db.scalars(select(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(20)).all()
    return [
        {
            "id": row.id,
            "model_name": row.model_name,
            "prompt_version": row.prompt_version,
            "metrics": row.metrics,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/relations")
def relations(db: Session = Depends(get_db)):
    rows = db.scalars(select(AssetRelation).order_by(AssetRelation.confidence.desc()).limit(200)).all()
    result = []
    for row in rows:
        source = db.get(AssetColumn, row.source_column_id)
        target = db.get(AssetColumn, row.target_column_id)
        result.append(
            {
                "id": row.id,
                "source": f"{source.table.name}.{source.name}",
                "target": f"{target.table.name}.{target.name}",
                "type": row.relation_type,
                "confidence": row.confidence,
                "evidence": row.evidence,
            }
        )
    return result

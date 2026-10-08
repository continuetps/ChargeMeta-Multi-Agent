from contextlib import contextmanager
from time import perf_counter

from ..db import SessionLocal
from ..models import AgentRun, InventoryJob, utc_now


def set_job_stage(job_id: int, agent_name: str) -> None:
    with SessionLocal() as db:
        job = db.get(InventoryJob, job_id)
        job.stage = agent_name
        job.status = "running"
        db.commit()


@contextmanager
def track_agent(job_id: int, agent_name: str, attempt: int, input_summary: dict):
    started = perf_counter()
    with SessionLocal() as db:
        run = AgentRun(job_id=job_id, agent_name=agent_name, attempt=attempt, input_summary=input_summary)
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    output: dict = {}
    metrics: dict = {}
    try:
        yield output, metrics
    except Exception as exc:
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            run.status = "failed"
            run.error = str(exc)[:1000]
            run.metrics = {"duration_ms": round((perf_counter() - started) * 1000, 2)}
            run.finished_at = utc_now()
            db.commit()
        raise
    else:
        metrics["duration_ms"] = round((perf_counter() - started) * 1000, 2)
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            run.status = "completed"
            run.output_summary = output
            run.metrics = metrics
            run.finished_at = utc_now()
            db.commit()

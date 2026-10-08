import asyncio

from celery import Celery

from .config import get_settings
from .graph.workflow import run_inventory

settings = get_settings()
celery_app = Celery("chargemeta", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
)


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="chargemeta.inventory",
)
def inventory_task(self, job_id: int):
    return asyncio.run(run_inventory(job_id))

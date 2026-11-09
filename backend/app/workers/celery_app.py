from celery import Celery
from backend.app.core.config import settings

celery_app = Celery(
    "smartdist_celery",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=["backend.app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    result_expires=3600,  # 1 hour
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)

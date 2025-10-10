from celery import Celery
from celery.signals import after_task_publish

from src.setup.celery_config import get_celery_settings

_settings = get_celery_settings()

celery_app = Celery(
    "posttagger",
    broker=_settings.REDIS_URL,
    backend=_settings.REDIS_URL,
)
celery_app.autodiscover_tasks(["src.worker"])

celery_app.conf.update(
    task_ignore_result=False,
    result_expires=_settings.RESULT_TTL_SECONDS,
)


@after_task_publish.connect
def mark_task_sent(sender=None, headers=None, body=None, **kwargs):
    """
    Store an explicit SENT state for tasks right after they are published.
    Allows distinguishing between nonexistent task ids and tasks that were
    accepted by the broker but not yet started.
    """
    task_id = (headers or {}).get("id") or (body or {}).get("id")
    if task_id:
        celery_app.backend.store_result(task_id, result=None, state="SENT")

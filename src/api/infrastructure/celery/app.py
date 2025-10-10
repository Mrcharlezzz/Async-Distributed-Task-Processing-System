from celery import Celery

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


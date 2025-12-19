import time
from typing import Any

from mpmath import mp

from src.api.infrastructure.celery.app import celery_app
from src.setup.worker_config import get_worker_settings

_settings = get_worker_settings()

celery_app.autodiscover_tasks(
    packages=["src.worker"],
    related_name="tasks",
    force=True,
)


def get_pi(digits: int) -> str:
    mp.dps = digits
    return str(mp.pi)


@celery_app.task(name="compute_pi", bind=True)
def compute_pi(self, payload: dict) -> dict:
    """
    Pi computation task.
    Simulates heavy pi calculation.
    """
    digits: int = payload["digits"]
    pi: str = get_pi(digits)

    for k in range(digits):
        time.sleep(_settings.SLEEP_PER_DIGIT_SEC)
        progress = (k + 1) / digits
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "message": None, "result": None},
        )

    result = {"progress": 1.0, "message": None, "result": pi}
    return result


def _simulate_steps(self, payload: dict[str, Any], steps: int, sleep: float = 0.1) -> None:
    for idx in range(steps):
        time.sleep(sleep)
        self.update_state(
            state="PROGRESS",
            meta={"progress": (idx + 1) / steps, "message": None, "result": None},
        )


@celery_app.task(name="document_analysis", bind=True)
def document_analysis(self, payload: dict) -> dict:
    """
    Dummy document analysis task.
    """
    _simulate_steps(self, payload, steps=5)
    return {
        "progress": 1.0,
        "message": None,
        "result": {
            "task_id": self.request.id,
            "task_type": payload.get("task_type"),
            "payload": payload.get("payload"),
            "analysis": "documents analyzed",
        },
    }


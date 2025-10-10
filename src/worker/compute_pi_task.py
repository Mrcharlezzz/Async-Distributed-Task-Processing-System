import time

from mpmath import mp

from src.api.infrastructure.celery.app import celery_app
from src.setup.worker_config import get_worker_settings

_settings = get_worker_settings()

def get_pi(digits: int) -> str:
    mp.dps = digits
    return str(mp.pi)

@celery_app.task(name="compute_pi", bind=True)
def compute_pi(self, payload: dict) -> dict:
    """
    Pi computation task.
    Simulates heavy pi calculation.
    """
    digits : int = payload["digits"]
    pi : str = get_pi(digits)

    for k in range(digits):
        time.sleep(_settings.SLEEP_PER_DIGIT_SEC)
        progress = (k + 1) / digits
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "message": None, "result": None},
        )

    result = {"progress": 1.0, "message": None, "result": pi}
    return result

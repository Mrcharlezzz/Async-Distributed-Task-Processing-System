import time

from mpmath import mp

from src.app.infrastructure.celery.app import celery_app
from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.worker.reporter import TaskReporter
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
    reporter = TaskReporter(self.request.id)
    payload_data = payload["payload"]
    digits: int = payload_data["digits"]
    pi: str = get_pi(digits)

    total = len(pi)
    with reporter.report_result_chunk(batch_size=1) as chunks:
        for k, digit in enumerate(pi):
            time.sleep(_settings.SLEEP_PER_DIGIT_SEC)
            progress = (k + 1) / total if total else 1.0
            status = TaskStatus(
                state=TaskState.RUNNING,
                progress=TaskProgress(current=k + 1, total=total, percentage=progress),
            )
            reporter.report_status(status)
            chunks.emit(digit)

    reporter.report_result({"task_id": self.request.id, "data": pi})
    return {"result": pi}

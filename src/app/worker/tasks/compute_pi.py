import random
import time

from mpmath import mp

from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.infrastructure.celery.app import celery_app
from src.app.worker.reporter import TaskReporter
from src.setup.worker_config import get_worker_settings

_settings = get_worker_settings()


def get_pi(digits: int) -> str:
    """Return pi to the requested number of digits."""
    mp.dps = digits
    return str(mp.pi)


@celery_app.task(name="compute_pi", bind=True)
def compute_pi(self, payload: dict) -> dict:
    """Compute pi and stream digits with periodic status updates."""
    reporter = TaskReporter(self.request.id)
    payload_data = payload["payload"]
    digits: int = payload_data["digits"]
    pi: str = get_pi(digits)

    total = len(pi)
    start_time = time.monotonic()
    with reporter.report_result_chunk(batch_size=1) as chunks:
        for k, digit in enumerate(pi):
            sleep_time = random.uniform(0.1, 0.5)
            done = k + 1
            progress = done / total if total else 1.0
            remaining = total - done
            elapsed = time.monotonic() - start_time
            avg_time = elapsed / done if done else 0.0
            eta_seconds = remaining * avg_time
            # Emit status before each digit so clients see steady progress.
            status = TaskStatus(
                state=TaskState.RUNNING,
                progress=TaskProgress(current=done, total=total, percentage=progress),
                metrics={
                    "eta_seconds": eta_seconds,
                    "digits_sent": done,
                    "digits_total": total,
                },
            )
            reporter.report_status(status)
            chunks.emit(digit)
            # Delay after emitting so the stream stays responsive on connect.
            time.sleep(sleep_time)

    # Final result is stored once, after streaming completes.
    reporter.report_result({"task_id": self.request.id, "data": pi})
    return {"result": pi}

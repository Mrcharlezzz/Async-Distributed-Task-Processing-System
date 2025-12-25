from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TaskReporter:
    """Mirror task state updates to Celery."""

    def __init__(self, celery_task: Any) -> None:
        self._task = celery_task

    def report_progress(self, progress: float, started_at: datetime) -> None:
        meta = {
            "progress": progress,
            "message": None,
            "result": None,
            "started_at": started_at.isoformat(),
        }
        self._task.update_state(state="PROGRESS", meta=meta)

    def report_completed(self, result: Any, started_at: datetime) -> dict:
        finished_at = datetime.now(timezone.utc)
        return {
            "progress": 1.0,
            "message": None,
            "result": result,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }

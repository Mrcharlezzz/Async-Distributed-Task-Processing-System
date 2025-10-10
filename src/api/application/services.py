import inject

from src.api.domain.models import StatusDTO
from src.api.domain.repositories import TaskManagerRepository


class ProgressService:
    """Provides access to progress data for background tasks."""

    def __init__(self):
        self._task_manager: TaskManagerRepository = inject.instance(TaskManagerRepository)

    def get_progress(self, task_name: str) -> StatusDTO:
        """Return the current status for the task identified by ``task_name``."""
        status = self._task_manager.get_status(task_name)
        return status

class TaskService:
    """Handles submission of asynchronous tasks to the Celery broker."""

    def __init__(self):
        self._task_manager: TaskManagerRepository = inject.instance(TaskManagerRepository)

    def push_task(self, task_name, payload: dict) -> str:
        """Enqueue a task with the provided payload and return its task id."""
        task_id = self._task_manager.enqueue(task_name, payload)
        return task_id

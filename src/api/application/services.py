import inject
from datetime import datetime
from src.api.domain.models import (
    Task,
    TaskMetadata,
    TaskPayload,
    TaskProgress,
    TaskState,
    TaskStatus,
)
from src.api.domain.repositories import TaskManagerRepository
from src.api.domain.task_registry import TaskRegistry


class ProgressService:
    """Provides access to progress data for background tasks."""

    def __init__(self):
        self._task_manager: TaskManagerRepository = inject.instance(TaskManagerRepository)

    async def get_progress(self, task_name: str) -> TaskStatus:
        """Return the current status for the task identified by ``task_name``."""
        status = await self._task_manager.get_status(task_name)
        return status

class TaskService:
    """Handles submission of asynchronous tasks to the Celery broker."""

    def __init__(self):
        self._task_manager: TaskManagerRepository = inject.instance(TaskManagerRepository)
        self._registry = TaskRegistry()

    async def push_task(self, task_name, payload: dict) -> str:
        """Enqueue a task with the provided payload and return its task id."""
        task_id = await self._task_manager.enqueue(task_name, payload, queue=None)
        return task_id

    async def create_task(self, payload: TaskPayload) -> Task:
        """
        Create a typed task and enqueue it via the task manager.
        """
        route = self._registry.route_for_payload(payload)

        # Prepare message for the worker
        message = {
            "task_type": route.task_type,
            "payload": payload.model_dump(),
        }

        celery_id = await self._task_manager.enqueue(
            route.celery_task,
            payload=message,
            queue=route.queue,
        )

        task = Task(
            id=celery_id,
            task_type=route.task_type,
            payload=payload,
            status=TaskStatus(state=TaskState.QUEUED, progress=TaskProgress()),
            metadata=TaskMetadata(created_at=datetime.utcnow()),
        )
        return task

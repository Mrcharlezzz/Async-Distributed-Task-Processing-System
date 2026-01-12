from datetime import UTC, datetime

import inject

from src.app.domain.models import (
    Task,
    TaskMetadata,
    TaskPayload,
    TaskProgress,
    TaskResult,
    TaskState,
    TaskStatus,
    TaskType,
)
from src.app.domain.repositories import StorageRepository, TaskManagerRepository


class TaskService:
    """Handles submission of asynchronous tasks to the Celery broker."""

    def __init__(self):
        self._task_manager: TaskManagerRepository = inject.instance(TaskManagerRepository)
        self._storage: StorageRepository = inject.instance(StorageRepository)

    async def push_task(
        self, task_type: TaskType, payload: TaskPayload, user_id: str = "anonymous"
    ) -> str:
        """Enqueue a task with the provided payload and return its task id."""
        task = await self.create_task(task_type, payload, user_id=user_id)
        return task.id

    async def create_task(
        self, task_type: TaskType, payload: TaskPayload, user_id: str = "anonymous"
    ) -> Task:
        """
        Create a typed task and enqueue it via the task manager.
        """
        task = Task(
            task_type=task_type,
            payload=payload,
            status=TaskStatus(state=TaskState.QUEUED, progress=TaskProgress()),
            metadata=TaskMetadata(created_at=datetime.now(UTC)),
        )
        task.id = await self._storage.create_task(user_id, task)
        try:
            task.id = await self._task_manager.enqueue(task)
        except Exception as exc:
            await self._storage.update_task_status(
                task.id,
                TaskStatus(state=TaskState.FAILED, progress=TaskProgress(), message=str(exc)),
                metadata=TaskMetadata(updated_at=datetime.now(UTC)),
            )
            raise
        return task

    async def get_status(self, task_id: str, user_id: str = "anonymous") -> TaskStatus:
        """Return the current status for the task identified by ``task_id``."""
        return await self._storage.get_status(user_id, task_id)

    async def get_result(self, task_id: str, user_id: str = "anonymous") -> TaskResult:
        """Return the current result payload for the task identified by ``task_id``."""
        return await self._storage.get_result(user_id, task_id)

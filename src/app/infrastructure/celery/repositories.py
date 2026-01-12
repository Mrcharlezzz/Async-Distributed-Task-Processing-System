from __future__ import annotations

import asyncio

from celery.result import AsyncResult

from src.app.domain.models.task import Task
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.repositories import TaskManagerRepository
from src.app.infrastructure.celery.app import celery_app
from src.app.infrastructure.celery.mappers import OrmMapper
from src.app.infrastructure.celery.task_registry import TaskRegistry


class CeleryTaskManager(TaskManagerRepository):
    """
    Orchestrates task queue operations such as enqueuing tasks and retrieving their status.
    """

    def __init__(self, celery_app_instance=celery_app):
        self._celery_app = celery_app_instance
        self._registry = TaskRegistry()

    async def enqueue(self, task: Task) -> str:
        """
        Enqueue a task and return the task id.
        """
        if task.id is None:
            raise ValueError("Task id is required to enqueue a task.")
        route = self._registry.route_for_task_type(task.task_type)
        message = {
            "task_type": task.task_type.value,
            "payload": task.payload.model_dump(),
        }
        async_result = await asyncio.to_thread(
            self._celery_app.send_task,
            route.celery_task,
            args=[message],
            queue=route.queue,
            task_id=task.id,
        )
        return async_result.id

    async def get_status(self, task_id: str) -> TaskStatus:
        """
        Retrieve the current status for a task.
        """
        result = await asyncio.to_thread(AsyncResult, task_id, app=self._celery_app)
        return await asyncio.to_thread(OrmMapper.to_status, result)

    async def get_result(self, task_id: str) -> TaskResult:
        """
        Retrieve the current result payload for a task.
        """
        async_result = await asyncio.to_thread(AsyncResult, task_id, app=self._celery_app)
        return await asyncio.to_thread(OrmMapper.to_result, async_result)

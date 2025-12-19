from __future__ import annotations

from typing import Protocol

from src.api.domain.models.task_status import TaskStatus


class TaskManagerRepository(Protocol):
    """Repository contract for enqueueing tasks and retrieving their status."""

    async def enqueue(self, task_name: str, payload: dict, queue: str | None = None) -> str:
        """Schedule a task with the given payload (and optional queue) and return its identifier."""

    async def get_status(self, task_id: str) -> TaskStatus:
        """Fetch the current status representation for the task identified by ``task_id``."""

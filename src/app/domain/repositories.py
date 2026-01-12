from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from src.app.domain.events.task_event import TaskEvent
from src.app.domain.models.task import Task
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_type import TaskType
from src.app.domain.models.task_view import TaskView


class TaskManagerRepository(Protocol):
    """Repository contract for enqueueing tasks and retrieving their status."""

    async def enqueue(self, task: Task) -> str:
        """Schedule a task and return its identifier."""

    async def get_status(self, task_id: str) -> TaskStatus:
        """Fetch the current status representation for the task identified by ``task_id``."""


class StorageRepository(Protocol):
    """Repository contract for task persistence and access control."""

    async def create_task(
        self,
        user_id: str,
        task: Task,
    ) -> str:
        """Persist a new task owned by ``user_id`` and return its id."""

    async def get_task(self, user_id: str, task_id: str) -> Task | None:
        """Return the task if owned by ``user_id``; otherwise ``None``."""

    async def get_status(self, user_id: str, task_id: str) -> TaskStatus:
        """Return the status for a task owned by ``user_id``."""

    async def get_result(self, user_id: str, task_id: str) -> TaskResult:
        """Return the result payload for a task owned by ``user_id``."""

    async def list_tasks(
        self,
        user_id: str,
        *,
        task_type: TaskType | None = None,
        state: TaskState | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskView]:
        """List tasks owned by ``user_id`` with optional filters."""

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        metadata: TaskMetadata | None = None,
    ) -> None:
        """Persist status changes and optional metadata updates."""

    async def set_task_result(
        self,
        task_id: str,
        result: TaskResult,
        finished_at: datetime | None = None,
    ) -> None:
        """Persist the task result payload and finalization timestamp."""


class TaskEventPublisherRepository(Protocol):
    """Repository contract for publishing task events to a stream."""

    def publish(self, events: TaskEvent | Sequence[TaskEvent]) -> None:
        """Publish task event(s) to the stream."""

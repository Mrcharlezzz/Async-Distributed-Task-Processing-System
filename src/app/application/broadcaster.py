from __future__ import annotations

from typing import Protocol

from src.app.domain.events.task_event import TaskEvent


class TaskStatusBroadcaster(Protocol):
    """Interface for broadcasting task events to presentation clients."""
    async def broadcast_status(self, event: TaskEvent) -> None:
        """Broadcast a task status event to connected clients."""

    async def broadcast_result_chunk(self, event: TaskEvent) -> None:
        """Broadcast a task result chunk event to connected clients."""

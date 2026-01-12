from __future__ import annotations

import base64
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from src.app.domain.models.task_status import TaskStatus


class EventType(str, Enum):
    """Event types emitted over the task event stream."""
    TASK_STATUS = "task.status"
    TASK_RESULT_CHUNK = "task.result_chunk"
    TASK_RESULT = "task.result"


class TaskEvent(BaseModel):
    """Envelope for task events transported over Redis Streams."""
    event_id: str
    type: EventType
    task_id: str
    ts: datetime
    version: int = 1
    payload: dict[str, Any]

    @classmethod
    def status(cls, task_id: str, status_snapshot: TaskStatus) -> TaskEvent:
        """Create a status event from a TaskStatus snapshot."""
        return cls(
            event_id=str(uuid4()),
            type=EventType.TASK_STATUS,
            task_id=task_id,
            ts=datetime.now(tz=UTC),
            payload={"status": status_snapshot.model_dump(mode="json")},
        )

    @classmethod
    def result_chunk(
        cls,
        task_id: str,
        chunk_id: str,
        data: Any,
        is_last: bool = False,
    ) -> TaskEvent:
        """Create a chunk event for incremental result streaming."""
        safe_data = data
        if isinstance(data, (bytes, bytearray, memoryview)):
            safe_data = base64.b64encode(bytes(data)).decode("ascii")
        return cls(
            event_id=str(uuid4()),
            type=EventType.TASK_RESULT_CHUNK,
            task_id=task_id,
            ts=datetime.now(tz=UTC),
            payload={"chunk_id": chunk_id, "data": safe_data, "is_last": is_last},
        )

    @classmethod
    def result(cls, task_id: str, result_snapshot: dict[str, Any]) -> TaskEvent:
        """Create a final result event."""
        return cls(
            event_id=str(uuid4()),
            type=EventType.TASK_RESULT,
            task_id=task_id,
            ts=datetime.now(tz=UTC),
            payload={"result": result_snapshot},
        )

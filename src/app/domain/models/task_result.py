from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.app.domain.models.task_metadata import TaskMetadata


class TaskResult(BaseModel):
    """Result payload for a completed task."""
    task_id: str = Field(description="Identifier of the task.")
    task_metadata: TaskMetadata | None = Field(
        default=None, description="Lifecycle metadata for the task."
    )
    data: Any | None = Field(default=None, description="Result payload.")
    expires_at: datetime | None = Field(
        default=None, description="When the result expires."
    )
    ttl_seconds: int | None = Field(
        default=None, description="Time-to-live in seconds."
    )

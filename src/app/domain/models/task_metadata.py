from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskMetadata(BaseModel):
    """Timestamps and optional custom metadata for a task."""
    """Common metadata about a task lifecycle."""

    created_at: datetime | None = Field(
        default=None, description="Timestamp when the task was created."
    )
    updated_at: datetime | None = Field(
        default=None, description="Timestamp when the task metadata was last updated."
    )
    started_at: datetime | None = Field(
        default=None, description="Timestamp when the task started running."
    )
    finished_at: datetime | None = Field(
        default=None, description="Timestamp when the task finished."
    )
    custom: dict[str, Any] | None = Field(
        default=None, description="Task-specific metadata."
    )

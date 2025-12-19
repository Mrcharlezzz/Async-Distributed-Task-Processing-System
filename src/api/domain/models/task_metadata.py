from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskMetadata(BaseModel):
    """Common metadata about a task lifecycle."""

    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    custom: dict[str, Any] | None = Field(
        default=None, description="Task-specific metadata."
    )

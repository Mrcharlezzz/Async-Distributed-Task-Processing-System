from datetime import datetime

from pydantic import BaseModel


class ExecutionConfig(BaseModel):
    """Execution-related configuration attached to a task."""

    time_limit_seconds: int | None = None
    soft_time_limit_seconds: int | None = None
    expires_at: datetime | None = None
    priority: int | None = None
    retry_limit: int | None = None
    eta: datetime | None = None

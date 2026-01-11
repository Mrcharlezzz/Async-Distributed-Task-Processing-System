from datetime import datetime

from pydantic import BaseModel, Field


class ExecutionConfig(BaseModel):
    """Optional execution overrides for a task."""
    """Execution-related configuration attached to a task."""

    time_limit_seconds: int | None = Field(
        default=None, description="Hard time limit in seconds."
    )
    soft_time_limit_seconds: int | None = Field(
        default=None, description="Soft time limit in seconds."
    )
    expires_at: datetime | None = Field(
        default=None, description="Absolute expiration time for the task."
    )
    priority: int | None = Field(
        default=None, description="Execution priority."
    )
    retry_limit: int | None = Field(
        default=None, description="Maximum number of retry attempts."
    )
    eta: datetime | None = Field(
        default=None, description="Estimated time of arrival for scheduling."
    )

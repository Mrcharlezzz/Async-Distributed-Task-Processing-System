from pydantic import BaseModel, Field


class TaskProgress(BaseModel):
    """Progress snapshot for a running task."""
    current: int | None = Field(default=None, description="Units completed so far.")
    total: int | None = Field(default=None, description="Total units expected.")
    percentage: float | None = Field(
        default=None, description="Completion ratio from 0 to 1."
    )
    phase: str | None = Field(
        default=None, description="Human-readable phase or step label."
    )

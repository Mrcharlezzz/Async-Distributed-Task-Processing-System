from pydantic import BaseModel, Field, SerializeAsAny

from src.app.domain.models.execution_config import ExecutionConfig
from src.app.domain.models.payloads import TaskPayload
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_type import TaskType


class Task(BaseModel):
    """Aggregate domain model for a task."""
    id: str | None = Field(default=None, description="Unique task identifier.")
    task_type: TaskType = Field(description="Type of task being executed.")
    payload: SerializeAsAny[TaskPayload] = Field(
        description="Task-specific payload data."
    )
    result: dict | None = Field(
        default=None, description="Raw result payload, if available."
    )
    status: TaskStatus = Field(description="Current status information.")
    metadata: TaskMetadata = Field(description="Lifecycle metadata for the task.")
    execution: ExecutionConfig | None = Field(
        default=None, description="Execution configuration overrides."
    )

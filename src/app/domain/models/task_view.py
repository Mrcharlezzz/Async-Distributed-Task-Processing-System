from pydantic import BaseModel, Field

from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_type import TaskType


class TaskView(BaseModel):
    """Read-only projection of task information for list views."""
    """Compact representation used for task listing screens."""

    id: str = Field(description="Unique task identifier.")
    task_type: TaskType = Field(description="Type of task being executed.")
    status: TaskStatus = Field(description="Current status information.")
    metadata: TaskMetadata = Field(description="Lifecycle metadata for the task.")

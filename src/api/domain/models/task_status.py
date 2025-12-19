from pydantic import BaseModel

from src.api.domain.models.task_progress import TaskProgress
from src.api.domain.models.task_state import TaskState


class TaskStatus(BaseModel):
    state: TaskState
    progress: TaskProgress
    message: str | None = None

from src.api.application.dtos import StatusDTO  # Backward compatibility
from src.api.domain.models.execution_config import ExecutionConfig
from src.api.domain.models.payloads import DocumentAnalysisPayload, TaskPayload
from src.api.domain.models.task import Task
from src.api.domain.models.task_metadata import TaskMetadata
from src.api.domain.models.task_progress import TaskProgress
from src.api.domain.models.task_state import TaskState
from src.api.domain.models.task_status import TaskStatus

__all__ = [
    "Task",
    "TaskStatus",
    "TaskProgress",
    "TaskState",
    "TaskPayload",
    "DocumentAnalysisPayload",
    "ExecutionConfig",
    "TaskMetadata",
    "StatusDTO",
]

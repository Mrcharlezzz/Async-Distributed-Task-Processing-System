from dataclasses import dataclass

from src.app.domain.models.task_type import TaskType


@dataclass(frozen=True)
class TaskRoute:
    task_type: TaskType
    celery_task: str
    queue: str | None = None


class TaskRegistry:
    """Registry mapping task types to Celery routing info."""

    def __init__(self) -> None:
        self._registry: dict[TaskType, TaskRoute] = {
            TaskType.COMPUTE_PI: TaskRoute(
                task_type=TaskType.COMPUTE_PI,
                celery_task="compute_pi",
                queue=None,
            ),
            TaskType.DOCUMENT_ANALYSIS: TaskRoute(
                task_type=TaskType.DOCUMENT_ANALYSIS,
                celery_task="document_analysis",
                queue="doc-tasks",
            ),
        }

    def route_for_task_type(self, task_type: TaskType) -> TaskRoute:
        """Return routing info for a task type."""
        try:
            return self._registry[task_type]
        except KeyError as exc:
            raise ValueError(f"No task route registered for task type {task_type!r}") from exc

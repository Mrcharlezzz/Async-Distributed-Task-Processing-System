from dataclasses import dataclass
from typing import Type

from src.api.domain.models.payloads import DocumentAnalysisPayload, TaskPayload


@dataclass(frozen=True)
class TaskRoute:
    task_type: str
    celery_task: str
    queue: str | None = None


class TaskRegistry:
    """Registry mapping payload types to Celery routing info."""

    def __init__(self) -> None:
        self._registry: dict[Type[TaskPayload], TaskRoute] = {
            DocumentAnalysisPayload: TaskRoute(
                task_type="document_analysis",
                celery_task="document_analysis",
                queue="doc-tasks",
            ),
        }

    def route_for_payload(self, payload: TaskPayload) -> TaskRoute:
        for cls, route in self._registry.items():
            if isinstance(payload, cls):
                return route
        raise ValueError(f"No task route registered for payload type {type(payload)!r}")

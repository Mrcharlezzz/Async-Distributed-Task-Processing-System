from celery.result import AsyncResult

from src.api.domain.exceptions import TaskNotFoundError
from src.api.domain.models.task_progress import TaskProgress
from src.api.domain.models.task_state import TaskState
from src.api.domain.models.task_status import TaskStatus


class CeleryMapper:
    @staticmethod
    def map_meta(async_result: AsyncResult) -> dict:
        info = async_result.info
        if isinstance(info, dict):
            return info
        if isinstance(async_result.result, dict):
            return async_result.result
        return {}

    @staticmethod
    def map_state(async_result: AsyncResult) -> TaskState:
        if async_result.state == "PENDING":
            raise TaskNotFoundError(async_result.id)
        if async_result.failed():
            return TaskState.FAILED
        if async_result.successful():
            return TaskState.COMPLETED
        if async_result.state == "REVOKED":
            return TaskState.CANCELLED
        if async_result.state in {"STARTED", "PROGRESS"}:
            return TaskState.RUNNING
        return TaskState.RUNNING

    @staticmethod
    def map_message(info: object) -> str | None:
        if isinstance(info, dict):
            return info.get("message")
        if info is None:
            return None
        return str(info)

    @staticmethod
    def map_status(async_result: AsyncResult) -> TaskStatus:
        info = async_result.info
        meta = CeleryMapper.map_meta(async_result)

        progress_value = meta.get("progress")
        progress = (
            TaskProgress(percentage=progress_value)
            if progress_value is not None
            else TaskProgress()
        )

        return TaskStatus(
            state=CeleryMapper.map_state(async_result),
            progress=progress,
            message=CeleryMapper.map_message(info),
        )

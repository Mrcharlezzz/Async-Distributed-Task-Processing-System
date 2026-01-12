from celery.result import AsyncResult

from src.app.domain.exceptions import TaskNotFoundError
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus


class OrmMapper:
    """Convert Celery AsyncResult objects into domain models."""
    @staticmethod
    def to_meta(async_result: AsyncResult) -> dict:
        """Extract a metadata dict from a Celery result payload."""
        info = async_result.info
        if isinstance(info, dict):
            return info
        if isinstance(async_result.result, dict):
            return async_result.result
        return {}

    @staticmethod
    def to_state(async_result: AsyncResult) -> TaskState:
        """Translate Celery state into the domain task state."""
        if async_result.state == "PENDING":
            raise TaskNotFoundError(async_result.id)
        if async_result.state == "SENT":
            return TaskState.QUEUED
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
    def to_message(info: object) -> str | None:
        """Normalize a status message from Celery info."""
        if isinstance(info, dict):
            return info.get("message")
        if info is None:
            return None
        return str(info)

    @staticmethod
    def to_status(async_result: AsyncResult) -> TaskStatus:
        """Build a TaskStatus from a Celery AsyncResult."""
        info = async_result.info
        meta = OrmMapper.to_meta(async_result)

        progress_value = meta.get("progress")
        progress = (
            TaskProgress(percentage=progress_value)
            if progress_value is not None
            else TaskProgress()
        )

        return TaskStatus(
            state=OrmMapper.to_state(async_result),
            progress=progress,
            message=OrmMapper.to_message(info),
        )

    @staticmethod
    def to_result(async_result: AsyncResult) -> TaskResult:
        """Build a TaskResult from a Celery AsyncResult."""
        if async_result.state == "PENDING":
            raise TaskNotFoundError(async_result.id)

        meta = OrmMapper.to_meta(async_result)
        result_payload = async_result.result if async_result.result is not None else meta or None

        created_at = meta.get("created_at") if isinstance(meta, dict) else None
        started_at = meta.get("started_at") if isinstance(meta, dict) else None
        finished_at = (
            meta.get("finished_at") if isinstance(meta, dict) else async_result.date_done
        )
        if finished_at is None:
            finished_at = async_result.date_done

        task_metadata = TaskMetadata(
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            custom=meta.get("custom") if isinstance(meta, dict) else None,
        )

        return TaskResult(
            task_id=async_result.id,
            task_metadata=task_metadata,
            data=result_payload,
        )

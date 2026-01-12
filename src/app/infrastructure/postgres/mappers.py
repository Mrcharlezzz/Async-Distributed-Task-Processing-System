from __future__ import annotations

from src.app.domain.models.payloads import (
    ComputePiPayload,
    DocumentAnalysisPayload,
    TaskPayload,
)
from src.app.domain.models.task import Task
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_type import TaskType
from src.app.domain.models.task_view import TaskView
from src.app.infrastructure.postgres.orm import (
    TaskMetadataRow,
    TaskPayloadRow,
    TaskResultRow,
    TaskRow,
    TaskStatusRow,
)


class OrmMapper:
    """Map between ORM rows and domain models."""
    @staticmethod
    def to_task_row(user_id: str, task: Task) -> TaskRow:
        """Create a TaskRow from a domain task."""
        if task.id is None:
            raise ValueError("Task id is required to persist TaskRow.")
        return TaskRow(
            id=task.id,
            user_id=user_id,
            task_type=task.task_type,
        )

    @staticmethod
    def to_payload_row(task_id: str, payload: TaskPayload) -> TaskPayloadRow:
        """Create a payload row from a task payload."""
        return TaskPayloadRow(
            task_id=task_id,
            payload=payload.model_dump(),
        )

    @staticmethod
    def to_metadata_row(task_id: str, metadata: TaskMetadata) -> TaskMetadataRow:
        """Create a metadata row from task metadata."""
        return TaskMetadataRow(
            task_id=task_id,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            started_at=metadata.started_at,
            finished_at=metadata.finished_at,
            custom=metadata.custom,
        )

    @staticmethod
    def to_status_row(task_id: str, status: TaskStatus) -> TaskStatusRow:
        """Create a status row from task status."""
        progress = status.progress
        return TaskStatusRow(
            task_id=task_id,
            state=status.state,
            progress_current=progress.current,
            progress_total=progress.total,
            progress_percentage=progress.percentage,
            progress_phase=progress.phase,
            message=status.message,
            metrics=status.metrics,
        )

    @staticmethod
    def to_result_row(task_id: str, result: TaskResult) -> TaskResultRow:
        """Create a result row from task result."""
        return TaskResultRow(
            task_id=task_id,
            data=result.data,
            finished_at=result.task_metadata.finished_at if result.task_metadata else None,
            expires_at=result.expires_at,
            ttl_seconds=result.ttl_seconds,
        )

    @staticmethod
    def to_domain_task(row: TaskRow) -> Task:
        """Create a domain Task from ORM rows."""
        payload_data = row.payload.payload if row.payload else {}
        payload = OrmMapper._payload_from_row(row.task_type, payload_data)
        status = OrmMapper.to_domain_status(row)
        metadata = OrmMapper.to_domain_metadata(row)
        result_payload = row.result.data if row.result else None

        return Task(
            id=row.id,
            task_type=row.task_type,
            payload=payload,
            result=result_payload,
            status=status,
            metadata=metadata,
        )

    @staticmethod
    def to_domain_metadata(row: TaskRow) -> TaskMetadata:
        """Create TaskMetadata from ORM rows."""
        if row.task_metadata is None:
            return TaskMetadata()
        return TaskMetadata(
            created_at=row.task_metadata.created_at,
            updated_at=row.task_metadata.updated_at,
            started_at=row.task_metadata.started_at,
            finished_at=row.task_metadata.finished_at,
            custom=row.task_metadata.custom,
        )

    @staticmethod
    def to_domain_status(row: TaskRow) -> TaskStatus:
        """Create TaskStatus from ORM rows."""
        if row.status is None:
            return TaskStatus(state=TaskState.QUEUED, progress=TaskProgress())
        progress = TaskProgress(
            current=row.status.progress_current,
            total=row.status.progress_total,
            percentage=row.status.progress_percentage,
            phase=row.status.progress_phase,
        )
        return TaskStatus(
            state=row.status.state,
            progress=progress,
            message=row.status.message,
            metrics=row.status.metrics,
        )

    @staticmethod
    def to_task_view(row: TaskRow) -> TaskView:
        """Create a TaskView from ORM rows."""
        return TaskView(
            id=row.id,
            task_type=row.task_type,
            status=OrmMapper.to_domain_status(row),
            metadata=OrmMapper.to_domain_metadata(row),
        )

    @staticmethod
    def to_domain_result(row: TaskRow) -> TaskResult:
        """Create TaskResult from ORM rows."""
        result_row = row.result
        return TaskResult(
            task_id=row.id,
            task_metadata=OrmMapper.to_domain_metadata(row),
            data=result_row.data if result_row else None,
            expires_at=result_row.expires_at if result_row else None,
            ttl_seconds=result_row.ttl_seconds if result_row else None,
        )

    @staticmethod
    def _payload_from_row(task_type: TaskType, payload: dict) -> TaskPayload:
        """Cast payload dict into the correct payload type."""
        if task_type == TaskType.COMPUTE_PI:
            return ComputePiPayload(**payload)
        if task_type == TaskType.DOCUMENT_ANALYSIS:
            return DocumentAnalysisPayload(**payload)
        return TaskPayload(**payload)

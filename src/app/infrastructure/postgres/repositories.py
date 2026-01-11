from __future__ import annotations

from datetime import datetime

from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import selectinload


from src.app.domain.models.task import Task
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_type import TaskType
from src.app.domain.exceptions import TaskAccessDeniedError, TaskNotFoundError
from src.app.domain.repositories import StorageRepository
from src.app.domain.models.task_view import TaskView
from src.app.infrastructure.postgres.orm import (
    PostgresOrm,
    TaskMetadataRow,
    TaskResultRow,
    TaskRow,
    TaskStatusRow,
)
from src.app.infrastructure.postgres.mappers import OrmMapper


class PostgresStorageRepository(StorageRepository):
    """Postgres-backed task storage using SQLAlchemy async sessions."""

    def __init__(self, orm: PostgresOrm) -> None:
        self._orm = orm

    async def create_task(self, user_id: str, task: Task) -> str:
        """Persist a new task and return its id."""
        if task.id is None:
            task.id = uuid4().hex

        task_row = OrmMapper.to_task_row(user_id, task)
        task_row.payload = OrmMapper.to_payload_row(task.id, task.payload)
        task_row.task_metadata = OrmMapper.to_metadata_row(task.id, task.metadata)
        task_row.status = OrmMapper.to_status_row(task.id, task.status)

        async with self._orm.session_factory() as session:
            async with session.begin():
                # One transaction ensures FK rows are created together.
                session.add(task_row)
        return task.id

    async def get_task(self, user_id: str, task_id: str) -> Task | None:
        """Fetch a task by id and enforce ownership."""
        async with self._orm.session_factory() as session:
            result = await session.execute(
                select(TaskRow)
                .options(
                    selectinload(TaskRow.payload),
                    selectinload(TaskRow.task_metadata),
                    selectinload(TaskRow.status),
                    selectinload(TaskRow.result),
                )
                .where(TaskRow.id == task_id)
            )
            task_row = result.scalar_one_or_none()

        if task_row is None:
            raise TaskNotFoundError(task_id)
        if task_row.user_id != user_id:
            raise TaskAccessDeniedError(task_id, user_id)
        return OrmMapper.to_domain_task(task_row)

    async def get_status(self, user_id: str, task_id: str) -> TaskStatus:
        """Fetch task status by id."""
        task = await self.get_task(user_id, task_id)
        return task.status

    async def get_result(self, user_id: str, task_id: str) -> TaskResult:
        """Fetch task result by id."""
        async with self._orm.session_factory() as session:
            result = await session.execute(
                select(TaskRow)
                .options(selectinload(TaskRow.task_metadata), selectinload(TaskRow.result))
                .where(TaskRow.id == task_id)
            )
            task_row = result.scalar_one_or_none()

        if task_row is None:
            raise TaskNotFoundError(task_id)
        if task_row.user_id != user_id:
            raise TaskAccessDeniedError(task_id, user_id)
        return OrmMapper.to_domain_result(task_row)

    async def list_tasks(
        self,
        user_id: str,
        *,
        task_type: TaskType | None = None,
        state: TaskState | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskView]:
        """List tasks for a user with optional filters."""
        statement = (
            select(TaskRow)
            .options(selectinload(TaskRow.task_metadata), selectinload(TaskRow.status))
            .where(TaskRow.user_id == user_id)
        )
        if task_type is not None:
            statement = statement.where(TaskRow.task_type == task_type)
        if state is not None:
            statement = statement.join(TaskRow.status).where(TaskStatusRow.state == state)

        statement = statement.order_by(TaskRow.id).limit(limit).offset(offset)

        async with self._orm.session_factory() as session:
            result = await session.execute(statement)
            rows = result.scalars().all()

        return [OrmMapper.to_task_view(row) for row in rows]

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        metadata: TaskMetadata | None = None,
    ) -> None:
        """Update task status and optional metadata."""
        async with self._orm.session_factory() as session:
            async with session.begin():
                # Ensure the task exists before mutating status/metadata.
                task_row = await session.get(TaskRow, task_id)
                if task_row is None:
                    raise TaskNotFoundError(task_id)

                status_row = OrmMapper.to_status_row(task_id, status)
                await session.merge(status_row)

                if metadata is not None:
                    metadata_row = await session.get(TaskMetadataRow, task_id)
                    if metadata_row is None:
                        metadata_row = OrmMapper.to_metadata_row(task_id, metadata)
                        session.add(metadata_row)
                    else:
                        self._merge_metadata(metadata_row, metadata)

    async def set_task_result(
        self,
        task_id: str,
        result: TaskResult,
        finished_at: datetime | None = None,
    ) -> None:
        """Persist the task result and finished timestamp."""
        async with self._orm.session_factory() as session:
            async with session.begin():
                # Enforce task existence; results are keyed to the task id.
                task_row = await session.get(TaskRow, task_id)
                if task_row is None:
                    raise TaskNotFoundError(task_id)

                result_row = OrmMapper.to_result_row(task_id, result)
                if finished_at is not None:
                    result_row.finished_at = finished_at
                await session.merge(result_row)

                if finished_at is not None:
                    metadata_row = await session.get(TaskMetadataRow, task_id)
                    if metadata_row is None:
                        metadata_row = OrmMapper.to_metadata_row(
                            task_id,
                            TaskMetadata(finished_at=finished_at),
                        )
                        session.add(metadata_row)
                    else:
                        self._merge_metadata(metadata_row, TaskMetadata(finished_at=finished_at))

    @staticmethod
    def _merge_metadata(target: TaskMetadataRow, updates: TaskMetadata) -> None:
        for field in ("created_at", "updated_at", "started_at", "finished_at", "custom"):
            value = getattr(updates, field)
            if value is not None:
                setattr(target, field, value)

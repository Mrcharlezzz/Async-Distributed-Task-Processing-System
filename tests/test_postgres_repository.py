from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from src.app.domain.exceptions import TaskAccessDeniedError
from src.app.domain.models.payloads import ComputePiPayload
from src.app.domain.models.task import Task
from src.app.domain.models.task_metadata import TaskMetadata
from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_result import TaskResult
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.models.task_type import TaskType
from src.app.infrastructure.postgres.orm import Base, PostgresOrm
from src.app.infrastructure.postgres.repositories import PostgresStorageRepository


@pytest_asyncio.fixture
async def repo(tmp_path):
    db_path = tmp_path / "test.db"
    orm = PostgresOrm(f"sqlite+aiosqlite:///{db_path}")
    async with orm.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repository = PostgresStorageRepository(orm)
    yield repository
    await orm.engine.dispose()


@pytest.mark.asyncio
async def test_get_status_returns_latest(repo: PostgresStorageRepository):
    task = Task(
        task_type=TaskType.COMPUTE_PI,
        payload=ComputePiPayload(digits=5),
        status=TaskStatus(state=TaskState.QUEUED, progress=TaskProgress()),
        metadata=TaskMetadata(created_at=datetime.now(timezone.utc)),
    )
    task_id = await repo.create_task("user-1", task)

    status = TaskStatus(
        state=TaskState.RUNNING,
        progress=TaskProgress(percentage=0.5),
        message=None,
    )
    await repo.update_task_status(task_id, status, TaskMetadata(updated_at=datetime.now(timezone.utc)))

    returned = await repo.get_status("user-1", task_id)
    assert returned.state == TaskState.RUNNING
    assert returned.progress.percentage == 0.5


@pytest.mark.asyncio
async def test_get_result_returns_persisted_result(repo: PostgresStorageRepository):
    task = Task(
        task_type=TaskType.COMPUTE_PI,
        payload=ComputePiPayload(digits=3),
        status=TaskStatus(state=TaskState.QUEUED, progress=TaskProgress()),
        metadata=TaskMetadata(created_at=datetime.now(timezone.utc)),
    )
    task_id = await repo.create_task("user-1", task)

    finished_at = datetime.now(timezone.utc)
    result = TaskResult(task_id=task_id, data={"pi": "3.141"}, task_metadata=TaskMetadata())
    await repo.set_task_result(task_id, result, finished_at=finished_at)

    returned = await repo.get_result("user-1", task_id)
    assert returned.data == {"pi": "3.141"}
    assert returned.task_metadata.finished_at == finished_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_status_enforces_acl(repo: PostgresStorageRepository):
    task = Task(
        task_type=TaskType.COMPUTE_PI,
        payload=ComputePiPayload(digits=2),
        status=TaskStatus(state=TaskState.QUEUED, progress=TaskProgress()),
        metadata=TaskMetadata(created_at=datetime.now(timezone.utc)),
    )
    task_id = await repo.create_task("owner", task)

    with pytest.raises(TaskAccessDeniedError):
        await repo.get_status("other-user", task_id)

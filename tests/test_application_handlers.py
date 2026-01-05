import pytest

from src.app.application.broadcaster import TaskStatusBroadcaster
from src.app.application.handlers import TaskEventHandler
from src.app.domain.events.task_event import TaskEvent
from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.repositories import StorageRepository


class StubStorage(StorageRepository):
    def __init__(self) -> None:
        self.status_calls: list[tuple[str, TaskStatus]] = []
        self.result_calls: list[tuple[str, object]] = []

    async def create_task(self, user_id: str, task):  # pragma: no cover - not used
        raise NotImplementedError

    async def get_task(self, user_id: str, task_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    async def get_status(self, user_id: str, task_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    async def get_result(self, user_id: str, task_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    async def list_tasks(self, user_id: str, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError

    async def update_task_status(self, task_id: str, status: TaskStatus, metadata=None) -> None:
        self.status_calls.append((task_id, status))

    async def set_task_result(self, task_id: str, result, finished_at=None) -> None:
        self.result_calls.append((task_id, result))


class StubBroadcaster(TaskStatusBroadcaster):
    def __init__(self) -> None:
        self.status_events: list[TaskEvent] = []
        self.chunk_events: list[TaskEvent] = []

    async def broadcast_status(self, event: TaskEvent) -> None:
        self.status_events.append(event)

    async def broadcast_result_chunk(self, event: TaskEvent) -> None:
        self.chunk_events.append(event)


@pytest.mark.asyncio
async def test_handle_status_event_updates_storage() -> None:
    storage = StubStorage()
    broadcaster = StubBroadcaster()
    handler = TaskEventHandler(storage=storage, broadcaster=broadcaster)

    status = TaskStatus(
        state=TaskState.RUNNING,
        progress=TaskProgress(current=1, total=4, percentage=0.25),
        message="working",
    )
    event = TaskEvent.status("task-1", status)

    await handler.handle_status_event(event)

    assert storage.status_calls == [("task-1", status)]
    assert broadcaster.status_events == [event]


@pytest.mark.asyncio
async def test_handle_result_event_updates_storage() -> None:
    storage = StubStorage()
    broadcaster = StubBroadcaster()
    handler = TaskEventHandler(storage=storage, broadcaster=broadcaster)

    payload = {"task_id": "task-2", "data": {"value": 42}}
    event = TaskEvent.result("task-2", payload)

    await handler.handle_result_event(event)

    assert len(storage.result_calls) == 1
    task_id, result = storage.result_calls[0]
    assert task_id == "task-2"
    assert result.task_id == "task-2"
    assert result.data == {"value": 42}


@pytest.mark.asyncio
async def test_handle_result_chunk_event_broadcasts() -> None:
    storage = StubStorage()
    broadcaster = StubBroadcaster()
    handler = TaskEventHandler(storage=storage, broadcaster=broadcaster)

    event = TaskEvent.result_chunk("task-3", "0", {"delta": "hi"}, is_last=False)

    await handler.handle_result_chunk_event(event)

    assert broadcaster.chunk_events == [event]
    assert storage.result_calls == []

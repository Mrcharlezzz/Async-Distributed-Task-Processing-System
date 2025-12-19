from __future__ import annotations

import pytest

from src.api.domain.models.task_progress import TaskProgress
from src.api.domain.models.task_state import TaskState
from src.api.domain.models.task_status import TaskStatus


@pytest.mark.asyncio
async def test_task_service_enqueue_uses_repository(stubbed_services):
    services_module, stub = stubbed_services
    service = services_module.TaskService()

    payload = {"digits": 12}
    task_id = await service.push_task("compute_pi", payload)

    assert task_id == "compute_pi-1"
    assert stub.enqueued == [("compute_pi", payload, None)]


@pytest.mark.asyncio
async def test_progress_service_returns_status_from_repository(stubbed_services):
    services_module, stub = stubbed_services
    status = TaskStatus(
        state=TaskState.COMPLETED,
        progress=TaskProgress(percentage=1.0),
        message=None,
    )
    stub.status_by_id["job-42"] = status

    service = services_module.ProgressService()
    returned = await service.get_progress("job-42")

    assert returned is status

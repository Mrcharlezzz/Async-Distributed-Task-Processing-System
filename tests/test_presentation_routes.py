from __future__ import annotations

from src.api.domain.models.task_progress import TaskProgress
from src.api.domain.models.task_state import TaskState
from src.api.domain.models.task_status import TaskStatus


def test_calculate_pi_rejects_zero(api_client):
    client, _ = api_client

    response = client.post("/calculate_pi", json={"n": 0})

    assert response.status_code == 422


def test_calculate_pi_rejects_values_above_limit(api_client):
    client, _ = api_client

    response = client.post("/calculate_pi", json={"n": 6})

    assert response.status_code == 422


def test_calculate_pi_enqueues_task_with_stub(api_client):
    client, stub = api_client

    response = client.post("/calculate_pi", json={"n": 3})

    assert response.status_code == 200
    assert response.json() == {"task_id": "compute_pi-1"}
    assert stub.enqueued == [("compute_pi", {"digits": 3}, None)]


def test_check_progress_requires_task_id(api_client):
    client, _ = api_client

    response = client.get("/check_progress")

    assert response.status_code == 422


def test_check_progress_returns_status_payload(api_client):
    client, stub = api_client
    status = TaskStatus(
        state=TaskState.RUNNING,
        progress=TaskProgress(percentage=0.5),
        message="working",
    )
    stub.status_by_id["job-1"] = status

    response = client.get("/check_progress", params={"task_id": "job-1"})

    assert response.status_code == 200
    assert response.json() == {
        "state": "RUNNING",
        "progress": {
            "current": None,
            "total": None,
            "percentage": 0.5,
            "phase": None,
        },
        "message": "working",
    }


def test_check_progress_returns_404_for_missing_task(api_client):
    client, _ = api_client

    response = client.get("/check_progress", params={"task_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Task with id 'missing' was not found."

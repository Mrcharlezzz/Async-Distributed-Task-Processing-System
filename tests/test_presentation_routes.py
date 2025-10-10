from __future__ import annotations

from src.api.domain.models import StatusDTO


def test_calculate_pi_rejects_zero(api_client):
    client, _ = api_client

    response = client.get("/calculate_pi", params={"n": 0})

    assert response.status_code == 422


def test_calculate_pi_rejects_values_above_limit(api_client):
    client, _ = api_client

    response = client.get("/calculate_pi", params={"n": 6})

    assert response.status_code == 422


def test_calculate_pi_enqueues_task_with_stub(api_client):
    client, stub = api_client

    response = client.get("/calculate_pi", params={"n": 3})

    assert response.status_code == 200
    assert response.json() == {"task_id": "compute_pi-1"}
    assert stub.enqueued == [("compute_pi", {"digits": 3})]


def test_check_progress_requires_task_id(api_client):
    client, _ = api_client

    response = client.get("/check_progress")

    assert response.status_code == 422


def test_check_progress_returns_status_payload(api_client):
    client, stub = api_client
    status = StatusDTO(
        task_id="job-1",
        state="PROGRESS",
        progress=0.5,
        message="working",
        result=None,
    )
    stub.status_by_id["job-1"] = status

    response = client.get("/check_progress", params={"task_id": "job-1"})

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "job-1",
        "state": "PROGRESS",
        "progress": 0.5,
        "message": "working",
        "result": None,
    }


def test_check_progress_returns_404_for_missing_task(api_client):
    client, _ = api_client

    response = client.get("/check_progress", params={"task_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Task with id 'missing' was not found."

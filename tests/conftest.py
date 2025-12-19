from __future__ import annotations

import importlib
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.domain.exceptions import TaskNotFoundError
from src.api.domain.models.task_status import TaskStatus
from src.api.domain.repositories import TaskManagerRepository


class StubTaskManager(TaskManagerRepository):
    """Simple in-memory TaskManager replacement for tests."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict, str | None]] = []
        self.status_by_id: dict[str, TaskStatus] = {}

    async def enqueue(self, task_name: str, payload: dict, queue: str | None = None) -> str:
        task_id = f"{task_name}-{len(self.enqueued) + 1}"
        self.enqueued.append((task_name, payload, queue))
        return task_id

    async def get_status(self, task_id: str) -> TaskStatus:
        if task_id not in self.status_by_id:
            raise TaskNotFoundError(task_id)
        return self.status_by_id[task_id]


@pytest.fixture
def env_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide required environment variables for ApiSettings."""
    monkeypatch.setenv("MAX_DIGITS", "5")
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("APP_VERSION", "0.1.0")


def _patch_inject_instance(
    monkeypatch: pytest.MonkeyPatch, stub: StubTaskManager
) -> Callable[[object], StubTaskManager]:
    """Patch `inject.instance` to always return the stub repository."""
    import inject

    def fake_instance(interface: object) -> StubTaskManager:
        if interface is not TaskManagerRepository:
            raise RuntimeError(f"Unexpected dependency request: {interface}")
        return stub

    monkeypatch.setattr(inject, "instance", fake_instance)
    return fake_instance


@pytest.fixture
def stubbed_services(env_settings: None, monkeypatch: pytest.MonkeyPatch):
    """Reload service module with stubbed repository injection."""
    stub = StubTaskManager()
    _patch_inject_instance(monkeypatch, stub)

    services_module = importlib.reload(importlib.import_module("src.api.application.services"))
    return services_module, stub


@pytest.fixture
def api_client(env_settings: None, monkeypatch: pytest.MonkeyPatch):
    """FastAPI test client with services wired to the stub task manager."""
    stub = StubTaskManager()
    _patch_inject_instance(monkeypatch, stub)

    # Reload modules so module-level singletons pick up the patched injector.
    services_module = importlib.reload(importlib.import_module("src.api.application.services"))  # noqa: F841
    routes_module = importlib.reload(importlib.import_module("src.api.presentation.routes"))

    app = FastAPI()
    app.include_router(routes_module.router)
    client = TestClient(app)
    return client, stub

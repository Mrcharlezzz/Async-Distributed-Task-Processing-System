import inject

from src.app.application.broadcaster import TaskStatusBroadcaster
from src.app.domain.repositories import StorageRepository, TaskManagerRepository
from src.app.infrastructure.celery.repositories import CeleryTaskManager
from src.app.infrastructure.postgres.orm import PostgresOrm
from src.app.infrastructure.postgres.repositories import PostgresStorageRepository
from src.app.presentation.websockets import WebSocketStatusBroadcaster, connection_manager
from src.setup.db_config import DatabaseSettings


def _config(binder: inject.Binder) -> None:
    """Bind domain interfaces to concrete implementations."""
    db_settings = DatabaseSettings()
    orm = PostgresOrm(db_settings.DATABASE_URL)
    binder.bind(TaskManagerRepository, CeleryTaskManager())
    binder.bind(StorageRepository, PostgresStorageRepository(orm))
    binder.bind(TaskStatusBroadcaster, WebSocketStatusBroadcaster(connection_manager))


def configure_di() -> None:
    """Dependency injection configuration."""
    if not inject.is_configured():
        inject.configure(_config)

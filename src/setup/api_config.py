
import inject
from pydantic_settings import BaseSettings

from src.api.domain.repositories import TaskManagerRepository
from src.api.infrastructure.celery.celery_task_manager import CeleryTaskManager


class ApiSettings(BaseSettings):
    MAX_DIGITS: int
    APP_NAME: str
    APP_VERSION: str

    class Config:
        env_file = ".env"
        extra = "ignore"
        

def get_api_settings() -> ApiSettings:
    return ApiSettings()

def _config(binder: inject.Binder) -> None:
    """
    Bind domain interfaces to concrete implementations.
    """
    # If you want singleton semantics, bind an instance (not a class):
    binder.bind(TaskManagerRepository, CeleryTaskManager())


def configure_di() -> None:
    """Dependency injection configuration."""
    if not inject.is_configured():
        inject.configure(_config)

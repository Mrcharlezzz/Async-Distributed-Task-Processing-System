from pydantic_settings import BaseSettings

class CelerySettings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/0"      # broker + backend
    RESULT_TTL_SECONDS: int = 3600

    class Config:
        env_file = ".env"
        extra = "ignore"

def get_celery_settings() -> CelerySettings:
    # simple singleton if you want later; minimal now
    return CelerySettings()

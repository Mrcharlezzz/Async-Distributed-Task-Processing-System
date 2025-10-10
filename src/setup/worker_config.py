from pydantic_settings import BaseSettings

class WorkerSettings(BaseSettings):
    SLEEP_PER_DIGIT_SEC: float = 0.05
    ROUNDING_POLICY: str = "TRUNCATE"

    class Config:
        env_file = ".env"
        extra = "ignore"

def get_worker_settings() -> WorkerSettings:
    # simple singleton if you want later; minimal now
    return WorkerSettings()

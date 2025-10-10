from fastapi import FastAPI

from src.api.presentation.routes import router as api_router
from src.setup.api_config import configure_di, get_api_settings

# Configure DI once at process start
_settings = get_api_settings()
configure_di()

app = FastAPI(
    title=_settings.APP_NAME,
    version=_settings.APP_VERSION,
    description="Async task API (compute π) with progress polling",
)

# If you import and instantiate services here, do it AFTER configure_di()

app.include_router(api_router, prefix="")

from fastapi import FastAPI

from src.app.presentation.websockets import router as ws_router
from src.app.presentation.naive_worker_routes import router as naive_router
from src.app.presentation.routes import router as api_router
from src.setup.api_config import ApiSettings
from src.setup.app_config import configure_di
from src.setup.stream_config import configure_stream_consumer

settings = ApiSettings()
configure_di()

consumer = configure_stream_consumer()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Async task API with progress polling",
)

async def _start_consumer() -> None:
    # Start the Redis streams consumer alongside the API process.
    await consumer.start()

async def _stop_consumer() -> None:
    # Ensure the consumer stops cleanly on shutdown to release Redis connections.
    await consumer.stop()

app.add_event_handler("startup", _start_consumer)
app.add_event_handler("shutdown", _stop_consumer)

app.include_router(api_router, prefix="")
app.include_router(naive_router, prefix="")
app.include_router(ws_router, prefix="")

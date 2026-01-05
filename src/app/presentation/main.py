from fastapi import FastAPI

import inject

from src.app.application.broadcaster import TaskStatusBroadcaster
from src.app.presentation.websockets import (
    WebSocketStatusBroadcaster,
    connection_manager,
    router as ws_router,
)
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
    await consumer.start()

async def _stop_consumer() -> None:
    await consumer.stop()

app.add_event_handler("startup", _start_consumer)
app.add_event_handler("shutdown", _stop_consumer)

from src.app.presentation.routes import router as api_router  # noqa: E402

app.include_router(api_router, prefix="")
app.include_router(ws_router, prefix="")

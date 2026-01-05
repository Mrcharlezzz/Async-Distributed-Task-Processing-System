import inject

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from src.app.application.handlers import TaskEventHandler
from src.app.domain.events.task_event import EventType
from src.app.domain.repositories import TaskEventPublisherRepository
from src.app.infrastructure.streams.client import StreamsClient, SyncStreamsClient
from src.app.infrastructure.streams.consumer import (
    GROUP_API,
    STREAM_TASK_EVENTS,
    StreamsConsumer,
    consumer_name,
)
from src.app.infrastructure.streams.publisher import StreamsPublisher, StreamsSyncPublisher
from src.app.infrastructure.streams.router import EventRouter

_stream_consumer: StreamsConsumer | None = None
_stream_publisher: StreamsSyncPublisher | None = None


class StreamSettings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/0"
    STREAM_NAME: str = STREAM_TASK_EVENTS
    GROUP_NAME: str = GROUP_API
    CONSUMER_NAME: str | None = None
    BLOCK_MS: int = 5000
    COUNT: int = 10
    RECLAIM_PENDING: bool = False
    RECLAIM_IDLE_MS: int = 60000

    model_config = ConfigDict(env_file=".env", extra="ignore")


def build_event_router() -> EventRouter:
    router = EventRouter()
    handler = TaskEventHandler()
    router.register(EventType.TASK_STATUS, handler.handle_status_event)
    router.register(EventType.TASK_RESULT, handler.handle_result_event)
    router.register(EventType.TASK_RESULT_CHUNK, handler.handle_result_chunk_event)
    return router


def build_stream_consumer(settings: StreamSettings | None = None) -> StreamsConsumer:
    if settings is None:
        settings = StreamSettings()
    client = StreamsClient(settings.REDIS_URL)
    router = build_event_router()
    name = settings.CONSUMER_NAME or consumer_name()
    return StreamsConsumer(
        client,
        stream=settings.STREAM_NAME,
        group=settings.GROUP_NAME,
        consumer_name=name,
        router=router,
        block_ms=settings.BLOCK_MS,
        count=settings.COUNT,
        reclaim_pending=settings.RECLAIM_PENDING,
        reclaim_idle_ms=settings.RECLAIM_IDLE_MS,
    )


def build_stream_publisher(settings: StreamSettings | None = None) -> StreamsSyncPublisher:
    if settings is None:
        settings = StreamSettings()
    client = SyncStreamsClient(settings.REDIS_URL)
    return StreamsSyncPublisher(client, settings.STREAM_NAME)


def configure_stream_publisher(settings: StreamSettings | None = None) -> StreamsSyncPublisher:
    global _stream_publisher
    if _stream_publisher is None:
        _stream_publisher = build_stream_publisher(settings)

    if inject.is_configured():
        injector = inject.get_injector()
        if hasattr(injector, "binder"):
            injector.binder.bind(TaskEventPublisherRepository, _stream_publisher)
        else:
            injector.bind(TaskEventPublisherRepository, _stream_publisher)
    else:
        def _config(binder: inject.Binder) -> None:
            binder.bind(TaskEventPublisherRepository, _stream_publisher)

        inject.configure(_config)

    return _stream_publisher


def configure_stream_consumer() -> StreamsConsumer:
    global _stream_consumer
    if _stream_consumer is None:
        _stream_consumer = build_stream_consumer()
    return _stream_consumer

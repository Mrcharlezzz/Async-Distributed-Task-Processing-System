from __future__ import annotations

from typing import Iterable, Sequence

from src.app.domain.events.task_event import TaskEvent
from src.app.infrastructure.streams.client import StreamsClient, SyncStreamsClient
from src.app.infrastructure.streams.serializers import encode_event


class StreamsPublisher:
    """Async publisher for Redis streams."""
    def __init__(self, client: StreamsClient, stream: str) -> None:
        self._client = client
        self._stream = stream

    async def publish(
        self,
        events: TaskEvent | Sequence[TaskEvent],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> None:
        """Publish one or more task events."""
        batch: Iterable[TaskEvent]
        if isinstance(events, TaskEvent):
            batch = [events]
        else:
            batch = events

        for event in batch:
            await self._client.redis.xadd(
                self._stream,
                encode_event(event),
                maxlen=maxlen,
                approximate=approximate,
            )


class StreamsSyncPublisher:
    """Sync publisher for Redis streams."""
    def __init__(self, client: SyncStreamsClient, stream: str) -> None:
        self._client = client
        self._stream = stream

    def publish(
        self,
        events: TaskEvent | Sequence[TaskEvent],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> None:
        """Publish one or more task events."""
        batch: Iterable[TaskEvent]
        if isinstance(events, TaskEvent):
            batch = [events]
        else:
            batch = events

        for event in batch:
            self._client.redis.xadd(
                self._stream,
                encode_event(event),
                maxlen=maxlen,
                approximate=approximate,
            )

    def close(self) -> None:
        """Close the underlying client connection."""
        self._client.close()

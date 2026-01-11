from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections.abc import Iterable

from redis.exceptions import ConnectionError, RedisError, TimeoutError

from src.app.infrastructure.streams.client import StreamsClient
from src.app.infrastructure.streams.router import EventRouter
from src.app.infrastructure.streams.serializers import decode_event

logger = logging.getLogger(__name__)

STREAM_TASK_EVENTS = "tasks:events"
GROUP_API = "api"


def consumer_name() -> str:
    """Generate a unique consumer name for this process."""
    return f"{socket.gethostname()}:{os.getpid()}"


class StreamsConsumer:
    """Consume Redis stream events and dispatch to handlers."""
    def __init__(
        self,
        client: StreamsClient,
        *,
        stream: str,
        group: str,
        consumer_name: str,
        router: EventRouter,
        block_ms: int,
        count: int,
        reclaim_pending: bool,
        reclaim_idle_ms: int,
    ) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._consumer_name = consumer_name
        self._router = router
        self._block_ms = block_ms
        self._count = count
        self._reclaim_pending = reclaim_pending
        self._reclaim_idle_ms = reclaim_idle_ms
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the consumer loop."""
        await self._client.ensure_consumer_group(
            stream=self._stream,
            group=self._group,
        )
        if self._reclaim_pending:
            await self._reclaim()
        self._task = asyncio.create_task(self._run(), name="redis-stream-consumer")

    async def stop(self) -> None:
        """Stop the consumer loop and close connections."""
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        await self._client.close()

    async def _run(self) -> None:
        """Read from the stream and dispatch events with retries."""
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                response = await self._client.redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer_name,
                    streams={self._stream: ">"},
                    count=self._count,
                    block=self._block_ms,
                )
                if not response:
                    continue
                await self._handle_response(response)
                backoff = 1.0
            except (ConnectionError, TimeoutError, RedisError) as exc:
                if self._stop_event.is_set():
                    break
                logger.exception("Redis stream consumer error", extra={"error": str(exc)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
            except asyncio.CancelledError:
                break

    async def _handle_response(
        self, response: Iterable[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]]
    ) -> None:
        """Decode and dispatch events, then acknowledge messages."""
        for _stream, entries in response:
            for message_id, fields in entries:
                try:
                    event = decode_event(fields)
                    await self._router.dispatch(event)
                except Exception as exc:
                    logger.exception(
                        "Failed to handle stream event",
                        extra={"message_id": message_id, "error": str(exc)},
                    )
                    continue
                await self._client.redis.xack(self._stream, self._group, message_id)

    async def _reclaim(self) -> None:
        """Reclaim pending messages idle past the configured threshold."""
        try:
            await self._client.redis.xautoclaim(
                self._stream,
                self._group,
                self._consumer_name,
                min_idle_time=self._reclaim_idle_ms,
                start_id="0-0",
            )
        except RedisError as exc:
            logger.warning("Failed to reclaim pending messages", extra={"error": str(exc)})

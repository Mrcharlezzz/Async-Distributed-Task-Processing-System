from __future__ import annotations

import logging

from redis import ConnectionPool as SyncConnectionPool
from redis import Redis as SyncRedis
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)


class StreamsClient:
    """Async Redis Streams client wrapper."""
    def __init__(
        self,
        url: str,
        *,
        max_connections: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
    ) -> None:
        pool = ConnectionPool.from_url(
            url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=retry_on_timeout,
            decode_responses=True,
        )
        self._redis = Redis(connection_pool=pool)

    @property
    def redis(self) -> Redis:
        """Expose the underlying async Redis client."""
        return self._redis

    async def ensure_consumer_group(
        self,
        *,
        stream: str,
        group: str,
        start_id: str = "$",
    ) -> None:
        """Create a consumer group if it does not already exist."""
        try:
            await self._redis.xgroup_create(
                name=stream,
                groupname=group,
                id=start_id,
                mkstream=True,
            )
            logger.info(
                "Created Redis consumer group",
                extra={"stream": stream, "group": group},
            )
        except ResponseError as exc:
            message = str(exc)
            # Ignore BUSYGROUP error if the group already exists
            if "BUSYGROUP" in message:
                return
            raise

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._redis.aclose()


class SyncStreamsClient:
    """Sync Redis Streams client wrapper."""
    def __init__(
        self,
        url: str,
        *,
        max_connections: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
    ) -> None:
        pool = SyncConnectionPool.from_url(
            url,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=retry_on_timeout,
            decode_responses=True,
        )
        self._redis = SyncRedis(connection_pool=pool)

    @property
    def redis(self) -> SyncRedis:
        """Expose the underlying sync Redis client."""
        return self._redis

    def close(self) -> None:
        """Close the underlying Redis connection."""
        self._redis.close()

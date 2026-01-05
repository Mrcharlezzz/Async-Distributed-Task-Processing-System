from __future__ import annotations

from typing import Any, Iterable

import inject

from src.app.domain.events.task_event import TaskEvent
from src.app.domain.models.task_status import TaskStatus
from src.app.domain.repositories import TaskEventPublisherRepository


class TaskReporter:
    """Publish task events to the stream."""

    def __init__(
        self,
        task_id: str,
        publisher: TaskEventPublisherRepository | None = None,
    ) -> None:
        self._task_id = task_id
        self._publisher = publisher or inject.instance(TaskEventPublisherRepository)

    def report_status(self, status: TaskStatus) -> None:
        event = TaskEvent.status(self._task_id, status)
        self._publish(event)

    def report_result(self, result_snapshot: dict[str, Any]) -> None:
        event = TaskEvent.result(self._task_id, result_snapshot)
        self._publish(event)

    def report_result_chunk(self, batch_size: int = 1) -> "ResultChunkReporter":
        return ResultChunkReporter(self, batch_size)

    def _publish(self, event: TaskEvent) -> None:
        self._publisher.publish(event)


class ResultChunkReporter:
    def __init__(self, reporter: TaskReporter, batch_size: int) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        self._reporter = reporter
        self._batch_size = batch_size
        self._chunk_index = 0
        self._batch: list[Any] = []

    def emit(self, item: Any) -> None:
        self._batch.append(item)
        if len(self._batch) >= self._batch_size:
            self._flush(is_last=False)

    def extend(self, items: Iterable[Any]) -> None:
        for item in items:
            self.emit(item)
        

    def _flush(self, is_last: bool) -> None:
        event = TaskEvent.result_chunk(
            self._reporter._task_id,
            str(self._chunk_index),
            list(self._batch),
            is_last=is_last,
        )
        self._reporter._publish(event)
        if is_last:
            return
        self._chunk_index += 1
        self._batch.clear()

    def __enter__(self) -> "ResultChunkReporter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._flush(is_last=True)

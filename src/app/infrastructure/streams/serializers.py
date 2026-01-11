from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from src.app.domain.events.task_event import EventType, TaskEvent

def _as_str(value: Any) -> str:
    """Normalize a value into a string."""
    return str(value)


def encode_event(event: TaskEvent) -> dict[str, str | bytes]:
    """Serialize a TaskEvent for Redis streams."""
    return {
        "event_id": event.event_id,
        "type": event.type.value,
        "task_id": event.task_id,
        "ts": event.ts.isoformat(),
        "payload": json.dumps(event.payload),
    }


def decode_event(fields: dict[str, Any]) -> TaskEvent:
    """Deserialize a TaskEvent from Redis stream fields."""
    raw_payload = fields.get("payload")
    payload_str = _as_str(raw_payload)
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid payload JSON") from exc

    event_data = {
        "event_id": _as_str(fields.get("event_id", "")),
        "type": EventType(_as_str(fields.get("type", ""))),
        "task_id": _as_str(fields.get("task_id", "")),
        "ts": datetime.fromisoformat(_as_str(fields.get("ts", ""))),
        "payload": payload,
    }
    try:
        return TaskEvent.model_validate(event_data)
    except ValidationError as exc:
        raise ValueError("Invalid event schema") from exc

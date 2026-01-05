from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.app.application.broadcaster import TaskStatusBroadcaster
from src.app.domain.events.task_event import TaskEvent

router = APIRouter(tags=["ws"])


class TaskConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def create_task_session(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(task_id, set()).add(websocket)

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(task_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(task_id, None)

    async def broadcast(self, task_id: str, payload: dict[str, object]) -> None:
        connections = list(self._connections.get(task_id, set()))
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                self.disconnect(task_id, websocket)


class WebSocketStatusBroadcaster(TaskStatusBroadcaster):
    def __init__(self, manager: TaskConnectionManager) -> None:
        self._manager = manager

    async def broadcast_status(self, event: TaskEvent) -> None:
        await self._manager.broadcast(
            event.task_id,
            {
                "type": event.type.value,
                "task_id": event.task_id,
                "payload": event.payload,
            },
        )

    async def broadcast_result_chunk(self, event: TaskEvent) -> None:
        await self._manager.broadcast(
            event.task_id,
            {
                "type": event.type.value,
                "task_id": event.task_id,
                "payload": event.payload,
            },
        )


connection_manager = TaskConnectionManager()


@router.websocket("/ws/tasks/{task_id}")
async def task_updates(websocket: WebSocket, task_id: str) -> None:
    await connection_manager.create_task_session(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(task_id, websocket)

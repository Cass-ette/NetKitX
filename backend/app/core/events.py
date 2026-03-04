from fastapi import WebSocket, WebSocketDisconnect
from typing import Any
import json


class ConnectionManager:
    """WebSocket connection manager for real-time task updates."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(task_id, []).append(websocket)

    def disconnect(self, task_id: str, websocket: WebSocket):
        if task_id in self.active:
            self.active[task_id].remove(websocket)
            if not self.active[task_id]:
                del self.active[task_id]

    async def send_event(self, task_id: str, event: dict[str, Any]):
        if task_id in self.active:
            message = json.dumps(event)
            for ws in self.active[task_id]:
                try:
                    await ws.send_text(message)
                except WebSocketDisconnect:
                    self.disconnect(task_id, ws)


manager = ConnectionManager()

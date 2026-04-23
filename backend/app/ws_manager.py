"""Active-WebSocket registry used by the scheduler to push notifications.

Single-threaded (FastAPI + AsyncIOScheduler share one event loop), so no
explicit locking needed. Broadcast swallows per-connection errors so one
dead socket can't break a push for everyone.
"""

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._connections.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    def count(self) -> int:
        return len(self._connections)

    async def broadcast(self, data: dict[str, Any]) -> None:
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                self._connections.discard(ws)

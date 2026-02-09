"""WebSocket helpers, connection manager, and websocket route."""
from __future__ import annotations

import asyncio
from typing import Any, Set

try:
    from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False
    APIRouter = Any  # type: ignore[assignment]
    WebSocket = Any  # type: ignore[assignment]
    WebSocketDisconnect = Exception  # type: ignore[assignment]

from ..models import WebSocketEvent

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._get_lock():
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._get_lock():
            self.active_connections.discard(websocket)

    async def broadcast(self, event: WebSocketEvent) -> None:
        """Broadcast an event to all connected clients."""
        if not self.active_connections:
            return

        message = event.to_dict()
        async with self._get_lock():
            dead_connections = set()
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                    dead_connections.add(connection)

            self.active_connections -= dead_connections

    async def send_to(self, websocket: WebSocket, event: WebSocketEvent) -> None:
        """Send an event to a specific client."""
        try:
            await websocket.send_json(event.to_dict())
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            await self.disconnect(websocket)


def get_ws_manager(websocket: WebSocket):
    return getattr(websocket.app.state, "ws_manager", None)


if HAS_FASTAPI:
    @router.websocket("/api/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        ws_manager=Depends(get_ws_manager),
    ):
        """
        WebSocket endpoint for real-time updates.

        Events:
        - request_queued: New request added to queue
        - request_started: Request processing started
        - request_completed: Request completed successfully
        - request_failed: Request failed
        - request_cancelled: Request was cancelled
        - request_retrying: Request is being retried
        - request_fallback: Request switched to fallback provider
        - provider_status: Provider status changed
        - stream_chunk: Streaming response chunk
        """
        if ws_manager is None:
            await websocket.close(code=1011)
            return

        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "subscribe":
                    channels = data.get("channels", [])
                    await ws_manager.send_to(
                        websocket,
                        WebSocketEvent(
                            type="subscribed",
                            data={"channels": channels},
                        ),
                    )

                elif data.get("type") == "ping":
                    await ws_manager.send_to(
                        websocket,
                        WebSocketEvent(
                            type="pong",
                            data={},
                        ),
                    )

        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            await ws_manager.disconnect(websocket)

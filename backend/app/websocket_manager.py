"""
WebSocket connection manager. Ported unchanged from Broadband FMS --
this is pure connection-pool bookkeeping with no dependency on Mongo
or FastAPI's deployment mode.
"""
import json
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket disconnected. Total active: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message, default=str))
            except Exception as exc:
                logger.info("Failed to broadcast (client disconnected): %s", exc)
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Singleton shared across routers and the ingest worker
ws_manager = WebSocketManager()

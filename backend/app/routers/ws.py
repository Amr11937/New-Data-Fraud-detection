from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..websocket_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws")
async def fraud_alerts_ws(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    await websocket.send_json({
        "type": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": ws_manager.connection_count,
    })
    try:
        while True:
            # Client doesn't need to send anything; this just keeps the
            # connection open and lets us detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

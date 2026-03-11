from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = {}
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    def update_client_filters(self, websocket: WebSocket, filters: dict):
        if websocket in self.active_connections:
            self.active_connections[websocket] = filters

    async def broadcast(self, headline: dict):
        """Send new headline to all connected clients."""
        message = json.dumps({"type": "new_headline", "data": headline})
        for ws in list(self.active_connections.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

    async def broadcast_analysis_update(self, headline_id: int, analysis: dict):
        """Send analysis update for an existing headline."""
        message = json.dumps({
            "type": "analysis_update",
            "headline_id": headline_id,
            "data": analysis,
        })
        for ws in list(self.active_connections.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

    async def broadcast_stats(self, stats: dict):
        """Send updated stats to all clients."""
        message = json.dumps({"type": "stats_update", "data": stats})
        for ws in list(self.active_connections.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

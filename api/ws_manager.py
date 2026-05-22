"""WebSocket fan-out for live updates."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Set

log = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self.active: Set = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active.add(websocket)

    async def disconnect(self, websocket) -> None:
        async with self._lock:
            self.active.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        if not self.active:
            return
        text = json.dumps(message, default=str)
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(text)
            except Exception as exc:
                log.debug("dropping ws client: %s", exc)
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.active.discard(ws)


import asyncio
from collections import defaultdict
from fastapi import WebSocket


class TrackingManager:
    def __init__(self):
        self.connections = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, order_id: int, websocket: WebSocket):
        await websocket.accept()

        async with self.lock:
            self.connections[order_id].add(websocket)

    async def register(self, order_id: int, websocket: WebSocket):
        """Register a socket that the route has already accepted."""
        async with self.lock:
            self.connections[order_id].add(websocket)

    async def disconnect(self, order_id: int, websocket: WebSocket):
        async with self.lock:
            self.connections[order_id].discard(websocket)

            if not self.connections[order_id]:
                self.connections.pop(order_id, None)

    async def broadcast(self, order_id: int, data: dict):
        async with self.lock:
            clients = list(self.connections.get(order_id, set()))

        for websocket in clients:
            try:
                await websocket.send_json(data)
            except Exception:
                await self.disconnect(order_id, websocket)


tracking_manager = TrackingManager()

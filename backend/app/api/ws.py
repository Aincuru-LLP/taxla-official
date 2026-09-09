import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from app.core.config import settings
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

async def redis_listener():
    """Background task to listen to Redis PubSub and broadcast to websockets"""
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("taxla:updates")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    # Broadcast the update event to all connected UI clients
                    await manager.broadcast(data)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe("taxla:updates")
                await redis_client.aclose()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Redis listener encountered connection issue: {e}")

# We need to start the redis_listener when the app starts. We'll rely on FastAPI lifespan or startup events.

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    subprotocol = websocket.headers.get("sec-websocket-protocol")
    if subprotocol:
        selected = subprotocol.split(",")[0].strip()
        await websocket.accept(subprotocol=selected)
    else:
        await websocket.accept()

    manager.active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket exception: %s", e)
        manager.disconnect(websocket)

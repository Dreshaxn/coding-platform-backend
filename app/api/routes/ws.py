"""
WebSocket endpoint for live submission status updates.

Flow:
  1. Client connects with JWT token as query param for auth
  2. We subscribe to the Redis pub/sub channel for that submission
  3. The judge worker publishes RUNNING -> per-test progress -> final verdict
  4. We forward each message to the client and close on terminal status

Clients that reconnect after a disconnect get the latest cached status
from sub:status:{submission_id} before subscribing to the live channel.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.cache.redis import get_async_redis

router = APIRouter()

TERMINAL_STATUSES = {"accepted", "wrong_answer", "runtime_error",
                     "time_limit_exceeded", "memory_limit_exceeded",
                     "compilation_error"}


def _authenticate_token(token: str) -> int | None:
    """Validate JWT and extract user_id. Returns None if anything's off."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        return int(user_id_str)
    except (JWTError, ValueError, TypeError):
        return None


@router.websocket("/ws/submissions/{submission_id}")
async def submission_ws(
    websocket: WebSocket,
    submission_id: int,
    token: str = Query(...),
):
    # authenticate before accepting — reject early with 4001
    user_id = _authenticate_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="invalid token")
        return

    await websocket.accept()

    r = await get_async_redis()
    pubsub = r.pubsub()
    channel = f"submission:{submission_id}"

    # send cached status first so late-joining clients aren't left hanging
    cached = await r.get(f"sub:status:{submission_id}")
    if cached:
        await websocket.send_text(cached.decode())

    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"].decode()
            await websocket.send_text(data)
            # once we see a final verdict, no more messages are coming
            if '"status":' in data and any(s in data for s in TERMINAL_STATUSES):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()

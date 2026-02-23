"""
Redis cache + pub/sub + job queue layer.

Two separate pools because FastAPI handlers need async and the judge
worker runs in a plain synchronous process. Both are lazy-initialised
so importing this module doesn't immediately open connections.

Key namespaces:
  cache:testcases:{problem_id}  – test case list          (TTL 1h)
  cache:problem:{problem_id}    – problem metadata         (TTL 5m)
  sub:status:{submission_id}    – latest status snapshot   (TTL 10m)
  submission:{submission_id}    – pub/sub channel for live updates
  judge:queue                   – FIFO list used as job queue
"""

import json
from typing import Any, Optional

import redis as sync_redis_lib
import redis.asyncio as async_redis_lib

from app.core.config import settings


# lazy-init pools so we don't open connections at import time
_async_pool: Optional[async_redis_lib.ConnectionPool] = None
_sync_pool: Optional[sync_redis_lib.ConnectionPool] = None


def _get_async_pool() -> async_redis_lib.ConnectionPool:
    global _async_pool
    if _async_pool is None:
        # decode_responses=False so we get raw bytes — we handle json ourselves
        _async_pool = async_redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=False,
        )
    return _async_pool


def _get_sync_pool() -> sync_redis_lib.ConnectionPool:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = sync_redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=False,
        )
    return _sync_pool


async def get_async_redis() -> async_redis_lib.Redis:
    return async_redis_lib.Redis(connection_pool=_get_async_pool())


def get_sync_redis() -> sync_redis_lib.Redis:
    return sync_redis_lib.Redis(connection_pool=_get_sync_pool())


# async cache helpers

async def cache_get(key: str) -> Any:
    r = await get_async_redis()
    val = await r.get(key)
    return json.loads(val) if val else None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = await get_async_redis()
    await r.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    r = await get_async_redis()
    await r.delete(key)


# sync cache helpers (for the judge worker)

def cache_get_sync(key: str) -> Any:
    r = get_sync_redis()
    val = r.get(key)
    return json.loads(val) if val else None


def cache_set_sync(key: str, value: Any, ttl: int = 300) -> None:
    r = get_sync_redis()
    r.set(key, json.dumps(value, default=str), ex=ttl)


def cache_delete_sync(key: str) -> None:
    r = get_sync_redis()
    r.delete(key)


# pub/sub for submission status updates
# we SET the latest status *and* PUBLISH it so that:
#   - active websocket subscribers get the message instantly via pub/sub
#   - clients that reconnect late can read sub:status:{id} to catch up

async def publish_status(submission_id: int, payload: dict) -> None:
    r = await get_async_redis()
    data = json.dumps(payload, default=str)
    await r.set(f"sub:status:{submission_id}", data, ex=600)
    await r.publish(f"submission:{submission_id}", data)


def publish_status_sync(submission_id: int, payload: dict) -> None:
    r = get_sync_redis()
    data = json.dumps(payload, default=str)
    r.set(f"sub:status:{submission_id}", data, ex=600)
    r.publish(f"submission:{submission_id}", data)


# job queue — LPUSH/BRPOP gives us a simple reliable FIFO without
# needing celery or RQ. upgrade to redis streams if you need acks later.

def enqueue_submission(submission_id: int) -> None:
    r = get_sync_redis()
    r.lpush("judge:queue", str(submission_id))


async def enqueue_submission_async(submission_id: int) -> None:
    r = await get_async_redis()
    await r.lpush("judge:queue", str(submission_id))


def dequeue_submission(timeout: int = 0) -> Optional[int]:
    """Blocking pop — returns submission id or None on timeout."""
    r = get_sync_redis()
    result = r.brpop("judge:queue", timeout=timeout)
    if result is None:
        return None
    return int(result[1])


# cleanup

async def close_async_pool() -> None:
    global _async_pool
    if _async_pool is not None:
        await _async_pool.disconnect()
        _async_pool = None


def close_sync_pool() -> None:
    global _sync_pool
    if _sync_pool is not None:
        _sync_pool.disconnect()
        _sync_pool = None

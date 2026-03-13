"""Agent health metrics — Redis read/write helpers.

Zero-token overhead: the agent loop writes a small JSON snapshot per turn;
the standalone monitor server reads it out-of-band.
"""

import json
import time

import redis.asyncio as aioredis

from app.core.config import settings

_METRICS_PREFIX = "agent:metrics:"
_METRICS_TTL = 3600  # 1 hour auto-expire


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def compute_health_score(
    effective_stagnation: int,
    consecutive_errors: int,
    results_negative: bool,
    all_actions_ok: bool = True,
) -> int:
    """Compute 0-100 health score from agent loop signals.

    Baseline 50, bidirectional: positive signals add points,
    negative signals subtract.  A healthy turn scores ~80-100,
    a stuck turn drops to 30 or below.
    """
    health = 50
    # Positive
    if all_actions_ok:
        health += 20
    if effective_stagnation == 0:
        health += 15
    if consecutive_errors == 0:
        health += 15
    # Negative
    health -= effective_stagnation * 8
    health -= consecutive_errors * 15
    if results_negative:
        health -= 10
    return max(0, min(100, health))


async def publish_metrics(session_id: int | str, metrics: dict) -> None:
    """Write metrics snapshot to Redis. Called from agent loop."""
    r = await _get_redis()
    try:
        metrics.setdefault("timestamp", time.time())
        key = f"{_METRICS_PREFIX}{session_id}"
        await r.set(key, json.dumps(metrics), ex=_METRICS_TTL)
        await r.sadd("agent:active_sessions", str(session_id))
    finally:
        await r.aclose()


async def get_metrics(session_id: int | str) -> dict | None:
    """Read metrics for a single session."""
    r = await _get_redis()
    try:
        raw = await r.get(f"{_METRICS_PREFIX}{session_id}")
        return json.loads(raw) if raw else None
    finally:
        await r.aclose()


async def list_active_sessions() -> list[dict]:
    """Return metrics for all active sessions, pruning expired ones."""
    r = await _get_redis()
    try:
        ids = await r.smembers("agent:active_sessions")
        results = []
        for sid in ids:
            raw = await r.get(f"{_METRICS_PREFIX}{sid}")
            if raw:
                results.append(json.loads(raw))
            else:
                await r.srem("agent:active_sessions", sid)
        return results
    finally:
        await r.aclose()


async def remove_session(session_id: int | str) -> None:
    """Clean up metrics when a session ends."""
    r = await _get_redis()
    try:
        await r.delete(f"{_METRICS_PREFIX}{session_id}")
        await r.srem("agent:active_sessions", str(session_id))
    finally:
        await r.aclose()

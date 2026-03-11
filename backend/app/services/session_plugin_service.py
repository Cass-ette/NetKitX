import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from app.core.config import settings
from app.plugins.base import PluginEvent, SessionPlugin
from app.plugins.registry import registry

logger = logging.getLogger(__name__)

SESSION_TTL = 3600  # 1 hour
SESSION_PREFIX = "psession:"
USER_SESSIONS_PREFIX = "psessions_user:"


class PluginSessionManager:
    """Manages plugin session lifecycle with Redis-backed state."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def _get_session_plugin(self, plugin_name: str) -> SessionPlugin | None:
        plugin = registry.get(plugin_name)
        if plugin is None:
            return None
        meta = registry.get_meta(plugin_name)
        if meta is None or meta.mode != "session":
            return None
        if not isinstance(plugin, SessionPlugin):
            return None
        return plugin

    async def create_session(self, plugin_name: str, user_id: int, params: dict[str, Any]) -> str:
        """Create a new plugin session. Returns session_id."""
        plugin = self._get_session_plugin(plugin_name)
        if plugin is None:
            raise ValueError(f"Plugin '{plugin_name}' not found or does not support session mode")

        session_id = str(uuid.uuid4())
        state = await plugin.on_session_start(params)

        r = await self._get_redis()
        now = datetime.now(timezone.utc).isoformat()
        session_data = {
            "plugin_name": plugin_name,
            "user_id": str(user_id),
            "state": json.dumps(state),
            "params": json.dumps(params),
            "created_at": now,
            "last_active": now,
        }
        key = f"{SESSION_PREFIX}{session_id}"
        await r.hset(key, mapping=session_data)
        await r.expire(key, SESSION_TTL)

        # Track user sessions
        user_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        await r.sadd(user_key, session_id)
        await r.expire(user_key, SESSION_TTL)

        logger.info("Created session %s for plugin %s (user=%d)", session_id, plugin_name, user_id)
        return session_id

    async def send_message(
        self, session_id: str, message: dict[str, Any]
    ) -> AsyncIterator[PluginEvent]:
        """Send a message to a session. Yields plugin events."""
        r = await self._get_redis()
        key = f"{SESSION_PREFIX}{session_id}"
        data = await r.hgetall(key)
        if not data:
            yield PluginEvent(type="error", data={"error": "Session not found or expired"})
            return

        plugin = self._get_session_plugin(data["plugin_name"])
        if plugin is None:
            yield PluginEvent(type="error", data={"error": "Plugin no longer available"})
            return

        state = json.loads(data["state"])

        async for event in plugin.on_message(session_id, message, state):
            yield event

        # Write back updated state and refresh TTL
        now = datetime.now(timezone.utc).isoformat()
        await r.hset(key, mapping={"state": json.dumps(state), "last_active": now})
        await r.expire(key, SESSION_TTL)

    async def close_session(self, session_id: str) -> None:
        """Close and cleanup a session."""
        r = await self._get_redis()
        key = f"{SESSION_PREFIX}{session_id}"
        data = await r.hgetall(key)
        if not data:
            return

        plugin = self._get_session_plugin(data["plugin_name"])
        if plugin is not None:
            state = json.loads(data["state"])
            try:
                await plugin.on_session_end(session_id, state)
            except Exception as e:
                logger.error("Error in on_session_end for %s: %s", session_id, e)

        user_key = f"{USER_SESSIONS_PREFIX}{data['user_id']}"
        await r.srem(user_key, session_id)
        await r.delete(key)
        logger.info("Closed session %s", session_id)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session info (without internal state)."""
        r = await self._get_redis()
        key = f"{SESSION_PREFIX}{session_id}"
        data = await r.hgetall(key)
        if not data:
            return None
        return {
            "session_id": session_id,
            "plugin_name": data["plugin_name"],
            "user_id": int(data["user_id"]),
            "created_at": data["created_at"],
            "last_active": data["last_active"],
        }

    async def list_user_sessions(self, user_id: int) -> list[dict[str, Any]]:
        """List all active sessions for a user."""
        r = await self._get_redis()
        user_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        session_ids = await r.smembers(user_key)

        sessions = []
        expired = []
        for sid in session_ids:
            info = await self.get_session(sid)
            if info is not None:
                sessions.append(info)
            else:
                expired.append(sid)

        # Clean up expired session references
        if expired:
            await r.srem(user_key, *expired)

        return sessions

    async def validate_session_owner(self, session_id: str, user_id: int) -> bool:
        """Check if a session belongs to the given user."""
        info = await self.get_session(session_id)
        if info is None:
            return False
        return info["user_id"] == user_id


session_manager = PluginSessionManager()

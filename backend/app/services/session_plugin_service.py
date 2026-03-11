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
        """
        Initialize a PluginSessionManager instance.
        
        Sets up internal state and defers creation of the Redis client by initializing the internal `_redis` attribute to `None`. The Redis client will be created lazily on first use.
        """
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """
        Lazily initialize and return a cached aioredis Redis client.
        
        Returns:
            aioredis.Redis: Redis client connected to `settings.REDIS_URL` with `decode_responses=True`; the instance is cached for subsequent calls.
        """
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def _get_session_plugin(self, plugin_name: str) -> SessionPlugin | None:
        """
        Retrieve a session-capable plugin instance by name from the registry.
        
        Parameters:
            plugin_name (str): The registry key/name of the plugin to resolve.
        
        Returns:
            SessionPlugin | None: A SessionPlugin instance if a plugin with the given name exists and its metadata indicates `mode == "session"`, `None` otherwise.
        """
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
        """
        Create and persist a new session for the specified plugin and user.
        
        Creates a session associated with the given plugin and user, initializes the plugin state using the provided parameters, stores session metadata and state in persistent storage, and returns the new session identifier.
        
        Parameters:
            plugin_name (str): Name of the plugin to create a session for.
            user_id (int): ID of the user who owns the session.
            params (dict[str, Any]): Parameters passed to the plugin's session start handler.
        
        Returns:
            session_id (str): UUID of the newly created session.
        
        Raises:
            ValueError: If the named plugin does not exist or does not support session mode.
        """
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
        """
        Deliver a message to a plugin session and stream resulting PluginEvent objects.
        
        If the session does not exist or the plugin is unavailable, yields a single error PluginEvent and returns.
        After processing messages from the plugin, updates the session state in storage and refreshes the session TTL.
        
        Parameters:
            session_id (str): Identifier of the session to target.
            message (dict[str, Any]): Payload forwarded to the plugin's message handler.
        
        Returns:
            AsyncIterator[PluginEvent]: An async iterator that yields PluginEvent values produced by the plugin; may yield an error PluginEvent if the session is missing or the plugin is no longer available.
        """
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
        """
        Close a plugin session and remove its stored state.
        
        If the session exists, invokes the plugin's `on_session_end` callback with the stored state (errors are logged),
        removes the session ID from the user's session set, deletes the session record from Redis, and logs the closure.
        
        Parameters:
        	session_id (str): The identifier of the session to close.
        """
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
        """
        Retrieve non-internal metadata for a session by its ID.
        
        Returns:
            dict: A dictionary with keys `session_id`, `plugin_name`, `user_id`, `created_at`, and `last_active` when the session exists; `None` if the session does not exist.
        """
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
        """
        List active plugin sessions for a user.
        
        Removes any expired session references from the user's session set before returning results.
        
        Parameters:
            user_id (int): ID of the user whose sessions will be listed.
        
        Returns:
            list[dict[str, Any]]: A list of session metadata dictionaries (each contains `session_id`, `plugin_name`, `user_id`, `created_at`, and `last_active`).
        """
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
        """
        Check if a session belongs to the given user.
        
        @returns: `true` if the session exists and is owned by `user_id`, `false` otherwise.
        """
        info = await self.get_session(session_id)
        if info is None:
            return False
        return info["user_id"] == user_id


session_manager = PluginSessionManager()

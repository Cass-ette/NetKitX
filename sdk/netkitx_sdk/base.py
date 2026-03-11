from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class PluginEvent:
    """An event emitted by a plugin during execution.

    type:
        "progress" — {"percent": int, "msg": str}
        "result"   — one row of output data (dict matching output.columns)
        "log"      — {"msg": str}
        "error"    — {"error": str}
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginMeta:
    """Plugin metadata, mirrors the fields in plugin.yaml."""

    name: str
    version: str
    description: str
    category: str  # recon | vuln | exploit | utils
    engine: str = "python"  # python | go | cli
    mode: str = "oneshot"  # oneshot | session
    params: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """Base class for all NetKitX Python plugins.

    Usage::

        from netkitx_sdk import PluginBase, PluginEvent, PluginMeta

        class Plugin(PluginBase):
            meta = PluginMeta(
                name="my-plugin",
                version="1.0.0",
                description="Does something useful",
                category="recon",
            )

            async def execute(self, params):
                yield PluginEvent("progress", {"percent": 0})
                yield PluginEvent("result",   {"host": params["target"], "alive": True})
                yield PluginEvent("progress", {"percent": 100})
    """

    meta: PluginMeta

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        """Execute the plugin.

        Must be an async generator that yields PluginEvent objects.
        The runtime collects all "result" events as output rows.
        """
        ...

    async def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise parameters before execution.

        Raise ValueError with a descriptive message for invalid input.
        The default implementation returns params unchanged.
        """
        return params

    async def cleanup(self) -> None:
        """
        Release plugin resources when execution finishes.
        
        Called after execution completes, including when an error occurs. Override to perform cleanup; the default implementation does nothing.
        """


class SessionPlugin(PluginBase):
    """Base class for session-mode plugins that support persistent connections.

    Instead of a single execute() call, session plugins maintain state across
    multiple messages within a session.
    """

    mode: str = "session"

    async def on_session_start(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Initialize and return the plugin's initial session state based on the provided parameters.
        
        Parameters:
            params (dict[str, Any]): Plugin parameters passed at session creation.
        
        Returns:
            dict[str, Any]: Initial mutable session state to be used for subsequent messages.
        """
        return {}

    async def on_message(
        self, session_id: str, message: dict[str, Any], state: dict[str, Any]
    ) -> AsyncIterator[PluginEvent]:
        """
        Handle an incoming message for a session and produce plugin events in response.
        
        Parameters:
            session_id (str): Identifier of the session the message belongs to.
            message (dict[str, Any]): Incoming message payload; typically contains a "type" key describing intent and any message-specific fields.
            state (dict[str, Any]): Mutable session state returned by `on_session_start`; handlers may read and modify this state.
        
        Returns:
            AsyncIterator[PluginEvent]: Asynchronous iterator yielding PluginEvent objects that represent events emitted in response to the message.
        """
        yield PluginEvent(type="error", data={"error": "not implemented"})

    async def on_session_end(self, session_id: str, state: dict[str, Any]) -> None:
        """
        Perform cleanup when a session ends.
        
        Parameters:
            session_id (str): Identifier of the session being ended.
            state (dict[str, Any]): Final session state available for cleanup.
        """

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        """
        Execute the plugin as a one-shot using the session lifecycle.
        
        This fallback implementation initializes a transient session state via `on_session_start`,
        dispatches an "execute" message to `on_message` with session_id `"oneshot"` (yielding all events),
        and finalizes the transient session via `on_session_end`.
        
        Parameters:
            params (dict[str, Any]): Execution parameters forwarded to the session start and the execute message.
        
        Returns:
            AsyncIterator[PluginEvent]: Events produced while handling the execute message.
        """
        state = await self.on_session_start(params)
        async for event in self.on_message("oneshot", {"type": "execute", "params": params}, state):
            yield event
        await self.on_session_end("oneshot", state)

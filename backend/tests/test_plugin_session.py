"""Tests for Plugin Session Engine (no Redis/DB required)."""

import importlib.util
import json
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

from netkitx_sdk.base import PluginBase, PluginEvent, PluginMeta, SessionPlugin


def _load_webshell_class():
    """
    Load the WebShellPlugin class from plugins/webshell/main.py if available.
    
    Attempts to import the module file and retrieve the attribute `WebShellPlugin`.
    Returns the class when the file exists and defines `WebShellPlugin`, otherwise returns `None`.
    
    Returns:
        The `WebShellPlugin` class if found, `None` otherwise.
    """
    plugin_file = Path(__file__).parent.parent.parent / "plugins" / "webshell" / "main.py"
    if not plugin_file.exists():
        return None
    spec = importlib.util.spec_from_file_location("webshell_main", plugin_file)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return getattr(module, "WebShellPlugin", None)


# ── Test fixtures ────────────────────────────────────────────────────


class DummySessionPlugin(SessionPlugin):
    """Minimal SessionPlugin for testing."""

    meta = PluginMeta(
        name="test-session",
        version="1.0.0",
        description="Test session plugin",
        category="utils",
        mode="session",
    )

    async def on_session_start(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Initialize a new session state for the plugin.
        
        Parameters:
            params (dict[str, Any]): Session start parameters. Recognizes the optional key `"echo"` (boolean) to control whether incoming commands are echoed; defaults to `True` if not provided.
        
        Returns:
            dict[str, Any]: Initial session state containing:
                - `counter` (int): starts at 0.
                - `echo` (bool): echo setting derived from `params["echo"]` or `True`.
        """
        return {"counter": 0, "echo": params.get("echo", True)}

    async def on_message(
        self, session_id: str, message: dict[str, Any], state: dict[str, Any]
    ) -> AsyncIterator[PluginEvent]:
        """
        Handle an incoming session message and emit a single PluginEvent based on its command.
        
        Increments state["counter"] as a side effect. If the message's "command" is "error", yields an error event; otherwise yields a result event containing an echo of the command and the updated counter.
        
        Parameters:
            session_id (str): Identifier of the session.
            message (dict[str, Any]): Client message; this function reads the "command" key.
            state (dict[str, Any]): Mutable session state; "counter" will be incremented.
        
        Returns:
            AsyncIterator[PluginEvent]: Yields one `PluginEvent`: an "error" event with `data={"error": "test error"}` when the command is "error", or a "result" event with `data={"output": "echo: <command>", "counter": <updated>}` otherwise.
        """
        state["counter"] += 1
        command = message.get("command", "")

        if command == "error":
            yield PluginEvent(type="error", data={"error": "test error"})
            return

        yield PluginEvent(
            type="result",
            data={"output": f"echo: {command}", "counter": state["counter"]},
        )

    async def on_session_end(self, session_id: str, state: dict[str, Any]) -> None:
        """
        Perform any cleanup or finalization required when a session ends.
        
        Parameters:
            session_id (str): Identifier of the session that is ending.
            state (dict[str, Any]): Final session state at the time of termination.
        """
        pass


# ── SessionPlugin base class tests ──────────────────────────────────


class TestSessionPluginBase:
    """Test SessionPlugin default methods."""

    def test_session_plugin_has_mode(self):
        """SessionPlugin.mode should be 'session'."""
        plugin = DummySessionPlugin()
        assert plugin.mode == "session"

    def test_session_plugin_is_plugin_base(self):
        """SessionPlugin should be a subclass of PluginBase."""
        assert issubclass(SessionPlugin, PluginBase)

    def test_session_plugin_meta_mode(self):
        """PluginMeta should store mode field."""
        meta = PluginMeta(
            name="test",
            version="1.0.0",
            description="test",
            category="utils",
            mode="session",
        )
        assert meta.mode == "session"

    def test_plugin_meta_default_mode(self):
        """PluginMeta mode should default to 'oneshot'."""
        meta = PluginMeta(
            name="test",
            version="1.0.0",
            description="test",
            category="utils",
        )
        assert meta.mode == "oneshot"

    @pytest.mark.asyncio
    async def test_default_on_session_start(self):
        """Default on_session_start should return empty dict."""
        plugin = SessionPlugin.__new__(SessionPlugin)
        state = await plugin.on_session_start({})
        assert state == {}

    @pytest.mark.asyncio
    async def test_default_on_message(self):
        """Default on_message should yield error event."""
        plugin = SessionPlugin.__new__(SessionPlugin)
        events = []
        async for event in plugin.on_message("sid", {}, {}):
            events.append(event)
        assert len(events) == 1
        assert events[0].type == "error"
        assert "not implemented" in events[0].data["error"]

    @pytest.mark.asyncio
    async def test_default_on_session_end(self):
        """Default on_session_end should not raise."""
        plugin = SessionPlugin.__new__(SessionPlugin)
        await plugin.on_session_end("sid", {})


# ── Execute fallback tests ──────────────────────────────────────────


class TestSessionPluginExecuteFallback:
    """Test SessionPlugin.execute() one-shot fallback."""

    @pytest.mark.asyncio
    async def test_execute_runs_session_lifecycle(self):
        """execute() should call on_session_start, on_message, on_session_end."""
        plugin = DummySessionPlugin()
        events = []
        async for event in plugin.execute({"echo": True}):
            events.append(event)

        assert len(events) == 1
        assert events[0].type == "result"
        assert events[0].data["counter"] == 1


# ── Message protocol tests ──────────────────────────────────────────


class TestSessionMessageProtocol:
    """Test message protocol format validation."""

    def test_client_message_format(self):
        """Client messages should have type and data fields."""
        msg = {"type": "message", "data": {"command": "ls -la"}}
        assert msg["type"] == "message"
        assert "command" in msg["data"]

    def test_ping_message_format(self):
        """Ping message should have type field."""
        msg = {"type": "ping"}
        assert msg["type"] == "ping"

    def test_server_event_format(self):
        """Server events should wrap PluginEvent in type/data."""
        event = PluginEvent(type="result", data={"output": "hello"})
        server_msg = {
            "type": "event",
            "data": {"type": event.type, "data": event.data},
        }
        assert server_msg["type"] == "event"
        assert server_msg["data"]["type"] == "result"
        assert server_msg["data"]["data"]["output"] == "hello"

    def test_error_event_format(self):
        """Error messages should have type='error' and data.error."""
        msg = {"type": "error", "data": {"error": "something went wrong"}}
        assert msg["type"] == "error"
        assert "error" in msg["data"]

    def test_session_end_format(self):
        """Session end messages should have reason field."""
        msg = {"type": "session_end", "data": {"reason": "timeout"}}
        assert msg["type"] == "session_end"
        assert msg["data"]["reason"] == "timeout"


# ── State serialization tests ────────────────────────────────────────


class TestSessionStateSerialization:
    """Test state JSON serialization/deserialization."""

    def test_simple_state_roundtrip(self):
        """Simple dict state should survive JSON roundtrip."""
        state = {"counter": 5, "cwd": "/tmp", "active": True}
        serialized = json.dumps(state)
        deserialized = json.loads(serialized)
        assert deserialized == state

    def test_nested_state_roundtrip(self):
        """Nested state should survive JSON roundtrip."""
        state = {
            "connection": {"url": "http://example.com", "password": "test"},
            "history": ["cmd1", "cmd2"],
            "counter": 3,
        }
        serialized = json.dumps(state)
        deserialized = json.loads(serialized)
        assert deserialized == state

    def test_empty_state_roundtrip(self):
        """Empty state should serialize correctly."""
        state = {}
        serialized = json.dumps(state)
        deserialized = json.loads(serialized)
        assert deserialized == state


# ── WebShell session tests ───────────────────────────────────────────


class TestWebShellSessionStart:
    """Test WebShell plugin on_session_start."""

    @pytest.mark.asyncio
    async def test_session_start_returns_state(self):
        """on_session_start should return connection state."""
        WebShellPlugin = _load_webshell_class()
        if WebShellPlugin is None:
            pytest.skip("webshell plugin not loadable")

        plugin = WebShellPlugin()
        state = await plugin.on_session_start(
            {
                "url": "http://target.com/shell.php",
                "password": "cmd",
                "shell_type": "php_eval",
                "timeout": 10,
            }
        )
        assert state["url"] == "http://target.com/shell.php"
        assert state["password"] == "cmd"
        assert state["shell_type"] == "php_eval"
        assert state["timeout"] == 10
        assert state["cwd"] == "/"

    @pytest.mark.asyncio
    async def test_session_start_defaults(self):
        """on_session_start should use defaults for missing params."""
        WebShellPlugin = _load_webshell_class()
        if WebShellPlugin is None:
            pytest.skip("webshell plugin not loadable")

        plugin = WebShellPlugin()
        state = await plugin.on_session_start({"url": "http://x.com/s.php", "password": "p"})
        assert state["shell_type"] == "php_eval"
        assert state["timeout"] == 15
        assert state["cwd"] == "/"


class TestWebShellCommandDispatch:
    """Test WebShell command dispatch logic in on_message."""

    @pytest.mark.asyncio
    async def test_cd_updates_cwd(self):
        """cd command should update state cwd."""
        WebShellPlugin = _load_webshell_class()
        if WebShellPlugin is None:
            pytest.skip("webshell plugin not loadable")

        plugin = WebShellPlugin()
        state = {
            "url": "http://target.com/shell.php",
            "password": "cmd",
            "shell_type": "php_eval",
            "timeout": 15,
            "cwd": "/",
        }

        events = []
        async for event in plugin.on_message("sid", {"command": "cd /tmp"}, state):
            events.append(event)

        assert state["cwd"] == "/tmp"
        assert len(events) == 1
        assert events[0].type == "result"
        assert "/tmp" in events[0].data["output"]

    @pytest.mark.asyncio
    async def test_cd_relative_path(self):
        """cd with relative path should append to cwd."""
        WebShellPlugin = _load_webshell_class()
        if WebShellPlugin is None:
            pytest.skip("webshell plugin not loadable")

        plugin = WebShellPlugin()
        state = {
            "url": "http://target.com/shell.php",
            "password": "cmd",
            "shell_type": "php_eval",
            "timeout": 15,
            "cwd": "/var",
        }

        events = []
        async for event in plugin.on_message("sid", {"command": "cd www"}, state):
            events.append(event)

        assert state["cwd"] == "/var/www"

    @pytest.mark.asyncio
    async def test_empty_command_error(self):
        """Empty command should yield error event."""
        WebShellPlugin = _load_webshell_class()
        if WebShellPlugin is None:
            pytest.skip("webshell plugin not loadable")

        plugin = WebShellPlugin()
        state = {
            "url": "http://target.com/shell.php",
            "password": "cmd",
            "shell_type": "php_eval",
            "timeout": 15,
            "cwd": "/",
        }

        events = []
        async for event in plugin.on_message("sid", {"command": ""}, state):
            events.append(event)

        assert len(events) == 1
        assert events[0].type == "error"


# ── DummySessionPlugin integration tests ─────────────────────────────


class TestDummySessionPlugin:
    """Integration tests using DummySessionPlugin."""

    @pytest.mark.asyncio
    async def test_session_lifecycle(self):
        """Full session lifecycle: start → messages → end."""
        plugin = DummySessionPlugin()

        # Start
        state = await plugin.on_session_start({"echo": True})
        assert state["counter"] == 0

        # Message 1
        events = []
        async for event in plugin.on_message("sid", {"command": "hello"}, state):
            events.append(event)
        assert state["counter"] == 1
        assert events[0].data["output"] == "echo: hello"

        # Message 2
        events = []
        async for event in plugin.on_message("sid", {"command": "world"}, state):
            events.append(event)
        assert state["counter"] == 2

        # End
        await plugin.on_session_end("sid", state)

    @pytest.mark.asyncio
    async def test_error_in_message(self):
        """Error command should yield error event without crashing."""
        plugin = DummySessionPlugin()
        state = await plugin.on_session_start({})

        events = []
        async for event in plugin.on_message("sid", {"command": "error"}, state):
            events.append(event)

        assert events[0].type == "error"
        assert events[0].data["error"] == "test error"

    @pytest.mark.asyncio
    async def test_state_persists_across_messages(self):
        """State mutations should persist across on_message calls."""
        plugin = DummySessionPlugin()
        state = await plugin.on_session_start({})

        for i in range(5):
            async for _ in plugin.on_message("sid", {"command": f"cmd{i}"}, state):
                pass

        assert state["counter"] == 5

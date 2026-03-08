"""Local testing utilities for NetKitX plugins.

Allows developers to run and assert plugin behaviour without a running
NetKitX instance.

Example::

    import asyncio
    from netkitx_sdk.testing import run_plugin, collect_results

    from my_plugin.main import Plugin

    async def test_basic():
        events = await run_plugin(Plugin(), {"target": "127.0.0.1"})
        results = collect_results(events)
        assert len(results) > 0
        assert results[0]["host"] == "127.0.0.1"

    asyncio.run(test_basic())

Or with pytest-asyncio::

    import pytest
    from netkitx_sdk.testing import run_plugin, collect_results

    @pytest.mark.asyncio
    async def test_basic():
        events = await run_plugin(Plugin(), {"target": "127.0.0.1"})
        assert collect_results(events)
"""

from __future__ import annotations

from typing import Any

from netkitx_sdk.base import PluginBase, PluginEvent


async def run_plugin(
    plugin: PluginBase,
    params: dict[str, Any],
    *,
    validate: bool = True,
) -> list[PluginEvent]:
    """Run a plugin locally and return all emitted events.

    Args:
        plugin:   An instantiated PluginBase subclass.
        params:   Input parameters dict.
        validate: If True (default), call validate_params() before execute().

    Returns:
        List of all PluginEvent objects emitted by the plugin.

    Raises:
        ValueError: If validate=True and validate_params() raises.
        Exception:  Any exception raised inside execute().
    """
    if validate:
        params = await plugin.validate_params(params)

    events: list[PluginEvent] = []
    try:
        async for event in plugin.execute(params):
            events.append(event)
    finally:
        await plugin.cleanup()

    return events


def collect_results(events: list[PluginEvent]) -> list[dict[str, Any]]:
    """Extract result rows from a list of events.

    Args:
        events: The list returned by run_plugin().

    Returns:
        List of data dicts from all events with type == "result".
    """
    return [e.data for e in events if e.type == "result"]


def collect_logs(events: list[PluginEvent]) -> list[str]:
    """Extract log messages from a list of events.

    Args:
        events: The list returned by run_plugin().

    Returns:
        List of message strings from all events with type == "log".
    """
    return [e.data.get("msg", str(e.data)) for e in events if e.type == "log"]


def last_progress(events: list[PluginEvent]) -> int | None:
    """Return the percent value of the last progress event, or None.

    Useful for asserting that a plugin reports 100% on success::

        assert last_progress(events) == 100
    """
    for e in reversed(events):
        if e.type == "progress":
            return e.data.get("percent")
    return None


def has_error(events: list[PluginEvent]) -> bool:
    """Return True if any error event was emitted."""
    return any(e.type == "error" for e in events)

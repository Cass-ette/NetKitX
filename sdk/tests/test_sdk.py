"""Tests for netkitx-sdk."""
import pytest

from netkitx_sdk import PluginBase, PluginEvent, PluginMeta
from netkitx_sdk.testing import (
    collect_logs,
    collect_results,
    has_error,
    last_progress,
    run_plugin,
)


# ── fixture plugins ──────────────────────────────────────────────────────────

class OkPlugin(PluginBase):
    meta = PluginMeta(
        name="ok-plugin",
        version="1.0.0",
        description="Always succeeds",
        category="recon",
    )

    async def execute(self, params):
        yield PluginEvent("log", {"msg": "starting"})
        yield PluginEvent("progress", {"percent": 50})
        yield PluginEvent("result", {"host": params["target"], "alive": True})
        yield PluginEvent("progress", {"percent": 100})


class ErrorPlugin(PluginBase):
    meta = PluginMeta(
        name="error-plugin",
        version="1.0.0",
        description="Always emits error",
        category="recon",
    )

    async def execute(self, params):
        yield PluginEvent("error", {"error": "something went wrong"})


class ValidatingPlugin(PluginBase):
    meta = PluginMeta(
        name="validating-plugin",
        version="1.0.0",
        description="Validates params",
        category="recon",
    )

    async def validate_params(self, params):
        if not params.get("target"):
            raise ValueError("target is required")
        return params

    async def execute(self, params):
        yield PluginEvent("result", {"host": params["target"]})


class CleanupPlugin(PluginBase):
    meta = PluginMeta(
        name="cleanup-plugin",
        version="1.0.0",
        description="Tracks cleanup calls",
        category="recon",
    )
    cleaned_up = False

    async def execute(self, params):
        yield PluginEvent("result", {"done": True})

    async def cleanup(self):
        CleanupPlugin.cleaned_up = True


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_plugin_returns_all_events():
    events = await run_plugin(OkPlugin(), {"target": "10.0.0.1"})
    assert len(events) == 4
    types = [e.type for e in events]
    assert types == ["log", "progress", "result", "progress"]


@pytest.mark.asyncio
async def test_collect_results():
    events = await run_plugin(OkPlugin(), {"target": "10.0.0.1"})
    results = collect_results(events)
    assert len(results) == 1
    assert results[0] == {"host": "10.0.0.1", "alive": True}


@pytest.mark.asyncio
async def test_collect_logs():
    events = await run_plugin(OkPlugin(), {"target": "10.0.0.1"})
    logs = collect_logs(events)
    assert logs == ["starting"]


@pytest.mark.asyncio
async def test_last_progress():
    events = await run_plugin(OkPlugin(), {"target": "10.0.0.1"})
    assert last_progress(events) == 100


@pytest.mark.asyncio
async def test_has_error_false():
    events = await run_plugin(OkPlugin(), {"target": "10.0.0.1"})
    assert not has_error(events)


@pytest.mark.asyncio
async def test_has_error_true():
    events = await run_plugin(ErrorPlugin(), {"target": "x"})
    assert has_error(events)


@pytest.mark.asyncio
async def test_validate_params_called():
    events = await run_plugin(ValidatingPlugin(), {"target": "192.168.1.1"})
    assert collect_results(events)[0]["host"] == "192.168.1.1"


@pytest.mark.asyncio
async def test_validate_params_raises():
    with pytest.raises(ValueError, match="target is required"):
        await run_plugin(ValidatingPlugin(), {})


@pytest.mark.asyncio
async def test_validate_skip():
    # validate=False skips validate_params — error comes from execute(), not validate_params()
    with pytest.raises(KeyError):
        await run_plugin(ValidatingPlugin(), {}, validate=False)


@pytest.mark.asyncio
async def test_cleanup_called():
    CleanupPlugin.cleaned_up = False
    await run_plugin(CleanupPlugin(), {})
    assert CleanupPlugin.cleaned_up


def test_plugin_event_defaults():
    e = PluginEvent(type="log")
    assert e.data == {}


def test_plugin_meta_defaults():
    m = PluginMeta(name="x", version="1.0.0", description="d", category="recon")
    assert m.engine == "python"
    assert m.params == []
    assert m.output == {}

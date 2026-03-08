# NetKitX SDK

Base classes and local testing utilities for [NetKitX](https://github.com/Cass-ette/NetKitX) plugin development.

## Install

```bash
pip install netkitx-sdk
```

With testing extras:

```bash
pip install "netkitx-sdk[testing]"
```

## Quick Start

### 1. Write your plugin

```python
# my_plugin/main.py
from netkitx_sdk import PluginBase, PluginEvent, PluginMeta

class Plugin(PluginBase):
    meta = PluginMeta(
        name="my-plugin",
        version="1.0.0",
        description="Does something useful",
        category="recon",
    )

    async def execute(self, params):
        target = params["target"]
        yield PluginEvent("progress", {"percent": 0, "msg": f"Scanning {target}..."})
        # ... your logic ...
        yield PluginEvent("result", {"host": target, "alive": True})
        yield PluginEvent("progress", {"percent": 100})
```

### 2. Write tests

```python
# tests/test_my_plugin.py
import pytest
from netkitx_sdk.testing import run_plugin, collect_results, last_progress

from my_plugin.main import Plugin

@pytest.mark.asyncio
async def test_basic():
    events = await run_plugin(Plugin(), {"target": "127.0.0.1"})
    results = collect_results(events)
    assert len(results) == 1
    assert results[0]["host"] == "127.0.0.1"
    assert last_progress(events) == 100
```

### 3. Run tests locally

```bash
pytest tests/ -v
```

### 4. Upload to NetKitX

```bash
zip my-plugin.zip plugin.yaml main.py
# Then upload via the Plugins page, or use netkitx-cli
```

## API Reference

### `PluginBase`

Abstract base class. Subclass it and implement `execute()`.

| Method | Required | Description |
|--------|----------|-------------|
| `execute(params)` | ✅ | Async generator, yield `PluginEvent` objects |
| `validate_params(params)` | ❌ | Validate/transform params before execution |
| `cleanup()` | ❌ | Release resources, called even on error |

### `PluginEvent`

```python
PluginEvent(type="progress", data={"percent": 50, "msg": "Half done"})
PluginEvent(type="result",   data={"host": "10.0.0.1", "port": 80})
PluginEvent(type="log",      data={"msg": "Connecting..."})
PluginEvent(type="error",    data={"error": "Connection refused"})
```

### `PluginMeta`

```python
PluginMeta(
    name="my-plugin",       # unique identifier, matches plugin.yaml
    version="1.0.0",        # SemVer
    description="...",
    category="recon",       # recon | vuln | exploit | utils
)
```

### Testing helpers

```python
from netkitx_sdk.testing import (
    run_plugin,       # run plugin, return list[PluginEvent]
    collect_results,  # filter type=="result" → list[dict]
    collect_logs,     # filter type=="log"    → list[str]
    last_progress,    # last progress percent → int | None
    has_error,        # any error event?      → bool
)
```

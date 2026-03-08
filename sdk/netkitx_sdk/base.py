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
        """Release resources after execution (called even on error)."""

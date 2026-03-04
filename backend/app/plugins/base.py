from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class PluginEvent:
    type: str  # "progress" | "result" | "error" | "log"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginMeta:
    name: str
    version: str
    description: str
    category: str  # recon | vuln | exploit | utils
    engine: str  # python | go | cli
    params: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """Base class for all NetKitX plugins."""

    meta: PluginMeta

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        """Execute the plugin. Yield events for real-time progress updates."""
        ...

    async def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize input parameters. Override for custom validation."""
        return params

    async def cleanup(self) -> None:
        """Cleanup resources after execution. Override if needed."""
        pass

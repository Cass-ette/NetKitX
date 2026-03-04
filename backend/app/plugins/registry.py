from typing import Any

from app.plugins.base import PluginBase, PluginMeta


class PluginRegistry:
    """Central registry for all loaded plugins."""

    def __init__(self):
        self._plugins: dict[str, PluginBase] = {}
        self._meta: dict[str, PluginMeta] = {}

    def register(self, plugin: PluginBase) -> None:
        self._plugins[plugin.meta.name] = plugin
        self._meta[plugin.meta.name] = plugin.meta

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)
        self._meta.pop(name, None)

    def get(self, name: str) -> PluginBase | None:
        return self._plugins.get(name)

    def get_meta(self, name: str) -> PluginMeta | None:
        return self._meta.get(name)

    def list_all(self) -> list[PluginMeta]:
        return list(self._meta.values())

    def list_by_category(self, category: str) -> list[PluginMeta]:
        return [m for m in self._meta.values() if m.category == category]


registry = PluginRegistry()

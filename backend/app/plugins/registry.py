from app.plugins.base import PluginBase, PluginMeta


class PluginRegistry:
    """Central registry for all loaded plugins."""

    def __init__(self):
        self._plugins: dict[str, PluginBase] = {}
        self._meta: dict[str, PluginMeta] = {}
        self._disabled: set[str] = set()

    def register(self, plugin: PluginBase) -> None:
        """Register a plugin and its metadata."""
        self._plugins[plugin.meta.name] = plugin
        self._meta[plugin.meta.name] = plugin.meta

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry."""
        self._plugins.pop(name, None)
        self._meta.pop(name, None)
        self._disabled.discard(name)

    def get(self, name: str) -> PluginBase | None:
        """Get a plugin instance by name."""
        return self._plugins.get(name)

    def get_meta(self, name: str) -> PluginMeta | None:
        """Get plugin metadata by name."""
        return self._meta.get(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is registered and enabled."""
        return name in self._meta and name not in self._disabled

    def set_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a registered plugin."""
        if name not in self._meta:
            return
        if enabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)

    def list_all(self) -> list[PluginMeta]:
        """Return metadata for all registered plugins."""
        return list(self._meta.values())

    def list_enabled(self) -> list[PluginMeta]:
        """Return metadata for enabled plugins only."""
        return [m for m in self._meta.values() if m.name not in self._disabled]

    def list_by_category(self, category: str) -> list[PluginMeta]:
        """Return metadata for plugins in a specific category."""
        return [m for m in self._meta.values() if m.category == category]


registry = PluginRegistry()

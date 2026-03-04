from app.plugins.registry import registry
from app.plugins.base import PluginMeta


def list_available_plugins() -> list[PluginMeta]:
    return registry.list_all()


def get_plugin_meta(name: str) -> PluginMeta | None:
    return registry.get_meta(name)

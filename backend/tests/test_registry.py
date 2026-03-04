"""Test plugin registry."""

from app.plugins.registry import PluginRegistry
from app.plugins.base import PluginBase, PluginMeta


class DummyPlugin(PluginBase):
    """Dummy plugin for testing."""

    meta = PluginMeta(
        name="test-plugin",
        version="1.0.0",
        description="Test plugin",
        category="utils",
        engine="python",
    )

    async def execute(self, params):
        yield


def test_registry_register():
    """Test plugin registration."""
    registry = PluginRegistry()
    plugin = DummyPlugin()

    registry.register(plugin)

    assert registry.get("test-plugin") == plugin
    assert registry.get_meta("test-plugin") == plugin.meta
    assert len(registry.list_all()) == 1


def test_registry_unregister():
    """Test plugin unregistration."""
    registry = PluginRegistry()
    plugin = DummyPlugin()

    registry.register(plugin)
    registry.unregister("test-plugin")

    assert registry.get("test-plugin") is None
    assert registry.get_meta("test-plugin") is None
    assert len(registry.list_all()) == 0


def test_registry_enabled_state():
    """Test plugin enabled/disabled state."""
    registry = PluginRegistry()
    plugin = DummyPlugin()

    registry.register(plugin)
    assert registry.is_enabled("test-plugin") is True

    registry.set_enabled("test-plugin", False)
    assert registry.is_enabled("test-plugin") is False
    assert len(registry.list_enabled()) == 0

    registry.set_enabled("test-plugin", True)
    assert registry.is_enabled("test-plugin") is True
    assert len(registry.list_enabled()) == 1

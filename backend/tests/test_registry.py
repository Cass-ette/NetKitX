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


def test_meta_ui_component_default():
    """Test that ui_component defaults to None."""
    meta = PluginMeta(
        name="no-ui",
        version="1.0.0",
        description="Plugin without custom UI",
        category="utils",
    )
    assert meta.ui_component is None


def test_meta_ui_component_set():
    """Test that ui_component can be set."""
    meta = PluginMeta(
        name="chart-plugin",
        version="1.0.0",
        description="Plugin with chart UI",
        category="recon",
        ui_component="chart",
    )
    assert meta.ui_component == "chart"


def test_registry_preserves_ui_component():
    """Test that registry preserves ui_component after registration."""

    class ChartPlugin(PluginBase):
        meta = PluginMeta(
            name="chart-test",
            version="1.0.0",
            description="Chart test",
            category="recon",
            ui_component="chart",
        )

        async def execute(self, params):
            yield

    registry = PluginRegistry()
    plugin = ChartPlugin()
    registry.register(plugin)

    retrieved_meta = registry.get_meta("chart-test")
    assert retrieved_meta is not None
    assert retrieved_meta.ui_component == "chart"

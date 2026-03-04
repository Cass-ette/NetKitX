import importlib
import importlib.util
import logging
from pathlib import Path

import yaml

from app.plugins.base import PluginBase, PluginMeta
from app.plugins.registry import registry

logger = logging.getLogger(__name__)


def load_plugin_meta(plugin_dir: Path) -> PluginMeta | None:
    """Load plugin metadata from plugin.yaml."""
    yaml_path = plugin_dir / "plugin.yaml"
    if not yaml_path.exists():
        logger.warning(f"No plugin.yaml found in {plugin_dir}")
        return None

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    return PluginMeta(
        name=config["name"],
        version=config.get("version", "0.0.1"),
        description=config.get("description", ""),
        category=config.get("category", "utils"),
        engine=config.get("engine", "python"),
        params=config.get("params", []),
        output=config.get("output", {}),
    )


def load_python_plugin(plugin_dir: Path) -> PluginBase | None:
    """Dynamically load a Python plugin from its directory."""
    main_file = plugin_dir / "main.py"
    if not main_file.exists():
        logger.warning(f"No main.py found in {plugin_dir}")
        return None

    spec = importlib.util.spec_from_file_location(
        f"plugins.{plugin_dir.name}", main_file
    )
    if not spec or not spec.loader:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find the PluginBase subclass in the module
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, PluginBase)
            and attr is not PluginBase
        ):
            return attr()
    return None


def load_all_plugins(plugins_dir: str) -> int:
    """Load all plugins from the plugins directory. Returns count loaded."""
    plugins_path = Path(plugins_dir)
    if not plugins_path.exists():
        logger.warning(f"Plugins directory not found: {plugins_dir}")
        return 0

    count = 0
    for plugin_dir in plugins_path.iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue

        meta = load_plugin_meta(plugin_dir)
        if not meta:
            continue

        if meta.engine == "python":
            plugin = load_python_plugin(plugin_dir)
            if plugin:
                plugin.meta = meta
                registry.register(plugin)
                logger.info(f"Loaded plugin: {meta.name} v{meta.version}")
                count += 1
        else:
            # For go/cli engines, register meta only — execution handled differently
            logger.info(f"Registered external plugin: {meta.name} ({meta.engine})")
            count += 1

    return count

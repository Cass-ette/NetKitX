import logging
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import settings
from app.plugins.loader import load_single_plugin
from app.plugins.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".txt"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("")
async def list_plugins():
    """List all registered plugins with enabled status."""
    return [
        {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "category": m.category,
            "engine": m.engine,
            "enabled": registry.is_enabled(m.name),
        }
        for m in registry.list_all()
    ]


@router.get("/categories")
async def list_categories():
    """List plugin categories with counts."""
    metas = registry.list_all()
    cats: dict[str, int] = {}
    for m in metas:
        cats[m.category] = cats.get(m.category, 0) + 1
    return cats


@router.get("/{name}")
async def get_plugin(name: str):
    """Get plugin details."""
    meta = registry.get_meta(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "category": meta.category,
        "engine": meta.engine,
        "params": meta.params,
        "output": meta.output,
        "enabled": registry.is_enabled(meta.name),
    }


@router.post("/upload")
async def upload_plugin(file: UploadFile):
    """Upload a plugin zip file, extract and hot-load it."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")

    # Validate zip contents
    names = zf.namelist()
    for name in names:
        # Block path traversal
        if ".." in name or name.startswith("/"):
            raise HTTPException(status_code=400, detail=f"Invalid path in zip: {name}")
        # Only allow safe file extensions (skip directories)
        if not name.endswith("/"):
            suffix = Path(name).suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Disallowed file type: {name} (allowed: {', '.join(ALLOWED_EXTENSIONS)})",
                )

    # Find plugin.yaml — at root or one level deep
    yaml_path = None
    for name in names:
        basename = Path(name).name
        depth = len(Path(name).parts)
        if basename == "plugin.yaml" and depth <= 2:
            yaml_path = name
            break

    if not yaml_path:
        raise HTTPException(
            status_code=400,
            detail="Zip must contain plugin.yaml at root or one level deep",
        )

    # Determine extraction target
    plugins_dir = Path(settings.PLUGINS_DIR)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # If plugin.yaml is at root level (depth 1), use zip filename as dir name
    # If one level deep (depth 2), use that parent directory name
    yaml_parts = Path(yaml_path).parts
    if len(yaml_parts) == 1:
        # plugin.yaml at root — use zip filename (without .zip) as directory
        dirname = Path(file.filename).stem
    else:
        dirname = yaml_parts[0]

    target_dir = plugins_dir / dirname

    # Clean up existing directory if re-uploading
    if target_dir.exists():
        # Unregister old plugin first
        from app.plugins.loader import load_plugin_meta

        old_meta = load_plugin_meta(target_dir)
        if old_meta:
            registry.unregister(old_meta.name)
        shutil.rmtree(target_dir)

    # Extract
    if len(yaml_parts) == 1:
        # Root-level files: extract into dirname/
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            if name.endswith("/"):
                (target_dir / name).mkdir(parents=True, exist_ok=True)
            else:
                member_path = target_dir / name
                member_path.parent.mkdir(parents=True, exist_ok=True)
                member_path.write_bytes(zf.read(name))
    else:
        # Already has directory structure: extract directly
        zf.extractall(plugins_dir)

    zf.close()

    # Hot-load the plugin
    if not load_single_plugin(target_dir, settings.ENGINES_DIR):
        shutil.rmtree(target_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Failed to load plugin from uploaded zip")

    from app.plugins.loader import load_plugin_meta

    meta = load_plugin_meta(target_dir)
    return {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "category": meta.category,
        "engine": meta.engine,
        "enabled": True,
    }


@router.patch("/{name}")
async def toggle_plugin(name: str, body: dict):
    """Enable or disable a plugin."""
    meta = registry.get_meta(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Missing 'enabled' field")

    registry.set_enabled(name, bool(enabled))
    return {"name": name, "enabled": registry.is_enabled(name)}


@router.delete("/{name}")
async def delete_plugin(name: str):
    """Unregister and delete a plugin."""
    meta = registry.get_meta(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    registry.unregister(name)

    # Find and delete the plugin directory
    plugins_dir = Path(settings.PLUGINS_DIR)
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        yaml_path = plugin_dir / "plugin.yaml"
        if yaml_path.exists():
            import yaml

            with open(yaml_path) as f:
                config = yaml.safe_load(f)
            if config and config.get("name") == name:
                shutil.rmtree(plugin_dir)
                logger.info(f"Deleted plugin directory: {plugin_dir}")
                break

    return {"deleted": name}

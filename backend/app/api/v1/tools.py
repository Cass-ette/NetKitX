from fastapi import APIRouter, HTTPException

from app.plugins.registry import registry

router = APIRouter()


@router.get("")
async def list_tools():
    """List all available tools (enabled plugins only)."""
    return [
        {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "category": m.category,
            "engine": m.engine,
            "mode": m.mode,
            "ui_component": m.ui_component,
            "params": m.params,
            "output": m.output,
        }
        for m in registry.list_enabled()
    ]


@router.get("/{name}")
async def get_tool(name: str):
    """Get a specific tool's metadata."""
    meta = registry.get_meta(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    if not registry.is_enabled(name):
        raise HTTPException(status_code=404, detail=f"Tool '{name}' is disabled")
    return {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "category": meta.category,
        "engine": meta.engine,
        "mode": meta.mode,
        "ui_component": meta.ui_component,
        "params": meta.params,
        "output": meta.output,
    }

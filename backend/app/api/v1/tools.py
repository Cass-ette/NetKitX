from fastapi import APIRouter, HTTPException

from app.plugins.registry import registry

router = APIRouter()


@router.get("")
async def list_tools():
    """List all available tools (plugin metadata)."""
    return [
        {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "category": m.category,
            "engine": m.engine,
            "params": m.params,
            "output": m.output,
        }
        for m in registry.list_all()
    ]


@router.get("/{name}")
async def get_tool(name: str):
    """Get a specific tool's metadata."""
    meta = registry.get_meta(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    return {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "category": meta.category,
        "engine": meta.engine,
        "params": meta.params,
        "output": meta.output,
    }

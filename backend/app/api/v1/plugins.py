from fastapi import APIRouter, HTTPException

from app.plugins.registry import registry

router = APIRouter()


@router.get("")
async def list_plugins():
    """List all registered plugins."""
    return [
        {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "category": m.category,
            "engine": m.engine,
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
    }

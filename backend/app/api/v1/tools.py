from fastapi import APIRouter, HTTPException

from app.plugins.registry import registry

router = APIRouter()


@router.get("")
async def list_tools():
    """
    Retrieve metadata for all enabled tools.
    
    Returns:
        tools (list[dict]): List of metadata dictionaries for each enabled tool. Each dictionary contains the keys
            `name`, `version`, `description`, `category`, `engine`, `mode`, `params`, and `output`.
    """
    return [
        {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "category": m.category,
            "engine": m.engine,
            "mode": m.mode,
            "params": m.params,
            "output": m.output,
        }
        for m in registry.list_enabled()
    ]


@router.get("/{name}")
async def get_tool(name: str):
    """
    Retrieve metadata for a tool identified by name.
    
    Returns:
        metadata (dict): Dictionary containing tool metadata with keys:
            - name: tool identifier
            - version: tool version string
            - description: human-readable description
            - category: tool category
            - engine: backend engine name
            - mode: operational mode
            - params: parameter schema or definition
            - output: output schema or definition
    
    Raises:
        HTTPException: 404 if the tool is not found or is disabled.
    """
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
        "params": meta.params,
        "output": meta.output,
    }

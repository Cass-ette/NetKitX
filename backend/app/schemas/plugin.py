from typing import Any

from pydantic import BaseModel


class PluginParam(BaseModel):
    name: str
    label: str = ""
    type: str = "string"
    required: bool = False
    default: Any = None
    options: list[str] | None = None
    placeholder: str = ""


class PluginResponse(BaseModel):
    name: str
    version: str
    description: str
    category: str
    engine: str
    params: list[PluginParam] = []
    output: dict[str, Any] = {}

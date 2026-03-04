from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskCreate(BaseModel):
    plugin_name: str
    params: dict[str, Any] = {}
    project_id: int | None = None


class TaskResponse(BaseModel):
    id: int
    plugin_name: str
    status: str
    params: dict[str, Any] | None
    result: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}

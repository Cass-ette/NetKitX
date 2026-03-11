"""Pydantic schemas for workflows."""

from datetime import datetime

from pydantic import BaseModel


class WorkflowNodeData(BaseModel):
    plugin: str | None = None
    command: str | None = None
    params: dict | None = None
    reason: str | None = None
    result_summary: str | None = None


class WorkflowNode(BaseModel):
    id: str
    type: str  # action-plugin | action-shell | start | end
    label: str
    data: WorkflowNodeData = WorkflowNodeData()


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str


class WorkflowResponse(BaseModel):
    id: int
    user_id: int
    session_id: int | None = None
    name: str
    description: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: int
    name: str
    description: str
    session_id: int | None = None
    node_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowListItem]
    total: int

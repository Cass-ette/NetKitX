"""Admin API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── User ──────────────────────────────────────────────────────────────


class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    avatar_url: str | None = None
    max_concurrent_tasks: int = 5
    max_daily_tasks: int = 100
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRoleRequest(BaseModel):
    role: str


class SystemStatsResponse(BaseModel):
    total_users: int
    admin_users: int
    regular_users: int
    total_tasks: int
    total_plugins: int


# ── Task Management ──────────────────────────────────────────────────


class AdminTaskResponse(BaseModel):
    id: int
    plugin_name: str
    status: str
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    created_by: int | None = None
    created_by_username: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminTaskListResponse(BaseModel):
    tasks: list[AdminTaskResponse]
    total: int


# ── Plugin Management ────────────────────────────────────────────────


class AdminPluginResponse(BaseModel):
    name: str
    version: str
    description: str | None = None
    category: str
    engine: str
    enabled: bool
    usage_count: int = 0

    model_config = {"from_attributes": True}


# ── Audit Log ────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    target_type: str
    target_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int


# ── User Quotas ──────────────────────────────────────────────────────


class UserQuotaResponse(BaseModel):
    user_id: int
    username: str
    max_concurrent_tasks: int
    max_daily_tasks: int
    current_running_tasks: int
    tasks_today: int


class UpdateUserQuotaRequest(BaseModel):
    max_concurrent_tasks: int | None = None
    max_daily_tasks: int | None = None


# ── Announcements ────────────────────────────────────────────────────


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    type: str = "info"


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    type: str | None = None
    active: bool | None = None


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    type: str
    active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Server Status ────────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    name: str
    status: str  # ok | error
    detail: str | None = None


class ServerStatusResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    services: list[ServiceStatus]

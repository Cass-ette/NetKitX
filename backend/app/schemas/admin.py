"""Admin API schemas."""

from datetime import datetime

from pydantic import BaseModel


class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    avatar_url: str | None = None
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

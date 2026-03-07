"""Admin API endpoints."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_admin_user
from app.models.user import User
from app.schemas.admin import (
    AdminPluginResponse,
    AdminTaskListResponse,
    AdminTaskResponse,
    AnnouncementCreate,
    AnnouncementResponse,
    AnnouncementUpdate,
    AuditLogListResponse,
    AuditLogResponse,
    ServerStatusResponse,
    SystemStatsResponse,
    UpdateUserQuotaRequest,
    UpdateUserRoleRequest,
    UserListResponse,
    UserQuotaResponse,
)
from app.services.admin_service import (
    cancel_task,
    create_announcement,
    create_audit_log,
    delete_announcement,
    delete_task,
    delete_user,
    get_all_plugins_with_usage,
    get_all_tasks,
    get_all_users,
    get_announcements,
    get_audit_logs,
    get_server_status,
    get_system_stats,
    get_user_quota,
    get_username_map,
    toggle_plugin,
    update_announcement,
    update_user_quota,
    update_user_role,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Helper ───────────────────────────────────────────────────────────


async def _audit(
    session: AsyncSession,
    admin: User,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict | None = None,
):
    await create_audit_log(
        session,
        user_id=admin.id,
        username=admin.username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


# ── Users ────────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserListResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    return await get_all_users(session, limit, offset)


@router.patch("/users/{user_id}/role", response_model=UserListResponse)
async def change_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = await update_user_role(session, user_id, body.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await _audit(session, admin, "change_role", "user", str(user_id), {"new_role": body.role})
    return user


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    success = await delete_user(session, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    await _audit(session, admin, "delete_user", "user", str(user_id))
    return {"message": "User deleted"}


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    return await get_system_stats(session)


# ── Task Management ─────────────────────────────────────────────────


@router.get("/tasks", response_model=AdminTaskListResponse)
async def list_all_tasks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int | None = None,
    status: str | None = None,
    plugin_name: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    tasks, total = await get_all_tasks(
        session,
        limit=limit,
        offset=offset,
        user_id=user_id,
        status=status,
        plugin_name=plugin_name,
        date_from=date_from,
        date_to=date_to,
    )
    # Resolve usernames
    user_ids = list({t.created_by for t in tasks if t.created_by})
    umap = await get_username_map(session, user_ids)
    items = []
    for t in tasks:
        resp = AdminTaskResponse.model_validate(t)
        resp.created_by_username = umap.get(t.created_by) if t.created_by else None
        items.append(resp)
    return AdminTaskListResponse(tasks=items, total=total)


@router.post("/tasks/{task_id}/cancel")
async def admin_cancel_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    task = await cancel_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await _audit(session, admin, "cancel_task", "task", str(task_id))
    return {"message": "Task cancelled", "status": task.status}


@router.delete("/tasks/{task_id}")
async def admin_delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    success = await delete_task(session, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    await _audit(session, admin, "delete_task", "task", str(task_id))
    return {"message": "Task deleted"}


# ── Plugin Management ────────────────────────────────────────────────


@router.get("/plugins", response_model=list[AdminPluginResponse])
async def list_plugins(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    return await get_all_plugins_with_usage(session)


@router.patch("/plugins/{plugin_name}/toggle")
async def toggle_plugin_status(
    plugin_name: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    result = await toggle_plugin(session, plugin_name)
    if not result:
        raise HTTPException(status_code=404, detail="Plugin not found")
    await _audit(
        session,
        admin,
        "toggle_plugin",
        "plugin",
        plugin_name,
        {"enabled": result["enabled"]},
    )
    return result


# ── Audit Log ────────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    user_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    logs, total = await get_audit_logs(
        session, limit=limit, offset=offset, action=action, user_id=user_id
    )
    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
    )


# ── User Quotas ──────────────────────────────────────────────────────


@router.get("/users/{user_id}/quota", response_model=UserQuotaResponse)
async def get_quota(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    quota = await get_user_quota(session, user_id)
    if not quota:
        raise HTTPException(status_code=404, detail="User not found")
    return quota


@router.patch("/users/{user_id}/quota", response_model=UserQuotaResponse)
async def change_quota(
    user_id: int,
    body: UpdateUserQuotaRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    user = await update_user_quota(
        session, user_id, body.max_concurrent_tasks, body.max_daily_tasks
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await _audit(
        session,
        admin,
        "update_quota",
        "user",
        str(user_id),
        {
            "max_concurrent_tasks": body.max_concurrent_tasks,
            "max_daily_tasks": body.max_daily_tasks,
        },
    )

    quota = await get_user_quota(session, user_id)
    return quota


# ── Announcements ────────────────────────────────────────────────────


@router.post("/announcements", response_model=AnnouncementResponse, status_code=201)
async def create_ann(
    body: AnnouncementCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if body.type not in ("info", "warning", "error"):
        raise HTTPException(status_code=400, detail="Invalid type")
    ann = await create_announcement(
        session,
        title=body.title,
        content=body.content,
        type=body.type,
        created_by=admin.id,
    )
    await _audit(session, admin, "create_announcement", "announcement", str(ann.id))
    return ann


@router.get("/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    return await get_announcements(session, limit=limit, offset=offset)


@router.patch("/announcements/{ann_id}", response_model=AnnouncementResponse)
async def edit_announcement(
    ann_id: int,
    body: AnnouncementUpdate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    ann = await update_announcement(
        session,
        ann_id,
        title=body.title,
        content=body.content,
        type=body.type,
        active=body.active,
    )
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await _audit(session, admin, "update_announcement", "announcement", str(ann_id))
    return ann


@router.delete("/announcements/{ann_id}")
async def remove_announcement(
    ann_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    success = await delete_announcement(session, ann_id)
    if not success:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await _audit(session, admin, "delete_announcement", "announcement", str(ann_id))
    return {"message": "Announcement deleted"}


# ── Server Status ────────────────────────────────────────────────────


@router.get("/server-status", response_model=ServerStatusResponse)
async def server_status(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    return await get_server_status(session)

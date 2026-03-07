"""Admin service for user management, tasks, plugins, audit, quotas, announcements, server status."""

import datetime
import logging

import psutil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.announcement import Announcement
from app.models.audit_log import AuditLog
from app.models.plugin import Plugin
from app.models.task import Task
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Users ────────────────────────────────────────────────────────────


async def get_all_users(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return result.scalar() or 0


async def update_user_role(session: AsyncSession, user_id: int, new_role: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.role = new_role
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    return True


async def get_system_stats(session: AsyncSession) -> dict:
    total_users = await get_user_count(session)
    admin_count = (
        await session.execute(select(func.count(User.id)).where(User.role == "admin"))
    ).scalar() or 0
    total_tasks = (await session.execute(select(func.count(Task.id)))).scalar() or 0
    total_plugins = (await session.execute(select(func.count(Plugin.id)))).scalar() or 0
    return {
        "total_users": total_users,
        "admin_users": admin_count,
        "regular_users": total_users - admin_count,
        "total_tasks": total_tasks,
        "total_plugins": total_plugins,
    }


# ── Task Management ─────────────────────────────────────────────────


async def get_all_tasks(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    user_id: int | None = None,
    status: str | None = None,
    plugin_name: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> tuple[list[Task], int]:
    stmt = select(Task)
    count_stmt = select(func.count(Task.id))

    if user_id is not None:
        stmt = stmt.where(Task.created_by == user_id)
        count_stmt = count_stmt.where(Task.created_by == user_id)
    if status:
        stmt = stmt.where(Task.status == status)
        count_stmt = count_stmt.where(Task.status == status)
    if plugin_name:
        stmt = stmt.where(Task.plugin_name == plugin_name)
        count_stmt = count_stmt.where(Task.plugin_name == plugin_name)
    if date_from:
        dt = datetime.datetime.combine(date_from, datetime.time.min)
        stmt = stmt.where(Task.created_at >= dt)
        count_stmt = count_stmt.where(Task.created_at >= dt)
    if date_to:
        dt = datetime.datetime.combine(date_to, datetime.time.max)
        stmt = stmt.where(Task.created_at <= dt)
        count_stmt = count_stmt.where(Task.created_at <= dt)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def cancel_task(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return None
    if task.status in ("pending", "running"):
        task.status = "failed"
        task.result = task.result or {}
        task.result["error"] = "Cancelled by admin"
        task.finished_at = datetime.datetime.utcnow()
        await session.commit()
        await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: int) -> bool:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return False
    await session.delete(task)
    await session.commit()
    return True


async def get_username_map(session: AsyncSession, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    result = await session.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
    return dict(result.all())


# ── Plugin Management ────────────────────────────────────────────────


async def get_all_plugins_with_usage(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Plugin, func.count(Task.id).label("usage_count"))
        .outerjoin(Task, Task.plugin_name == Plugin.name)
        .group_by(Plugin.id)
        .order_by(Plugin.name)
    )
    rows = result.all()
    return [
        {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "category": plugin.category,
            "engine": plugin.engine,
            "enabled": plugin.enabled,
            "usage_count": usage_count,
        }
        for plugin, usage_count in rows
    ]


async def toggle_plugin(session: AsyncSession, plugin_name: str) -> dict | None:
    result = await session.execute(select(Plugin).where(Plugin.name == plugin_name))
    plugin = result.scalar_one_or_none()
    if not plugin:
        return None
    plugin.enabled = not plugin.enabled
    await session.commit()
    await session.refresh(plugin)
    return {"name": plugin.name, "enabled": plugin.enabled}


# ── Audit Log ────────────────────────────────────────────────────────


async def create_audit_log(
    session: AsyncSession,
    *,
    user_id: int,
    username: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    session.add(log)
    await session.commit()
    return log


async def get_audit_logs(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    user_id: int | None = None,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


# ── User Quotas ──────────────────────────────────────────────────────


async def get_user_quota(session: AsyncSession, user_id: int) -> dict | None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    running = (
        await session.execute(
            select(func.count(Task.id)).where(Task.created_by == user_id, Task.status == "running")
        )
    ).scalar() or 0

    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    today_count = (
        await session.execute(
            select(func.count(Task.id)).where(
                Task.created_by == user_id, Task.created_at >= today_start
            )
        )
    ).scalar() or 0

    return {
        "user_id": user.id,
        "username": user.username,
        "max_concurrent_tasks": user.max_concurrent_tasks,
        "max_daily_tasks": user.max_daily_tasks,
        "current_running_tasks": running,
        "tasks_today": today_count,
    }


async def update_user_quota(
    session: AsyncSession,
    user_id: int,
    max_concurrent: int | None = None,
    max_daily: int | None = None,
) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if max_concurrent is not None:
        user.max_concurrent_tasks = max_concurrent
    if max_daily is not None:
        user.max_daily_tasks = max_daily
    await session.commit()
    await session.refresh(user)
    return user


async def check_quota(session: AsyncSession, user_id: int) -> str | None:
    """Check if user has exceeded quota. Returns error message or None."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return "User not found"

    running = (
        await session.execute(
            select(func.count(Task.id)).where(Task.created_by == user_id, Task.status == "running")
        )
    ).scalar() or 0

    if running >= user.max_concurrent_tasks:
        return f"Concurrent task limit reached ({user.max_concurrent_tasks})"

    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    today_count = (
        await session.execute(
            select(func.count(Task.id)).where(
                Task.created_by == user_id, Task.created_at >= today_start
            )
        )
    ).scalar() or 0

    if today_count >= user.max_daily_tasks:
        return f"Daily task limit reached ({user.max_daily_tasks})"

    return None


# ── Announcements ────────────────────────────────────────────────────


async def create_announcement(
    session: AsyncSession,
    *,
    title: str,
    content: str,
    type: str,
    created_by: int,
) -> Announcement:
    ann = Announcement(
        title=title,
        content=content,
        type=type,
        created_by=created_by,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann


async def get_announcements(
    session: AsyncSession,
    *,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Announcement]:
    stmt = select(Announcement)
    if active_only:
        stmt = stmt.where(Announcement.active.is_(True))
    stmt = stmt.order_by(Announcement.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_announcement(
    session: AsyncSession,
    ann_id: int,
    **kwargs: object,
) -> Announcement | None:
    result = await session.execute(select(Announcement).where(Announcement.id == ann_id))
    ann = result.scalar_one_or_none()
    if not ann:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(ann, key):
            setattr(ann, key, value)
    await session.commit()
    await session.refresh(ann)
    return ann


async def delete_announcement(session: AsyncSession, ann_id: int) -> bool:
    result = await session.execute(select(Announcement).where(Announcement.id == ann_id))
    ann = result.scalar_one_or_none()
    if not ann:
        return False
    await session.delete(ann)
    await session.commit()
    return True


# ── Server Status ────────────────────────────────────────────────────


async def get_server_status(session: AsyncSession) -> dict:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    services: list[dict] = []

    # DB check
    try:
        await session.execute(select(func.now()))
        services.append({"name": "PostgreSQL", "status": "ok"})
    except Exception as e:
        services.append({"name": "PostgreSQL", "status": "error", "detail": str(e)})

    # Redis check
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        services.append({"name": "Redis", "status": "ok"})
    except Exception as e:
        services.append({"name": "Redis", "status": "error", "detail": str(e)})

    # Docker check
    try:
        import docker

        client = docker.from_env()
        client.ping()
        client.close()
        services.append({"name": "Docker", "status": "ok"})
    except Exception as e:
        services.append({"name": "Docker", "status": "error", "detail": str(e)})

    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / 1024 / 1024, 1),
        "memory_total_mb": round(mem.total / 1024 / 1024, 1),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
        "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
        "services": services,
    }

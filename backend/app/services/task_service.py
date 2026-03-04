from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


async def create_task(
    session: AsyncSession, plugin_name: str, params: dict, user_id: int, project_id: int | None = None
) -> Task:
    task = Task(
        plugin_name=plugin_name,
        params=params,
        created_by=user_id,
        project_id=project_id,
        status="pending",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def list_tasks(
    session: AsyncSession, user_id: int, status: str | None = None, limit: int = 50
) -> list[Task]:
    query = select(Task).where(Task.created_by == user_id).order_by(Task.created_at.desc()).limit(limit)
    if status:
        query = query.where(Task.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_task_status(
    session: AsyncSession, task_id: int, status: str, result: dict | None = None
) -> Task | None:
    task = await get_task(session, task_id)
    if not task:
        return None
    task.status = status
    if status == "running":
        task.started_at = datetime.now(timezone.utc)
    if status in ("done", "failed"):
        task.finished_at = datetime.now(timezone.utc)
    if result is not None:
        task.result = result
    await session.commit()
    await session.refresh(task)
    return task

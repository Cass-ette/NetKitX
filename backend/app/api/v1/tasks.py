import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session, async_session
from app.core.deps import get_current_user
from app.core.events import manager
from app.models.user import User
from app.plugins.registry import registry
from app.schemas.task import TaskCreate, TaskResponse
from app.services.task_service import create_task, get_task, list_tasks, update_task_status

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_plugin(task_id: int, plugin_name: str, params: dict):
    """Background coroutine that executes a plugin and pushes events via WebSocket."""
    tid = str(task_id)
    plugin = registry.get(plugin_name)

    if not plugin:
        async with async_session() as session:
            await update_task_status(
                session, task_id, "failed", {"error": f"Plugin '{plugin_name}' not found"}
            )
        await manager.send_event(tid, {"type": "error", "data": {"error": "Plugin not found"}})
        return

    # Mark running
    async with async_session() as session:
        await update_task_status(session, task_id, "running")
    await manager.send_event(tid, {"type": "status", "data": {"status": "running"}})

    try:
        results = []
        logs = []
        async for event in plugin.execute(params):
            await manager.send_event(tid, {"type": event.type, "data": event.data})
            if event.type == "result":
                results.append(event.data)
            elif event.type == "log":
                logs.append(event.data.get("msg", str(event.data)))
            elif event.type == "error":
                async with async_session() as session:
                    await update_task_status(session, task_id, "failed", {"error": event.data})
                return

        async with async_session() as session:
            await update_task_status(session, task_id, "done", {"items": results, "logs": logs})
        await manager.send_event(
            tid, {"type": "status", "data": {"status": "done", "items_count": len(results)}}
        )

    except Exception as e:
        logger.exception(f"Plugin '{plugin_name}' failed for task {task_id}")
        async with async_session() as session:
            await update_task_status(session, task_id, "failed", {"error": str(e)})
        await manager.send_event(tid, {"type": "error", "data": {"error": str(e)}})


@router.post("", response_model=TaskResponse, status_code=201)
async def create(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Verify plugin exists
    if not registry.get_meta(body.plugin_name):
        raise HTTPException(status_code=404, detail=f"Plugin '{body.plugin_name}' not found")

    # Check user quota
    from app.services.admin_service import check_quota

    quota_error = await check_quota(session, user.id)
    if quota_error:
        raise HTTPException(status_code=429, detail=quota_error)

    task = await create_task(session, body.plugin_name, body.params, user.id, body.project_id)

    # Dispatch as background asyncio task
    asyncio.create_task(_run_plugin(task.id, body.plugin_name, body.params))

    return task


@router.get("", response_model=list[TaskResponse])
async def list_all(
    status: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_tasks(session, user.id, status=status)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_one(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await get_task(session, task_id)
    if not task or task.created_by != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/logs")
async def get_logs(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return historical logs for a completed or running task."""
    task = await get_task(session, task_id)
    if not task or task.created_by != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    logs = (task.result or {}).get("logs", [])
    return {"task_id": task_id, "status": task.status, "logs": logs}

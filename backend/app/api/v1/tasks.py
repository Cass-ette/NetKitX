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
        async for event in plugin.execute(params):
            await manager.send_event(tid, {"type": event.type, "data": event.data})
            if event.type == "result":
                results.append(event.data)
            elif event.type == "error":
                async with async_session() as session:
                    await update_task_status(session, task_id, "failed", {"error": event.data})
                return

        async with async_session() as session:
            await update_task_status(session, task_id, "done", {"items": results})
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

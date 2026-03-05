"""Topology API — returns graph data for task scan results."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.services.task_service import get_task
from app.services.topology_service import build_topology

router = APIRouter()


@router.get("/tasks/{task_id}")
async def get_topology(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await get_task(session, task_id)
    if not task or task.created_by != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "done":
        raise HTTPException(status_code=400, detail="Task is not completed yet")

    return build_topology(task.result)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse
from app.services.task_service import create_task, get_task, list_tasks

router = APIRouter()


@router.post("", response_model=TaskResponse, status_code=201)
async def create(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await create_task(session, body.plugin_name, body.params, user.id, body.project_id)
    # TODO: dispatch to Celery worker
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

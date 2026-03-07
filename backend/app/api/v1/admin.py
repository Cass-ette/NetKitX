"""Admin API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_admin_user
from app.models.user import User
from app.schemas.admin import (
    SystemStatsResponse,
    UpdateUserRoleRequest,
    UserListResponse,
)
from app.services.admin_service import (
    delete_user,
    get_all_users,
    get_system_stats,
    update_user_role,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserListResponse])
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    """List all users (admin only)."""
    users = await get_all_users(session, limit, offset)
    return users


@router.patch("/users/{user_id}/role", response_model=UserListResponse)
async def change_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Change a user's role (admin only)."""
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = await update_user_role(session, user_id, body.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Delete a user (admin only)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    success = await delete_user(session, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted"}


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_admin_user),
):
    """Get system statistics (admin only)."""
    stats = await get_system_stats(session)
    return stats

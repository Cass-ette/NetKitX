"""Whitelist API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.whitelist import WhitelistTargetCreate, WhitelistTargetResponse
from app.services.whitelist_service import add_target, remove_target, list_targets

router = APIRouter()


@router.get("/whitelist", response_model=list[WhitelistTargetResponse])
async def get_whitelist(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get user's authorized targets."""
    targets = await list_targets(session, user.id)
    return targets


@router.post("/whitelist", response_model=WhitelistTargetResponse, status_code=201)
async def create_whitelist_target(
    body: WhitelistTargetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add an authorized target."""
    target = await add_target(session, user.id, body)
    return target


@router.delete("/whitelist/{target_id}", status_code=204)
async def delete_whitelist_target(
    target_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove an authorized target."""
    success = await remove_target(session, user.id, target_id)
    if not success:
        raise HTTPException(status_code=404, detail="Target not found")

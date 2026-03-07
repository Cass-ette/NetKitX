"""Admin service for user management and system stats."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin import Plugin
from app.models.task import Task
from app.models.user import User


async def get_all_users(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    """Get all users with pagination."""
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_count(session: AsyncSession) -> int:
    """Get total user count."""
    result = await session.execute(select(func.count(User.id)))
    return result.scalar() or 0


async def update_user_role(
    session: AsyncSession,
    user_id: int,
    new_role: str,
) -> User | None:
    """Update user's role."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    user.role = new_role
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    """Delete a user."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False

    await session.delete(user)
    await session.commit()
    return True


async def get_system_stats(session: AsyncSession) -> dict:
    """Get system statistics for admin dashboard."""
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

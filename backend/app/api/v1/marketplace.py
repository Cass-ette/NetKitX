"""Marketplace API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models import (
    MarketplacePlugin,
    MarketplaceReview,
    MarketplaceVersion,
    User,
    UserInstalledPlugin,
)
from app.schemas.marketplace import (
    MarketplaceDependencyResponse,
    MarketplacePluginDetail,
    MarketplacePluginResponse,
    MarketplaceReviewCreate,
    MarketplaceReviewResponse,
    MarketplaceVersionResponse,
    UserInstalledPluginResponse,
)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/plugins", response_model=list[MarketplacePluginResponse])
async def list_plugins(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[list[str]] = Query(None, description="Filter by tags"),
    verified_only: bool = Query(False, description="Show only verified plugins"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List marketplace plugins."""
    stmt = select(MarketplacePlugin)

    # Apply filters
    if query:
        search_filter = or_(
            MarketplacePlugin.name.ilike(f"%{query}%"),
            MarketplacePlugin.display_name.ilike(f"%{query}%"),
            MarketplacePlugin.description.ilike(f"%{query}%"),
        )
        stmt = stmt.where(search_filter)

    if category:
        stmt = stmt.where(MarketplacePlugin.category == category)

    if tags:
        stmt = stmt.where(MarketplacePlugin.tags.overlap(tags))

    if verified_only:
        stmt = stmt.where(MarketplacePlugin.verified == True)  # noqa: E712

    # Order by downloads and rating
    stmt = stmt.order_by(MarketplacePlugin.downloads.desc(), MarketplacePlugin.rating.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    plugins = result.scalars().all()

    return plugins


@router.get("/plugins/{plugin_name}", response_model=MarketplacePluginDetail)
async def get_plugin_detail(
    plugin_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get plugin details with versions."""
    stmt = (
        select(MarketplacePlugin)
        .where(MarketplacePlugin.name == plugin_name)
        .options(selectinload(MarketplacePlugin.versions))
    )

    result = await session.execute(stmt)
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Find latest non-yanked version
    latest_version = None
    if plugin.versions:
        non_yanked = [v for v in plugin.versions if not v.yanked]
        if non_yanked:
            # Sort by version (simple string sort for now)
            non_yanked.sort(key=lambda v: v.published_at, reverse=True)
            latest_version = non_yanked[0].version

    response = MarketplacePluginDetail.model_validate(plugin)
    response.latest_version = latest_version

    return response


@router.get("/plugins/{plugin_name}/versions", response_model=list[MarketplaceVersionResponse])
async def list_plugin_versions(
    plugin_name: str,
    include_yanked: bool = Query(False, description="Include yanked versions"),
    session: AsyncSession = Depends(get_session),
):
    """List plugin versions."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get versions
    stmt = select(MarketplaceVersion).where(MarketplaceVersion.plugin_id == plugin.id)

    if not include_yanked:
        stmt = stmt.where(MarketplaceVersion.yanked == False)  # noqa: E712

    stmt = stmt.order_by(MarketplaceVersion.published_at.desc())

    result = await session.execute(stmt)
    versions = result.scalars().all()

    return versions


@router.get(
    "/plugins/{plugin_name}/versions/{version}/dependencies",
    response_model=list[MarketplaceDependencyResponse],
)
async def get_version_dependencies(
    plugin_name: str,
    version: str,
    session: AsyncSession = Depends(get_session),
):
    """Get version dependencies."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get version
    version_stmt = (
        select(MarketplaceVersion)
        .where(MarketplaceVersion.plugin_id == plugin.id, MarketplaceVersion.version == version)
        .options(selectinload(MarketplaceVersion.dependencies))
    )
    version_result = await session.execute(version_stmt)
    version_obj = version_result.scalar_one_or_none()

    if not version_obj:
        raise HTTPException(status_code=404, detail="Version not found")

    return version_obj.dependencies


@router.get("/categories", response_model=list[str])
async def list_categories(session: AsyncSession = Depends(get_session)):
    """List all plugin categories."""
    stmt = (
        select(MarketplacePlugin.category).distinct().where(MarketplacePlugin.category.isnot(None))
    )
    result = await session.execute(stmt)
    categories = [c for c in result.scalars().all() if c]
    return sorted(categories)


@router.get("/installed", response_model=list[UserInstalledPluginResponse])
async def list_installed_plugins(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List user's installed plugins."""
    stmt = (
        select(UserInstalledPlugin)
        .where(UserInstalledPlugin.user_id == current_user.id)
        .order_by(UserInstalledPlugin.installed_at.desc())
    )

    result = await session.execute(stmt)
    installed = result.scalars().all()

    return installed


@router.post("/plugins/{plugin_name}/reviews", response_model=MarketplaceReviewResponse)
async def create_review(
    plugin_name: str,
    review: MarketplaceReviewCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create or update plugin review."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Check if review exists
    existing_stmt = select(MarketplaceReview).where(
        MarketplaceReview.plugin_id == plugin.id, MarketplaceReview.user_id == current_user.id
    )
    existing_result = await session.execute(existing_stmt)
    existing_review = existing_result.scalar_one_or_none()

    if existing_review:
        # Update existing review
        existing_review.rating = review.rating
        existing_review.comment = review.comment
        await session.commit()
        await session.refresh(existing_review)
        review_obj = existing_review
    else:
        # Create new review
        review_obj = MarketplaceReview(
            plugin_id=plugin.id,
            user_id=current_user.id,
            rating=review.rating,
            comment=review.comment,
        )
        session.add(review_obj)
        await session.commit()
        await session.refresh(review_obj)

    # Update plugin rating
    rating_stmt = select(func.avg(MarketplaceReview.rating)).where(
        MarketplaceReview.plugin_id == plugin.id
    )
    rating_result = await session.execute(rating_stmt)
    avg_rating = rating_result.scalar()
    plugin.rating = float(avg_rating) if avg_rating else None
    await session.commit()

    return review_obj


@router.get("/plugins/{plugin_name}/reviews", response_model=list[MarketplaceReviewResponse])
async def list_reviews(
    plugin_name: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List plugin reviews."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get reviews
    stmt = (
        select(MarketplaceReview)
        .where(MarketplaceReview.plugin_id == plugin.id)
        .order_by(MarketplaceReview.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(stmt)
    reviews = result.scalars().all()

    return reviews

"""Marketplace API endpoints."""

import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.deps import get_admin_user, get_current_user, is_official_publisher
from app.models import (
    MarketplaceDependency,
    MarketplacePlugin,
    MarketplaceReport,
    MarketplaceReview,
    MarketplaceVersion,
    User,
    UserInstalledPlugin,
)
from app.schemas.marketplace import (
    MarketplaceDependencyResponse,
    MarketplacePluginDetail,
    MarketplacePluginResponse,
    MarketplaceReportCreate,
    MarketplaceReportResponse,
    MarketplaceReviewCreate,
    MarketplaceReviewResponse,
    MarketplaceVersionResponse,
    PluginPublishResponse,
    PluginUpdateInfo,
    UpdateCheckResponse,
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


@router.post("/install")
async def install_plugin(
    plugin_name: str,
    version: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Install a plugin from marketplace.

    Resolves dependencies and installs all required plugins.
    """
    from app.marketplace.installer import InstallError, PluginInstaller
    from app.marketplace.resolver import Dependency, Package, resolve_dependencies

    # Get plugin from marketplace
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found in marketplace")

    # Get all marketplace plugins and versions for resolver
    all_plugins_stmt = select(MarketplacePlugin).options(
        selectinload(MarketplacePlugin.versions).selectinload(MarketplaceVersion.dependencies)
    )
    all_plugins_result = await session.execute(all_plugins_stmt)
    all_plugins = all_plugins_result.scalars().all()

    # Build available packages dict for resolver
    available_packages: dict[str, list[Package]] = {}
    for mp in all_plugins:
        packages = []
        for mv in mp.versions:
            if mv.yanked:
                continue

            deps = [
                Dependency(
                    plugin_name=dep.depends_on_plugin,
                    constraint=dep.version_constraint,
                    optional=dep.optional,
                )
                for dep in mv.dependencies
            ]

            packages.append(Package(name=mp.name, version=mv.version, dependencies=deps))

        if packages:
            available_packages[mp.name] = packages

    # Resolve dependencies
    try:
        solution = resolve_dependencies(plugin_name, version, available_packages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dependency resolution failed: {e}")

    # Install plugins in dependency order
    installer = PluginInstaller(session, current_user.id)
    installed = []

    try:
        for pkg_name, pkg_version in solution.items():
            # Get version info
            version_stmt = (
                select(MarketplaceVersion)
                .join(MarketplacePlugin)
                .where(
                    MarketplacePlugin.name == pkg_name,
                    MarketplaceVersion.version == pkg_version,
                )
            )
            version_result = await session.execute(version_stmt)
            version_obj = version_result.scalar_one_or_none()

            if not version_obj:
                raise HTTPException(
                    status_code=404, detail=f"Version {pkg_version} not found for {pkg_name}"
                )

            # Install
            await installer.install(
                plugin_name=pkg_name,
                version=pkg_version,
                package_url=version_obj.package_url,
                package_hash=version_obj.package_hash,
            )

            installed.append({"plugin": pkg_name, "version": pkg_version})

            # Update download count
            plugin_update_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == pkg_name)
            plugin_update_result = await session.execute(plugin_update_stmt)
            plugin_to_update = plugin_update_result.scalar_one_or_none()
            if plugin_to_update:
                plugin_to_update.downloads += 1
                await session.commit()

        return {"success": True, "installed": installed}

    except InstallError as e:
        # Rollback on installation error
        await installer.rollback()
        raise HTTPException(status_code=500, detail=f"Installation failed: {e}")
    except Exception as e:
        await installer.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post("/publish", response_model=PluginPublishResponse)
async def publish_plugin(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Publish a plugin to marketplace.

    Accepts a zip file containing plugin.yaml and plugin code.
    Validates structure, extracts metadata, runs security scan, and creates marketplace entry.
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a zip archive")

    # Save uploaded file to temp
    temp_dir = Path(tempfile.mkdtemp(prefix="netkitx_publish_"))
    zip_path = temp_dir / file.filename

    try:
        # Save upload
        content = await file.read()
        with open(zip_path, "wb") as f:
            f.write(content)

        # Run security scan
        from app.marketplace.scanner import SecurityScanner

        scanner = SecurityScanner()
        scan_result = await scanner.scan_package(zip_path)

        if not scan_result.passed:
            # Build error message with issues
            critical_issues = [i for i in scan_result.issues if i.severity == "critical"]
            high_issues = [i for i in scan_result.issues if i.severity == "high"]

            error_msg = f"Security scan failed (score: {scan_result.score}/100).\n"
            if critical_issues:
                error_msg += f"Critical issues ({len(critical_issues)}):\n"
                for issue in critical_issues[:3]:  # Show first 3
                    error_msg += f"  - {issue.message}"
                    if issue.file:
                        error_msg += f" in {issue.file}"
                    error_msg += "\n"
            if high_issues:
                error_msg += f"High severity issues ({len(high_issues)}):\n"
                for issue in high_issues[:3]:
                    error_msg += f"  - {issue.message}"
                    if issue.file:
                        error_msg += f" in {issue.file}"
                    error_msg += "\n"

            raise HTTPException(status_code=400, detail=error_msg)

        # Calculate hash
        sha256 = hashlib.sha256()
        sha256.update(content)
        package_hash = sha256.hexdigest()
        package_size = len(content)

        # Extract and validate
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Check for path traversal
            for member in zf.namelist():
                member_path = extract_dir / member
                if not member_path.resolve().is_relative_to(extract_dir.resolve()):
                    raise HTTPException(status_code=400, detail=f"Unsafe path in zip: {member}")
            zf.extractall(extract_dir)

        # Find plugin.yaml
        plugin_yaml_path = None
        if (extract_dir / "plugin.yaml").exists():
            plugin_yaml_path = extract_dir / "plugin.yaml"
        else:
            # Check one level deep
            for subdir in extract_dir.iterdir():
                if subdir.is_dir() and (subdir / "plugin.yaml").exists():
                    plugin_yaml_path = subdir / "plugin.yaml"
                    break

        if not plugin_yaml_path:
            raise HTTPException(status_code=400, detail="No plugin.yaml found in package")

        # Parse plugin.yaml
        with open(plugin_yaml_path) as f:
            plugin_config = yaml.safe_load(f)

        # Validate required fields
        required_fields = ["name", "version", "description", "category", "engine"]
        for field in required_fields:
            if field not in plugin_config:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        plugin_name = plugin_config["name"]
        version = plugin_config["version"]

        # Check if plugin exists
        plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
        plugin_result = await session.execute(plugin_stmt)
        plugin = plugin_result.scalar_one_or_none()

        if not plugin:
            # Create new plugin
            plugin = MarketplacePlugin(
                name=plugin_name,
                display_name=plugin_config.get("display_name", plugin_name),
                author=current_user.username,
                description=plugin_config.get("description"),
                category=plugin_config.get("category"),
                tags=plugin_config.get("tags", []),
                homepage_url=plugin_config.get("homepage_url"),
                repository_url=plugin_config.get("repository_url"),
                license=plugin_config.get("license"),
                verified=is_official_publisher(current_user),
            )
            session.add(plugin)
            await session.flush()
        else:
            # Verify ownership
            if plugin.author != current_user.username:
                raise HTTPException(status_code=403, detail="You are not the author of this plugin")
            # Upgrade to verified if publisher is now official
            if not plugin.verified and is_official_publisher(current_user):
                plugin.verified = True

        # Check if version already exists
        version_stmt = select(MarketplaceVersion).where(
            MarketplaceVersion.plugin_id == plugin.id, MarketplaceVersion.version == version
        )
        version_result = await session.execute(version_stmt)
        existing_version = version_result.scalar_one_or_none()

        if existing_version:
            raise HTTPException(
                status_code=400, detail=f"Version {version} already exists for {plugin_name}"
            )

        # TODO: Upload to S3/MinIO - for now use placeholder URL
        # Store zip in persistent packages directory
        from app.core.config import settings

        packages_dir = Path(settings.PLUGINS_DIR) / "_packages"
        packages_dir.mkdir(parents=True, exist_ok=True)
        package_filename = f"{plugin_name}-{version}.zip"
        package_dest = packages_dir / package_filename
        with open(package_dest, "wb") as pf:
            pf.write(content)
        package_url = f"/api/v1/marketplace/packages/{package_filename}"

        # Create version
        new_version = MarketplaceVersion(
            plugin_id=plugin.id,
            version=version,
            changelog=plugin_config.get("changelog"),
            package_url=package_url,
            package_hash=package_hash,
            package_size=package_size,
            min_netkitx_version=plugin_config.get("requires", {}).get("netkitx"),
        )
        session.add(new_version)
        await session.flush()

        # Create dependencies
        dependencies = plugin_config.get("dependencies", [])
        for dep in dependencies:
            if isinstance(dep, dict):
                dep_obj = MarketplaceDependency(
                    version_id=new_version.id,
                    depends_on_plugin=dep["name"],
                    version_constraint=dep.get("version", "*"),
                    optional=dep.get("optional", False),
                )
                session.add(dep_obj)

        await session.commit()

        return PluginPublishResponse(
            success=True,
            plugin_name=plugin_name,
            version=version,
            message=f"Successfully published {plugin_name} version {version}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")
    finally:
        # Cleanup temp directory
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/packages/{filename}")
async def download_package(filename: str):
    """Serve a published plugin package zip file."""
    from fastapi.responses import FileResponse
    from app.core.config import settings

    packages_dir = Path(settings.PLUGINS_DIR) / "_packages"
    package_path = packages_dir / filename
    if not package_path.exists() or not package_path.is_file():
        raise HTTPException(status_code=404, detail="Package not found")
    return FileResponse(package_path, media_type="application/zip", filename=filename)


@router.delete("/plugins/{plugin_name}/versions/{version}")
async def yank_version(
    plugin_name: str,
    version: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Yank a plugin version (mark as unavailable but don't delete)."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Verify ownership
    if plugin.author != current_user.username:
        raise HTTPException(status_code=403, detail="You are not the author of this plugin")

    # Get version
    version_stmt = select(MarketplaceVersion).where(
        MarketplaceVersion.plugin_id == plugin.id, MarketplaceVersion.version == version
    )
    version_result = await session.execute(version_stmt)
    version_obj = version_result.scalar_one_or_none()

    if not version_obj:
        raise HTTPException(status_code=404, detail="Version not found")

    # Yank version
    version_obj.yanked = True
    await session.commit()

    return {"success": True, "message": f"Version {version} of {plugin_name} has been yanked"}


@router.post("/plugins/{plugin_name}/report", response_model=MarketplaceReportResponse)
async def report_plugin(
    plugin_name: str,
    report: MarketplaceReportCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Report a plugin for security or policy violations."""
    # Get plugin
    plugin_stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Check if user already reported this plugin
    existing_stmt = select(MarketplaceReport).where(
        MarketplaceReport.plugin_id == plugin.id,
        MarketplaceReport.reporter_id == current_user.id,
        MarketplaceReport.status == "pending",
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already reported this plugin")

    # Create report
    report_obj = MarketplaceReport(
        plugin_id=plugin.id,
        reporter_id=current_user.id,
        reason=report.reason,
        description=report.description,
        status="pending",
    )
    session.add(report_obj)
    await session.commit()
    await session.refresh(report_obj)

    return report_obj


@router.get("/reports", response_model=list[MarketplaceReportResponse])
async def list_reports(
    status: Optional[str] = Query(None, pattern="^(pending|reviewing|resolved|rejected)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """List security reports (admin only)."""
    stmt = select(MarketplaceReport)

    if status:
        stmt = stmt.where(MarketplaceReport.status == status)

    stmt = stmt.order_by(MarketplaceReport.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(stmt)
    reports = result.scalars().all()

    return reports


@router.put("/plugins/{plugin_name}/verify")
async def verify_plugin(
    plugin_name: str,
    current_user: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """Mark a plugin as verified (admin only)."""
    stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    result = await session.execute(stmt)
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    plugin.verified = True
    await session.commit()

    return {"success": True, "message": f"Plugin {plugin_name} is now verified"}


@router.delete("/plugins/{plugin_name}/verify")
async def unverify_plugin(
    plugin_name: str,
    current_user: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove verified status from a plugin (admin only)."""
    stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == plugin_name)
    result = await session.execute(stmt)
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    plugin.verified = False
    await session.commit()

    return {"success": True, "message": f"Plugin {plugin_name} is no longer verified"}


@router.get("/updates", response_model=UpdateCheckResponse)
async def check_updates(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Check for available updates for user's installed plugins."""
    from app.marketplace.version import Version

    # Get user's installed plugins
    installed_stmt = select(UserInstalledPlugin).where(
        UserInstalledPlugin.user_id == current_user.id
    )
    installed_result = await session.execute(installed_stmt)
    installed_plugins = installed_result.scalars().all()

    updates = []

    for installed in installed_plugins:
        # Get plugin from marketplace
        plugin_stmt = (
            select(MarketplacePlugin)
            .where(MarketplacePlugin.name == installed.plugin_name)
            .options(selectinload(MarketplacePlugin.versions))
        )
        plugin_result = await session.execute(plugin_stmt)
        plugin = plugin_result.scalar_one_or_none()

        if not plugin:
            continue

        # Find latest non-yanked version
        non_yanked = [v for v in plugin.versions if not v.yanked]
        if not non_yanked:
            continue

        # Sort by version
        try:
            non_yanked.sort(key=lambda v: Version.parse(v.version), reverse=True)
            latest_version_obj = non_yanked[0]

            current_ver = Version.parse(installed.version)
            latest_ver = Version.parse(latest_version_obj.version)

            # Check if update available
            if latest_ver > current_ver:
                # Check for breaking changes (major version bump)
                has_breaking = latest_ver.major > current_ver.major

                updates.append(
                    PluginUpdateInfo(
                        plugin_name=installed.plugin_name,
                        current_version=installed.version,
                        latest_version=latest_version_obj.version,
                        changelog=latest_version_obj.changelog,
                        published_at=latest_version_obj.published_at,
                        has_breaking_changes=has_breaking,
                    )
                )
        except ValueError:
            # Skip if version parsing fails
            continue

    return UpdateCheckResponse(
        updates_available=len(updates),
        plugins=updates,
    )


@router.post("/update/{plugin_name}")
async def update_plugin(
    plugin_name: str,
    version: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a plugin to specified version (or latest)."""
    from app.marketplace.installer import InstallError, PluginInstaller
    from app.marketplace.resolver import Dependency, Package, resolve_dependencies
    from app.marketplace.version import Version

    # Check if plugin is installed
    installed_stmt = select(UserInstalledPlugin).where(
        UserInstalledPlugin.user_id == current_user.id,
        UserInstalledPlugin.plugin_name == plugin_name,
    )
    installed_result = await session.execute(installed_stmt)
    installed = installed_result.scalar_one_or_none()

    if not installed:
        raise HTTPException(status_code=404, detail="Plugin not installed")

    # Get plugin from marketplace
    plugin_stmt = (
        select(MarketplacePlugin)
        .where(MarketplacePlugin.name == plugin_name)
        .options(selectinload(MarketplacePlugin.versions))
    )
    plugin_result = await session.execute(plugin_stmt)
    plugin = plugin_result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found in marketplace")

    # Determine target version
    if version is None:
        # Find latest non-yanked version
        non_yanked = [v for v in plugin.versions if not v.yanked]
        if not non_yanked:
            raise HTTPException(status_code=404, detail="No available versions")

        try:
            non_yanked.sort(key=lambda v: Version.parse(v.version), reverse=True)
            target_version = non_yanked[0].version
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid version format")
    else:
        target_version = version

    # Check if already on target version
    if installed.version == target_version:
        return {"success": True, "message": "Already on target version", "version": target_version}

    # Get all marketplace plugins and versions for resolver
    all_plugins_stmt = select(MarketplacePlugin).options(
        selectinload(MarketplacePlugin.versions).selectinload(MarketplaceVersion.dependencies)
    )
    all_plugins_result = await session.execute(all_plugins_stmt)
    all_plugins = all_plugins_result.scalars().all()

    # Build available packages dict for resolver
    available_packages: dict[str, list[Package]] = {}
    for mp in all_plugins:
        packages = []
        for mv in mp.versions:
            if mv.yanked:
                continue

            deps = [
                Dependency(
                    plugin_name=dep.depends_on_plugin,
                    constraint=dep.version_constraint,
                    optional=dep.optional,
                )
                for dep in mv.dependencies
            ]

            packages.append(Package(name=mp.name, version=mv.version, dependencies=deps))

        if packages:
            available_packages[mp.name] = packages

    # Resolve dependencies for target version
    try:
        resolve_dependencies(plugin_name, target_version, available_packages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dependency resolution failed: {e}")

    # Install/update plugin
    installer = PluginInstaller(session, current_user.id)

    try:
        # Get version info
        version_stmt = (
            select(MarketplaceVersion)
            .join(MarketplacePlugin)
            .where(
                MarketplacePlugin.name == plugin_name,
                MarketplaceVersion.version == target_version,
            )
        )
        version_result = await session.execute(version_stmt)
        version_obj = version_result.scalar_one_or_none()

        if not version_obj:
            raise HTTPException(status_code=404, detail=f"Version {target_version} not found")

        # Install (will overwrite existing)
        await installer.install(
            plugin_name=plugin_name,
            version=target_version,
            package_url=version_obj.package_url,
            package_hash=version_obj.package_hash,
        )

        return {
            "success": True,
            "message": f"Updated {plugin_name} to version {target_version}",
            "version": target_version,
        }

    except InstallError as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post("/update-all")
async def update_all_plugins(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update all plugins with available updates."""
    from app.marketplace.installer import InstallError, PluginInstaller
    from app.marketplace.resolver import Dependency, Package

    # Get updates
    updates_response = await check_updates(current_user, session)

    if updates_response.updates_available == 0:
        return {"success": True, "message": "All plugins are up to date", "updated": []}

    # Get all marketplace plugins and versions for resolver
    all_plugins_stmt = select(MarketplacePlugin).options(
        selectinload(MarketplacePlugin.versions).selectinload(MarketplaceVersion.dependencies)
    )
    all_plugins_result = await session.execute(all_plugins_stmt)
    all_plugins = all_plugins_result.scalars().all()

    # Build available packages dict
    available_packages: dict[str, list[Package]] = {}
    for mp in all_plugins:
        packages = []
        for mv in mp.versions:
            if mv.yanked:
                continue

            deps = [
                Dependency(
                    plugin_name=dep.depends_on_plugin,
                    constraint=dep.version_constraint,
                    optional=dep.optional,
                )
                for dep in mv.dependencies
            ]

            packages.append(Package(name=mp.name, version=mv.version, dependencies=deps))

        if packages:
            available_packages[mp.name] = packages

    installer = PluginInstaller(session, current_user.id)
    updated = []
    failed = []

    # Update each plugin
    for update_info in updates_response.plugins:
        try:
            # Get version info
            version_stmt = (
                select(MarketplaceVersion)
                .join(MarketplacePlugin)
                .where(
                    MarketplacePlugin.name == update_info.plugin_name,
                    MarketplaceVersion.version == update_info.latest_version,
                )
            )
            version_result = await session.execute(version_stmt)
            version_obj = version_result.scalar_one_or_none()

            if not version_obj:
                failed.append(
                    {
                        "plugin": update_info.plugin_name,
                        "error": f"Version {update_info.latest_version} not found",
                    }
                )
                continue

            # Install (will overwrite existing)
            await installer.install(
                plugin_name=update_info.plugin_name,
                version=update_info.latest_version,
                package_url=version_obj.package_url,
                package_hash=version_obj.package_hash,
            )

            updated.append(
                {
                    "plugin": update_info.plugin_name,
                    "from_version": update_info.current_version,
                    "to_version": update_info.latest_version,
                }
            )

        except (InstallError, Exception) as e:
            failed.append(
                {
                    "plugin": update_info.plugin_name,
                    "error": str(e),
                }
            )

    return {
        "success": True,
        "updated": updated,
        "failed": failed,
        "message": f"Updated {len(updated)} plugins, {len(failed)} failed",
    }

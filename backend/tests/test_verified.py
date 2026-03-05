"""Tests for plugin verified mechanism.

Unit tests (no DB required) for is_official_publisher and get_admin_user.
Integration tests (DB required, run in CI) for publish auto-verified and admin API.
"""

import zipfile

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import get_session
from app.core.deps import get_admin_user, get_current_user, is_official_publisher
from app.main import app
from app.models import MarketplacePlugin, User


# ---------------------------------------------------------------------------
# Fake user for unit tests (no DB)
# ---------------------------------------------------------------------------


class FakeUser:
    def __init__(self, username="testuser", role="user"):
        self.username = username
        self.role = role


# ---------------------------------------------------------------------------
# Unit tests — no database required
# ---------------------------------------------------------------------------


class TestIsOfficialPublisher:
    """Test is_official_publisher helper."""

    def test_admin_is_official(self):
        user = FakeUser(username="admin", role="admin")
        assert is_official_publisher(user) is True

    def test_whitelisted_user_is_official(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "VERIFIED_PUBLISHERS", ["official", "trusted"])

        user = FakeUser(username="official", role="user")
        assert is_official_publisher(user) is True

    def test_normal_user_not_official(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "VERIFIED_PUBLISHERS", [])

        user = FakeUser(username="normaluser", role="user")
        assert is_official_publisher(user) is False

    def test_admin_always_official_regardless_of_whitelist(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "VERIFIED_PUBLISHERS", [])

        user = FakeUser(username="admin", role="admin")
        assert is_official_publisher(user) is True

    def test_whitelist_is_exact_match(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "VERIFIED_PUBLISHERS", ["official"])

        user = FakeUser(username="official2", role="user")
        assert is_official_publisher(user) is False


class TestGetAdminUser:
    """Test get_admin_user dependency."""

    @pytest.mark.asyncio
    async def test_admin_passes(self):
        user = FakeUser(username="admin", role="admin")
        result = await get_admin_user(user)
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        user = FakeUser(username="normaluser", role="user")
        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(user)
        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Integration tests — require PostgreSQL (run in CI)
# ---------------------------------------------------------------------------

needs_db = pytest.mark.skipif(
    True,  # Always skip locally; CI overrides via conftest/env
    reason="Requires PostgreSQL (netkitx_test)",
)

try:
    import asyncpg  # noqa: F401

    from tests.conftest import db_session  # noqa: F401

    # If we can connect, we'll let the tests try
    _HAS_DB_FIXTURES = True
except Exception:
    _HAS_DB_FIXTURES = False


def _make_plugin_zip(tmp_path, name="test-plugin", version="1.0.0"):
    """Create a minimal plugin zip for publishing."""
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        f"""
name: {name}
version: {version}
display_name: {name.title()}
description: A test plugin
category: utils
engine: python
license: MIT
"""
    )
    (plugin_dir / "main.py").write_text(
        """
async def execute(params):
    yield {"result": "test"}
"""
    )

    zip_path = tmp_path / f"{name}-{version}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in plugin_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(tmp_path))

    return zip_path


def _make_client(db_session, user, admin_user=None):
    """Build dependency overrides for a given user."""

    async def override_get_session():
        yield db_session

    async def override_get_current_user():
        return user

    async def override_get_admin_user():
        if admin_user is not None:
            return admin_user
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    if admin_user is not None or (user and user.role == "admin"):
        app.dependency_overrides[get_admin_user] = override_get_admin_user


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create admin user."""
    user = User(username="admin", email="admin@example.com", hashed_password="hashed", role="admin")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def normal_user(db_session):
    """Create normal user."""
    user = User(
        username="normaluser", email="normal@example.com", hashed_password="hashed", role="user"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def whitelisted_user(db_session):
    """Create a user in the VERIFIED_PUBLISHERS whitelist."""
    user = User(
        username="official", email="official@example.com", hashed_password="hashed", role="user"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.skipif(not _HAS_DB_FIXTURES, reason="Requires PostgreSQL")
class TestAutoVerifiedOnPublish:
    """Test that official publishers get auto-verified plugins."""

    @pytest.mark.asyncio
    async def test_admin_publish_auto_verified(self, db_session, admin_user, tmp_path):
        _make_client(db_session, admin_user)
        zip_path = _make_plugin_zip(tmp_path, name="admin-plugin")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with open(zip_path, "rb") as f:
                response = await ac.post(
                    "/api/v1/marketplace/publish",
                    files={"file": ("admin-plugin-1.0.0.zip", f, "application/zip")},
                )

        assert response.status_code == 200
        stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == "admin-plugin")
        result = await db_session.execute(stmt)
        assert result.scalar_one().verified is True
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_whitelisted_publish_auto_verified(
        self, db_session, whitelisted_user, tmp_path, monkeypatch
    ):
        from app.core import config

        monkeypatch.setattr(config.settings, "VERIFIED_PUBLISHERS", ["official"])
        _make_client(db_session, whitelisted_user)
        zip_path = _make_plugin_zip(tmp_path, name="official-plugin")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with open(zip_path, "rb") as f:
                response = await ac.post(
                    "/api/v1/marketplace/publish",
                    files={"file": ("official-plugin-1.0.0.zip", f, "application/zip")},
                )

        assert response.status_code == 200
        stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == "official-plugin")
        result = await db_session.execute(stmt)
        assert result.scalar_one().verified is True
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_normal_publish_not_verified(self, db_session, normal_user, tmp_path):
        _make_client(db_session, normal_user)
        zip_path = _make_plugin_zip(tmp_path, name="normal-plugin")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with open(zip_path, "rb") as f:
                response = await ac.post(
                    "/api/v1/marketplace/publish",
                    files={"file": ("normal-plugin-1.0.0.zip", f, "application/zip")},
                )

        assert response.status_code == 200
        stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == "normal-plugin")
        result = await db_session.execute(stmt)
        assert result.scalar_one().verified is False
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_existing_plugin_upgraded_on_official_publish(
        self, db_session, admin_user, tmp_path
    ):
        plugin = MarketplacePlugin(
            name="upgrade-plugin",
            display_name="Upgrade Plugin",
            author=admin_user.username,
            description="Test",
            category="utils",
            verified=False,
        )
        db_session.add(plugin)
        await db_session.commit()

        _make_client(db_session, admin_user)
        zip_path = _make_plugin_zip(tmp_path, name="upgrade-plugin", version="2.0.0")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with open(zip_path, "rb") as f:
                response = await ac.post(
                    "/api/v1/marketplace/publish",
                    files={"file": ("upgrade-plugin-2.0.0.zip", f, "application/zip")},
                )

        assert response.status_code == 200
        await db_session.refresh(plugin)
        assert plugin.verified is True
        app.dependency_overrides.clear()


@pytest.mark.skipif(not _HAS_DB_FIXTURES, reason="Requires PostgreSQL")
class TestAdminVerifyAPI:
    """Test admin verify/unverify endpoints."""

    @pytest.mark.asyncio
    async def test_admin_verify_plugin(self, db_session, admin_user):
        plugin = MarketplacePlugin(
            name="unverified-plugin",
            display_name="Unverified",
            author="someone",
            description="Test",
            category="utils",
            verified=False,
        )
        db_session.add(plugin)
        await db_session.commit()

        _make_client(db_session, admin_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put("/api/v1/marketplace/plugins/unverified-plugin/verify")

        assert response.status_code == 200
        assert response.json()["success"] is True
        await db_session.refresh(plugin)
        assert plugin.verified is True
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_admin_unverify_plugin(self, db_session, admin_user):
        plugin = MarketplacePlugin(
            name="verified-plugin",
            display_name="Verified",
            author="someone",
            description="Test",
            category="utils",
            verified=True,
        )
        db_session.add(plugin)
        await db_session.commit()

        _make_client(db_session, admin_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/v1/marketplace/plugins/verified-plugin/verify")

        assert response.status_code == 200
        assert response.json()["success"] is True
        await db_session.refresh(plugin)
        assert plugin.verified is False
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_nonexistent_plugin(self, db_session, admin_user):
        _make_client(db_session, admin_user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put("/api/v1/marketplace/plugins/no-such-plugin/verify")

        assert response.status_code == 404
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_non_admin_verify_forbidden(self, db_session, normal_user):
        plugin = MarketplacePlugin(
            name="some-plugin",
            display_name="Some Plugin",
            author="someone",
            description="Test",
            category="utils",
        )
        db_session.add(plugin)
        await db_session.commit()

        async def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = lambda: normal_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put("/api/v1/marketplace/plugins/some-plugin/verify")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_non_admin_unverify_forbidden(self, db_session, normal_user):
        plugin = MarketplacePlugin(
            name="some-plugin",
            display_name="Some Plugin",
            author="someone",
            description="Test",
            category="utils",
            verified=True,
        )
        db_session.add(plugin)
        await db_session.commit()

        async def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = lambda: normal_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/v1/marketplace/plugins/some-plugin/verify")

        assert response.status_code == 403
        app.dependency_overrides.clear()

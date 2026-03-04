"""Tests for marketplace API endpoints."""

import pytest_asyncio
from httpx import AsyncClient

from app.models import MarketplacePlugin, MarketplaceVersion


@pytest_asyncio.fixture
async def marketplace_plugin(db_session):
    """Create a test marketplace plugin."""
    plugin = MarketplacePlugin(
        name="test-plugin",
        display_name="Test Plugin",
        author="testuser",
        description="A test plugin",
        category="utils",
        tags=["test", "example"],
        downloads=100,
        verified=True,
    )
    db_session.add(plugin)
    await db_session.flush()

    version = MarketplaceVersion(
        plugin_id=plugin.id,
        version="1.0.0",
        package_url="https://example.com/test-plugin-1.0.0.zip",
        package_hash="abc123" * 10 + "ab",
        changelog="Initial release",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(plugin)

    return plugin


async def test_list_plugins_empty(client: AsyncClient):
    """List plugins returns empty list when no plugins exist."""
    response = await client.get("/api/v1/marketplace/plugins")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_plugins(client: AsyncClient, marketplace_plugin):
    """List plugins returns existing plugins."""
    response = await client.get("/api/v1/marketplace/plugins")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-plugin"
    assert data[0]["verified"] is True


async def test_list_plugins_filter_by_category(client: AsyncClient, marketplace_plugin):
    """Filter plugins by category."""
    response = await client.get("/api/v1/marketplace/plugins?category=utils")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = await client.get("/api/v1/marketplace/plugins?category=nonexistent")
    assert response.status_code == 200
    assert len(response.json()) == 0


async def test_list_plugins_search(client: AsyncClient, marketplace_plugin):
    """Search plugins by query string."""
    response = await client.get("/api/v1/marketplace/plugins?query=test")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = await client.get("/api/v1/marketplace/plugins?query=nomatch")
    assert response.status_code == 200
    assert len(response.json()) == 0


async def test_list_plugins_verified_only(client: AsyncClient, marketplace_plugin):
    """Filter to verified plugins only."""
    response = await client.get("/api/v1/marketplace/plugins?verified_only=true")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_plugin_detail(client: AsyncClient, marketplace_plugin):
    """Get plugin detail returns full info with versions."""
    response = await client.get("/api/v1/marketplace/plugins/test-plugin")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-plugin"
    assert data["latest_version"] == "1.0.0"
    assert len(data["versions"]) == 1


async def test_get_plugin_detail_not_found(client: AsyncClient):
    """Get non-existent plugin returns 404."""
    response = await client.get("/api/v1/marketplace/plugins/no-such-plugin")
    assert response.status_code == 404


async def test_list_plugin_versions(client: AsyncClient, marketplace_plugin):
    """List plugin versions."""
    response = await client.get("/api/v1/marketplace/plugins/test-plugin/versions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["version"] == "1.0.0"
    assert data[0]["yanked"] is False


async def test_list_categories(client: AsyncClient, marketplace_plugin):
    """List categories returns all unique categories."""
    response = await client.get("/api/v1/marketplace/categories")
    assert response.status_code == 200
    assert "utils" in response.json()


async def test_list_installed_requires_auth(client: AsyncClient):
    """Installed plugins endpoint requires authentication."""
    response = await client.get("/api/v1/marketplace/installed")
    assert response.status_code == 401


async def test_create_review_requires_auth(client: AsyncClient, marketplace_plugin):
    """Creating a review requires authentication."""
    response = await client.post(
        "/api/v1/marketplace/plugins/test-plugin/reviews",
        json={"rating": 5, "comment": "Great plugin!"},
    )
    assert response.status_code == 401

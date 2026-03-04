"""Tests for plugin publishing."""

import hashlib
import zipfile

import pytest

from app.models import MarketplacePlugin, MarketplaceVersion


@pytest.fixture
def sample_plugin_package(tmp_path):
    """Create a sample plugin package."""
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # Create plugin.yaml
    (plugin_dir / "plugin.yaml").write_text(
        """
name: test-plugin
version: 1.0.0
display_name: Test Plugin
description: A test plugin
category: utils
engine: python
license: MIT

dependencies:
  - name: base-plugin
    version: ">=1.0.0"
"""
    )

    # Create main.py
    (plugin_dir / "main.py").write_text(
        """
async def execute(params):
    yield {"result": "test"}
"""
    )

    # Create zip
    zip_path = tmp_path / "test-plugin-1.0.0.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in plugin_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(tmp_path))

    # Calculate hash
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        sha256.update(f.read())

    return zip_path, sha256.hexdigest()


class TestPluginPublish:
    """Test plugin publishing."""

    @pytest.mark.asyncio
    async def test_publish_new_plugin(self, client, test_user, sample_plugin_package, db_session):
        """Publish a new plugin successfully."""
        zip_path, expected_hash = sample_plugin_package

        with open(zip_path, "rb") as f:
            response = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("test-plugin-1.0.0.zip", f, "application/zip")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["plugin_name"] == "test-plugin"
        assert data["version"] == "1.0.0"

        # Verify database
        from sqlalchemy import select

        stmt = select(MarketplacePlugin).where(MarketplacePlugin.name == "test-plugin")
        result = await db_session.execute(stmt)
        plugin = result.scalar_one_or_none()

        assert plugin is not None
        assert plugin.author == test_user.username
        assert plugin.display_name == "Test Plugin"
        assert plugin.category == "utils"

    @pytest.mark.asyncio
    async def test_publish_duplicate_version(
        self, client, test_user, sample_plugin_package, db_session
    ):
        """Cannot publish same version twice."""
        zip_path, _ = sample_plugin_package

        # First publish
        with open(zip_path, "rb") as f:
            response1 = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("test-plugin-1.0.0.zip", f, "application/zip")},
            )
        assert response1.status_code == 200

        # Second publish (should fail)
        with open(zip_path, "rb") as f:
            response2 = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("test-plugin-1.0.0.zip", f, "application/zip")},
            )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_wrong_owner(self, client, test_user, sample_plugin_package, db_session):
        """Cannot publish update for plugin owned by another user."""
        zip_path, _ = sample_plugin_package

        # Create plugin owned by another user
        plugin = MarketplacePlugin(
            name="test-plugin",
            display_name="Test Plugin",
            author="otheruser",
            description="Test",
            category="utils",
        )
        db_session.add(plugin)
        await db_session.commit()

        # Try to publish as test_user
        with open(zip_path, "rb") as f:
            response = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("test-plugin-1.0.0.zip", f, "application/zip")},
            )

        assert response.status_code == 403
        assert "not the author" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_invalid_zip(self, client, test_user, tmp_path):
        """Reject invalid zip files."""
        # Create zip without plugin.yaml
        zip_path = tmp_path / "invalid.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("random.txt", "content")

        with open(zip_path, "rb") as f:
            response = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("invalid.zip", f, "application/zip")},
            )

        assert response.status_code == 400
        assert "No plugin.yaml found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_path_traversal(self, client, test_user, tmp_path):
        """Reject zip with path traversal attempt."""
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious")

        with open(zip_path, "rb") as f:
            response = await client.post(
                "/api/v1/marketplace/publish",
                files={"file": ("malicious.zip", f, "application/zip")},
            )

        assert response.status_code == 400
        assert "path traversal" in response.json()["detail"].lower()


class TestVersionYank:
    """Test version yanking."""

    @pytest.mark.asyncio
    async def test_yank_version(self, client, test_user, db_session):
        """Yank a version successfully."""
        # Create plugin and version
        plugin = MarketplacePlugin(
            name="test-plugin",
            display_name="Test Plugin",
            author=test_user.username,
            description="Test",
            category="utils",
        )
        db_session.add(plugin)
        await db_session.flush()

        version = MarketplaceVersion(
            plugin_id=plugin.id,
            version="1.0.0",
            package_url="https://example.com/test.zip",
            package_hash="abc123",
        )
        db_session.add(version)
        await db_session.commit()

        # Yank version
        response = await client.delete(
            "/api/v1/marketplace/plugins/test-plugin/versions/1.0.0",
        )

        assert response.status_code == 200
        assert "yanked" in response.json()["message"]

        # Verify yanked flag
        await db_session.refresh(version)
        assert version.yanked is True

    @pytest.mark.asyncio
    async def test_yank_wrong_owner(self, client, test_user, db_session):
        """Cannot yank version of plugin owned by another user."""
        # Create plugin owned by another user
        plugin = MarketplacePlugin(
            name="test-plugin",
            display_name="Test Plugin",
            author="otheruser",
            description="Test",
            category="utils",
        )
        db_session.add(plugin)
        await db_session.flush()

        version = MarketplaceVersion(
            plugin_id=plugin.id,
            version="1.0.0",
            package_url="https://example.com/test.zip",
            package_hash="abc123",
        )
        db_session.add(version)
        await db_session.commit()

        # Try to yank
        response = await client.delete(
            "/api/v1/marketplace/plugins/test-plugin/versions/1.0.0",
        )

        assert response.status_code == 403
        assert "not the author" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_yank_nonexistent_version(self, client, test_user, db_session):
        """Cannot yank nonexistent version."""
        # Create plugin
        plugin = MarketplacePlugin(
            name="test-plugin",
            display_name="Test Plugin",
            author=test_user.username,
            description="Test",
            category="utils",
        )
        db_session.add(plugin)
        await db_session.commit()

        # Try to yank nonexistent version
        response = await client.delete(
            "/api/v1/marketplace/plugins/test-plugin/versions/9.9.9",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

"""Tests for plugin installer."""

import hashlib
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.marketplace.installer import InstallError, PluginInstaller


@pytest_asyncio.fixture
async def mock_session():
    """Mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def temp_plugins_dir(tmp_path):
    """Create temporary plugins directory."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    return plugins_dir


@pytest.fixture
def sample_plugin_zip(tmp_path):
    """Create a sample plugin zip file."""
    # Create plugin structure
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # Create plugin.yaml
    (plugin_dir / "plugin.yaml").write_text(
        """
name: test-plugin
version: 1.0.0
description: Test plugin
category: utils
engine: python
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
    zip_path = tmp_path / "test-plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in plugin_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(tmp_path))

    # Calculate hash
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        sha256.update(f.read())

    return zip_path, sha256.hexdigest()


class TestPluginInstaller:
    """Test PluginInstaller."""

    @pytest.mark.asyncio
    async def test_verify_hash_success(self, mock_session, sample_plugin_zip):
        """Hash verification succeeds with correct hash."""
        zip_path, expected_hash = sample_plugin_zip

        installer = PluginInstaller(mock_session, user_id=1)
        assert installer._verify_hash(zip_path, expected_hash) is True

    @pytest.mark.asyncio
    async def test_verify_hash_failure(self, mock_session, sample_plugin_zip):
        """Hash verification fails with wrong hash."""
        zip_path, _ = sample_plugin_zip

        installer = PluginInstaller(mock_session, user_id=1)
        assert installer._verify_hash(zip_path, "wrong_hash") is False

    @pytest.mark.asyncio
    async def test_extract_safe(self, mock_session, sample_plugin_zip, tmp_path):
        """Extract zip file safely."""
        zip_path, _ = sample_plugin_zip
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        installer = PluginInstaller(mock_session, user_id=1)
        installer._extract(zip_path, extract_dir)

        # Check extracted files
        assert (extract_dir / "test-plugin" / "plugin.yaml").exists()
        assert (extract_dir / "test-plugin" / "main.py").exists()

    @pytest.mark.asyncio
    async def test_extract_path_traversal(self, mock_session, tmp_path):
        """Reject zip with path traversal attempt."""
        # Create malicious zip
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious content")

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        installer = PluginInstaller(mock_session, user_id=1)
        with pytest.raises(InstallError, match="Unsafe path"):
            installer._extract(zip_path, extract_dir)

    @pytest.mark.asyncio
    async def test_find_plugin_root_at_root(self, mock_session, tmp_path):
        """Find plugin.yaml at root level."""
        (tmp_path / "plugin.yaml").write_text("name: test")

        installer = PluginInstaller(mock_session, user_id=1)
        root = installer._find_plugin_root(tmp_path)

        assert root == tmp_path

    @pytest.mark.asyncio
    async def test_find_plugin_root_one_level_deep(self, mock_session, tmp_path):
        """Find plugin.yaml one level deep."""
        subdir = tmp_path / "test-plugin"
        subdir.mkdir()
        (subdir / "plugin.yaml").write_text("name: test")

        installer = PluginInstaller(mock_session, user_id=1)
        root = installer._find_plugin_root(tmp_path)

        assert root == subdir

    @pytest.mark.asyncio
    async def test_find_plugin_root_not_found(self, mock_session, tmp_path):
        """Return None when plugin.yaml not found."""
        installer = PluginInstaller(mock_session, user_id=1)
        root = installer._find_plugin_root(tmp_path)

        assert root is None

    @pytest.mark.asyncio
    async def test_rollback(self, mock_session, temp_plugins_dir):
        """Rollback removes installed plugins."""
        # Create fake installed plugin
        plugin_dir = temp_plugins_dir / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.yaml").write_text("name: test")

        installer = PluginInstaller(mock_session, user_id=1)
        installer.installed_plugins = ["test-plugin"]

        with patch("app.marketplace.installer.settings") as mock_settings:
            mock_settings.PLUGINS_DIR = str(temp_plugins_dir)
            await installer.rollback()

        assert not plugin_dir.exists()
        assert len(installer.installed_plugins) == 0

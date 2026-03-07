"""Plugin installer."""

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import UserInstalledPlugin
from app.plugins.loader import load_single_plugin


class InstallError(Exception):
    """Installation error."""

    pass


class VerificationError(InstallError):
    """Package verification error."""

    pass


class PluginInstaller:
    """Install plugins from marketplace."""

    def __init__(self, session: AsyncSession, user_id: int):
        """Initialize installer.

        Args:
            session: Database session
            user_id: User ID for installation tracking
        """
        self.session = session
        self.user_id = user_id
        self.installed_plugins: list[str] = []  # Track for rollback

    async def install(
        self,
        plugin_name: str,
        version: str,
        package_url: str,
        package_hash: str,
    ) -> Path:
        """Install a plugin package.

        Args:
            plugin_name: Plugin name
            version: Plugin version
            package_url: URL to download package
            package_hash: Expected SHA256 hash

        Returns:
            Path to installed plugin directory

        Raises:
            InstallError: If installation fails
            VerificationError: If hash verification fails
        """
        temp_dir = None
        plugin_dir = None

        try:
            # Download package
            temp_dir = Path(tempfile.mkdtemp(prefix="netkitx_install_"))
            package_path = temp_dir / f"{plugin_name}-{version}.zip"

            await self._download(package_url, package_path)

            # Verify hash
            if not self._verify_hash(package_path, package_hash):
                raise VerificationError(f"Hash verification failed for {plugin_name} {version}")

            # Extract package
            extract_dir = temp_dir / "extract"
            extract_dir.mkdir()
            self._extract(package_path, extract_dir)

            # Validate structure
            plugin_root = self._find_plugin_root(extract_dir)
            if not plugin_root:
                raise InstallError("Invalid plugin structure: no plugin.yaml found")

            # Install to plugins directory
            plugins_dir = Path(settings.PLUGINS_DIR)
            plugins_dir.mkdir(parents=True, exist_ok=True)

            plugin_dir = plugins_dir / plugin_name
            if plugin_dir.exists():
                # Remove existing installation
                shutil.rmtree(plugin_dir)

            shutil.copytree(plugin_root, plugin_dir)

            # Load plugin
            if not load_single_plugin(plugin_dir, settings.ENGINES_DIR):
                raise InstallError(f"Failed to load plugin {plugin_name}")

            # Record installation
            await self._record_installation(plugin_name, version)

            self.installed_plugins.append(plugin_name)

            return plugin_dir

        except Exception as e:
            # Rollback on error
            if plugin_dir and plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            raise InstallError(f"Installation failed: {e}") from e

        finally:
            # Cleanup temp directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _download(self, url: str, dest: Path):
        """Download or copy a plugin package. Local paths are copied directly."""
        if url.startswith("/api/v1/marketplace/packages/"):
            # Local package — copy directly from _packages directory
            filename = url.split("/")[-1]
            local_path = Path(settings.PLUGINS_DIR) / "_packages" / filename
            if local_path.exists():
                shutil.copy2(local_path, dest)
                return

        # Remote URL — download via HTTP
        import os

        if url.startswith("/"):
            base = os.environ.get("SANDBOX_API_URL", "http://127.0.0.1:8000")
            url = f"{base}{url}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                with open(dest, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

    def _verify_hash(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file SHA256 hash."""
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        actual_hash = sha256.hexdigest()
        return actual_hash == expected_hash

    def _extract(self, zip_path: Path, dest_dir: Path):
        """Extract zip file safely."""
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Check for path traversal
            for member in zf.namelist():
                member_path = Path(dest_dir) / member
                if not member_path.resolve().is_relative_to(dest_dir.resolve()):
                    raise InstallError(f"Unsafe path in zip: {member}")

            zf.extractall(dest_dir)

    def _find_plugin_root(self, extract_dir: Path) -> Optional[Path]:
        """Find plugin root directory containing plugin.yaml."""
        # Check root level
        if (extract_dir / "plugin.yaml").exists():
            return extract_dir

        # Check one level deep
        for subdir in extract_dir.iterdir():
            if subdir.is_dir() and (subdir / "plugin.yaml").exists():
                return subdir

        return None

    async def _record_installation(self, plugin_name: str, version: str):
        """Record plugin installation in database."""
        # Check if already installed
        from sqlalchemy import select

        stmt = select(UserInstalledPlugin).where(
            UserInstalledPlugin.user_id == self.user_id,
            UserInstalledPlugin.plugin_name == plugin_name,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update version
            existing.version = version
        else:
            # Create new record
            record = UserInstalledPlugin(
                user_id=self.user_id,
                plugin_name=plugin_name,
                version=version,
            )
            self.session.add(record)

        await self.session.commit()

    async def rollback(self):
        """Rollback installed plugins."""
        plugins_dir = Path(settings.PLUGINS_DIR)

        for plugin_name in reversed(self.installed_plugins):
            plugin_dir = plugins_dir / plugin_name
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)

            # Remove from database
            from sqlalchemy import delete

            stmt = delete(UserInstalledPlugin).where(
                UserInstalledPlugin.user_id == self.user_id,
                UserInstalledPlugin.plugin_name == plugin_name,
            )
            await self.session.execute(stmt)

        await self.session.commit()
        self.installed_plugins.clear()

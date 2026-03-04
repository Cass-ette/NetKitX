"""Tests for security scanner."""

import tempfile
import zipfile
from pathlib import Path

import pytest

from app.marketplace.scanner import SecurityScanner


@pytest.fixture
def create_plugin_package():
    """Helper to create plugin packages for testing."""

    def _create(files: dict[str, str]) -> Path:
        """Create a plugin package with given files.

        Args:
            files: Dict of filename -> content

        Returns:
            Path to created zip file
        """
        temp_dir = Path(tempfile.mkdtemp())
        plugin_dir = temp_dir / "test-plugin"
        plugin_dir.mkdir()

        for filename, content in files.items():
            file_path = plugin_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        zip_path = temp_dir / "test-plugin.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file_path in plugin_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(temp_dir))

        return zip_path

    return _create


class TestSecurityScanner:
    """Test security scanner."""

    @pytest.mark.asyncio
    async def test_scan_safe_plugin(self, create_plugin_package):
        """Safe plugin passes scan."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: safe-plugin
version: 1.0.0
description: A safe plugin
category: utils
engine: python
license: MIT
""",
                "main.py": """
async def execute(params):
    result = params.get('input', '')
    yield {'output': result.upper()}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is True
        assert result.score >= 70
        assert result.critical_count == 0

    @pytest.mark.asyncio
    async def test_scan_dangerous_eval(self, create_plugin_package):
        """Plugin with eval() fails scan."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: dangerous-plugin
version: 1.0.0
description: Dangerous plugin
category: utils
engine: python
license: MIT
""",
                "main.py": """
async def execute(params):
    code = params.get('code', '')
    result = eval(code)  # Dangerous!
    yield {'result': result}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert result.critical_count > 0
        assert any("eval" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_dangerous_exec(self, create_plugin_package):
        """Plugin with exec() fails scan."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: dangerous-plugin
version: 1.0.0
description: Dangerous plugin
category: utils
engine: python
license: MIT
""",
                "main.py": """
async def execute(params):
    code = params.get('code', '')
    exec(code)  # Dangerous!
    yield {'result': 'done'}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert result.critical_count > 0
        assert any("exec" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_subprocess(self, create_plugin_package):
        """Plugin with subprocess gets flagged."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: subprocess-plugin
version: 1.0.0
description: Uses subprocess
category: utils
engine: python
license: MIT
""",
                "main.py": """
import subprocess

async def execute(params):
    cmd = params.get('command', 'ls')
    result = subprocess.call(cmd, shell=True)
    yield {'result': result}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert any("subprocess" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_path_traversal(self, create_plugin_package):
        """Zip with path traversal fails scan."""
        temp_dir = Path(tempfile.mkdtemp())
        zip_path = temp_dir / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious")

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert result.critical_count > 0
        assert any("path traversal" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_no_license(self, create_plugin_package):
        """Plugin without license gets warning."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: no-license-plugin
version: 1.0.0
description: No license
category: utils
engine: python
""",
                "main.py": """
async def execute(params):
    yield {'result': 'ok'}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert any("license" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_dangerous_permissions(self, create_plugin_package):
        """Plugin with dangerous permissions gets flagged."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: dangerous-perms
version: 1.0.0
description: Dangerous permissions
category: utils
engine: python
license: MIT
permissions:
  - filesystem:write
  - database:write
""",
                "main.py": """
async def execute(params):
    yield {'result': 'ok'}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert any("permission" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_javascript_eval(self, create_plugin_package):
        """JavaScript plugin with eval() gets flagged."""
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: js-plugin
version: 1.0.0
description: JavaScript plugin
category: utils
engine: javascript
license: MIT
""",
                "main.js": """
async function execute(params) {
    const code = params.code;
    const result = eval(code);  // Dangerous!
    return { result };
}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert any("eval" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_missing_plugin_yaml(self, create_plugin_package):
        """Package without plugin.yaml fails scan."""
        zip_path = create_plugin_package(
            {
                "main.py": """
async def execute(params):
    yield {'result': 'ok'}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        assert result.passed is False
        assert result.critical_count > 0
        assert any("plugin.yaml" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_scan_score_calculation(self, create_plugin_package):
        """Score decreases with more issues."""
        # Plugin with multiple medium issues
        zip_path = create_plugin_package(
            {
                "plugin.yaml": """
name: multi-issue
version: 1.0.0
description: Multiple issues
category: utils
engine: python
""",  # No license (medium)
                "main.py": """
import requests  # External HTTP (medium)

async def execute(params):
    url = params.get('url')
    response = requests.get(url)  # HTTP request (medium)
    with open('/tmp/output.txt', 'w') as f:  # File write (medium)
        f.write(response.text)
    yield {'result': 'done'}
""",
            }
        )

        scanner = SecurityScanner()
        result = await scanner.scan_package(zip_path)

        # Should have multiple medium issues
        medium_issues = [i for i in result.issues if i.severity == "medium"]
        assert len(medium_issues) >= 2

        # Score should be reduced but not critical
        assert result.score < 100
        assert result.score > 50

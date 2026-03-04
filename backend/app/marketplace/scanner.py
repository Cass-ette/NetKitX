"""Security scanner for plugin packages."""

import ast
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SecurityIssue:
    """Security issue found in plugin."""

    severity: str  # critical, high, medium, low
    category: str  # code, dependency, permission, malware
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


@dataclass
class ScanResult:
    """Result of security scan."""

    passed: bool
    issues: list[SecurityIssue]
    score: int  # 0-100, higher is better

    @property
    def critical_count(self) -> int:
        """Count critical issues."""
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        """Count high severity issues."""
        return sum(1 for i in self.issues if i.severity == "high")


class SecurityScanner:
    """Scan plugin packages for security issues."""

    # Dangerous Python modules and functions
    DANGEROUS_MODULES = {
        "subprocess",
        "os",
        "pickle",
        "marshal",
    }

    DANGEROUS_IMPORTS = {
        "eval",
        "exec",
        "compile",
        "__import__",
    }

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        (r"eval\s*\(", "Use of eval() is dangerous"),
        (r"exec\s*\(", "Use of exec() is dangerous"),
        (r"__import__\s*\(", "Dynamic imports can be dangerous"),
        (r"open\s*\([^)]*['\"]w['\"]", "File write operation"),
        (r"requests\.get\s*\([^)]*http", "External HTTP request"),
        (r"socket\.socket", "Direct socket usage"),
        (r"ctypes\.", "Use of ctypes (low-level)"),
    ]

    # Allowed licenses (permissive open source)
    ALLOWED_LICENSES = {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "GPL-3.0",
        "LGPL-3.0",
        "MPL-2.0",
    }

    def __init__(self):
        """Initialize scanner."""
        self.issues: list[SecurityIssue] = []

    async def scan_package(self, package_path: Path) -> ScanResult:
        """Scan a plugin package.

        Args:
            package_path: Path to plugin zip file

        Returns:
            ScanResult with issues found
        """
        self.issues = []

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                # Check for path traversal
                self._check_zip_safety(zf)

                # Extract to temp for analysis
                import tempfile

                with tempfile.TemporaryDirectory() as temp_dir:
                    zf.extractall(temp_dir)
                    temp_path = Path(temp_dir)

                    # Find plugin root
                    plugin_root = self._find_plugin_root(temp_path)
                    if not plugin_root:
                        self.issues.append(
                            SecurityIssue(
                                severity="critical",
                                category="code",
                                message="No plugin.yaml found",
                            )
                        )
                        return self._build_result()

                    # Scan plugin.yaml
                    self._scan_plugin_yaml(plugin_root)

                    # Scan Python files
                    for py_file in plugin_root.rglob("*.py"):
                        self._scan_python_file(py_file, plugin_root)

                    # Scan JavaScript files
                    for js_file in plugin_root.rglob("*.js"):
                        self._scan_javascript_file(js_file, plugin_root)

                    # Check file sizes
                    self._check_file_sizes(plugin_root)

        except zipfile.BadZipFile:
            self.issues.append(
                SecurityIssue(
                    severity="critical",
                    category="code",
                    message="Invalid zip file",
                )
            )
        except Exception as e:
            self.issues.append(
                SecurityIssue(
                    severity="high",
                    category="code",
                    message=f"Scan error: {e}",
                )
            )

        return self._build_result()

    def _check_zip_safety(self, zf: zipfile.ZipFile):
        """Check for path traversal in zip."""
        for name in zf.namelist():
            if name.startswith("/") or ".." in name:
                self.issues.append(
                    SecurityIssue(
                        severity="critical",
                        category="malware",
                        message=f"Path traversal attempt: {name}",
                    )
                )

    def _find_plugin_root(self, extract_dir: Path) -> Optional[Path]:
        """Find plugin root directory."""
        if (extract_dir / "plugin.yaml").exists():
            return extract_dir

        for subdir in extract_dir.iterdir():
            if subdir.is_dir() and (subdir / "plugin.yaml").exists():
                return subdir

        return None

    def _scan_plugin_yaml(self, plugin_root: Path):
        """Scan plugin.yaml for issues."""
        import yaml

        yaml_path = plugin_root / "plugin.yaml"
        try:
            with open(yaml_path) as f:
                config = yaml.safe_load(f)

            # Check license
            license_name = config.get("license")
            if not license_name:
                self.issues.append(
                    SecurityIssue(
                        severity="medium",
                        category="code",
                        message="No license specified",
                        file="plugin.yaml",
                    )
                )
            elif license_name not in self.ALLOWED_LICENSES:
                self.issues.append(
                    SecurityIssue(
                        severity="low",
                        category="code",
                        message=f"Non-standard license: {license_name}",
                        file="plugin.yaml",
                    )
                )

            # Check permissions
            permissions = config.get("permissions", [])
            dangerous_perms = {"filesystem:write", "database:write", "subprocess:exec"}
            for perm in permissions:
                if perm in dangerous_perms:
                    self.issues.append(
                        SecurityIssue(
                            severity="medium",
                            category="permission",
                            message=f"Dangerous permission requested: {perm}",
                            file="plugin.yaml",
                        )
                    )

        except Exception as e:
            self.issues.append(
                SecurityIssue(
                    severity="high",
                    category="code",
                    message=f"Invalid plugin.yaml: {e}",
                    file="plugin.yaml",
                )
            )

    def _scan_python_file(self, file_path: Path, plugin_root: Path):
        """Scan Python file for security issues."""
        try:
            content = file_path.read_text()
            rel_path = str(file_path.relative_to(plugin_root))

            # Parse AST
            try:
                tree = ast.parse(content)
                self._check_python_ast(tree, rel_path)
            except SyntaxError as e:
                self.issues.append(
                    SecurityIssue(
                        severity="high",
                        category="code",
                        message=f"Syntax error: {e}",
                        file=rel_path,
                        line=e.lineno,
                    )
                )

            # Pattern matching
            for pattern, message in self.SUSPICIOUS_PATTERNS:
                for match in re.finditer(pattern, content):
                    line_num = content[: match.start()].count("\n") + 1
                    self.issues.append(
                        SecurityIssue(
                            severity="medium",
                            category="code",
                            message=message,
                            file=rel_path,
                            line=line_num,
                        )
                    )

        except Exception as e:
            self.issues.append(
                SecurityIssue(
                    severity="low",
                    category="code",
                    message=f"Failed to scan {file_path.name}: {e}",
                )
            )

    def _check_python_ast(self, tree: ast.AST, file_path: str):
        """Check Python AST for dangerous patterns."""
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Check dangerous modules
                    if alias.name in self.DANGEROUS_MODULES:
                        self.issues.append(
                            SecurityIssue(
                                severity="high",
                                category="code",
                                message=f"Dangerous module import: {alias.name}",
                                file=file_path,
                                line=node.lineno,
                            )
                        )
                    # Check dangerous functions
                    if alias.name in self.DANGEROUS_IMPORTS:
                        self.issues.append(
                            SecurityIssue(
                                severity="high",
                                category="code",
                                message=f"Dangerous import: {alias.name}",
                                file=file_path,
                                line=node.lineno,
                            )
                        )

            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "compile"}:
                        self.issues.append(
                            SecurityIssue(
                                severity="critical",
                                category="code",
                                message=f"Dangerous function: {node.func.id}()",
                                file=file_path,
                                line=node.lineno,
                            )
                        )

    def _scan_javascript_file(self, file_path: Path, plugin_root: Path):
        """Scan JavaScript file for security issues."""
        try:
            content = file_path.read_text()
            rel_path = str(file_path.relative_to(plugin_root))

            # Check for dangerous patterns
            dangerous_js = [
                (r"eval\s*\(", "Use of eval()"),
                (r"Function\s*\(", "Dynamic function creation"),
                (r"document\.write", "Use of document.write"),
                (r"innerHTML\s*=", "Direct innerHTML assignment (XSS risk)"),
            ]

            for pattern, message in dangerous_js:
                for match in re.finditer(pattern, content):
                    line_num = content[: match.start()].count("\n") + 1
                    self.issues.append(
                        SecurityIssue(
                            severity="medium",
                            category="code",
                            message=message,
                            file=rel_path,
                            line=line_num,
                        )
                    )

        except Exception as e:
            self.issues.append(
                SecurityIssue(
                    severity="low",
                    category="code",
                    message=f"Failed to scan {file_path.name}: {e}",
                )
            )

    def _check_file_sizes(self, plugin_root: Path):
        """Check for suspiciously large files."""
        max_file_size = 10 * 1024 * 1024  # 10MB
        total_size = 0

        for file_path in plugin_root.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size

                if size > max_file_size:
                    self.issues.append(
                        SecurityIssue(
                            severity="medium",
                            category="code",
                            message=f"Large file: {size / 1024 / 1024:.1f}MB",
                            file=str(file_path.relative_to(plugin_root)),
                        )
                    )

        # Check total package size
        max_total_size = 50 * 1024 * 1024  # 50MB
        if total_size > max_total_size:
            self.issues.append(
                SecurityIssue(
                    severity="low",
                    category="code",
                    message=f"Large package: {total_size / 1024 / 1024:.1f}MB",
                )
            )

    def _build_result(self) -> ScanResult:
        """Build scan result with score."""
        # Calculate score (start at 100, deduct for issues)
        score = 100
        for issue in self.issues:
            if issue.severity == "critical":
                score -= 25
            elif issue.severity == "high":
                score -= 15
            elif issue.severity == "medium":
                score -= 5
            elif issue.severity == "low":
                score -= 2

        score = max(0, score)

        # Pass if no critical issues and score >= 70
        passed = self.critical_count == 0 and score >= 70

        return ScanResult(passed=passed, issues=self.issues, score=score)

    @property
    def critical_count(self) -> int:
        """Count critical issues."""
        return sum(1 for i in self.issues if i.severity == "critical")

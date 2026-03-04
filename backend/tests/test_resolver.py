"""Tests for dependency resolver."""

import pytest

from app.marketplace.resolver import (
    CircularDependencyError,
    ConflictError,
    Dependency,
    DependencyResolver,
    Package,
)


class TestSimpleDependencies:
    """Test simple dependency resolution."""

    def test_single_package_no_deps(self):
        """Resolve single package with no dependencies."""
        packages = {"plugin-a": [Package("plugin-a", "1.0.0", [])]}

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result == {"plugin-a": "1.0.0"}

    def test_single_dependency(self):
        """Resolve package with one dependency."""
        packages = {
            "plugin-a": [
                Package(
                    "plugin-a",
                    "1.0.0",
                    [Dependency("plugin-b", ">=1.0.0")],
                )
            ],
            "plugin-b": [Package("plugin-b", "1.0.0", [])],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result == {"plugin-a": "1.0.0", "plugin-b": "1.0.0"}

    def test_chain_dependencies(self):
        """Resolve chain of dependencies A -> B -> C."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", ">=1.0.0")])],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-c", ">=1.0.0")])],
            "plugin-c": [Package("plugin-c", "1.0.0", [])],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result == {
            "plugin-a": "1.0.0",
            "plugin-b": "1.0.0",
            "plugin-c": "1.0.0",
        }

    def test_select_latest_version(self):
        """Select latest version when no specific version requested."""
        packages = {
            "plugin-a": [
                Package("plugin-a", "1.0.0", []),
                Package("plugin-a", "1.5.0", []),
                Package("plugin-a", "2.0.0", []),
            ]
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result == {"plugin-a": "2.0.0"}

    def test_select_specific_version(self):
        """Select specific version when requested."""
        packages = {
            "plugin-a": [
                Package("plugin-a", "1.0.0", []),
                Package("plugin-a", "2.0.0", []),
            ]
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a", "1.0.0")

        assert result == {"plugin-a": "1.0.0"}


class TestVersionConstraints:
    """Test version constraint matching."""

    def test_constraint_selects_highest_matching(self):
        """Constraint selects highest matching version."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", ">=1.0.0,<2.0.0")])],
            "plugin-b": [
                Package("plugin-b", "1.0.0", []),
                Package("plugin-b", "1.5.0", []),
                Package("plugin-b", "2.0.0", []),
            ],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result["plugin-b"] == "1.5.0"

    def test_caret_constraint(self):
        """Caret constraint matches compatible versions."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", "^1.2.0")])],
            "plugin-b": [
                Package("plugin-b", "1.0.0", []),
                Package("plugin-b", "1.2.0", []),
                Package("plugin-b", "1.9.0", []),
                Package("plugin-b", "2.0.0", []),
            ],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result["plugin-b"] == "1.9.0"


class TestConflicts:
    """Test conflict detection."""

    def test_no_matching_version(self):
        """Raise error when no version matches constraint."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", ">=2.0.0")])],
            "plugin-b": [Package("plugin-b", "1.0.0", [])],
        }

        resolver = DependencyResolver(packages)
        with pytest.raises(ConflictError, match="No version of 'plugin-b' satisfies"):
            resolver.resolve("plugin-a")

    def test_version_conflict(self):
        """Raise error when two dependencies need different versions."""
        packages = {
            "plugin-a": [
                Package(
                    "plugin-a",
                    "1.0.0",
                    [
                        Dependency("plugin-b", "1.0.0"),
                        Dependency("plugin-c", "1.0.0"),
                    ],
                )
            ],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-d", "1.0.0")])],
            "plugin-c": [Package("plugin-c", "1.0.0", [Dependency("plugin-d", "2.0.0")])],
            "plugin-d": [
                Package("plugin-d", "1.0.0", []),
                Package("plugin-d", "2.0.0", []),
            ],
        }

        resolver = DependencyResolver(packages)
        with pytest.raises(ConflictError, match="Version conflict"):
            resolver.resolve("plugin-a")

    def test_missing_dependency(self):
        """Raise error when dependency not found."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-missing", ">=1.0.0")])]
        }

        resolver = DependencyResolver(packages)
        with pytest.raises(ConflictError, match="Dependency 'plugin-missing' not found"):
            resolver.resolve("plugin-a")


class TestCircularDependencies:
    """Test circular dependency detection."""

    def test_direct_circular(self):
        """Detect direct circular dependency A -> B -> A."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", ">=1.0.0")])],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-a", ">=1.0.0")])],
        }

        resolver = DependencyResolver(packages)
        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            resolver.resolve("plugin-a")

    def test_indirect_circular(self):
        """Detect indirect circular dependency A -> B -> C -> A."""
        packages = {
            "plugin-a": [Package("plugin-a", "1.0.0", [Dependency("plugin-b", ">=1.0.0")])],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-c", ">=1.0.0")])],
            "plugin-c": [Package("plugin-c", "1.0.0", [Dependency("plugin-a", ">=1.0.0")])],
        }

        resolver = DependencyResolver(packages)
        with pytest.raises(CircularDependencyError):
            resolver.resolve("plugin-a")


class TestOptionalDependencies:
    """Test optional dependency handling."""

    def test_optional_dependency_skipped(self):
        """Optional dependencies are not resolved."""
        packages = {
            "plugin-a": [
                Package(
                    "plugin-a",
                    "1.0.0",
                    [Dependency("plugin-b", ">=1.0.0", optional=True)],
                )
            ],
            "plugin-b": [Package("plugin-b", "1.0.0", [])],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        # Only plugin-a should be in solution, not optional plugin-b
        assert result == {"plugin-a": "1.0.0"}


class TestComplexScenarios:
    """Test complex dependency scenarios."""

    def test_diamond_dependency(self):
        """Resolve diamond dependency: A -> B,C and B,C -> D."""
        packages = {
            "plugin-a": [
                Package(
                    "plugin-a",
                    "1.0.0",
                    [
                        Dependency("plugin-b", ">=1.0.0"),
                        Dependency("plugin-c", ">=1.0.0"),
                    ],
                )
            ],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-d", ">=1.0.0")])],
            "plugin-c": [Package("plugin-c", "1.0.0", [Dependency("plugin-d", ">=1.0.0")])],
            "plugin-d": [Package("plugin-d", "1.0.0", [])],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        assert result == {
            "plugin-a": "1.0.0",
            "plugin-b": "1.0.0",
            "plugin-c": "1.0.0",
            "plugin-d": "1.0.0",
        }

    def test_multiple_versions_same_constraint(self):
        """Multiple packages depend on same plugin with compatible constraints."""
        packages = {
            "plugin-a": [
                Package(
                    "plugin-a",
                    "1.0.0",
                    [
                        Dependency("plugin-b", ">=1.0.0"),
                        Dependency("plugin-c", ">=1.0.0"),
                    ],
                )
            ],
            "plugin-b": [Package("plugin-b", "1.0.0", [Dependency("plugin-d", "^1.0.0")])],
            "plugin-c": [Package("plugin-c", "1.0.0", [Dependency("plugin-d", "^1.2.0")])],
            "plugin-d": [
                Package("plugin-d", "1.0.0", []),
                Package("plugin-d", "1.2.0", []),
                Package("plugin-d", "1.5.0", []),
            ],
        }

        resolver = DependencyResolver(packages)
        result = resolver.resolve("plugin-a")

        # Should select 1.5.0 which satisfies both ^1.0.0 and ^1.2.0
        assert result["plugin-d"] == "1.5.0"

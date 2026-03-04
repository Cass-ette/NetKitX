"""Dependency resolver using simplified PubGrub algorithm."""

from dataclasses import dataclass
from typing import Optional

from app.marketplace.version import Version, VersionConstraint


@dataclass
class Dependency:
    """Plugin dependency."""

    plugin_name: str
    constraint: str
    optional: bool = False


@dataclass
class Package:
    """Package with version and dependencies."""

    name: str
    version: str
    dependencies: list[Dependency]


class ConflictError(Exception):
    """Dependency conflict error."""

    pass


class CircularDependencyError(Exception):
    """Circular dependency error."""

    pass


class DependencyResolver:
    """Resolve plugin dependencies."""

    def __init__(self, available_packages: dict[str, list[Package]]):
        """Initialize resolver with available packages.

        Args:
            available_packages: Dict mapping plugin name to list of available versions
        """
        self.available_packages = available_packages
        self.solution: dict[str, str] = {}  # plugin_name -> selected_version
        self.visited: set[str] = set()  # For circular dependency detection

    def resolve(self, root_plugin: str, root_version: Optional[str] = None) -> dict[str, str]:
        """Resolve dependencies for a plugin.

        Args:
            root_plugin: Plugin name to install
            root_version: Specific version or None for latest

        Returns:
            Dict mapping plugin name to selected version

        Raises:
            ConflictError: If dependencies cannot be satisfied
            CircularDependencyError: If circular dependency detected
        """
        self.solution = {}
        self.visited = set()

        # Find root package
        if root_plugin not in self.available_packages:
            raise ConflictError(f"Plugin '{root_plugin}' not found")

        packages = self.available_packages[root_plugin]
        if not packages:
            raise ConflictError(f"No versions available for '{root_plugin}'")

        # Select root version
        if root_version:
            root_pkg = next((p for p in packages if p.version == root_version), None)
            if not root_pkg:
                raise ConflictError(f"Version '{root_version}' not found for '{root_plugin}'")
        else:
            # Select latest version
            root_pkg = max(packages, key=lambda p: Version.parse(p.version))

        # Start resolution
        self._resolve_package(root_pkg)

        return self.solution

    def _resolve_package(self, package: Package):
        """Recursively resolve a package's dependencies."""
        # Check for circular dependency
        if package.name in self.visited:
            raise CircularDependencyError(f"Circular dependency detected: {package.name}")

        # Already resolved with compatible version
        if package.name in self.solution:
            existing_version = self.solution[package.name]
            if existing_version != package.version:
                raise ConflictError(
                    f"Version conflict for '{package.name}': "
                    f"need {package.version}, already have {existing_version}"
                )
            return

        # Mark as visiting
        self.visited.add(package.name)

        # Add to solution
        self.solution[package.name] = package.version

        # Resolve dependencies
        for dep in package.dependencies:
            if dep.optional:
                # Skip optional dependencies for now
                continue

            self._resolve_dependency(dep)

        # Mark as resolved
        self.visited.remove(package.name)

    def _resolve_dependency(self, dep: Dependency):
        """Resolve a single dependency."""
        if dep.plugin_name not in self.available_packages:
            raise ConflictError(f"Dependency '{dep.plugin_name}' not found")

        packages = self.available_packages[dep.plugin_name]
        if not packages:
            raise ConflictError(f"No versions available for '{dep.plugin_name}'")

        # Find matching version
        constraint = VersionConstraint(dep.constraint)
        matching = [p for p in packages if constraint.matches(Version.parse(p.version))]

        if not matching:
            raise ConflictError(
                f"No version of '{dep.plugin_name}' satisfies constraint '{dep.constraint}'"
            )

        # Select highest matching version
        selected = max(matching, key=lambda p: Version.parse(p.version))

        # Recursively resolve
        self._resolve_package(selected)


def resolve_dependencies(
    plugin_name: str,
    version: Optional[str],
    available_packages: dict[str, list[Package]],
) -> dict[str, str]:
    """Convenience function to resolve dependencies.

    Args:
        plugin_name: Plugin to install
        version: Specific version or None for latest
        available_packages: Available packages by name

    Returns:
        Dict mapping plugin name to selected version
    """
    resolver = DependencyResolver(available_packages)
    return resolver.resolve(plugin_name, version)

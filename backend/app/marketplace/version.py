"""Semantic versioning utilities."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Version:
    """Semantic version."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse version string."""
        # SemVer regex pattern
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
        match = re.match(pattern, version_str.strip())

        if not match:
            raise ValueError(f"Invalid version string: {version_str}")

        major, minor, patch, prerelease, build = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build,
        )

    def __str__(self) -> str:
        """String representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )

    def __lt__(self, other: "Version") -> bool:
        """Less than comparison."""
        # Compare major.minor.patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

        # Prerelease versions have lower precedence
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and other.prerelease:
            return self._compare_prerelease(self.prerelease, other.prerelease) < 0

        return False

    def __le__(self, other: "Version") -> bool:
        """Less than or equal comparison."""
        return self == other or self < other

    def __gt__(self, other: "Version") -> bool:
        """Greater than comparison."""
        return not self <= other

    def __ge__(self, other: "Version") -> bool:
        """Greater than or equal comparison."""
        return not self < other

    @staticmethod
    def _compare_prerelease(pre1: str, pre2: str) -> int:
        """Compare prerelease versions."""
        parts1 = pre1.split(".")
        parts2 = pre2.split(".")

        for p1, p2 in zip(parts1, parts2):
            # Numeric comparison if both are numbers
            if p1.isdigit() and p2.isdigit():
                if int(p1) != int(p2):
                    return int(p1) - int(p2)
            # Numeric identifiers have lower precedence
            elif p1.isdigit():
                return -1
            elif p2.isdigit():
                return 1
            # Lexical comparison
            elif p1 != p2:
                return -1 if p1 < p2 else 1

        # Longer prerelease has higher precedence
        return len(parts1) - len(parts2)


class VersionConstraint:
    """Version constraint matcher."""

    def __init__(self, constraint_str: str):
        """Initialize constraint."""
        self.constraint_str = constraint_str.strip()
        self._parse()

    def _parse(self):
        """Parse constraint string."""
        # Range must be checked first: ">=1.0.0,<2.0.0"
        if "," in self.constraint_str:
            self.type = "range"
            parts = [p.strip() for p in self.constraint_str.split(",")]
            self.constraints = [VersionConstraint(p) for p in parts]

        # Exact version: "1.2.3"
        elif re.match(r"^\d+\.\d+\.\d+", self.constraint_str):
            self.type = "exact"
            self.version = Version.parse(self.constraint_str)

        # Greater than or equal: ">=1.2.3"
        elif self.constraint_str.startswith(">="):
            self.type = "gte"
            self.version = Version.parse(self.constraint_str[2:])

        # Greater than: ">1.2.3"
        elif self.constraint_str.startswith(">"):
            self.type = "gt"
            self.version = Version.parse(self.constraint_str[1:])

        # Less than or equal: "<=1.2.3"
        elif self.constraint_str.startswith("<="):
            self.type = "lte"
            self.version = Version.parse(self.constraint_str[2:])

        # Less than: "<1.2.3"
        elif self.constraint_str.startswith("<"):
            self.type = "lt"
            self.version = Version.parse(self.constraint_str[1:])

        # Caret: "^1.2.3" (compatible with 1.x.x)
        elif self.constraint_str.startswith("^"):
            self.type = "caret"
            self.version = Version.parse(self.constraint_str[1:])

        # Tilde: "~1.2.3" (compatible with 1.2.x)
        elif self.constraint_str.startswith("~"):
            self.type = "tilde"
            self.version = Version.parse(self.constraint_str[1:])

        # Wildcard: "1.2.*" or "1.*"
        elif "*" in self.constraint_str:
            self.type = "wildcard"
            self.pattern = self.constraint_str.replace("*", r"\d+")

        else:
            raise ValueError(f"Invalid constraint: {self.constraint_str}")

    def matches(self, version: Version) -> bool:
        """Check if version matches constraint."""
        if self.type == "exact":
            return version == self.version

        elif self.type == "gte":
            return version >= self.version

        elif self.type == "gt":
            return version > self.version

        elif self.type == "lte":
            return version <= self.version

        elif self.type == "lt":
            return version < self.version

        elif self.type == "caret":
            # ^1.2.3 matches >=1.2.3 <2.0.0
            if self.version.major == 0:
                # ^0.2.3 matches >=0.2.3 <0.3.0
                return (
                    version >= self.version
                    and version.major == 0
                    and version.minor == self.version.minor
                )
            return version >= self.version and version.major == self.version.major

        elif self.type == "tilde":
            # ~1.2.3 matches >=1.2.3 <1.3.0
            return (
                version >= self.version
                and version.major == self.version.major
                and version.minor == self.version.minor
            )

        elif self.type == "wildcard":
            return bool(re.match(self.pattern, str(version)))

        elif self.type == "range":
            return all(c.matches(version) for c in self.constraints)

        return False


def find_best_version(versions: list[str], constraint: str) -> Optional[str]:
    """Find best matching version."""
    constraint_obj = VersionConstraint(constraint)
    matching = []

    for v_str in versions:
        try:
            v = Version.parse(v_str)
            if constraint_obj.matches(v):
                matching.append((v, v_str))
        except ValueError:
            continue

    if not matching:
        return None

    # Return highest matching version
    matching.sort(key=lambda x: x[0], reverse=True)
    return matching[0][1]

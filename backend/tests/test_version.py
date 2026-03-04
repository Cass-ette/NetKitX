"""Tests for marketplace version manager."""

import pytest

from app.marketplace.version import Version, VersionConstraint, find_best_version


class TestVersionParse:
    """Test Version.parse()."""

    def test_basic(self):
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None

    def test_prerelease(self):
        v = Version.parse("1.0.0-alpha.1")
        assert v.major == 1
        assert v.prerelease == "alpha.1"

    def test_build_metadata(self):
        v = Version.parse("1.0.0+build.123")
        assert v.build == "build.123"

    def test_invalid(self):
        with pytest.raises(ValueError):
            Version.parse("not-a-version")

    def test_str(self):
        assert str(Version.parse("1.2.3")) == "1.2.3"
        assert str(Version.parse("1.0.0-beta")) == "1.0.0-beta"


class TestVersionComparison:
    """Test version comparison operators."""

    def test_equal(self):
        assert Version.parse("1.2.3") == Version.parse("1.2.3")
        assert not (Version.parse("1.2.3") == Version.parse("1.2.4"))

    def test_lt(self):
        assert Version.parse("1.0.0") < Version.parse("2.0.0")
        assert Version.parse("1.0.0") < Version.parse("1.1.0")
        assert Version.parse("1.0.0") < Version.parse("1.0.1")

    def test_gt(self):
        assert Version.parse("2.0.0") > Version.parse("1.9.9")

    def test_prerelease_lower_than_release(self):
        assert Version.parse("1.0.0-alpha") < Version.parse("1.0.0")

    def test_prerelease_ordering(self):
        assert Version.parse("1.0.0-alpha") < Version.parse("1.0.0-beta")
        assert Version.parse("1.0.0-alpha.1") < Version.parse("1.0.0-alpha.2")


class TestVersionConstraint:
    """Test VersionConstraint.matches()."""

    def test_exact(self):
        c = VersionConstraint("1.2.3")
        assert c.matches(Version.parse("1.2.3"))
        assert not c.matches(Version.parse("1.2.4"))

    def test_gte(self):
        c = VersionConstraint(">=1.2.0")
        assert c.matches(Version.parse("1.2.0"))
        assert c.matches(Version.parse("2.0.0"))
        assert not c.matches(Version.parse("1.1.9"))

    def test_gt(self):
        c = VersionConstraint(">1.2.0")
        assert c.matches(Version.parse("1.2.1"))
        assert not c.matches(Version.parse("1.2.0"))

    def test_lte(self):
        c = VersionConstraint("<=1.2.0")
        assert c.matches(Version.parse("1.2.0"))
        assert c.matches(Version.parse("1.0.0"))
        assert not c.matches(Version.parse("1.2.1"))

    def test_lt(self):
        c = VersionConstraint("<2.0.0")
        assert c.matches(Version.parse("1.9.9"))
        assert not c.matches(Version.parse("2.0.0"))

    def test_caret_major(self):
        c = VersionConstraint("^1.2.3")
        assert c.matches(Version.parse("1.2.3"))
        assert c.matches(Version.parse("1.9.9"))
        assert not c.matches(Version.parse("2.0.0"))
        assert not c.matches(Version.parse("1.2.2"))

    def test_caret_zero_major(self):
        c = VersionConstraint("^0.2.3")
        assert c.matches(Version.parse("0.2.3"))
        assert c.matches(Version.parse("0.2.9"))
        assert not c.matches(Version.parse("0.3.0"))

    def test_tilde(self):
        c = VersionConstraint("~1.2.3")
        assert c.matches(Version.parse("1.2.3"))
        assert c.matches(Version.parse("1.2.9"))
        assert not c.matches(Version.parse("1.3.0"))

    def test_range(self):
        c = VersionConstraint(">=1.0.0,<2.0.0")
        assert c.matches(Version.parse("1.0.0"))
        assert c.matches(Version.parse("1.9.9"))
        assert not c.matches(Version.parse("2.0.0"))
        assert not c.matches(Version.parse("0.9.9"))

    def test_invalid_constraint(self):
        with pytest.raises(ValueError):
            VersionConstraint("invalid")


class TestFindBestVersion:
    """Test find_best_version()."""

    def test_find_latest(self):
        versions = ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]
        assert find_best_version(versions, ">=1.0.0") == "2.0.0"

    def test_find_within_range(self):
        versions = ["1.0.0", "1.5.0", "2.0.0"]
        assert find_best_version(versions, ">=1.0.0,<2.0.0") == "1.5.0"

    def test_no_match(self):
        versions = ["1.0.0", "1.5.0"]
        assert find_best_version(versions, ">=2.0.0") is None

    def test_empty_list(self):
        assert find_best_version([], ">=1.0.0") is None

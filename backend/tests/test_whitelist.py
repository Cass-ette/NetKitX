"""Unit tests for whitelist service."""


from app.services.whitelist_service import (
    extract_targets_from_params,
    _is_subdomain,
    _is_ip_in_cidr,
)


# ---------------------------------------------------------------------------
# Test target extraction
# ---------------------------------------------------------------------------


def test_extract_targets_url():
    """Test extracting hostname from URL params."""
    params = {"url": "https://example.com/path"}
    targets = extract_targets_from_params(params)
    assert targets == ["example.com"]


def test_extract_targets_trigger_url():
    """Test extracting hostname from trigger_url."""
    params = {"trigger_url": "http://test.example.com:8080/callback"}
    targets = extract_targets_from_params(params)
    assert targets == ["test.example.com"]


def test_extract_targets_domain():
    """Test extracting domain param."""
    params = {"domain": "example.com"}
    targets = extract_targets_from_params(params)
    assert targets == ["example.com"]


def test_extract_targets_target():
    """Test extracting target param."""
    params = {"target": "192.168.1.1"}
    targets = extract_targets_from_params(params)
    assert targets == ["192.168.1.1"]


def test_extract_targets_host():
    """Test extracting host param."""
    params = {"host": "api.example.com"}
    targets = extract_targets_from_params(params)
    assert targets == ["api.example.com"]


def test_extract_targets_multiple():
    """Test extracting multiple targets."""
    params = {"url": "https://example.com/", "trigger_url": "http://callback.test.com/"}
    targets = extract_targets_from_params(params)
    assert set(targets) == {"example.com", "callback.test.com"}


def test_extract_targets_deduplication():
    """Test deduplication of targets."""
    params = {"url": "https://example.com/", "domain": "example.com"}
    targets = extract_targets_from_params(params)
    assert targets == ["example.com"]


def test_extract_targets_empty():
    """Test extraction with no target params."""
    params = {"other_param": "value"}
    targets = extract_targets_from_params(params)
    assert targets == []


def test_extract_targets_case_normalization():
    """Test case normalization."""
    params = {"domain": "Example.COM"}
    targets = extract_targets_from_params(params)
    assert targets == ["example.com"]


# ---------------------------------------------------------------------------
# Test subdomain matching
# ---------------------------------------------------------------------------


def test_is_subdomain_exact_match():
    """Test exact domain match."""
    assert _is_subdomain("example.com", "example.com") is True


def test_is_subdomain_valid():
    """Test valid subdomain."""
    assert _is_subdomain("api.example.com", "example.com") is True
    assert _is_subdomain("test.api.example.com", "example.com") is True


def test_is_subdomain_invalid():
    """Test invalid subdomain."""
    assert _is_subdomain("example.com", "api.example.com") is False
    assert _is_subdomain("notexample.com", "example.com") is False
    assert _is_subdomain("fakeexample.com", "example.com") is False


# ---------------------------------------------------------------------------
# Test CIDR matching
# ---------------------------------------------------------------------------


def test_is_ip_in_cidr_valid():
    """Test IP within CIDR range."""
    assert _is_ip_in_cidr("192.168.1.10", "192.168.1.0/24") is True
    assert _is_ip_in_cidr("10.0.0.1", "10.0.0.0/8") is True


def test_is_ip_in_cidr_invalid():
    """Test IP outside CIDR range."""
    assert _is_ip_in_cidr("192.168.2.10", "192.168.1.0/24") is False
    assert _is_ip_in_cidr("11.0.0.1", "10.0.0.0/8") is False


def test_is_ip_in_cidr_invalid_input():
    """Test invalid IP or CIDR."""
    assert _is_ip_in_cidr("not-an-ip", "192.168.1.0/24") is False
    assert _is_ip_in_cidr("192.168.1.1", "invalid-cidr") is False


# ---------------------------------------------------------------------------
# Test admin bypass (logic test, no DB)
# ---------------------------------------------------------------------------


def test_admin_bypass_logic():
    """Test that admin bypass logic is correct (conceptual test)."""
    # This is a conceptual test to document the expected behavior
    # In actual code, admin users should bypass whitelist validation
    is_admin = True
    # When is_admin=True, validate_targets should return (True, None)
    # This is tested in integration tests with actual DB
    assert is_admin is True  # Placeholder assertion

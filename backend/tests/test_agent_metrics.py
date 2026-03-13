"""Unit tests for agent_metrics helpers (no real Redis required)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent_metrics import (
    compute_health_score,
    get_metrics,
    list_active_sessions,
    publish_metrics,
    remove_session,
)


# ---------------------------------------------------------------------------
# health score
# ---------------------------------------------------------------------------


def test_health_score_perfect():
    # 50 + 20(ok) + 15(no stag) + 15(no err) = 100
    assert compute_health_score(0, 0, False, all_actions_ok=True) == 100


def test_health_score_stagnation():
    # 50 + 20(ok) - 24(stag=3) + 15(no err) = 61
    assert compute_health_score(3, 0, False, all_actions_ok=True) == 61


def test_health_score_errors():
    # 50 + 15(no stag) - 30(err=2) = 35
    assert compute_health_score(0, 2, False, all_actions_ok=False) == 35


def test_health_score_negative():
    # 50 + 20(ok) + 15(no stag) + 15(no err) - 10(neg) = 90
    assert compute_health_score(0, 0, True, all_actions_ok=True) == 90


def test_health_score_combined():
    # 50 - 40(stag=5) - 30(err=2) - 10(neg) = -30 → 0
    assert compute_health_score(5, 2, True, all_actions_ok=False) == 0


def test_health_score_floor():
    assert compute_health_score(10, 10, True, all_actions_ok=False) == 0


def test_health_score_recovery():
    """After stagnation clears and actions succeed, score bounces back."""
    bad = compute_health_score(3, 1, True, all_actions_ok=False)
    good = compute_health_score(0, 0, False, all_actions_ok=True)
    assert good > bad
    assert good == 100


# ---------------------------------------------------------------------------
# publish / get
# ---------------------------------------------------------------------------


def _make_redis_mock():
    """Create a dict-backed fake Redis."""
    store: dict[str, str] = {}
    sets: dict[str, set[str]] = {}

    r = AsyncMock()

    async def _set(key, value, ex=None):
        store[key] = value

    async def _get(key):
        return store.get(key)

    async def _delete(key):
        store.pop(key, None)

    async def _sadd(key, member):
        sets.setdefault(key, set()).add(member)

    async def _smembers(key):
        return set(sets.get(key, set()))

    async def _srem(key, member):
        s = sets.get(key)
        if s:
            s.discard(member)

    r.set = AsyncMock(side_effect=_set)
    r.get = AsyncMock(side_effect=_get)
    r.delete = AsyncMock(side_effect=_delete)
    r.sadd = AsyncMock(side_effect=_sadd)
    r.smembers = AsyncMock(side_effect=_smembers)
    r.srem = AsyncMock(side_effect=_srem)
    r.aclose = AsyncMock()
    return r


@pytest.fixture()
def mock_redis():
    r = _make_redis_mock()
    with patch("app.services.agent_metrics._get_redis", return_value=r):
        yield r


@pytest.mark.asyncio
async def test_publish_and_get(mock_redis):
    await publish_metrics(42, {"turn": 1, "health_score": 100})
    result = await get_metrics(42)
    assert result is not None
    assert result["turn"] == 1
    assert result["health_score"] == 100
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_get_missing(mock_redis):
    result = await get_metrics(999)
    assert result is None


@pytest.mark.asyncio
async def test_list_active_sessions(mock_redis):
    await publish_metrics(1, {"session_id": 1, "turn": 2})
    await publish_metrics(2, {"session_id": 2, "turn": 5})
    sessions = await list_active_sessions()
    assert len(sessions) == 2
    ids = {s["session_id"] for s in sessions}
    assert ids == {1, 2}


@pytest.mark.asyncio
async def test_remove_session(mock_redis):
    await publish_metrics(10, {"session_id": 10, "turn": 1})
    sessions = await list_active_sessions()
    assert len(sessions) == 1

    await remove_session(10)
    sessions = await list_active_sessions()
    assert len(sessions) == 0
    assert await get_metrics(10) is None


@pytest.mark.asyncio
async def test_expired_cleanup(mock_redis):
    """If metrics key expired but session ID still in set, list should prune it."""
    # Manually add session to set without corresponding metrics key
    await mock_redis.sadd("agent:active_sessions", "99")
    sessions = await list_active_sessions()
    assert len(sessions) == 0
    # Should have been removed from the set
    remaining = await mock_redis.smembers("agent:active_sessions")
    assert "99" not in remaining

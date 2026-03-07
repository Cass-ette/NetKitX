"""Tests for admin API endpoints."""

import pytest
from httpx import AsyncClient

from app.models import User, Announcement
from app.models.task import Task
from app.models.plugin import Plugin


# ── Helper ───────────────────────────────────────────────────────────


async def _make_admin(db_session, test_user):
    test_user.role = "admin"
    await db_session.commit()


# ── User Management ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.get("/api/v1/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "admin_users" in data
    assert "total_tasks" in data
    assert "total_plugins" in data


@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    assert users[0]["username"] == "testuser"


@pytest.mark.asyncio
async def test_admin_change_role(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    user2 = User(username="user2", email="user2@example.com", hashed_password="hashed")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    response = await client.patch(f"/api/v1/admin/users/{user2.id}/role", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.patch(f"/api/v1/admin/users/{test_user.id}/role", json={"role": "user"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_delete_user(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    user2 = User(username="user2", email="user2@example.com", hashed_password="hashed")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    response = await client.delete(f"/api/v1/admin/users/{user2.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.delete(f"/api/v1/admin/users/{test_user.id}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_forbidden(client: AsyncClient, test_user):
    response = await client.get("/api/v1/admin/stats")
    assert response.status_code == 403


# ── Task Management ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_tasks(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    task = Task(plugin_name="nmap", status="done", created_by=test_user.id)
    db_session.add(task)
    await db_session.commit()

    response = await client.get("/api/v1/admin/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["tasks"]) >= 1


@pytest.mark.asyncio
async def test_admin_list_tasks_filter_status(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    db_session.add(Task(plugin_name="nmap", status="done", created_by=test_user.id))
    db_session.add(Task(plugin_name="nmap", status="running", created_by=test_user.id))
    await db_session.commit()

    response = await client.get("/api/v1/admin/tasks?status=running")
    assert response.status_code == 200
    data = response.json()
    for t in data["tasks"]:
        assert t["status"] == "running"


@pytest.mark.asyncio
async def test_admin_cancel_task(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    task = Task(plugin_name="nmap", status="running", created_by=test_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.post(f"/api/v1/admin/tasks/{task.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_admin_delete_task(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    task = Task(plugin_name="nmap", status="done", created_by=test_user.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.delete(f"/api/v1/admin/tasks/{task.id}")
    assert response.status_code == 200


# ── Plugin Management ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_plugins(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    plugin = Plugin(name="test-plugin", version="1.0.0", category="recon", engine="python")
    db_session.add(plugin)
    await db_session.commit()

    response = await client.get("/api/v1/admin/plugins")
    assert response.status_code == 200
    plugins = response.json()
    assert len(plugins) >= 1
    assert plugins[0]["usage_count"] >= 0


@pytest.mark.asyncio
async def test_admin_toggle_plugin(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    plugin = Plugin(
        name="toggle-plugin", version="1.0.0", category="recon", engine="python", enabled=True
    )
    db_session.add(plugin)
    await db_session.commit()

    response = await client.patch("/api/v1/admin/plugins/toggle-plugin/toggle")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


# ── Audit Log ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_audit_log_created_on_action(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    user2 = User(username="audituser", email="audit@example.com", hashed_password="hashed")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    # Changing role should create audit log
    await client.patch(f"/api/v1/admin/users/{user2.id}/role", json={"role": "admin"})

    response = await client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(log["action"] == "change_role" for log in data["logs"])


# ── User Quotas ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_get_user_quota(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.get(f"/api/v1/admin/users/{test_user.id}/quota")
    assert response.status_code == 200
    data = response.json()
    assert data["max_concurrent_tasks"] == 5
    assert data["max_daily_tasks"] == 100
    assert "current_running_tasks" in data
    assert "tasks_today" in data


@pytest.mark.asyncio
async def test_admin_update_user_quota(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.patch(
        f"/api/v1/admin/users/{test_user.id}/quota",
        json={"max_concurrent_tasks": 10, "max_daily_tasks": 200},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["max_concurrent_tasks"] == 10
    assert data["max_daily_tasks"] == 200


# ── Announcements ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_create_announcement(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    response = await client.post(
        "/api/v1/admin/announcements",
        json={"title": "Test", "content": "Test content", "type": "info"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test"
    assert data["active"] is True


@pytest.mark.asyncio
async def test_admin_list_announcements(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    ann = Announcement(title="Visible", content="content", type="info", created_by=test_user.id)
    db_session.add(ann)
    await db_session.commit()

    response = await client.get("/api/v1/admin/announcements")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_admin_update_announcement(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    ann = Announcement(title="Original", content="content", type="info", created_by=test_user.id)
    db_session.add(ann)
    await db_session.commit()
    await db_session.refresh(ann)

    response = await client.patch(
        f"/api/v1/admin/announcements/{ann.id}",
        json={"title": "Updated", "active": False},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["active"] is False


@pytest.mark.asyncio
async def test_admin_delete_announcement(client: AsyncClient, db_session, test_user):
    await _make_admin(db_session, test_user)
    ann = Announcement(title="ToDelete", content="content", type="info", created_by=test_user.id)
    db_session.add(ann)
    await db_session.commit()
    await db_session.refresh(ann)

    response = await client.delete(f"/api/v1/admin/announcements/{ann.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_announcements(client: AsyncClient, db_session, test_user):
    ann = Announcement(
        title="Public", content="visible", type="warning", active=True, created_by=test_user.id
    )
    db_session.add(ann)
    await db_session.commit()

    response = await client.get("/api/v1/announcements")
    assert response.status_code == 200
    data = response.json()
    assert any(a["title"] == "Public" for a in data)


# ── Task Quota Check ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_quota_concurrent_limit(client: AsyncClient, db_session, test_user):
    """Verify 429 when concurrent task limit reached."""
    from unittest.mock import MagicMock

    from app.plugins.registry import registry

    # Register a fake plugin so the 404 check passes
    fake_meta = MagicMock()
    fake_meta.name = "fake-plugin"
    original_get_meta = registry.get_meta
    registry.get_meta = lambda name: fake_meta if name == "fake-plugin" else None

    try:
        test_user.max_concurrent_tasks = 1
        await db_session.commit()

        task = Task(plugin_name="fake-plugin", status="running", created_by=test_user.id)
        db_session.add(task)
        await db_session.commit()

        response = await client.post("/api/v1/tasks", json={"plugin_name": "fake-plugin"})
        assert response.status_code == 429
    finally:
        registry.get_meta = original_get_meta

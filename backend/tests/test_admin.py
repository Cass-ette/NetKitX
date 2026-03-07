"""Tests for admin API endpoints."""

import pytest
from httpx import AsyncClient

from app.models import User


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient, db_session, test_user):
    """Test admin stats endpoint."""
    # Make test_user an admin
    test_user.role = "admin"
    await db_session.commit()

    response = await client.get("/api/v1/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "admin_users" in data
    assert "total_tasks" in data
    assert "total_plugins" in data


@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient, db_session, test_user):
    """Test listing users."""
    test_user.role = "admin"
    await db_session.commit()

    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    assert users[0]["username"] == "testuser"


@pytest.mark.asyncio
async def test_admin_change_role(client: AsyncClient, db_session, test_user):
    """Test changing user role."""
    test_user.role = "admin"
    await db_session.commit()

    # Create another user
    user2 = User(username="user2", email="user2@example.com", hashed_password="hashed")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    response = await client.patch(f"/api/v1/admin/users/{user2.id}/role", json={"role": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client: AsyncClient, db_session, test_user):
    """Test that admin cannot change their own role."""
    test_user.role = "admin"
    await db_session.commit()

    response = await client.patch(f"/api/v1/admin/users/{test_user.id}/role", json={"role": "user"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_delete_user(client: AsyncClient, db_session, test_user):
    """Test deleting a user."""
    test_user.role = "admin"
    await db_session.commit()

    # Create another user
    user2 = User(username="user2", email="user2@example.com", hashed_password="hashed")
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    response = await client.delete(f"/api/v1/admin/users/{user2.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client: AsyncClient, db_session, test_user):
    """Test that admin cannot delete themselves."""
    test_user.role = "admin"
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/users/{test_user.id}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_forbidden(client: AsyncClient, test_user):
    """Test that non-admin users get 403."""
    # test_user is not admin by default
    response = await client.get("/api/v1/admin/stats")
    assert response.status_code == 403

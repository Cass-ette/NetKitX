"""Terminal session management API: create/destroy per-user sandbox containers."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/session")
async def start_session(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Start (or reuse) sandbox container for the current user."""
    from app.services.container_service import (
        get_user_container,
        create_user_container,
        get_container_status,
    )

    container_id = get_user_container(user.id)
    if container_id:
        status = get_container_status(user.id)
        return {"created": False, "container_id": container_id[:12], **status}

    # Extract token so the sandbox netkitx CLI is pre-authenticated
    auth_header = request.headers.get("Authorization", "")
    user_token = auth_header.removeprefix("Bearer ").strip()

    try:
        container_id = create_user_container(user.id, user_token)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    status = get_container_status(user.id)
    return {"created": True, "container_id": container_id[:12], **status}


@router.get("/session")
async def get_session_status(
    user: User = Depends(get_current_user),
):
    """Get current sandbox container status."""
    from app.services.container_service import get_container_status

    return get_container_status(user.id)


@router.delete("/session")
async def stop_session(
    user: User = Depends(get_current_user),
):
    """Destroy the user's sandbox container."""
    from app.services.container_service import destroy_user_container

    destroy_user_container(user.id)
    return {"destroyed": True, "user_id": user.id}

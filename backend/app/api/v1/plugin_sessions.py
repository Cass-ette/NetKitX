import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.deps import get_current_user
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.plugin_session import SessionCreate, SessionResponse
from app.services.session_plugin_service import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/plugin-sessions", response_model=SessionResponse)
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
):
    """Create a new plugin session."""
    try:
        session_id = await session_manager.create_session(body.plugin_name, user.id, body.params)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    info = await session_manager.get_session(session_id)
    return SessionResponse(**info)


@router.get("/plugin-sessions", response_model=list[SessionResponse])
async def list_sessions(user: User = Depends(get_current_user)):
    """List active sessions for the current user."""
    sessions = await session_manager.list_user_sessions(user.id)
    return [SessionResponse(**s) for s in sessions]


@router.get("/plugin-sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, user: User = Depends(get_current_user)):
    """Get session info."""
    info = await session_manager.get_session(session_id)
    if info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if info["user_id"] != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return SessionResponse(**info)


@router.delete("/plugin-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_session(session_id: str, user: User = Depends(get_current_user)):
    """Close a plugin session."""
    if not await session_manager.validate_session_owner(session_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await session_manager.close_session(session_id)


async def plugin_session_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for plugin session communication."""
    # Authenticate via query param token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    username = decode_access_token(token)
    if not username:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify session exists and belongs to user
    info = await session_manager.get_session(session_id)
    if info is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    logger.info("WebSocket connected for session %s", session_id)

    try:
        while True:
            raw = await websocket.receive_text()

            # Handle ping/pong keepalive
            if raw == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "data": {"error": "Invalid JSON"}})
                )
                continue

            msg_type = msg.get("type", "message")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "message":
                data = msg.get("data", {})
                async for event in session_manager.send_message(session_id, data):
                    await websocket.send_text(
                        json.dumps(
                            {"type": "event", "data": {"type": event.type, "data": event.data}}
                        )
                    )

            elif msg_type == "close":
                await session_manager.close_session(session_id)
                await websocket.send_text(
                    json.dumps({"type": "session_end", "data": {"reason": "client_close"}})
                )
                await websocket.close()
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception as e:
        logger.error("WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.send_text(json.dumps({"type": "error", "data": {"error": str(e)}}))
        except Exception:
            pass

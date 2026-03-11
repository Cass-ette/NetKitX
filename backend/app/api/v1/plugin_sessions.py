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
    """
    Create a new plugin session for the authenticated user.
    
    Parameters:
        body (SessionCreate): Request payload specifying `plugin_name` and `params` for the new session.
    
    Returns:
        SessionResponse: Details of the created session.
    
    Raises:
        HTTPException: 400 if session creation fails (e.g., invalid parameters or business rule violation).
    """
    try:
        session_id = await session_manager.create_session(body.plugin_name, user.id, body.params)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    info = await session_manager.get_session(session_id)
    return SessionResponse(**info)


@router.get("/plugin-sessions", response_model=list[SessionResponse])
async def list_sessions(user: User = Depends(get_current_user)):
    """
    List active plugin sessions belonging to the current user.
    
    Returns:
        list[SessionResponse]: A list of SessionResponse objects representing the user's active sessions.
    """
    sessions = await session_manager.list_user_sessions(user.id)
    return [SessionResponse(**s) for s in sessions]


@router.get("/plugin-sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, user: User = Depends(get_current_user)):
    """
    Retrieve a plugin session by ID for the current user.
    
    Raises:
        HTTPException: 404 if the session does not exist.
        HTTPException: 403 if the session exists but is not owned by the current user.
    
    Returns:
        SessionResponse: Session information for the requested session.
    """
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
    """
    Handle a WebSocket connection for a plugin session, authenticating the client and routing messages and events.
    
    The connection is authenticated using an access token provided as the "token" query parameter; if the token is missing or invalid the socket is closed. If the session does not exist the socket is closed. After accepting the connection, the handler:
    - Responds to plain-text "ping" or JSON messages with `"type": "ping"` by sending `{"type": "pong"}`.
    - Accepts JSON messages with a `"type"` field:
      - `"message"`: forwards the message `data` to the session and streams back generated events as messages with `{"type": "event", "data": {"type": <event.type>, "data": <event.data>}}`.
      - `"close"`: closes the session, sends `{"type": "session_end", "data": {"reason": "client_close"}}`, and closes the socket.
    - On malformed JSON, sends `{"type": "error", "data": {"error": "Invalid JSON"}}`.
    - On unexpected errors, attempts to send `{"type": "error", "data": {"error": "<error message>"}}` and logs the error.
    
    Parameters:
        websocket (WebSocket): The FastAPI WebSocket connection.
        session_id (str): The identifier of the plugin session to attach to.
    """
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

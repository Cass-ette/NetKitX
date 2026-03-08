"""Knowledge service: session persistence & event-to-turn conversion."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.knowledge import AgentSession, KnowledgeEntry, SessionTurn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    agent_mode: str,
    security_mode: str,
    lang: str,
) -> AgentSession:
    session = AgentSession(
        user_id=user_id,
        title=title[:300],
        agent_mode=agent_mode,
        security_mode=security_mode,
        lang=lang,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_sessions(
    db: AsyncSession,
    user_id: int,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[AgentSession], int]:
    total = (
        await db.execute(select(func.count(AgentSession.id)).where(AgentSession.user_id == user_id))
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                select(AgentSession)
                .where(AgentSession.user_id == user_id)
                .order_by(AgentSession.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return list(rows), total


async def get_session_detail(
    db: AsyncSession, session_id: int, user_id: int
) -> AgentSession | None:
    row = (
        await db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id, AgentSession.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    return row


async def get_session_turns(db: AsyncSession, session_id: int) -> list[SessionTurn]:
    rows = (
        (
            await db.execute(
                select(SessionTurn)
                .where(SessionTurn.session_id == session_id)
                .order_by(SessionTurn.turn_number, SessionTurn.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def delete_session(db: AsyncSession, session_id: int, user_id: int) -> bool:
    session = await get_session_detail(db, session_id, user_id)
    if not session:
        return False
    await db.execute(delete(SessionTurn).where(SessionTurn.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Knowledge CRUD (Phase 2 data, endpoints ready)
# ---------------------------------------------------------------------------


async def get_knowledge_entries(
    db: AsyncSession,
    user_id: int,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[KnowledgeEntry], int]:
    total = (
        await db.execute(
            select(func.count(KnowledgeEntry.id)).where(KnowledgeEntry.user_id == user_id)
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                select(KnowledgeEntry)
                .where(KnowledgeEntry.user_id == user_id)
                .order_by(KnowledgeEntry.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return list(rows), total


async def delete_knowledge_entry(db: AsyncSession, entry_id: int, user_id: int) -> bool:
    row = (
        await db.execute(
            select(KnowledgeEntry).where(
                KnowledgeEntry.id == entry_id, KnowledgeEntry.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Event → Turn conversion (pure logic, testable)
# ---------------------------------------------------------------------------


def _events_to_turns(
    messages: list[dict[str, str]],
    collected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert raw SSE events + original messages into SessionTurn dicts.

    Returns a list of dicts ready for SessionTurn(**d) construction.
    """
    turns: list[dict[str, Any]] = []
    turn_number = 0

    # 1. Add original user messages
    for msg in messages:
        if msg.get("role") == "user":
            turns.append(
                {
                    "turn_number": turn_number,
                    "role": "user",
                    "content": msg.get("content", ""),
                }
            )

    # 2. Process collected SSE events
    current_content = ""
    current_action: dict | None = None
    current_action_status: str | None = None

    for evt in collected:
        event_type = evt.get("event", "")
        data = evt.get("data", {}) if isinstance(evt.get("data"), dict) else {}

        if event_type == "turn":
            # Flush previous assistant content if any
            if current_content or current_action:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": current_action,
                        "action_status": current_action_status,
                    }
                )
                current_content = ""
                current_action = None
                current_action_status = None
            turn_number = data.get("turn", turn_number + 1)

        elif event_type == "text":
            current_content += data.get("content", "")

        elif event_type == "action":
            current_action = data.get("action")
            current_action_status = "proposed"

        elif event_type == "action_status":
            current_action_status = "executing"

        elif event_type == "action_result":
            # Flush assistant turn with action
            if current_content or current_action:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": current_action,
                        "action_status": "done",
                    }
                )
                current_content = ""
                current_action = None
                current_action_status = None

            # Add action result as separate turn
            turns.append(
                {
                    "turn_number": turn_number,
                    "role": "action_result",
                    "content": "",
                    "action_result": data.get("result"),
                }
            )

        elif event_type == "action_error":
            error_data = {
                "error": data.get("error", ""),
                "error_type": data.get("error_type", ""),
            }
            if current_content or current_action:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": current_action,
                        "action_result": error_data,
                        "action_status": "error",
                    }
                )
                current_content = ""
                current_action = None
                current_action_status = None
            else:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "action_result",
                        "content": "",
                        "action_result": error_data,
                    }
                )

        elif event_type == "done":
            break

    # Flush any remaining assistant content
    if current_content or current_action:
        turns.append(
            {
                "turn_number": turn_number,
                "role": "assistant",
                "content": current_content,
                "action": current_action,
                "action_status": current_action_status,
            }
        )

    return turns


# ---------------------------------------------------------------------------
# Finalize session (runs in background after SSE stream ends)
# ---------------------------------------------------------------------------


async def finalize_session(
    session_id: int,
    collected: list[dict[str, Any]],
    messages: list[dict[str, str]],
    reason: str,
) -> None:
    """Save turns and update session status. Opens its own DB session."""
    try:
        async with async_session() as db:
            # Convert events to turns
            turn_dicts = _events_to_turns(messages, collected)

            # Batch insert
            for td in turn_dicts:
                turn = SessionTurn(
                    session_id=session_id,
                    turn_number=td.get("turn_number", 0),
                    role=td["role"],
                    content=td.get("content", ""),
                    action=td.get("action"),
                    action_result=td.get("action_result"),
                    action_status=td.get("action_status"),
                )
                db.add(turn)

            # Update session
            agent_session = (
                await db.execute(select(AgentSession).where(AgentSession.id == session_id))
            ).scalar_one_or_none()

            if agent_session:
                status = "completed" if reason in ("complete", "waiting", "max_turns") else "failed"
                # Count actual turn events
                max_turn = 0
                for td in turn_dicts:
                    if td.get("turn_number", 0) > max_turn:
                        max_turn = td["turn_number"]
                agent_session.status = status
                agent_session.total_turns = max_turn
                agent_session.finished_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info("Session %d finalized: %s (%d turns)", session_id, reason, len(turn_dicts))

    except Exception:
        logger.exception("Failed to finalize session %d", session_id)

"""Session & knowledge REST endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    AgentSessionDetail,
    AgentSessionResponse,
    KnowledgeEntryResponse,
    KnowledgeListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    SessionListResponse,
    SessionTurnResponse,
)
from app.services.knowledge_service import (
    delete_knowledge_entry,
    delete_session,
    extract_knowledge,
    get_knowledge_entries,
    get_session_detail,
    get_session_turns,
    get_sessions,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    items, total = await get_sessions(db, user.id, offset, limit)
    return SessionListResponse(
        items=[AgentSessionResponse.model_validate(s) for s in items],
        total=total,
    )


@router.get("/sessions/{session_id}", response_model=AgentSessionDetail)
async def get_session_by_id(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    session = await get_session_detail(db, session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    turns = await get_session_turns(db, session_id)
    return AgentSessionDetail(
        **AgentSessionResponse.model_validate(session).model_dump(),
        turns=[SessionTurnResponse.model_validate(t) for t in turns],
    )


@router.delete("/sessions/{session_id}")
async def remove_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    deleted = await delete_session(db, session_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Knowledge (Phase 2 data, endpoints ready)
# ---------------------------------------------------------------------------


@router.get("/knowledge", response_model=KnowledgeListResponse)
async def list_knowledge(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    items, total = await get_knowledge_entries(db, user.id, offset, limit)
    return KnowledgeListResponse(
        items=[KnowledgeEntryResponse.model_validate(e) for e in items],
        total=total,
    )


@router.delete("/knowledge/{entry_id}")
async def remove_knowledge(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    deleted = await delete_knowledge_entry(db, entry_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return {"ok": True}


@router.post("/sessions/{session_id}/extract")
async def extract_session_knowledge(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Trigger knowledge extraction for a completed session."""
    session = await get_session_detail(db, session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Launch extraction in background
    asyncio.create_task(
        _run_extraction(session_id, user.id),
    )
    return {"status": "processing", "session_id": session_id}


async def _run_extraction(session_id: int, user_id: int) -> None:
    try:
        await extract_knowledge(session_id, user_id)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Background extraction failed for session %d", session_id
        )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    user: User = Depends(get_current_user),
):
    """Search knowledge entries by semantic similarity."""
    from app.core.config import settings
    from app.services.embedding_service import search_similar_knowledge

    if not settings.RAG_ENABLED:
        return KnowledgeSearchResponse(results=[])

    results = await search_similar_knowledge(body.query, user.id, limit=body.limit)
    return KnowledgeSearchResponse(
        results=[
            KnowledgeSearchResult(
                knowledge=KnowledgeEntryResponse.model_validate(entry),
                similarity=round(sim, 4),
            )
            for entry, sim in results
        ]
    )

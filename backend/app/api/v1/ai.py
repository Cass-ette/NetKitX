"""AI analysis & chat endpoints (SSE streaming)."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.models.ai_settings import AISettings
from app.schemas.ai import AISettingsUpdate, AISettingsResponse, AIAnalyzeRequest, AIChatRequest
from app.services.ai_service import (
    encrypt_key,
    decrypt_key,
    mask_key,
    stream_claude,
    stream_deepseek,
    get_system_prompt,
    get_lang_reminder,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_ai_settings(session: AsyncSession, user_id: int) -> AISettings | None:
    result = await session.execute(select(AISettings).where(AISettings.user_id == user_id))
    return result.scalar_one_or_none()


@router.get("/settings", response_model=AISettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ai = await _get_ai_settings(session, user.id)
    if not ai:
        raise HTTPException(status_code=404, detail="AI not configured")
    plain_key = decrypt_key(ai.api_key_enc)
    return AISettingsResponse(
        provider=ai.provider,
        api_key_masked=mask_key(plain_key),
        model=ai.model,
    )


@router.put("/settings", response_model=AISettingsResponse)
async def update_settings(
    body: AISettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ai = await _get_ai_settings(session, user.id)
    enc = encrypt_key(body.api_key)
    if ai:
        ai.provider = body.provider
        ai.api_key_enc = enc
        ai.model = body.model
    else:
        ai = AISettings(
            user_id=user.id,
            provider=body.provider,
            api_key_enc=enc,
            model=body.model,
        )
        session.add(ai)
    await session.commit()
    return AISettingsResponse(
        provider=body.provider,
        api_key_masked=mask_key(body.api_key),
        model=body.model,
    )


@router.delete("/settings")
async def delete_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ai = await _get_ai_settings(session, user.id)
    if ai:
        await session.delete(ai)
        await session.commit()
    return {"ok": True}


async def _stream_ai(provider: str, api_key: str, model: str, messages: list[dict[str, str]]):
    if provider == "claude":
        gen = stream_claude(api_key, model, messages)
    elif provider == "deepseek":
        gen = stream_deepseek(api_key, model, messages)
    else:
        yield f"data: {json.dumps({'error': 'Unknown provider'})}\n\n"
        return

    async for chunk in gen:
        yield f"data: {json.dumps({'content': chunk})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/analyze")
async def analyze(
    body: AIAnalyzeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ai = await _get_ai_settings(session, user.id)
    if not ai:
        raise HTTPException(status_code=400, detail="AI not configured")

    api_key = decrypt_key(ai.api_key_enc)

    # Build context from task if provided
    context_parts: list[str] = []
    if body.task_id:
        from app.services.task_service import get_task

        task = await get_task(session, body.task_id)
        if task:
            context_parts.append(f"Tool: {task.plugin_name}")
            context_parts.append(f"Status: {task.status}")
            if task.params:
                context_parts.append(f"Parameters: {json.dumps(task.params)}")
            if task.result:
                result_str = json.dumps(task.result, default=str)
                # Truncate very large results
                if len(result_str) > 8000:
                    result_str = result_str[:8000] + "...(truncated)"
                context_parts.append(f"Results:\n{result_str}")

    if body.content:
        context_parts.append(body.content)

    user_content = "\n\n".join(context_parts) if context_parts else "No data provided."
    if body.custom_prompt:
        user_content = f"{body.custom_prompt}\n\n---\n\n{user_content}"
    user_content += get_lang_reminder(body.lang)

    messages = [
        {"role": "system", "content": get_system_prompt(body.mode, body.lang)},
        {"role": "user", "content": user_content},
    ]

    return StreamingResponse(
        _stream_ai(ai.provider, api_key, ai.model, messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat")
async def chat(
    body: AIChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ai = await _get_ai_settings(session, user.id)
    if not ai:
        raise HTTPException(status_code=400, detail="AI not configured")

    api_key = decrypt_key(ai.api_key_enc)

    # Prepend system prompt for security context
    messages = [
        {"role": "system", "content": get_system_prompt(body.mode, body.lang)},
        *body.messages,
    ]

    return StreamingResponse(
        _stream_ai(ai.provider, api_key, ai.model, messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

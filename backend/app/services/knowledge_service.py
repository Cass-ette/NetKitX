"""Knowledge service: session persistence, event-to-turn conversion, knowledge extraction."""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.knowledge import AgentSession, KnowledgeEntry, SessionTurn

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a cybersecurity knowledge extractor. Analyze this agent session and extract structured data.

Return a JSON object with exactly these fields:
- scenario: (string) Brief description of the attack/defense scenario
- target_type: (string) One of: web|network|host|api|cloud|other
- vulnerability_type: (string) One of: sqli|xss|rce|ssrf|shellshock|lfi|rfi|misconfig|privesc|other
- tools_used: (array of strings) Tools and commands used
- attack_chain: (string) Step-by-step progression of what was attempted
- outcome: (string) One of: success|partial|failed
- key_findings: (string) Important technical discoveries
- tags: (array of strings) Searchable keywords
- summary: (string) 2-3 sentence executive summary

Return ONLY valid JSON, no markdown code fences, no extra text.

Session data:
{digest}"""

REPORT_PROMPT = """\
Based on this cybersecurity session analysis, write a concise learning report.

Format as markdown with these sections:
## 场景概述
(1-2 sentences)

## 攻击/防御过程
(numbered key steps, what worked and what didn't)

## 关键教训
(each lesson: what went wrong/right, why, how to do better next time)

## 正确做法
(the optimal approach for this type of scenario)

{lang_instruction}

Extraction data:
{extraction_json}"""


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
    current_actions: list[dict] = []
    current_action_status: str | None = None

    def _flush_action() -> dict | list[dict] | None:
        """Return single dict or list depending on count."""
        if len(current_actions) > 1:
            return list(current_actions)
        elif len(current_actions) == 1:
            return current_actions[0]
        return None

    for evt in collected:
        event_type = evt.get("event", "")
        data = evt.get("data", {}) if isinstance(evt.get("data"), dict) else {}

        if event_type == "turn":
            # Flush previous assistant content if any
            if current_content or current_actions:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": _flush_action(),
                        "action_status": current_action_status,
                    }
                )
                current_content = ""
                current_actions = []
                current_action_status = None
            turn_number = data.get("turn", turn_number + 1)

        elif event_type == "text":
            current_content += data.get("content", "")

        elif event_type == "action":
            # Support both single action and multi-action events
            actions_data = data.get("actions")
            action_data = data.get("action")
            if actions_data and isinstance(actions_data, list):
                current_actions.extend(actions_data)
            elif action_data:
                current_actions.append(action_data)
            current_action_status = "proposed"

        elif event_type == "action_status":
            current_action_status = "executing"

        elif event_type == "action_result":
            # On first action_result, flush assistant turn with accumulated actions
            if current_content or current_actions:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": _flush_action(),
                        "action_status": "done",
                    }
                )
                current_content = ""
                current_actions = []
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
            if current_content or current_actions:
                turns.append(
                    {
                        "turn_number": turn_number,
                        "role": "assistant",
                        "content": current_content,
                        "action": _flush_action(),
                        "action_result": error_data,
                        "action_status": "error",
                    }
                )
                current_content = ""
                current_actions = []
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
    if current_content or current_actions:
        turns.append(
            {
                "turn_number": turn_number,
                "role": "assistant",
                "content": current_content,
                "action": _flush_action(),
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
    user_id: int | None = None,
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
                status = (
                    "completed"
                    if reason in ("complete", "waiting", "max_turns", "stagnation", "aborted")
                    else "failed"
                )
                # Count actual turn events
                max_turn = 0
                for td in turn_dicts:
                    if td.get("turn_number", 0) > max_turn:
                        max_turn = td["turn_number"]
                agent_session.status = status
                agent_session.total_turns = max_turn
                agent_session.finished_at = datetime.utcnow()

            await db.commit()
            logger.info("Session %d finalized: %s (%d turns)", session_id, reason, len(turn_dicts))

        # Auto-extract knowledge if enabled
        from app.core.config import settings

        if settings.AUTO_EXTRACT_KNOWLEDGE and user_id is not None:
            try:
                await extract_knowledge(session_id, user_id)
            except Exception:
                logger.exception("Auto-extract failed for session %d", session_id)

    except Exception:
        logger.exception("Failed to finalize session %d", session_id)


# ---------------------------------------------------------------------------
# Knowledge Extraction (Phase 2)
# ---------------------------------------------------------------------------

MAX_RESULT_CHARS = 500


def _compress_action_result(result: dict | None) -> str:
    """Compress an action result dict into a compact string for digest."""
    if not result:
        return "(no output)"
    parts = []
    if result.get("error"):
        parts.append(f"ERROR: {str(result['error'])[:MAX_RESULT_CHARS]}")
    if result.get("exit_code") is not None:
        parts.append(f"exit_code={result['exit_code']}")
    if result.get("stdout"):
        stdout = str(result["stdout"])[:MAX_RESULT_CHARS]
        parts.append(f"stdout: {stdout}")
    if result.get("stderr"):
        stderr = str(result["stderr"])[:MAX_RESULT_CHARS]
        parts.append(f"stderr: {stderr}")
    if result.get("items"):
        items = result["items"]
        items_str = json.dumps(items[:5], default=str, ensure_ascii=False)
        if len(items_str) > MAX_RESULT_CHARS:
            items_str = items_str[:MAX_RESULT_CHARS] + "..."
        parts.append(f"{len(items)} result(s): {items_str}")
    return " | ".join(parts) if parts else "(empty result)"


def _format_single_action(action: dict) -> str:
    """Format a single action dict into a one-line description."""
    atype = action.get("type", "?")
    if atype == "plugin":
        desc = f"plugin: {action.get('plugin', '?')}"
        params = action.get("params")
        if params:
            desc += f" params={json.dumps(params, ensure_ascii=False)[:200]}"
    elif atype == "shell":
        desc = f"shell: {action.get('command', '?')[:200]}"
    else:
        desc = json.dumps(action, ensure_ascii=False)[:200]
    return desc


def build_session_digest(turns: list[SessionTurn]) -> str:
    """Compress session turns into a compact text digest for AI extraction."""
    lines: list[str] = []
    for turn in turns:
        if turn.role == "user":
            lines.append(f"[User] {turn.content[:1000]}")
        elif turn.role == "assistant":
            content_preview = turn.content[:500] if turn.content else ""
            if content_preview:
                lines.append(f"[Turn {turn.turn_number}] {content_preview}")
            if turn.action:
                action = turn.action
                if isinstance(action, list):
                    for a in action:
                        lines.append(f"[Action] {_format_single_action(a)}")
                elif isinstance(action, dict):
                    lines.append(f"[Action] {_format_single_action(action)}")
        elif turn.role == "action_result":
            compressed = _compress_action_result(turn.action_result)
            lines.append(f"[Result] {compressed}")
    return "\n".join(lines)


def _parse_extraction_json(raw: str) -> dict[str, Any]:
    """Parse AI extraction response, handling markdown fences."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else 3
        text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


VALID_TARGET_TYPES = {"web", "network", "host", "api", "cloud", "other"}
VALID_VULN_TYPES = {
    "sqli",
    "xss",
    "rce",
    "ssrf",
    "shellshock",
    "lfi",
    "rfi",
    "misconfig",
    "privesc",
    "other",
}
VALID_OUTCOMES = {"success", "partial", "failed"}


def _sanitize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and normalize extracted fields."""
    return {
        "scenario": str(data.get("scenario", ""))[:500],
        "target_type": data.get("target_type", "other")
        if data.get("target_type") in VALID_TARGET_TYPES
        else "other",
        "vulnerability_type": data.get("vulnerability_type", "other")
        if data.get("vulnerability_type") in VALID_VULN_TYPES
        else "other",
        "tools_used": data.get("tools_used") if isinstance(data.get("tools_used"), list) else [],
        "attack_chain": str(data.get("attack_chain", ""))[:2000],
        "outcome": data.get("outcome", "partial")
        if data.get("outcome") in VALID_OUTCOMES
        else "partial",
        "key_findings": str(data.get("key_findings", ""))[:2000],
        "tags": data.get("tags") if isinstance(data.get("tags"), list) else [],
        "summary": str(data.get("summary", ""))[:1000],
    }


async def extract_knowledge(session_id: int, user_id: int) -> int:
    """Extract knowledge from a completed session. Returns KnowledgeEntry.id."""
    from app.models.ai_settings import AISettings
    from app.services.ai_service import call_ai, decrypt_key, get_lang_reminder

    async with async_session() as db:
        # Check for existing successful extraction
        existing = (
            await db.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.session_id == session_id,
                    KnowledgeEntry.user_id == user_id,
                    KnowledgeEntry.extraction_status == "success",
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing.id

        # Clean up stuck "processing" or "failed" entries so we can retry
        stale = (
            (
                await db.execute(
                    select(KnowledgeEntry).where(
                        KnowledgeEntry.session_id == session_id,
                        KnowledgeEntry.user_id == user_id,
                        KnowledgeEntry.extraction_status.in_(["processing", "failed"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        for entry in stale:
            await db.delete(entry)
        if stale:
            await db.commit()

        # Load session + turns
        session_row = (
            await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id, AgentSession.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if not session_row:
            raise ValueError(f"Session {session_id} not found for user {user_id}")

        turns = await get_session_turns(db, session_id)
        if not turns:
            raise ValueError(f"Session {session_id} has no turns")

        # Load AI settings
        ai_row = (
            await db.execute(select(AISettings).where(AISettings.user_id == user_id))
        ).scalar_one_or_none()
        if not ai_row:
            raise ValueError("AI not configured")

        api_key = decrypt_key(ai_row.api_key_enc)

        # Create pending entry
        entry = KnowledgeEntry(
            user_id=user_id,
            session_id=session_id,
            extraction_status="processing",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        entry_id = entry.id

    # Run extraction outside the DB session to avoid long-held connections
    try:
        async with async_session() as db:
            digest = build_session_digest(turns)
            prompt = EXTRACTION_PROMPT.format(digest=digest)

            # Call 1: Structured extraction
            extraction_raw = await call_ai(
                provider=ai_row.provider,
                api_key=api_key,
                model=ai_row.model,
                messages=[{"role": "user", "content": prompt}],
                base_url=ai_row.base_url,
            )

            extracted = _parse_extraction_json(extraction_raw)
            sanitized = _sanitize_extraction(extracted)

            # Call 2: Learning report
            lang = session_row.lang or "en"
            from app.services.ai_service import LANG_MAP

            lang_name = LANG_MAP.get(lang, lang)
            lang_instruction = f"Write the entire report in {lang_name}."
            report_prompt = REPORT_PROMPT.format(
                extraction_json=json.dumps(sanitized, ensure_ascii=False, indent=2),
                lang_instruction=lang_instruction,
            )
            report_prompt += get_lang_reminder(lang)

            learning_report = await call_ai(
                provider=ai_row.provider,
                api_key=api_key,
                model=ai_row.model,
                messages=[{"role": "user", "content": report_prompt}],
                base_url=ai_row.base_url,
            )

            # Update entry
            entry_row = (
                await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id))
            ).scalar_one()
            entry_row.scenario = sanitized["scenario"]
            entry_row.target_type = sanitized["target_type"]
            entry_row.vulnerability_type = sanitized["vulnerability_type"]
            entry_row.tools_used = sanitized["tools_used"]
            entry_row.attack_chain = sanitized["attack_chain"]
            entry_row.outcome = sanitized["outcome"]
            entry_row.key_findings = sanitized["key_findings"]
            entry_row.tags = sanitized["tags"]
            entry_row.summary = sanitized["summary"]
            entry_row.learning_report = learning_report
            entry_row.raw_data = extracted
            entry_row.extraction_status = "success"

            # Update session summary
            session_obj = (
                await db.execute(select(AgentSession).where(AgentSession.id == session_id))
            ).scalar_one_or_none()
            if session_obj:
                session_obj.summary = sanitized["summary"][:300]

            await db.commit()
            logger.info(
                "Knowledge extraction complete for session %d, entry %d", session_id, entry_id
            )

            # Auto-embed if RAG is enabled
            try:
                from app.services.embedding_service import embed_knowledge_entry

                await embed_knowledge_entry(entry_id)
            except Exception:
                logger.exception("Auto-embed failed for entry %d", entry_id)

            return entry_id

    except Exception:
        logger.exception("Knowledge extraction failed for session %d", session_id)
        # Mark entry as failed
        try:
            async with async_session() as db:
                entry_row = (
                    await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id))
                ).scalar_one_or_none()
                if entry_row:
                    entry_row.extraction_status = "failed"
                    await db.commit()
        except Exception:
            logger.exception("Failed to mark entry %d as failed", entry_id)
        raise

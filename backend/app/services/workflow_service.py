"""Workflow service: extract from sessions, CRUD, replay execution."""

import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import AgentSession, SessionTurn
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)

LANG_MAP = {
    "zh-CN": "Simplified Chinese (简体中文)",
    "zh-TW": "Traditional Chinese (繁體中文)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "de": "German (Deutsch)",
    "fr": "French (Français)",
    "ru": "Russian (Русский)",
    "en": "English",
}


# ---------------------------------------------------------------------------
# Pure functions (testable without DB)
# ---------------------------------------------------------------------------


def _summarize_result(result: dict | None) -> str:
    """One-line summary of an action result."""
    if result is None:
        return ""
    if result.get("error"):
        return f"Error: {str(result['error'])[:120]}"
    if result.get("items"):
        return f"{len(result['items'])} result(s)"
    if result.get("stdout"):
        first_line = str(result["stdout"]).strip().split("\n")[0]
        return first_line[:120]
    if result.get("exit_code") is not None:
        return f"exit_code={result['exit_code']}"
    return ""


def build_reflection_prompt(
    workflow_name: str,
    completed_steps: list[dict],
    current_label: str,
    current_result: dict,
    step: int,
    total: int,
    lang: str = "en",
) -> str:
    """Build a prompt asking AI to reflect on the current workflow step.

    Args:
        workflow_name: Name of the workflow being replayed.
        completed_steps: List of dicts with keys label, type, result_summary.
        current_label: Label of the current step.
        current_result: Full result dict of the current step.
        step: Current step number (1-based).
        total: Total number of action steps.
        lang: Language code for output.
    """
    lang_name = LANG_MAP.get(lang or "en", lang or "en")

    parts: list[str] = []
    parts.append(f'You are analyzing step {step}/{total} of workflow "{workflow_name}".')

    if completed_steps:
        parts.append("\nCompleted steps:")
        for s in completed_steps:
            parts.append(
                f"  - [{s.get('type', 'plugin')}] {s.get('label', '?')}"
                f": {s.get('result_summary', '')}"
            )

    parts.append(f"\nCurrent step: {current_label}")

    result_str = json.dumps(current_result, default=str, ensure_ascii=False)
    if len(result_str) > 2000:
        result_str = result_str[:2000] + "..."
    parts.append(f"Result:\n{result_str}")

    parts.append(
        "\nProvide a concise analysis (max 150 words) with exactly 3 sections:\n"
        "**Findings** — What this step discovered\n"
        "**Significance** — Impact on the overall attack chain\n"
        "**Next** — Expected follow-up actions"
    )

    parts.append(f"\n[LANGUAGE: Respond in {lang_name}]")

    return "\n".join(parts)


def extract_workflow_from_turns(
    turns: list[dict[str, Any]],
    session_title: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert SessionTurn dicts into workflow nodes + edges.

    Logic:
    1. Create start node
    2. Walk turns: find assistant turns with action, pair with next action_result
    3. Create end node
    4. Chain edges: start -> action-1 -> action-2 -> ... -> end
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Start node
    nodes.append(
        {
            "id": "start",
            "type": "start",
            "label": session_title[:60] or "Start",
            "data": {},
        }
    )

    action_index = 0
    i = 0
    while i < len(turns):
        turn = turns[i]
        if turn.get("role") == "assistant" and turn.get("action"):
            action = turn["action"]
            action_type = action.get("type", "plugin")
            action_index += 1
            node_id = f"action-{action_index}"

            # Determine node type
            if action_type == "shell":
                node_type = "action-shell"
                label = action.get("command", "shell")[:60]
            else:
                node_type = "action-plugin"
                label = action.get("plugin", "unknown")

            node_data: dict[str, Any] = {
                "plugin": action.get("plugin"),
                "command": action.get("command"),
                "params": action.get("params"),
                "reason": action.get("reason"),
                "result_summary": "",
            }

            # Look ahead for action_result
            if i + 1 < len(turns) and turns[i + 1].get("role") == "action_result":
                result = turns[i + 1].get("action_result")
                node_data["result_summary"] = _summarize_result(result)
                i += 1  # skip the result turn

            nodes.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "label": label,
                    "data": node_data,
                }
            )
        i += 1

    # End node
    nodes.append(
        {
            "id": "end",
            "type": "end",
            "label": "End",
            "data": {},
        }
    )

    # Chain edges
    for idx in range(len(nodes) - 1):
        edges.append(
            {
                "id": f"e-{nodes[idx]['id']}-{nodes[idx + 1]['id']}",
                "source": nodes[idx]["id"],
                "target": nodes[idx + 1]["id"],
            }
        )

    return nodes, edges


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_workflow_from_session(
    db: AsyncSession,
    session_id: int,
    user_id: int,
) -> Workflow:
    """Load session turns, extract workflow, save to DB."""
    # Load session
    session = (
        await db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id, AgentSession.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # Load turns
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

    # Convert ORM objects to dicts
    turn_dicts = []
    for t in rows:
        turn_dicts.append(
            {
                "role": t.role,
                "content": t.content,
                "action": t.action,
                "action_result": t.action_result,
                "action_status": t.action_status,
            }
        )

    nodes, edges = extract_workflow_from_turns(turn_dicts, session.title)

    workflow = Workflow(
        user_id=user_id,
        session_id=session_id,
        name=session.title[:200],
        description=f"Auto-generated from session #{session_id}",
        nodes=nodes,
        edges=edges,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflows(
    db: AsyncSession,
    user_id: int,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Workflow], int]:
    total = (
        await db.execute(select(func.count(Workflow.id)).where(Workflow.user_id == user_id))
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                select(Workflow)
                .where(Workflow.user_id == user_id)
                .order_by(Workflow.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def get_workflow(
    db: AsyncSession,
    workflow_id: int,
    user_id: int,
) -> Workflow | None:
    return (
        await db.execute(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
        )
    ).scalar_one_or_none()


async def delete_workflow(
    db: AsyncSession,
    workflow_id: int,
    user_id: int,
) -> bool:
    workflow = await get_workflow(db, workflow_id, user_id)
    if not workflow:
        return False
    await db.delete(workflow)
    await db.commit()
    return True

"""Workflow service: extract from sessions, CRUD, replay execution."""

import json
import logging
from graphlib import CycleError, TopologicalSorter
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


def build_execution_plan(
    nodes: list[dict], edges: list[dict]
) -> tuple[list[list[str]], dict[str, set[str]]]:
    """Build layered execution plan from DAG.

    Returns:
        (levels, parents) where levels is list of parallel node-id groups,
        parents maps each node to its parent node ids.
    """
    node_ids = {n["id"] for n in nodes}
    if not node_ids:
        return [], {}

    # Build adjacency: predecessors for each node
    predecessors: dict[str, set[str]] = {nid: set() for nid in node_ids}
    parents: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for e in edges:
        src, tgt = e["source"], e["target"]
        if src in node_ids and tgt in node_ids:
            predecessors[tgt].add(src)
            parents[tgt].add(src)

    try:
        ts = TopologicalSorter(predecessors)
        ts.prepare()
    except CycleError as exc:
        raise ValueError(f"Workflow contains a cycle: {exc}") from exc

    levels: list[list[str]] = []
    while ts.is_active():
        ready = list(ts.get_ready())
        if not ready:
            break
        levels.append(sorted(ready))
        for nid in ready:
            ts.done(nid)

    return levels, parents


def _wf_action_fingerprint(action: dict) -> str:
    """Fingerprint an action for deduplication (local to workflow extraction)."""
    atype = action.get("type", "")
    if atype == "shell":
        return f"shell:{action.get('command', '')}"
    elif atype == "plugin":
        params = json.dumps(action.get("params") or {}, sort_keys=True)
        return f"plugin:{action.get('plugin', '')}:{params}"
    return ""


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
    seen_fingerprints: set[str] = set()
    i = 0
    while i < len(turns):
        turn = turns[i]
        if turn.get("role") == "assistant" and turn.get("action"):
            raw_action = turn["action"]

            # Normalize to list for uniform processing
            action_list = raw_action if isinstance(raw_action, list) else [raw_action]

            # Collect result turns that follow
            result_turns = []
            j = i + 1
            while j < len(turns) and turns[j].get("role") == "action_result":
                result_turns.append(turns[j])
                j += 1

            turn_node_ids = []
            for idx, action in enumerate(action_list):
                # Deduplicate by fingerprint
                fp = _wf_action_fingerprint(action)
                if fp and fp in seen_fingerprints:
                    continue
                if fp:
                    seen_fingerprints.add(fp)

                action_type = action.get("type", "plugin")
                action_index += 1
                node_id = f"action-{action_index}"
                turn_node_ids.append(node_id)

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

                # Match result turn by index if available
                if idx < len(result_turns):
                    result = result_turns[idx].get("action_result")
                    node_data["result_summary"] = _summarize_result(result)

                nodes.append(
                    {
                        "id": node_id,
                        "type": node_type,
                        "label": label,
                        "data": node_data,
                    }
                )

            # Skip consumed result turns
            i = j if result_turns else i + 1
            continue
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

    # Build edges: group action nodes by their turn to create fan-out/fan-in
    action_nodes = [n for n in nodes if n["type"] not in ("start", "end")]
    if not action_nodes:
        edges.append({"id": "e-start-end", "source": "start", "target": "end"})
    else:
        # Group consecutive action nodes that came from multi-action turns
        # Since action_index is sequential and multi-action turns produce consecutive ids,
        # we rebuild groups by walking the node list
        groups: list[list[str]] = []
        seen: set[str] = set()
        for n in action_nodes:
            if n["id"] not in seen:
                # Find consecutive nodes (fan-out siblings share same turn)
                group = [n["id"]]
                seen.add(n["id"])
                groups.append(group)

        # For multi-action, we need to know which nodes were produced together.
        # Re-parse from turns to get grouping info (apply same dedup logic)
        group_list: list[list[str]] = []
        idx = 0
        group_seen: set[str] = set()
        ai = 0
        while ai < len(turns):
            turn = turns[ai]
            if turn.get("role") == "assistant" and turn.get("action"):
                raw_action = turn["action"]
                action_list = raw_action if isinstance(raw_action, list) else [raw_action]
                group = []
                for act in action_list:
                    fp = _wf_action_fingerprint(act)
                    if fp and fp in group_seen:
                        continue
                    if fp:
                        group_seen.add(fp)
                    if idx < len(action_nodes):
                        group.append(action_nodes[idx]["id"])
                        idx += 1
                if group:
                    group_list.append(group)
                # Skip result turns
                ai += 1
                while ai < len(turns) and turns[ai].get("role") == "action_result":
                    ai += 1
                continue
            ai += 1

        # Fallback: if grouping didn't work, treat all as linear
        if not group_list:
            group_list = [[n["id"]] for n in action_nodes]

        # Connect groups: start -> group[0], group[-1] -> next group[0], last group -> end
        prev_nodes = ["start"]
        for group in group_list:
            # Fan-out: each prev node connects to each node in current group
            for src in prev_nodes:
                for tgt in group:
                    edges.append(
                        {
                            "id": f"e-{src}-{tgt}",
                            "source": src,
                            "target": tgt,
                        }
                    )
            prev_nodes = group
        # Fan-in to end
        for src in prev_nodes:
            edges.append(
                {
                    "id": f"e-{src}-end",
                    "source": src,
                    "target": "end",
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

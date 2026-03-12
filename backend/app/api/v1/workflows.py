"""Workflow REST + SSE endpoints."""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.workflow import (
    WorkflowListItem,
    WorkflowListResponse,
    WorkflowPatchBody,
    WorkflowResponse,
)
from app.services.workflow_service import (
    _summarize_result,
    build_execution_plan,
    build_reflection_prompt,
    create_workflow_from_session,
    delete_workflow,
    get_workflow,
    get_workflows,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    items, total = await get_workflows(db, user.id, offset, limit)
    return WorkflowListResponse(
        items=[
            WorkflowListItem(
                id=w.id,
                name=w.name,
                description=w.description,
                session_id=w.session_id,
                node_count=len(w.nodes) if isinstance(w.nodes, list) else 0,
                status=w.status,
                created_at=w.created_at,
            )
            for w in items
        ],
        total=total,
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow_detail(
    workflow_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    workflow = await get_workflow(db, workflow_id, user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponse.model_validate(workflow)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow_endpoint(
    workflow_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    ok = await delete_workflow(db, workflow_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"ok": True}


@router.post("/workflows/from-session/{session_id}", response_model=WorkflowResponse)
async def create_from_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    try:
        workflow = await create_workflow_from_session(db, session_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WorkflowResponse.model_validate(workflow)


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def patch_workflow(
    workflow_id: int,
    body: WorkflowPatchBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update workflow fields. Validates DAG if nodes/edges are provided."""
    workflow = await get_workflow(db, workflow_id, user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.nodes is not None or body.edges is not None:
        new_nodes = body.nodes if body.nodes is not None else workflow.nodes
        new_edges = body.edges if body.edges is not None else workflow.edges
        try:
            build_execution_plan(new_nodes, new_edges)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        workflow.nodes = new_nodes
        workflow.edges = new_edges

    if body.name is not None:
        workflow.name = body.name
    if body.description is not None:
        workflow.description = body.description

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: int,
    reflect: bool = Query(False),
    simulate: bool = Query(False),
    lang: str = Query("en"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Execute workflow nodes as a DAG, streaming SSE events."""
    workflow = await get_workflow(db, workflow_id, user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    nodes = workflow.nodes if isinstance(workflow.nodes, list) else []
    wf_edges = workflow.edges if isinstance(workflow.edges, list) else []
    wf_id = workflow.id
    wf_name = workflow.name
    user_id = user.id
    is_simulate = simulate

    # Build execution plan (DAG layers)
    try:
        levels, parents = build_execution_plan(nodes, wf_edges)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build node lookup
    node_map = {n["id"]: n for n in nodes}
    action_nodes = [n for n in nodes if n.get("type", "") not in ("start", "end")]
    total_steps = len(action_nodes)

    async def event_stream():
        from app.core.database import async_session
        from app.services.agent_service import execute_plugin_action

        try:
            final_status = "completed"
            completed_steps: list[dict] = []
            failed_nodes: set[str] = set()
            step_num = 0
            start_time = time.time()

            # Load AI settings once if reflect is enabled
            ai_config = None
            if reflect:
                try:
                    async with async_session() as ai_db:
                        from app.models.ai_settings import AISettings
                        from app.services.ai_service import decrypt_key

                        ai_row = (
                            await ai_db.execute(
                                select(AISettings).where(AISettings.user_id == user_id)
                            )
                        ).scalar_one_or_none()
                        if ai_row:
                            ai_config = {
                                "provider": ai_row.provider,
                                "api_key": decrypt_key(ai_row.api_key_enc),
                                "model": ai_row.model,
                                "base_url": getattr(ai_row, "base_url", None),
                            }
                except Exception:
                    logger.exception("Failed to load AI settings for reflection")

            def _has_failed_ancestor(nid: str) -> bool:
                """Check if any ancestor of this node has failed."""
                for parent_id in parents.get(nid, set()):
                    if parent_id in failed_nodes:
                        return True
                    if _has_failed_ancestor(parent_id):
                        return True
                return False

            for level in levels:
                # Filter out start/end and determine runnable vs skipped
                runnable = []
                for nid in level:
                    node = node_map.get(nid)
                    if not node:
                        continue
                    node_type = node.get("type", "")
                    if node_type in ("start", "end"):
                        continue
                    if _has_failed_ancestor(nid):
                        failed_nodes.add(nid)
                        yield f"data: {json.dumps({'event': 'node_skip', 'node_id': nid, 'reason': 'ancestor_failed'})}\n\n"
                        continue
                    runnable.append(node)

                if not runnable:
                    continue

                # Use asyncio.Queue for real-time SSE from parallel tasks
                queue: asyncio.Queue = asyncio.Queue()
                sentinel = object()

                async def run_single_node(n: dict) -> None:
                    nid = n["id"]
                    n_type = n.get("type", "")
                    n_data = n.get("data", {})
                    try:
                        if is_simulate:
                            result = {
                                "simulated": True,
                                "result_summary": n_data.get("result_summary", ""),
                                "params": n_data.get("params"),
                                "command": n_data.get("command"),
                                "plugin": n_data.get("plugin"),
                            }
                            await queue.put(("result", nid, n, result))
                            return

                        if n_type == "action-plugin":
                            action = {
                                "type": "plugin",
                                "plugin": n_data.get("plugin", ""),
                                "params": n_data.get("params") or {},
                            }
                            result = await execute_plugin_action(action)
                        elif n_type == "action-shell":
                            command = n_data.get("command", "")
                            from app.services.sandbox import (
                                is_command_safe,
                                execute_shell,
                            )

                            safe, reason = is_command_safe(command)
                            if not safe:
                                result = {"error": f"Command blocked: {reason}"}
                            else:
                                result = await execute_shell(command)
                        else:
                            result = {"error": f"Unknown node type: {n_type}"}

                        if result.get("error"):
                            await queue.put(("error", nid, n, result))
                        else:
                            await queue.put(("result", nid, n, result))
                    except Exception as e:
                        logger.exception("Workflow node %s failed", nid)
                        await queue.put(("error", nid, n, {"error": str(e)}))
                    finally:
                        await queue.put(sentinel)

                # Emit node_start for all runnable nodes in this level
                for n in runnable:
                    step_num += 1
                    yield f"data: {json.dumps({'event': 'node_start', 'node_id': n['id'], 'label': n.get('label', ''), 'step': step_num, 'total_steps': total_steps})}\n\n"

                # Launch parallel tasks
                tasks = [asyncio.create_task(run_single_node(n)) for n in runnable]
                remaining = len(tasks)

                while remaining > 0:
                    item = await queue.get()
                    if item is sentinel:
                        remaining -= 1
                        continue

                    kind, nid, n, result = item
                    if kind == "error":
                        yield f"data: {json.dumps({'event': 'node_error', 'node_id': nid, 'error': result.get('error', '')})}\n\n"
                        failed_nodes.add(nid)
                        final_status = "failed"
                    else:
                        result_summary = _summarize_result(result)
                        yield f"data: {json.dumps({'event': 'node_result', 'node_id': nid, 'result': result, 'result_summary': result_summary})}\n\n"

                        # AI reflection
                        if reflect and ai_config:
                            try:
                                from app.services.ai_service import call_ai

                                prompt = build_reflection_prompt(
                                    workflow_name=wf_name,
                                    completed_steps=completed_steps,
                                    current_label=n.get("label", ""),
                                    current_result=result,
                                    step=step_num,
                                    total=total_steps,
                                    lang=lang,
                                )
                                reflection = await call_ai(
                                    provider=ai_config["provider"],
                                    api_key=ai_config["api_key"],
                                    model=ai_config["model"],
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "You are a penetration testing workflow analyst.",
                                        },
                                        {"role": "user", "content": prompt},
                                    ],
                                    base_url=ai_config.get("base_url"),
                                )
                                yield f"data: {json.dumps({'event': 'node_reflection', 'node_id': nid, 'reflection': reflection})}\n\n"
                            except Exception:
                                logger.exception("Reflection failed for node %s", nid)

                        completed_steps.append(
                            {
                                "label": n.get("label", ""),
                                "type": n.get("type", "").replace("action-", ""),
                                "result_summary": _summarize_result(result),
                            }
                        )

                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)

            total_time_ms = int((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'event': 'workflow_done', 'status': final_status, 'total_time_ms': total_time_ms})}\n\n"
        finally:
            # Always reset status — even if client disconnects mid-stream
            try:
                async with async_session() as db2:
                    from sqlalchemy import select as sel
                    from app.models.workflow import Workflow as WF

                    wf = (await db2.execute(sel(WF).where(WF.id == wf_id))).scalar_one_or_none()
                    if wf:
                        wf.status = "ready"
                        await db2.commit()
            except Exception:
                logger.exception("Failed to reset workflow status")

    # Mark as running
    workflow.status = "running"
    await db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

"""Workflow REST + SSE endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.workflow import (
    WorkflowListItem,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.services.workflow_service import (
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


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Execute workflow nodes sequentially, streaming SSE events."""
    workflow = await get_workflow(db, workflow_id, user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status == "running":
        raise HTTPException(status_code=409, detail="Workflow already running")

    nodes = workflow.nodes if isinstance(workflow.nodes, list) else []
    wf_id = workflow.id

    async def event_stream():
        from app.core.database import async_session
        from app.services.agent_service import execute_plugin_action

        final_status = "completed"

        for node in nodes:
            node_type = node.get("type", "")
            node_id = node.get("id", "")

            # Skip start/end nodes
            if node_type in ("start", "end"):
                continue

            # Emit node_start
            yield f"data: {json.dumps({'event': 'node_start', 'node_id': node_id, 'label': node.get('label', '')})}\n\n"

            data = node.get("data", {})
            try:
                if node_type == "action-plugin":
                    action = {
                        "type": "plugin",
                        "plugin": data.get("plugin", ""),
                        "params": data.get("params") or {},
                    }
                    result = await execute_plugin_action(action)
                elif node_type == "action-shell":
                    # Shell replay: run in sandbox if available
                    command = data.get("command", "")
                    from app.services.sandbox import is_command_safe, execute_shell

                    safe, reason = is_command_safe(command)
                    if not safe:
                        result = {"error": f"Command blocked: {reason}"}
                    else:
                        result = await execute_shell(command)
                else:
                    result = {"error": f"Unknown node type: {node_type}"}

                if result.get("error"):
                    yield f"data: {json.dumps({'event': 'node_error', 'node_id': node_id, 'error': result['error']})}\n\n"
                    final_status = "failed"
                else:
                    yield f"data: {json.dumps({'event': 'node_result', 'node_id': node_id, 'result': result})}\n\n"

            except Exception as e:
                logger.exception("Workflow node %s failed", node_id)
                yield f"data: {json.dumps({'event': 'node_error', 'node_id': node_id, 'error': str(e)})}\n\n"
                final_status = "failed"

        yield f"data: {json.dumps({'event': 'workflow_done', 'status': final_status})}\n\n"

        # Update workflow status back to ready
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

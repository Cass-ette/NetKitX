"""Report export endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.services.task_service import get_task
from app.services.report_service import render_html, render_pdf

router = APIRouter()


@router.get("/{task_id}/export")
async def export_report(
    task_id: int,
    format: str = Query("html", pattern="^(html|pdf)$"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await get_task(session, task_id)
    if not task or task.created_by != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "done":
        raise HTTPException(status_code=400, detail="Task is not completed yet")

    if format == "pdf":
        pdf_bytes = render_pdf(task)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report-{task_id}.pdf"},
        )

    html_str = render_html(task)
    return HTMLResponse(content=html_str)

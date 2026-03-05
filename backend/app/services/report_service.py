"""Report generation service — renders task results as HTML or PDF."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.models.task import Task

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def _format_duration(task: Task) -> str:
    if task.started_at and task.finished_at:
        delta = task.finished_at - task.started_at
        total = int(delta.total_seconds())
        if total < 60:
            return f"{total}s"
        return f"{total // 60}m {total % 60}s"
    return "N/A"


def _extract_columns(items: list[dict]) -> list[str]:
    if not items:
        return []
    return list(items[0].keys())


def render_html(task: Task) -> str:
    items = (task.result or {}).get("items", [])
    columns = _extract_columns(items)

    html = _env.get_template("report.html").render(
        plugin_name=task.plugin_name,
        status=task.status,
        created_at=task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "N/A",
        duration=_format_duration(task),
        params=task.params or {},
        items=items,
        columns=columns,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        version=settings.VERSION,
    )
    return html


def render_pdf(task: Task) -> bytes:
    from weasyprint import HTML

    html_str = render_html(task)
    return HTML(string=html_str).write_pdf()

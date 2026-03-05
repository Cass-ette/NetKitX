import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, get_session
from app.core.events import manager
from app.api.v1 import auth, tools, tasks, plugins, marketplace, reports, topology
from app.plugins.loader import load_all_plugins

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Load plugins on startup
    count = load_all_plugins(settings.PLUGINS_DIR, settings.ENGINES_DIR)
    logger.info(f"Loaded {count} plugins")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(plugins.router, prefix="/api/v1/plugins", tags=["plugins"])
app.include_router(marketplace.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(topology.router, prefix="/api/v1/topology", tags=["topology"])


@app.get("/api/health")
async def health():
    from app.plugins.registry import registry

    return {
        "status": "ok",
        "version": settings.VERSION,
        "plugins_loaded": len(registry.list_all()),
    }


@app.get("/api/v1/stats")
async def stats():
    """Dashboard statistics."""
    from sqlalchemy import select, func
    from app.models.task import Task
    from app.plugins.registry import registry

    async for session in get_session():
        total_tasks = (await session.execute(select(func.count(Task.id)))).scalar() or 0
        running_tasks = (
            await session.execute(select(func.count(Task.id)).where(Task.status == "running"))
        ).scalar() or 0

    all_plugins = registry.list_all()
    categories = {}
    for m in all_plugins:
        categories[m.category] = categories.get(m.category, 0) + 1

    return {
        "tools_count": len(all_plugins),
        "tasks_total": total_tasks,
        "tasks_running": running_tasks,
        "plugins_count": len(all_plugins),
        "categories": categories,
    }


@app.websocket("/api/v1/ws/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: int):
    """WebSocket endpoint for real-time task updates."""
    tid = str(task_id)
    await manager.connect(tid, websocket)
    try:
        while True:
            # Keep connection alive; client can send ping/pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(tid, websocket)

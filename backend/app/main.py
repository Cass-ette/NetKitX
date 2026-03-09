import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, get_session
from app.core.events import manager
from app.api.v1 import (
    auth,
    tools,
    tasks,
    plugins,
    marketplace,
    reports,
    topology,
    ai,
    terminal,
    admin,
    knowledge,
    passkey,
    whitelist,
)
from app.plugins.loader import load_all_plugins

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Load plugins on startup
    count = load_all_plugins(settings.PLUGINS_DIR, settings.ENGINES_DIR)
    logger.info(f"Loaded {count} plugins")

    # Background task: clean up idle sandbox containers every 5 minutes
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(5 * 60)
            try:
                from app.services.container_service import cleanup_idle_containers

                cleanup_idle_containers()
            except Exception as e:
                logger.error("Container cleanup error: %s", e)

    task = asyncio.create_task(_cleanup_loop())

    # Background task: subscribe to Redis for hot plugin reload
    async def _plugin_reload_loop():
        try:
            import redis.asyncio as aioredis
            from app.plugins.loader import load_single_plugin
            import json

            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("netkitx.plugin.installed")
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    plugin_names = json.loads(message["data"])
                    plugins_path = __import__("pathlib").Path(settings.PLUGINS_DIR)
                    for name in plugin_names:
                        plugin_dir = plugins_path / name
                        if load_single_plugin(plugin_dir, settings.ENGINES_DIR):
                            logger.info("Hot-reloaded plugin: %s", name)
                except Exception as e:
                    logger.error("Plugin hot-reload error: %s", e)
        except Exception as e:
            logger.error("Redis subscribe error: %s", e)

    reload_task = asyncio.create_task(_plugin_reload_loop())

    yield

    task.cancel()
    reload_task.cancel()


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
app.include_router(passkey.router, prefix="/api/v1/auth/passkey", tags=["passkey"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(plugins.router, prefix="/api/v1/plugins", tags=["plugins"])
app.include_router(marketplace.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(topology.router, prefix="/api/v1/topology", tags=["topology"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(terminal.router, prefix="/api/v1/terminal", tags=["terminal"])
app.include_router(admin.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
app.include_router(whitelist.router, prefix="/api/v1", tags=["whitelist"])


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


@app.get("/api/v1/announcements")
async def public_announcements(session: AsyncSession = Depends(get_session)):
    """Public endpoint: active announcements for dashboard banner."""
    from app.services.admin_service import get_announcements
    from app.schemas.admin import AnnouncementResponse

    anns = await get_announcements(session, active_only=True, limit=10)
    return [AnnouncementResponse.model_validate(a) for a in anns]


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

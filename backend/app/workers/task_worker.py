import asyncio
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="netkitx.run_plugin")
def run_plugin_task(self, task_id: int, plugin_name: str, params: dict):
    """Celery task that executes a plugin."""
    logger.info(f"Starting plugin '{plugin_name}' for task {task_id}")

    # Run the async plugin execution in a sync context
    asyncio.run(_execute_plugin(task_id, plugin_name, params))


async def _execute_plugin(task_id: int, plugin_name: str, params: dict):
    from app.plugins.registry import registry
    from app.core.database import async_session
    from app.services.task_service import update_task_status

    plugin = registry.get(plugin_name)
    if not plugin:
        async with async_session() as session:
            await update_task_status(session, task_id, "failed", {"error": f"Plugin '{plugin_name}' not found"})
        return

    async with async_session() as session:
        await update_task_status(session, task_id, "running")

    try:
        results = []
        async for event in plugin.execute(params):
            if event.type == "result":
                results.append(event.data)
            elif event.type == "error":
                async with async_session() as session:
                    await update_task_status(session, task_id, "failed", {"error": event.data})
                return

        async with async_session() as session:
            await update_task_status(session, task_id, "done", {"items": results})
    except Exception as e:
        logger.exception(f"Plugin '{plugin_name}' failed for task {task_id}")
        async with async_session() as session:
            await update_task_status(session, task_id, "failed", {"error": str(e)})

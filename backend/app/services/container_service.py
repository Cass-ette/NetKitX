"""Container lifecycle management for user sandbox terminals."""

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "netkitx-sandbox")
SANDBOX_API_URL = os.environ.get("SANDBOX_API_URL", "http://127.0.0.1:8000")
CONTAINER_PREFIX = "netkitx-user-"
IDLE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes

# Track last activity time per user_id
_last_active: dict[int, float] = {}


def _command_preview(command: str, limit: int = 160) -> str:
    command = " ".join(command.split())
    if len(command) <= limit:
        return command
    return command[:limit] + "..."


def _get_docker():
    try:
        import docker

        return docker.from_env()
    except ImportError:
        raise RuntimeError("docker SDK not installed. Run: pip install docker")
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Docker daemon: {e}")


def _container_name(user_id: int) -> str:
    return f"{CONTAINER_PREFIX}{user_id}"


def get_user_container(user_id: int) -> str | None:
    """Return container ID if user's container exists and is running."""
    try:
        client = _get_docker()
        name = _container_name(user_id)
        container = client.containers.get(name)
        if container.status == "running":
            return container.id
        return None
    except Exception:
        return None


def create_user_container(user_id: int, token: str) -> str:
    """Create an isolated sandbox container for the user. Returns container ID."""
    client = _get_docker()
    name = _container_name(user_id)

    # Remove existing container if stopped
    try:
        old = client.containers.get(name)
        old.remove(force=True)
    except Exception:
        pass

    container = client.containers.run(
        SANDBOX_IMAGE,
        name=name,
        detach=True,
        stdin_open=True,
        tty=True,
        environment={
            "NETKITX_TOKEN": token,
            "NETKITX_API": SANDBOX_API_URL,
        },
        mem_limit="512m",
        nano_cpus=500_000_000,  # 0.5 CPU
        network_mode="bridge",
        # No host volume mounts — full isolation
        labels={"netkitx.user_id": str(user_id), "netkitx.sandbox": "true"},
    )
    logger.info("Created sandbox container %s for user %s", container.id[:12], user_id)
    return container.id


async def _exec_local(command: str) -> dict[str, Any]:
    """Execute a shell command locally (fallback when sandbox container is unavailable)."""
    preview = _command_preview(command)
    logger.info("Executing shell locally command=%s", preview)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        logger.info(
            "Local shell execution completed exit_code=%s command=%s",
            proc.returncode or 0,
            preview,
        )
        return {
            "stdout": stdout.decode("utf-8", errors="replace")[:30720],
            "stderr": stderr.decode("utf-8", errors="replace")[:10240],
            "exit_code": proc.returncode or 0,
        }
    except asyncio.TimeoutError:
        logger.warning("Local shell execution timed out command=%s", preview)
        return {"error": "Command timed out (120s)", "exit_code": -1}
    except Exception as e:
        logger.exception("Local shell execution crashed command=%s", preview)
        return {"error": str(e), "exit_code": -1}


async def exec_in_container(user_id: int, command: str, token: str) -> dict[str, Any]:
    """Execute a shell command in the user's sandbox container.

    Falls back to local execution if the sandbox image is not available
    (e.g. local dev environment without the netkitx-sandbox image).
    """
    preview = _command_preview(command)
    container_id = get_user_container(user_id)
    if not container_id:
        try:
            logger.info("No running sandbox found, creating container for user=%s", user_id)
            container_id = create_user_container(user_id, token)
        except Exception as e:
            logger.warning("Cannot create sandbox container, falling back to local exec: %s", e)
            return await _exec_local(command)

    _last_active[user_id] = time.monotonic()

    try:
        client = _get_docker()
        container = client.containers.get(container_id)
        logger.info(
            "Executing shell in sandbox user=%s container=%s command=%s",
            user_id,
            container.id[:12],
            preview,
        )
        exit_code, output = container.exec_run(
            ["bash", "-c", command],
            stdout=True,
            stderr=True,
            demux=True,
            workdir="/home/user",
        )
        stdout, stderr = output if isinstance(output, tuple) else (output, b"")
        stdout = (stdout or b"").decode("utf-8", errors="replace")[:30720]
        stderr = (stderr or b"").decode("utf-8", errors="replace")[:10240]
        logger.info(
            "Sandbox shell execution completed user=%s exit_code=%s command=%s",
            user_id,
            exit_code,
            preview,
        )
        return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}
    except Exception as e:
        logger.exception(
            "Sandbox shell execution crashed user=%s command=%s",
            user_id,
            preview,
        )
        return {"error": str(e), "exit_code": -1}


def destroy_user_container(user_id: int):
    """Stop and remove the user's sandbox container."""
    try:
        client = _get_docker()
        container = client.containers.get(_container_name(user_id))
        container.remove(force=True)
        _last_active.pop(user_id, None)
        logger.info("Destroyed sandbox container for user %s", user_id)
    except Exception:
        pass


def get_container_status(user_id: int) -> dict[str, Any]:
    """Return container status info."""
    try:
        client = _get_docker()
        container = client.containers.get(_container_name(user_id))
        return {
            "exists": True,
            "status": container.status,
            "id": container.id[:12],
            "image": SANDBOX_IMAGE,
        }
    except Exception:
        return {"exists": False, "status": "none"}


def cleanup_idle_containers():
    """Remove sandbox containers idle for more than IDLE_TIMEOUT_SECONDS."""
    now = time.monotonic()
    try:
        client = _get_docker()
        containers = client.containers.list(filters={"label": "netkitx.sandbox=true"})
        for c in containers:
            try:
                user_id_str = c.labels.get("netkitx.user_id", "")
                if not user_id_str:
                    continue
                user_id = int(user_id_str)
                last = _last_active.get(user_id, 0)
                if now - last > IDLE_TIMEOUT_SECONDS:
                    c.remove(force=True)
                    _last_active.pop(user_id, None)
                    logger.info("Cleaned up idle container for user %s", user_id)
            except Exception:
                pass
    except Exception as e:
        logger.error("cleanup_idle_containers error: %s", e)

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

logger = logging.getLogger(__name__)


class GoEnginePlugin(PluginBase):
    """Wrapper that runs a Go binary as a plugin via subprocess + JSON stdio."""

    def __init__(self, meta: PluginMeta, binary_path: str):
        self.meta = meta
        self.binary_path = binary_path

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        binary = Path(self.binary_path)
        if not binary.exists():
            yield PluginEvent(
                type="error", data={"error": f"Engine binary not found: {self.binary_path}"}
            )
            return

        proc = await asyncio.create_subprocess_exec(
            str(binary),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send params via stdin
        stdin_data = json.dumps(params).encode()
        proc.stdin.write(stdin_data)
        proc.stdin.close()

        # Read stdout line by line — each line is a JSON event
        async for line in proc.stdout:
            line = line.decode().strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                yield PluginEvent(type=event.get("type", "log"), data=event.get("data", {}))
            except json.JSONDecodeError:
                yield PluginEvent(type="log", data={"msg": line})

        await proc.wait()

        if proc.returncode != 0:
            stderr = await proc.stderr.read()
            yield PluginEvent(
                type="error",
                data={
                    "error": f"Engine exited with code {proc.returncode}",
                    "stderr": stderr.decode(),
                },
            )

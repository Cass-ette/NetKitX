import asyncio
import platform
from typing import Any, AsyncIterator

from app.plugins.base import PluginBase, PluginEvent, PluginMeta


class PingSweep(PluginBase):
    meta = PluginMeta(
        name="example-ping",
        version="1.0.0",
        description="Simple Ping Sweep",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        targets = [t.strip() for t in params["targets"].split(",")]
        count = params.get("count", 3)
        total = len(targets)

        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Pinging {total} hosts..."})

        for i, host in enumerate(targets):
            alive, latency = await self._ping(host, count)
            yield PluginEvent(
                type="result",
                data={"host": host, "alive": alive, "latency_ms": latency},
            )
            pct = (i + 1) * 100 // total
            yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Pinged {i+1}/{total}"})

        yield PluginEvent(type="progress", data={"percent": 100, "msg": "Ping sweep complete"})

    async def _ping(self, host: str, count: int) -> tuple[bool, float | None]:
        flag = "-n" if platform.system().lower() == "windows" else "-c"
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", flag, str(count), "-W", "2", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                # Parse average latency from output
                output = stdout.decode()
                for line in output.splitlines():
                    if "avg" in line or "Average" in line:
                        parts = line.split("/")
                        if len(parts) >= 5:
                            return True, round(float(parts[4]), 2)
                return True, None
            return False, None
        except (asyncio.TimeoutError, OSError):
            return False, None

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

DICT_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "dicts" / "directory" / "common.txt"


class DirScan(PluginBase):
    meta = PluginMeta(
        name="dir-scan",
        version="1.0.0",
        description="目录扫描",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        base_url = params["url"].strip().rstrip("/")
        concurrency = int(params.get("concurrency", 30))
        timeout = int(params.get("timeout", 5))
        status_filter = {int(s.strip()) for s in params.get("status_filter", "200").split(",")}

        # Load wordlist
        if DICT_PATH.exists():
            paths = [p.strip() for p in DICT_PATH.read_text().splitlines() if p.strip()]
        else:
            paths = ["admin", "login", "robots.txt", ".git", ".env", "backup"]

        total = len(paths)
        yield PluginEvent(type="log", data={"msg": f"Scanning {base_url} with {total} paths"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Scanning {total} paths..."})

        found = 0
        done = 0
        sem = asyncio.Semaphore(concurrency)
        title_re = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

        async def check_path(client: httpx.AsyncClient, path: str):
            nonlocal found, done
            url = f"{base_url}/{path}"
            try:
                resp = await client.get(url, follow_redirects=False)
                if resp.status_code in status_filter:
                    title = ""
                    if resp.headers.get("content-type", "").startswith("text/html"):
                        m = title_re.search(resp.text[:2000])
                        if m:
                            title = m.group(1).strip()[:80]
                    found += 1
                    return {
                        "url": url,
                        "status": resp.status_code,
                        "size": len(resp.content),
                        "title": title,
                    }
            except Exception:
                pass
            finally:
                done += 1
            return None

        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            batch_size = max(concurrency, 20)
            for start in range(0, total, batch_size):
                batch = paths[start : start + batch_size]

                async def limited_check(p):
                    async with sem:
                        return await check_path(client, p)

                results = await asyncio.gather(*[limited_check(p) for p in batch])
                for r in results:
                    if r:
                        yield PluginEvent(type="result", data=r)
                        yield PluginEvent(type="log", data={"msg": f"  [{r['status']}] {r['url']}"})

                pct = min(done * 100 // total, 99)
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Scanned {done}/{total}, found {found}"})

        yield PluginEvent(type="log", data={"msg": f"Complete: {found} paths found"})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": f"Done — {found} paths found"})

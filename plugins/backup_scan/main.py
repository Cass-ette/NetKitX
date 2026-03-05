import asyncio
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

EXT_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "dicts" / "backup" / "extensions.txt"

# Common base filenames to check
BASE_NAMES = [
    "index", "main", "config", "database", "db", "backup", "dump",
    "site", "web", "www", "data", "admin", "home", "default",
]


class BackupScan(PluginBase):
    meta = PluginMeta(
        name="backup-scan",
        version="1.0.0",
        description="备份文件探测",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        base_url = params["url"].strip().rstrip("/")
        concurrency = int(params.get("concurrency", 20))
        timeout = int(params.get("timeout", 5))

        # Build check list from domain name + base names + extensions
        hostname = urlparse(base_url).hostname or "site"
        domain_parts = [hostname, hostname.split(".")[0]]  # e.g. example.com, example

        if EXT_PATH.exists():
            extensions = [e.strip() for e in EXT_PATH.read_text().splitlines() if e.strip()]
        else:
            extensions = [".bak", ".zip", ".sql", ".tar.gz", ".old", "~", ".swp"]

        # Generate paths: domain-based + common basenames + direct paths
        check_paths = set()
        for name in domain_parts + BASE_NAMES:
            for ext in extensions:
                check_paths.add(f"{name}{ext}")
        # Also check direct well-known backup files
        check_paths.update([
            "backup.zip", "backup.tar.gz", "backup.sql", "db.sql", "database.sql",
            "dump.sql", "site.zip", "www.zip", "web.zip", "1.zip", "archive.zip",
            "htdocs.zip", "public.zip", "html.zip", "src.zip",
        ])

        paths = sorted(check_paths)
        total = len(paths)

        yield PluginEvent(type="log", data={"msg": f"Scanning {base_url} for backup files ({total} paths)"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Checking {total} paths..."})

        found = 0
        done = 0
        sem = asyncio.Semaphore(concurrency)

        async def check_one(client: httpx.AsyncClient, path: str):
            nonlocal found, done
            url = f"{base_url}/{path}"
            try:
                resp = await client.head(url, follow_redirects=False)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    cl = resp.headers.get("content-length", "unknown")
                    # Skip tiny HTML responses (likely error pages)
                    if "text/html" in ct and cl != "unknown" and int(cl) < 500:
                        return None
                    found += 1
                    return {
                        "url": url,
                        "status": resp.status_code,
                        "size": cl,
                        "content_type": ct.split(";")[0],
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

                async def limited(p):
                    async with sem:
                        return await check_one(client, p)

                results = await asyncio.gather(*[limited(p) for p in batch])
                for r in results:
                    if r:
                        yield PluginEvent(type="result", data=r)
                        yield PluginEvent(type="log", data={"msg": f"  [FOUND] {r['url']} ({r['size']} bytes)"})

                pct = min(done * 100 // total, 99)
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Checked {done}/{total}, found {found}"})

        yield PluginEvent(type="log", data={"msg": f"Complete: {found} backup files found"})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": f"Done — {found} backup files found"})

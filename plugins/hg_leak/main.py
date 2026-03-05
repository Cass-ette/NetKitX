from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

HG_PATHS = [
    ".hg/requires",
    ".hg/store/fncache",
    ".hg/store/00manifest.i",
    ".hg/store/00changelog.i",
    ".hg/dirstate",
    ".hg/branch",
    ".hg/hgrc",
    ".hg/last-message.txt",
    ".hg/bookmarks",
    ".hg/undo.dirstate",
]


class HgLeak(PluginBase):
    meta = PluginMeta(
        name="hg-leak",
        version="1.0.0",
        description="Hg 泄露检测",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        base_url = params["url"].strip().rstrip("/")
        timeout = int(params.get("timeout", 10))
        total = len(HG_PATHS)

        yield PluginEvent(type="log", data={"msg": f"Checking Hg leak on {base_url}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Checking .hg/ paths..."})

        found = 0
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for i, path in enumerate(HG_PATHS):
                url = f"{base_url}/{path}"
                try:
                    resp = await client.get(url, follow_redirects=False)
                    if resp.status_code == 200:
                        found += 1
                        size = len(resp.content)
                        detail = ""
                        if path == ".hg/requires":
                            detail = resp.text.strip().replace("\n", ", ")[:100]
                        elif path == ".hg/branch":
                            detail = f"branch: {resp.text.strip()[:50]}"
                        elif path == ".hg/hgrc":
                            detail = "Hg config exposed"
                        elif path == ".hg/dirstate":
                            detail = f"binary ({size} bytes)"
                        else:
                            detail = f"{size} bytes"
                        yield PluginEvent(
                            type="result",
                            data={"url": url, "status": "leaked", "detail": detail},
                        )
                        yield PluginEvent(type="log", data={"msg": f"  [LEAK] {url} — {detail}"})
                    else:
                        yield PluginEvent(
                            type="log", data={"msg": f"  [OK] {url} — {resp.status_code}"}
                        )
                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"  [ERR] {url} — {e}"})

                pct = (i + 1) * 100 // total
                yield PluginEvent(
                    type="progress", data={"percent": pct, "msg": f"Checked {i + 1}/{total}"}
                )

        summary = (
            f"Hg leak {'DETECTED' if found else 'not found'} — {found}/{total} paths accessible"
        )
        yield PluginEvent(type="log", data={"msg": summary})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

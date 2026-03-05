from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

SVN_PATHS = [
    ".svn/entries",
    ".svn/wc.db",
    ".svn/format",
    ".svn/all-wcprops",
    ".svn/props/",
    ".svn/pristine/",
    ".svn/text-base/",
    ".svn/tmp/",
]


class SvnLeak(PluginBase):
    meta = PluginMeta(
        name="svn-leak",
        version="1.0.0",
        description="SVN 泄露检测",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        base_url = params["url"].strip().rstrip("/")
        timeout = int(params.get("timeout", 10))
        total = len(SVN_PATHS)

        yield PluginEvent(type="log", data={"msg": f"Checking SVN leak on {base_url}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Checking .svn/ paths..."})

        found = 0
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for i, path in enumerate(SVN_PATHS):
                url = f"{base_url}/{path}"
                try:
                    resp = await client.get(url, follow_redirects=False)
                    if resp.status_code == 200:
                        found += 1
                        size = len(resp.content)
                        detail = ""
                        if path == ".svn/entries":
                            lines = resp.text.strip().splitlines()
                            if lines and lines[0].isdigit():
                                detail = f"SVN format version {lines[0]}"
                            else:
                                detail = f"{size} bytes"
                        elif path == ".svn/wc.db":
                            detail = f"SQLite DB ({size} bytes)" if resp.content[:6] == b"SQLite" else f"{size} bytes"
                        else:
                            detail = f"{size} bytes"
                        yield PluginEvent(type="result", data={"url": url, "status": "leaked", "detail": detail})
                        yield PluginEvent(type="log", data={"msg": f"  [LEAK] {url} — {detail}"})
                    else:
                        yield PluginEvent(type="log", data={"msg": f"  [OK] {url} — {resp.status_code}"})
                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"  [ERR] {url} — {e}"})

                pct = (i + 1) * 100 // total
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Checked {i+1}/{total}"})

        summary = f"SVN leak {'DETECTED' if found else 'not found'} — {found}/{total} paths accessible"
        yield PluginEvent(type="log", data={"msg": summary})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

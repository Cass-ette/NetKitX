from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

GIT_PATHS = [
    ".git/HEAD",
    ".git/config",
    ".git/index",
    ".git/description",
    ".git/info/refs",
    ".git/logs/HEAD",
    ".git/refs/heads/master",
    ".git/refs/heads/main",
    ".git/COMMIT_EDITMSG",
    ".git/packed-refs",
]


class GitLeak(PluginBase):
    meta = PluginMeta(
        name="git-leak",
        version="1.0.0",
        description="Git 泄露检测",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        base_url = params["url"].strip().rstrip("/")
        timeout = int(params.get("timeout", 10))
        total = len(GIT_PATHS)

        yield PluginEvent(type="log", data={"msg": f"Checking Git leak on {base_url}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Checking .git/ paths..."})

        found = 0
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for i, path in enumerate(GIT_PATHS):
                url = f"{base_url}/{path}"
                try:
                    resp = await client.get(url, follow_redirects=False)
                    status = "leaked" if resp.status_code == 200 else "not found"
                    detail = ""
                    if resp.status_code == 200:
                        found += 1
                        content = resp.text[:200].strip()
                        # Validate content looks like git data
                        if path == ".git/HEAD" and content.startswith("ref:"):
                            detail = content
                        elif path == ".git/config" and "[core]" in content:
                            detail = "Git config exposed"
                        elif path == ".git/description":
                            detail = content[:100]
                        else:
                            detail = f"{len(resp.content)} bytes"
                        yield PluginEvent(type="result", data={"url": url, "status": status, "detail": detail})
                        yield PluginEvent(type="log", data={"msg": f"  [LEAK] {url} — {detail}"})
                    else:
                        yield PluginEvent(type="log", data={"msg": f"  [OK] {url} — {resp.status_code}"})
                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"  [ERR] {url} — {e}"})

                pct = (i + 1) * 100 // total
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Checked {i+1}/{total}"})

        summary = f"Git leak {'DETECTED' if found else 'not found'} — {found}/{total} paths accessible"
        yield PluginEvent(type="log", data={"msg": summary})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

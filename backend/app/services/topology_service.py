"""Topology service — converts scan results into graph nodes and edges."""

from __future__ import annotations

from typing import Any


def build_topology(task_result: dict[str, Any] | None) -> dict[str, Any]:
    """Convert task result items into a topology graph structure.

    Returns:
        {"nodes": [...], "edges": [...]} where each node has {id, type, label, data}
        and each edge has {id, source, target}.
    """
    if not task_result:
        return {"nodes": [], "edges": []}

    items = task_result.get("items", [])
    if not items:
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_hosts: dict[str, dict[str, Any]] = {}

    # Scanner center node
    scanner_id = "scanner"
    nodes.append(
        {
            "id": scanner_id,
            "type": "scanner",
            "label": "Scanner",
            "data": {"total_results": len(items)},
        }
    )

    for item in items:
        host = item.get("host") or item.get("ip") or item.get("address")
        if not host:
            continue

        host_id = f"host-{host}"

        if host_id not in seen_hosts:
            seen_hosts[host_id] = {
                "id": host_id,
                "type": "host",
                "label": host,
                "data": {"host": host, "ports": [], "services": []},
            }
            edges.append(
                {"id": f"edge-{scanner_id}-{host_id}", "source": scanner_id, "target": host_id}
            )

        node_data = seen_hosts[host_id]["data"]

        port = item.get("port")
        if port and port not in node_data["ports"]:
            node_data["ports"].append(port)

        service = item.get("service")
        if service and service not in node_data["services"]:
            node_data["services"].append(service)

    nodes.extend(seen_hosts.values())

    return {"nodes": nodes, "edges": edges}
